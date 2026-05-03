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


# --- KVKK Compliance ---------------------------------------------------------
# =============================================================================

@api.get("/kvkk/export")
async def kvkk_export_data(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """KVKK - Tüm kişisel verilerimi dışa aktar."""
    hotel_id = current_hotel["_id"]

    hotel = await db.hotels.find_one({"_id": hotel_id})
    listings = await db.availability_listings.find({"hotel_id": hotel_id}).to_list(length=1000)
    requests_out = await db.requests.find({"from_hotel_id": hotel_id}).to_list(length=1000)
    requests_in = await db.requests.find({"to_hotel_id": hotel_id}).to_list(length=1000)
    matches = await db.matches.find({"$or": [{"hotel_a_id": hotel_id}, {"hotel_b_id": hotel_id}]}).to_list(length=1000)
    payments = await db.payments.find({"hotel_id": hotel_id}).to_list(length=500)
    invoices = await db.invoices.find({"hotel_id": hotel_id}).to_list(length=500)
    notifications = await db.notifications.find({"hotel_id": hotel_id}).to_list(length=500)

    return {
        "export_date": now_utc().isoformat(),
        "hotel": serialize_doc(hotel) if hotel else None,
        "listings_count": len(listings),
        "listings": [serialize_doc(l) for l in listings],
        "outgoing_requests_count": len(requests_out),
        "outgoing_requests": [serialize_doc(r) for r in requests_out],
        "incoming_requests_count": len(requests_in),
        "incoming_requests": [serialize_doc(r) for r in requests_in],
        "matches_count": len(matches),
        "matches": [serialize_doc(m) for m in matches],
        "payments_count": len(payments),
        "payments": [serialize_doc(p) for p in payments],
        "invoices_count": len(invoices),
        "invoices": [serialize_doc(i) for i in invoices],
        "notifications_count": len(notifications),
    }


@api.post("/kvkk/delete-request")
async def kvkk_delete_request(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """KVKK - Hesap silme talebi oluştur."""
    hotel_id = current_hotel["_id"]
    existing = await db.kvkk_requests.find_one({"hotel_id": hotel_id, "status": "pending"})
    if existing:
        return {"message": "Zaten bekleyen bir silme talebiniz var", "request_id": existing["_id"]}

    req_id = str(uuid.uuid4())
    await db.kvkk_requests.insert_one({
        "_id": req_id,
        "hotel_id": hotel_id,
        "type": "account_deletion",
        "status": "pending",
        "created_at": now_utc(),
    })
    await create_notification(hotel_id, "kvkk_request", "Silme Talebi Alındı", "Hesap silme talebiniz alınmıştır. 30 gün içinde işleme alınacaktır.", {"request_id": req_id})
    return {"message": "Silme talebi oluşturuldu. 30 gün içinde işleme alınacaktır.", "request_id": req_id}


# =============================================================================
