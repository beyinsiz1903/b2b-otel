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


# --- Advanced Pricing Engine ------------------------------------------------
# ============================================================================

def pricing_rule_to_public(doc: Dict[str, Any]) -> PricingRulePublic:
    return PricingRulePublic(
        id=doc["_id"],
        hotel_id=doc["hotel_id"],
        name=doc["name"],
        rule_type=doc["rule_type"],
        room_type=doc.get("room_type"),
        multiplier=doc["multiplier"],
        date_start=doc.get("date_start"),
        date_end=doc.get("date_end"),
        occupancy_threshold_min=doc.get("occupancy_threshold_min"),
        occupancy_threshold_max=doc.get("occupancy_threshold_max"),
        days_before_min=doc.get("days_before_min"),
        days_before_max=doc.get("days_before_max"),
        weekend_days=doc.get("weekend_days"),
        is_active=doc.get("is_active", True),
        priority=doc.get("priority", 0),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


@api.post("/pricing/rules", response_model=PricingRulePublic)
async def create_pricing_rule(payload: PricingRuleCreate, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    rule_id = str(uuid.uuid4())
    now = now_utc()
    doc = {
        "_id": rule_id,
        "hotel_id": current_hotel["_id"],
        **payload.model_dump(),
        "created_at": now,
        "updated_at": now,
    }
    await db.pricing_rules.insert_one(doc)
    await log_activity(current_hotel["_id"], "create", "pricing_rule", rule_id, {"name": payload.name, "type": payload.rule_type})
    return pricing_rule_to_public(doc)


@api.get("/pricing/rules", response_model=List[PricingRulePublic])
async def list_pricing_rules(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    cursor = db.pricing_rules.find({"hotel_id": current_hotel["_id"]}).sort("priority", -1)
    docs = await cursor.to_list(length=100)
    return [pricing_rule_to_public(d) for d in docs]


@api.put("/pricing/rules/{rule_id}", response_model=PricingRulePublic)
async def update_pricing_rule(rule_id: str, payload: PricingRuleUpdate, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    doc = await db.pricing_rules.find_one({"_id": rule_id, "hotel_id": current_hotel["_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Fiyatlama kuralı bulunamadı")

    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items()}
    if not updates:
        return pricing_rule_to_public(doc)
    updates["updated_at"] = now_utc()
    await db.pricing_rules.update_one({"_id": rule_id}, {"$set": updates})
    refreshed = await db.pricing_rules.find_one({"_id": rule_id})
    return pricing_rule_to_public(refreshed)


@api.delete("/pricing/rules/{rule_id}")
async def delete_pricing_rule(rule_id: str, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    doc = await db.pricing_rules.find_one({"_id": rule_id, "hotel_id": current_hotel["_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Fiyatlama kuralı bulunamadı")
    await db.pricing_rules.delete_one({"_id": rule_id})
    return {"message": "Fiyatlama kuralı silindi"}


async def _calculate_dynamic_price(hotel_id: str, room_type: str, target_date: date, base_price: float) -> Dict[str, Any]:
    """Belirli bir gün için dinamik fiyat hesapla."""
    rules_cursor = db.pricing_rules.find({
        "hotel_id": hotel_id,
        "is_active": True,
        "$or": [{"room_type": room_type}, {"room_type": None}],
    }).sort("priority", -1)
    rules = await rules_cursor.to_list(length=50)

    applied_rules = []
    final_multiplier = 1.0
    target_str = target_date.isoformat()
    today = date.today()
    days_until = (target_date - today).days

    for rule in rules:
        applies = False
        rule_type = rule["rule_type"]

        if rule_type == "seasonal":
            rs = rule.get("date_start")
            re = rule.get("date_end")
            if rs and re:
                applies = rs <= target_str <= re

        elif rule_type == "weekend":
            weekend_days = rule.get("weekend_days", [4, 5, 6])  # Cuma, Cumartesi, Pazar
            applies = target_date.weekday() in weekend_days

        elif rule_type == "occupancy":
            # Doluluk oranına bakarak karar ver
            inv = await db.inventory.find_one({"hotel_id": hotel_id, "room_type": room_type})
            if inv:
                avail = await db.daily_availability.find_one({"inventory_id": inv["_id"], "date": target_str})
                if avail and avail.get("total_rooms", 0) > 0:
                    occupancy = avail.get("booked_rooms", 0) / avail["total_rooms"]
                    occ_min = rule.get("occupancy_threshold_min", 0)
                    occ_max = rule.get("occupancy_threshold_max", 1)
                    applies = occ_min <= occupancy <= occ_max

        elif rule_type == "early_bird":
            db_min = rule.get("days_before_min", 30)
            db_max = rule.get("days_before_max", 365)
            applies = db_min <= days_until <= db_max

        elif rule_type == "last_minute":
            db_min = rule.get("days_before_min", 0)
            db_max = rule.get("days_before_max", 7)
            applies = db_min <= days_until <= db_max

        elif rule_type == "holiday":
            rs = rule.get("date_start")
            re = rule.get("date_end")
            if rs and re:
                applies = rs <= target_str <= re

        if applies:
            final_multiplier *= rule["multiplier"]
            applied_rules.append({
                "rule_id": rule["_id"],
                "name": rule["name"],
                "type": rule_type,
                "multiplier": rule["multiplier"],
            })

    calculated_price = round(base_price * final_multiplier, 2)

    return {
        "base_price": base_price,
        "final_price": calculated_price,
        "final_multiplier": round(final_multiplier, 4),
        "applied_rules": applied_rules,
        "date": target_str,
    }


@api.post("/pricing/calculate")
async def calculate_price(payload: PriceCalculateRequest, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """Tarih aralığı için dinamik fiyat hesapla."""
    try:
        d_start = date.fromisoformat(payload.date_start)
        d_end = date.fromisoformat(payload.date_end)
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz tarih formatı")

    if d_start > d_end:
        raise HTTPException(status_code=400, detail="Başlangıç tarihi bitiş tarihinden sonra olamaz")

    days = []
    total_price = 0.0
    current_d = d_start
    while current_d <= d_end:
        day_result = await _calculate_dynamic_price(
            current_hotel["_id"], payload.room_type, current_d, payload.base_price
        )
        days.append(day_result)
        total_price += day_result["final_price"]
        current_d += timedelta(days=1)

    night_count = len(days)
    avg_price = round(total_price / night_count, 2) if night_count > 0 else 0

    return {
        "room_type": payload.room_type,
        "date_start": payload.date_start,
        "date_end": payload.date_end,
        "base_price": payload.base_price,
        "total_price": round(total_price, 2),
        "average_price": avg_price,
        "night_count": night_count,
        "daily_breakdown": days,
    }


@api.get("/pricing/market-comparison")
async def market_comparison(
    room_type: Optional[str] = None,
    region: Optional[str] = None,
    current_hotel: Dict[str, Any] = Depends(get_current_hotel),
):
    """Piyasa karşılaştırması - benzer ilanlara göre fiyat önerisi."""
    query: Dict[str, Any] = {}
    if room_type:
        query["room_type"] = room_type
    if region:
        query["region"] = region

    # Aktif ilanları al (süresi geçmemiş)
    query["date_end"] = {"$gte": now_utc()}
    cursor = db.availability_listings.find(query).sort("created_at", -1).limit(100)
    listings = await cursor.to_list(length=100)

    if not listings:
        return {
            "room_type": room_type,
            "region": region,
            "sample_size": 0,
            "avg_price_min": None,
            "avg_price_max": None,
            "min_price": None,
            "max_price": None,
            "median_price": None,
            "my_avg_price": None,
            "recommendation": "Yeterli veri yok",
        }

    # Kendi ilanlarım vs. piyasa
    my_listings = [l for l in listings if l["hotel_id"] == current_hotel["_id"]]
    other_listings = [l for l in listings if l["hotel_id"] != current_hotel["_id"]]

    all_prices_min = [l["price_min"] for l in listings if l.get("price_min")]
    all_prices_max = [l["price_max"] for l in listings if l.get("price_max")]

    avg_min = round(sum(all_prices_min) / len(all_prices_min), 2) if all_prices_min else None
    avg_max = round(sum(all_prices_max) / len(all_prices_max), 2) if all_prices_max else None

    # Median: price_min ile price_max'in orta noktası üzerinden — daha temsili
    midpoints = [
        ((l["price_min"] + l["price_max"]) / 2.0) if l.get("price_min") and l.get("price_max")
        else (l.get("price_min") or l.get("price_max"))
        for l in listings
    ]
    midpoints = [m for m in midpoints if m is not None]

    def _median(vals):
        if not vals:
            return None
        s = sorted(vals)
        n = len(s)
        if n % 2 == 1:
            return round(s[n // 2], 2)
        return round((s[n // 2 - 1] + s[n // 2]) / 2.0, 2)

    median_price = _median(midpoints)
    median_price_min = _median(all_prices_min)
    median_price_max = _median(all_prices_max)

    my_prices_mid = [
        ((l["price_min"] + l["price_max"]) / 2.0) if l.get("price_min") and l.get("price_max")
        else (l.get("price_min") or l.get("price_max"))
        for l in my_listings
    ]
    my_prices_mid = [m for m in my_prices_mid if m is not None]
    my_avg = round(sum(my_prices_mid) / len(my_prices_mid), 2) if my_prices_mid else None

    # Öneri — kıyas için median midpoint kullanılır (avg_min'e göre daha temsili)
    recommendation = "Fiyatlarınız piyasa ortalamasında"
    benchmark = median_price or avg_min
    if my_avg and benchmark:
        if my_avg > benchmark * 1.2:
            recommendation = "Fiyatlarınız piyasa ortalamasının %20'den fazla üstünde. İndirim düşünebilirsiniz."
        elif my_avg < benchmark * 0.8:
            recommendation = "Fiyatlarınız piyasa ortalamasının %20'den fazla altında. Fiyat artışı düşünebilirsiniz."

    return {
        "room_type": room_type,
        "region": region,
        "sample_size": len(listings),
        "my_listing_count": len(my_listings),
        "other_listing_count": len(other_listings),
        "avg_price_min": avg_min,
        "avg_price_max": avg_max,
        "min_price": min(all_prices_min) if all_prices_min else None,
        "max_price": max(all_prices_max) if all_prices_max else None,
        "median_price": median_price,            # midpoint median (önerilen)
        "median_price_min": median_price_min,
        "median_price_max": median_price_max,
        "my_avg_price": my_avg,
        "recommendation": recommendation,
    }


@api.get("/pricing/history")
async def price_history(
    room_type: Optional[str] = None,
    months: int = 6,
    current_hotel: Dict[str, Any] = Depends(get_current_hotel),
):
    """Fiyat geçmişi - son N ay."""
    query: Dict[str, Any] = {"hotel_id": current_hotel["_id"]}
    if room_type:
        query["room_type"] = room_type

    # Son N ay
    now = now_utc()
    cutoff = now - timedelta(days=months * 30)
    query["created_at"] = {"$gte": cutoff}

    cursor = db.availability_listings.find(query).sort("created_at", -1)
    listings = await cursor.to_list(length=500)

    monthly_data: Dict[str, Dict[str, Any]] = {}
    for l in listings:
        month_key = l["created_at"].strftime("%Y-%m")
        if month_key not in monthly_data:
            monthly_data[month_key] = {"prices_min": [], "prices_max": [], "count": 0}
        monthly_data[month_key]["prices_min"].append(l.get("price_min", 0))
        monthly_data[month_key]["prices_max"].append(l.get("price_max", 0))
        monthly_data[month_key]["count"] += 1

    history = []
    for month_key in sorted(monthly_data.keys()):
        data = monthly_data[month_key]
        history.append({
            "month": month_key,
            "avg_price_min": round(sum(data["prices_min"]) / len(data["prices_min"]), 2),
            "avg_price_max": round(sum(data["prices_max"]) / len(data["prices_max"]), 2),
            "listing_count": data["count"],
            "min_price": min(data["prices_min"]),
            "max_price": max(data["prices_max"]),
        })

    return {"room_type": room_type, "months": months, "history": history}


# ============================================================================
