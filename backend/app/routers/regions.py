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


# --- Regions Info & Admin Region Pricing -------------------------------------
# =============================================================================

@api.get("/regions")
async def list_regions():
    """Tüm bölgeleri listele."""
    result = []
    for key, info in REGIONS.items():
        # Admin tarafından özelleştirilmiş fiyat kontrolü
        custom = await db.region_pricing.find_one({"_id": key})
        fee = custom["match_fee"] if custom and "match_fee" in custom else info["match_fee"]
        result.append({
            "id": key,
            "label": info["label"],
            "prefix": info["prefix"],
            "match_fee": fee,
        })
    return result


@api.get("/admin/region-pricing")
async def admin_get_region_pricing(admin: Dict[str, Any] = Depends(get_current_admin)):
    """Admin: Bölge bazlı fiyatlandırma."""
    result = []
    for key, info in REGIONS.items():
        custom = await db.region_pricing.find_one({"_id": key})
        result.append({
            "region": key,
            "label": info["label"],
            "default_fee": info["match_fee"],
            "custom_fee": custom.get("match_fee") if custom else None,
            "active_fee": custom["match_fee"] if custom and "match_fee" in custom else info["match_fee"],
        })
    return result


@api.put("/admin/region-pricing/{region}")
async def admin_update_region_pricing(region: str, body: Dict[str, Any], admin: Dict[str, Any] = Depends(get_current_admin)):
    """Admin: Bölge eşleşme ücretini güncelle."""
    if region not in REGIONS:
        raise HTTPException(status_code=400, detail="Geçersiz bölge")
    match_fee = body.get("match_fee")
    if match_fee is None or match_fee < 0:
        raise HTTPException(status_code=400, detail="Geçerli bir ücret girin")
    await db.region_pricing.update_one(
        {"_id": region},
        {"$set": {"match_fee": float(match_fee), "updated_at": now_utc(), "updated_by": admin["_id"]}},
        upsert=True,
    )
    return {"message": f"{region} bölgesi eşleşme ücreti ₺{match_fee:.2f} olarak güncellendi"}


# =============================================================================
