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


# --- Subscription System -----------------------------------------------------
# =============================================================================

@api.get("/subscriptions/plans")
async def list_subscription_plans():
    """Mevcut abonelik planlarını listele."""
    return SUBSCRIPTION_PLANS


@api.post("/subscriptions/subscribe")
async def subscribe(body: Dict[str, str], current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """Bir plana abone ol."""
    plan_id = body.get("plan_id", "free")
    billing_cycle = body.get("billing_cycle", "monthly")

    plan = next((p for p in SUBSCRIPTION_PLANS if p["id"] == plan_id), None)
    if not plan:
        raise HTTPException(status_code=400, detail="Geçersiz plan")

    # Mevcut aktif abonelik varsa iptal et
    await db.subscriptions.update_many(
        {"hotel_id": current_hotel["_id"], "status": "active"},
        {"$set": {"status": "cancelled", "cancelled_at": now_utc()}}
    )

    now = now_utc()
    price = plan["price_yearly"] if billing_cycle == "yearly" else plan["price_monthly"]
    expires_at = now + timedelta(days=365 if billing_cycle == "yearly" else 30)

    sub_id = str(uuid.uuid4())
    doc = {
        "_id": sub_id,
        "hotel_id": current_hotel["_id"],
        "plan_id": plan_id,
        "plan_name": plan["name"],
        "billing_cycle": billing_cycle,
        "price": price,
        "max_matches": plan["max_matches_per_month"],
        "matches_used": 0,
        "status": "active",
        "started_at": now,
        "expires_at": expires_at,
        "cancelled_at": None,
    }
    await db.subscriptions.insert_one(doc)

    await create_notification(current_hotel["_id"], "subscription_created", "Abonelik Aktif", f"{plan['name']} planına abone oldunuz.", {"subscription_id": sub_id})
    return serialize_doc(doc)


@api.get("/subscriptions/my")
async def my_subscription(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """Aktif aboneliğimi getir."""
    sub = await db.subscriptions.find_one({"hotel_id": current_hotel["_id"], "status": "active"}, sort=[("started_at", -1)])
    if not sub:
        return {"plan_id": "free", "plan_name": "Ücretsiz", "max_matches": 5, "matches_used": 0, "status": "active"}
    return serialize_doc(sub)


@api.post("/subscriptions/cancel")
async def cancel_subscription(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """Aboneliği iptal et."""
    sub = await db.subscriptions.find_one({"hotel_id": current_hotel["_id"], "status": "active"})
    if not sub:
        raise HTTPException(status_code=400, detail="Aktif abonelik yok")
    await db.subscriptions.update_one({"_id": sub["_id"]}, {"$set": {"status": "cancelled", "cancelled_at": now_utc()}})
    return {"message": "Abonelik iptal edildi"}


# =============================================================================
