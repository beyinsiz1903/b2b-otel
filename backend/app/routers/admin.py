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


# --- Admin endpoints --------------------------------------------------------

@api.get("/admin/overview")
async def admin_overview(admin: Dict[str, Any] = Depends(get_current_admin)):
    total_hotels = await db.hotels.count_documents({})
    total_listings = await db.availability_listings.count_documents({})
    total_requests = await db.requests.count_documents({})
    total_matches = await db.matches.count_documents({})

    # Fee totals
    matches_cursor = db.matches.find({})
    matches = await matches_cursor.to_list(length=10000)
    total_fees = sum(m.get("fee_amount", 0) for m in matches)
    paid_fees = sum(m.get("fee_amount", 0) for m in matches if m.get("fee_status") == "paid")
    due_fees = sum(m.get("fee_amount", 0) for m in matches if m.get("fee_status") == "due")

    # Recent activity
    recent_logs_cursor = db.activity_logs.find({}).sort("created_at", -1).limit(20)
    recent_logs = await recent_logs_cursor.to_list(length=20)
    for log in recent_logs:
        log["id"] = str(log.pop("_id"))
        if isinstance(log.get("created_at"), datetime):
            log["created_at"] = log["created_at"].isoformat()

    return {
        "total_hotels": total_hotels,
        "total_listings": total_listings,
        "total_requests": total_requests,
        "total_matches": total_matches,
        "total_fees": total_fees,
        "paid_fees": paid_fees,
        "due_fees": due_fees,
        "recent_activity": recent_logs,
    }


@api.get("/admin/hotels")
async def admin_list_hotels(
    status_filter: Optional[str] = None,  # pending_review | approved | rejected | all
    admin: Dict[str, Any] = Depends(get_current_admin)
):
    query = {}
    if status_filter and status_filter != "all":
        query["approval_status"] = status_filter
    cursor = db.hotels.find(query).sort("created_at", -1)
    docs = await cursor.to_list(length=1000)
    result = []
    for doc in docs:
        hotel_id = doc["_id"]
        match_count = await db.matches.count_documents({"$or": [{"hotel_a_id": hotel_id}, {"hotel_b_id": hotel_id}]})
        listing_count = await db.availability_listings.count_documents({"hotel_id": hotel_id})
        result.append({
            "id": hotel_id,
            "name": doc["name"],
            "email": doc["email"],
            "region": doc["region"],
            "concept": doc["concept"],
            "phone": doc["phone"],
            "address": doc.get("address", ""),
            "contact_person": doc.get("contact_person", ""),
            "is_admin": doc.get("is_admin", False),
            "approval_status": doc.get("approval_status", "approved"),
            "rejection_reason": doc.get("rejection_reason"),
            "documents": doc.get("documents", []),
            "created_at": doc["created_at"].isoformat() if isinstance(doc.get("created_at"), datetime) else None,
            "match_count": match_count,
            "listing_count": listing_count,
        })
    return result


@api.put("/admin/hotels/{hotel_id}/approve")
async def admin_approve_hotel(hotel_id: str, admin: Dict[str, Any] = Depends(get_current_admin)):
    hotel = await db.hotels.find_one({"_id": hotel_id})
    if not hotel:
        raise HTTPException(status_code=404, detail="Otel bulunamadı")
    await db.hotels.update_one(
        {"_id": hotel_id},
        {"$set": {"approval_status": "approved", "rejection_reason": None, "updated_at": now_utc()}}
    )
    await log_activity(admin["_id"], "approve_hotel", "hotel", hotel_id, {"hotel_name": hotel.get("name")})
    return {"id": hotel_id, "approval_status": "approved", "message": f"{hotel.get('name')} onaylandı."}


@api.put("/admin/hotels/{hotel_id}/reject")
async def admin_reject_hotel(hotel_id: str, body: Dict[str, str], admin: Dict[str, Any] = Depends(get_current_admin)):
    hotel = await db.hotels.find_one({"_id": hotel_id})
    if not hotel:
        raise HTTPException(status_code=404, detail="Otel bulunamadı")
    reason = body.get("reason", "")
    await db.hotels.update_one(
        {"_id": hotel_id},
        {"$set": {"approval_status": "rejected", "rejection_reason": reason, "updated_at": now_utc()}}
    )
    await log_activity(admin["_id"], "reject_hotel", "hotel", hotel_id, {"reason": reason})
    return {"id": hotel_id, "approval_status": "rejected", "message": f"{hotel.get('name')} reddedildi."}


@api.get("/admin/matches")
async def admin_list_matches(admin: Dict[str, Any] = Depends(get_current_admin)):
    cursor = db.matches.find({}).sort("created_at", -1).limit(200)
    docs = await cursor.to_list(length=200)
    if not docs:
        return []

    # Toplu join — N+1 yerine tek sorguda otel + ödeme bilgilerini topla
    hotel_ids = {d["hotel_a_id"] for d in docs} | {d["hotel_b_id"] for d in docs}
    hotels_cur = db.hotels.find({"_id": {"$in": list(hotel_ids)}}, {"_id": 1, "name": 1})
    hotels_map = {h["_id"]: h.get("name", "?") async for h in hotels_cur}

    match_ids = [d["_id"] for d in docs]
    payments_cur = db.payments.find(
        {"match_id": {"$in": match_ids}},
        {"_id": 1, "match_id": 1, "hotel_id": 1, "amount": 1, "status": 1, "completed_at": 1, "created_at": 1},
    )
    payments_by_match: Dict[str, list] = defaultdict(list)
    async for p in payments_cur:
        payments_by_match[p["match_id"]].append(p)

    result = []
    for d in docs:
        m_payments = payments_by_match.get(d["_id"], [])
        completed = [p for p in m_payments if p.get("status") == "completed"]
        amount_paid = sum(p.get("amount", 0) for p in completed)
        last_payment = max(m_payments, key=lambda p: p.get("created_at") or datetime.min.replace(tzinfo=timezone.utc), default=None)
        result.append({
            "id": d["_id"],
            "reference_code": d["reference_code"],
            "hotel_a_name": hotels_map.get(d["hotel_a_id"], "Silinmiş otel"),
            "hotel_b_name": hotels_map.get(d["hotel_b_id"], "Silinmiş otel"),
            "fee_amount": d["fee_amount"],
            "fee_status": d["fee_status"],
            "accepted_at": d["accepted_at"].isoformat() if isinstance(d.get("accepted_at"), datetime) else None,
            "amount_paid": amount_paid,
            "payment_count": len(m_payments),
            "last_payment_status": last_payment.get("status") if last_payment else None,
            "last_payment_at": (
                last_payment.get("completed_at").isoformat()
                if last_payment and isinstance(last_payment.get("completed_at"), datetime)
                else None
            ),
        })
    return result


@api.put("/admin/hotels/{hotel_id}/toggle-admin")
async def admin_toggle_admin(hotel_id: str, admin: Dict[str, Any] = Depends(get_current_admin)):
    hotel = await db.hotels.find_one({"_id": hotel_id})
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    new_val = not hotel.get("is_admin", False)
    await db.hotels.update_one({"_id": hotel_id}, {"$set": {"is_admin": new_val, "updated_at": now_utc()}})
    return {"id": hotel_id, "is_admin": new_val}


@api.put("/admin/matches/{match_id}/fee-status")
async def admin_update_fee_status(match_id: str, body: Dict[str, str], admin: Dict[str, Any] = Depends(get_current_admin)):
    new_status = body.get("fee_status")
    if new_status not in ("due", "paid", "waived"):
        raise HTTPException(status_code=400, detail="Invalid fee_status")
    await db.matches.update_one({"_id": match_id}, {"$set": {"fee_status": new_status}})
    return {"id": match_id, "fee_status": new_status}


