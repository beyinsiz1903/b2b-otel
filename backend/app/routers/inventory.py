"""Auto-generated module — see _split_server.py. Behavior preserved verbatim."""
import asyncio
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import time
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException,
    Query, Request, Response, UploadFile, WebSocket, WebSocketDisconnect, status,
)
from fastapi.responses import (
    FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse,
)
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, Field
from pymongo.errors import DuplicateKeyError

from app.api_router import api
from app.config import (
    ALLOWED_MIME_TYPES, JWT_ACCESS_TOKEN_EXPIRE_MINUTES, JWT_ALGORITHM,
    JWT_SECRET_KEY, MATCH_FEE_TL, MAX_FILE_SIZE_MB, REGIONS, SHEETS_SCOPES,
    SUBSCRIPTION_PLANS, UPLOAD_DIR, limiter, logger,
)
from app.db import db
from app.models import (
    AlternativeOffer, AlternativePayload, AvailabilityBulkSet,
    AvailabilityListingCreate, AvailabilityListingMine, AvailabilityListingPublic,
    AvailabilityListingUpdate, ChangePasswordRequest, CheckAvailabilityRequest,
    DailyAvailabilityPublic, ForgotPasswordRequest, HotelBase, HotelCreate,
    HotelMeUpdate, HotelPublic, InventoryItemCreate, InventoryItemPublic,
    InventoryItemUpdate, InvoicePublic, MatchPublic, NotificationPublic,
    PaymentInitiate, PaymentPublic, PMSAvailabilityRoom, PMSAvailabilitySync,
    PMSCallbackUpdate, PMSConnectResponse, PMSReservationEvent, PMSStatusResponse,
    PriceCalculateRequest, PricingRuleCreate, PricingRulePublic, PricingRuleUpdate,
    RequestCreate, RequestPublic, ResetPasswordRequest, RoomTemplateCreate,
    RoomTemplatePublic, RoomTemplateUpdate, SheetsConfigPublic, SheetsConfigSave,
    SubscriptionPublic, Token,
)
from app.security import (
    create_access_token, get_current_admin, get_current_hotel, get_password_hash,
    oauth2_scheme, pwd_context, validate_password, verify_password,
)
from app.utils import (
    log_activity, next_reference_code, now_utc, sanitize_input, serialize_doc,
)
from app.ws import create_notification, ws_manager
from app.services.billing import (
    auto_create_invoice, get_region_match_fee,
    consume_match_quota as _consume_match_quota,
    refund_match_quota as _refund_match_quota,
    refund_match_quota_by_hotel as _refund_match_quota_by_hotel,
)
from app.services.inventory import (
    decrement_inventory_on_match as _decrement_inventory_on_match,
    increment_inventory_on_cancel as _increment_inventory_on_cancel,
)
from app.services.pms_helpers import (
    pms_auth_by_api_key as _pms_auth_by_api_key,
    pms_constant_time_eq as _pms_constant_time_eq,
    pms_hash_key as _pms_hash_key,
    pms_verify_hmac as _pms_verify_hmac,
)
from app.services.sheets_helpers import (
    build_flow as _build_flow,
    get_frontend_url as _get_frontend_url,
    get_or_create_spreadsheet as _get_or_create_spreadsheet,
    get_redirect_uri as _get_redirect_uri,
    get_sheets_credentials as _get_sheets_credentials,
    oauth_result_page as _oauth_result_page,
    write_sheet as _write_sheet,
)
from app.services.pricing_engine import (
    calculate_dynamic_price as _calculate_dynamic_price,
)
from email_service import (
    EmailNotConfiguredError, build_password_reset_email, send_email,
)

# Optional heavy deps used by some routers — imported lazily inside routes:
# google.oauth2.credentials, googleapiclient.discovery, google_auth_oauthlib.flow,
# google.auth.transport.requests, reportlab.* — left as inside-function imports
# in the original code where applicable. If a route uses them at module level,
# we add the import inside the chunk body.


# --- Hotel Inventory System -------------------------------------------------
# ============================================================================

def inventory_to_public(doc: Dict[str, Any]) -> InventoryItemPublic:
    return InventoryItemPublic(
        id=doc["_id"],
        hotel_id=doc["hotel_id"],
        room_type=doc["room_type"],
        room_type_name=doc["room_type_name"],
        total_rooms=doc["total_rooms"],
        description=doc.get("description"),
        features=doc.get("features"),
        capacity_label=doc.get("capacity_label"),
        pax=doc.get("pax"),
        image_urls=doc.get("image_urls"),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


@api.post("/inventory", response_model=InventoryItemPublic)
async def create_inventory_item(payload: InventoryItemCreate, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """Yeni oda tipi envanteri oluştur."""
    inv_id = str(uuid.uuid4())
    now = now_utc()
    doc = {
        "_id": inv_id,
        "hotel_id": current_hotel["_id"],
        "room_type": payload.room_type,
        "room_type_name": payload.room_type_name,
        "total_rooms": payload.total_rooms,
        "description": payload.description,
        "features": payload.features or [],
        "capacity_label": payload.capacity_label,
        "pax": payload.pax,
        "image_urls": payload.image_urls or [],
        "created_at": now,
        "updated_at": now,
    }
    await db.inventory.insert_one(doc)
    await log_activity(current_hotel["_id"], "create", "inventory", inv_id, {"room_type": payload.room_type, "total_rooms": payload.total_rooms})
    return inventory_to_public(doc)


@api.get("/inventory", response_model=List[InventoryItemPublic])
async def list_inventory(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """Otelin tüm envanter kalemlerini listele."""
    cursor = db.inventory.find({"hotel_id": current_hotel["_id"]}).sort("created_at", -1)
    docs = await cursor.to_list(length=200)
    return [inventory_to_public(d) for d in docs]


@api.get("/inventory/{inv_id}", response_model=InventoryItemPublic)
async def get_inventory_item(inv_id: str, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    doc = await db.inventory.find_one({"_id": inv_id, "hotel_id": current_hotel["_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Envanter kalemi bulunamadı")
    return inventory_to_public(doc)


@api.put("/inventory/{inv_id}", response_model=InventoryItemPublic)
async def update_inventory_item(inv_id: str, payload: InventoryItemUpdate, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    doc = await db.inventory.find_one({"_id": inv_id, "hotel_id": current_hotel["_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Envanter kalemi bulunamadı")

    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        return inventory_to_public(doc)
    updates["updated_at"] = now_utc()
    await db.inventory.update_one({"_id": inv_id}, {"$set": updates})
    await log_activity(current_hotel["_id"], "update", "inventory", inv_id, {"fields": list(updates.keys())})
    refreshed = await db.inventory.find_one({"_id": inv_id})
    return inventory_to_public(refreshed)


@api.delete("/inventory/{inv_id}")
async def delete_inventory_item(inv_id: str, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    doc = await db.inventory.find_one({"_id": inv_id, "hotel_id": current_hotel["_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Envanter kalemi bulunamadı")
    # İlişkili günlük müsaitlikleri de sil
    await db.daily_availability.delete_many({"inventory_id": inv_id})
    await db.inventory.delete_one({"_id": inv_id})
    await log_activity(current_hotel["_id"], "delete", "inventory", inv_id, {})
    return {"message": "Envanter kalemi ve ilişkili müsaitlikler silindi"}


@api.post("/inventory/availability/bulk")
async def set_availability_bulk(payload: AvailabilityBulkSet, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """Tarih aralığı için toplu müsaitlik ayarla."""
    inv = await db.inventory.find_one({"_id": payload.inventory_id, "hotel_id": current_hotel["_id"]})
    if not inv:
        raise HTTPException(status_code=404, detail="Envanter kalemi bulunamadı")

    if payload.available_rooms > inv["total_rooms"]:
        raise HTTPException(status_code=400, detail=f"Müsait oda sayısı toplam oda sayısından ({inv['total_rooms']}) fazla olamaz")

    try:
        d_start = date.fromisoformat(payload.date_start)
        d_end = date.fromisoformat(payload.date_end)
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz tarih formatı. YYYY-MM-DD kullanın.")

    if d_start > d_end:
        raise HTTPException(status_code=400, detail="Başlangıç tarihi bitiş tarihinden sonra olamaz")

    if (d_end - d_start).days > 365:
        raise HTTPException(status_code=400, detail="En fazla 365 günlük aralık ayarlanabilir")

    updated_count = 0
    current_date = d_start
    while current_date <= d_end:
        date_str = current_date.isoformat()
        existing = await db.daily_availability.find_one({
            "inventory_id": payload.inventory_id,
            "date": date_str,
        })

        booked = existing.get("booked_rooms", 0) if existing else 0
        if payload.available_rooms < booked:
            raise HTTPException(
                status_code=400,
                detail=f"{date_str} tarihinde {booked} oda zaten rezerveli. Müsait oda sayısı bundan az olamaz."
            )

        avail_doc = {
            "hotel_id": current_hotel["_id"],
            "inventory_id": payload.inventory_id,
            "date": date_str,
            "available_rooms": payload.available_rooms,
            "booked_rooms": booked,
            "total_rooms": inv["total_rooms"],
            "price_per_night": payload.price_per_night,
            "notes": payload.notes,
            "updated_at": now_utc(),
        }

        if existing:
            await db.daily_availability.update_one({"_id": existing["_id"]}, {"$set": avail_doc})
        else:
            avail_doc["_id"] = str(uuid.uuid4())
            avail_doc["created_at"] = now_utc()
            await db.daily_availability.insert_one(avail_doc)

        updated_count += 1
        current_date += timedelta(days=1)

    await log_activity(current_hotel["_id"], "bulk_availability", "inventory", payload.inventory_id,
                       {"date_start": payload.date_start, "date_end": payload.date_end, "available_rooms": payload.available_rooms, "days": updated_count})

    return {"message": f"{updated_count} günlük müsaitlik güncellendi", "days_updated": updated_count}


@api.get("/inventory/{inv_id}/calendar")
async def get_inventory_calendar(
    inv_id: str,
    month: Optional[str] = None,  # YYYY-MM
    current_hotel: Dict[str, Any] = Depends(get_current_hotel),
):
    """Belirli envanter kalemi için takvim görünümü."""
    inv = await db.inventory.find_one({"_id": inv_id, "hotel_id": current_hotel["_id"]})
    if not inv:
        raise HTTPException(status_code=404, detail="Envanter kalemi bulunamadı")

    if month:
        try:
            year, mon = map(int, month.split("-"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Geçersiz ay formatı. YYYY-MM kullanın.")
    else:
        now = now_utc()
        year, mon = now.year, now.month

    # Ayın ilk ve son günü
    first_day = date(year, mon, 1)
    if mon == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, mon + 1, 1) - timedelta(days=1)

    cursor = db.daily_availability.find({
        "inventory_id": inv_id,
        "date": {"$gte": first_day.isoformat(), "$lte": last_day.isoformat()},
    }).sort("date", 1)
    docs = await cursor.to_list(length=31)

    # Tüm günleri doldur
    calendar_data = {}
    current_d = first_day
    while current_d <= last_day:
        calendar_data[current_d.isoformat()] = {
            "date": current_d.isoformat(),
            "available_rooms": inv["total_rooms"],
            "booked_rooms": 0,
            "total_rooms": inv["total_rooms"],
            "price_per_night": None,
            "has_data": False,
        }
        current_d += timedelta(days=1)

    for d in docs:
        calendar_data[d["date"]] = {
            "date": d["date"],
            "available_rooms": d["available_rooms"],
            "booked_rooms": d.get("booked_rooms", 0),
            "total_rooms": d.get("total_rooms", inv["total_rooms"]),
            "price_per_night": d.get("price_per_night"),
            "has_data": True,
        }

    return {
        "inventory_id": inv_id,
        "room_type_name": inv["room_type_name"],
        "room_type": inv["room_type"],
        "total_rooms": inv["total_rooms"],
        "month": f"{year}-{mon:02d}",
        "days": list(calendar_data.values()),
    }


@api.get("/inventory/summary/all")
async def get_inventory_summary(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """Otelin tüm envanter özeti - bugünkü durum."""
    today_str = date.today().isoformat()
    inv_cursor = db.inventory.find({"hotel_id": current_hotel["_id"]})
    inventories = await inv_cursor.to_list(length=200)

    summary = []
    for inv in inventories:
        # Bugünkü müsaitlik
        today_avail = await db.daily_availability.find_one({
            "inventory_id": inv["_id"],
            "date": today_str,
        })

        # Bu ay toplam rezervasyon sayısı
        now = now_utc()
        first_of_month = date(now.year, now.month, 1).isoformat()
        if now.month == 12:
            last_of_month = date(now.year + 1, 1, 1).isoformat()
        else:
            last_of_month = date(now.year, now.month + 1, 1).isoformat()

        month_cursor = db.daily_availability.find({
            "inventory_id": inv["_id"],
            "date": {"$gte": first_of_month, "$lt": last_of_month},
            "booked_rooms": {"$gt": 0},
        })
        month_bookings = await month_cursor.to_list(length=31)
        total_booked_nights = sum(d.get("booked_rooms", 0) for d in month_bookings)

        # Doluluk oranı hesapla
        total_capacity_this_month = inv["total_rooms"] * 30
        occupancy_rate = round(total_booked_nights / total_capacity_this_month * 100, 1) if total_capacity_this_month > 0 else 0

        summary.append({
            "inventory_id": inv["_id"],
            "room_type": inv["room_type"],
            "room_type_name": inv["room_type_name"],
            "total_rooms": inv["total_rooms"],
            "today_available": today_avail["available_rooms"] if today_avail else inv["total_rooms"],
            "today_booked": today_avail.get("booked_rooms", 0) if today_avail else 0,
            "today_price": today_avail.get("price_per_night") if today_avail else None,
            "month_booked_nights": total_booked_nights,
            "occupancy_rate": occupancy_rate,
            "capacity_label": inv.get("capacity_label"),
            "pax": inv.get("pax"),
        })

    return {"hotel_id": current_hotel["_id"], "date": today_str, "items": summary}




@api.post("/inventory/check-availability")
async def check_availability(
    payload: Optional[CheckAvailabilityRequest] = None,
    room_type: Optional[str] = None,
    date_start: Optional[str] = None,
    date_end: Optional[str] = None,
    current_hotel: Dict[str, Any] = Depends(get_current_hotel),
):
    """Belirli tarih aralığında oda tipi müsaitliğini kontrol et (overbooking engelleme).

    Hem JSON body hem de query parametreleri kabul edilir (legacy frontend uyumluluğu).
    Body öncelik kazanır; body alanı `None` ise query değeri devreye girer.
    """
    if payload is not None:
        room_type = payload.room_type or room_type
        date_start = payload.date_start or date_start
        date_end = payload.date_end or date_end
    if not room_type or not date_start or not date_end:
        raise HTTPException(status_code=422, detail="room_type, date_start, date_end zorunlu")

    inv = await db.inventory.find_one({"hotel_id": current_hotel["_id"], "room_type": room_type})
    if not inv:
        return {"available": True, "message": "Bu oda tipi için envanter tanımı yok, ilan oluşturulabilir", "min_available": None}

    try:
        d_start = date.fromisoformat(date_start)
        d_end = date.fromisoformat(date_end)
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz tarih formatı")

    min_available = inv["total_rooms"]
    problem_dates = []
    current_d = d_start
    while current_d <= d_end:
        date_str = current_d.isoformat()
        avail = await db.daily_availability.find_one({
            "inventory_id": inv["_id"],
            "date": date_str,
        })
        if avail:
            available = avail.get("available_rooms", inv["total_rooms"])
            if available < min_available:
                min_available = available
            if available <= 0:
                problem_dates.append(date_str)

        current_d += timedelta(days=1)

    return {
        "available": min_available > 0,
        "min_available": min_available,
        "total_rooms": inv["total_rooms"],
        "problem_dates": problem_dates,
        "message": "Müsait" if min_available > 0 else f"Bu tarih aralığında müsait oda yok: {', '.join(problem_dates[:5])}",
    }
