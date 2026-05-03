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


# --- Admin Revenue Dashboard -------------------------------------------------
# =============================================================================

@api.get("/admin/revenue")
async def admin_revenue(
    months: int = 6,
    admin: Dict[str, Any] = Depends(get_current_admin),
):
    """Admin: Platform gelir genel bakışı."""
    now = now_utc()
    start_date = now - timedelta(days=months * 30)

    all_payments = await db.payments.find({
        "status": "completed",
        "completed_at": {"$gte": start_date},
    }).to_list(length=5000)

    all_matches = await db.matches.find({
        "created_at": {"$gte": start_date},
    }).to_list(length=5000)

    total_revenue = sum(p["amount"] for p in all_payments)
    total_matches = len(all_matches)
    paid_matches = sum(1 for m in all_matches if m.get("fee_status") == "paid")
    unpaid_matches = total_matches - paid_matches

    # Aylık kırılım
    monthly = defaultdict(lambda: {"revenue": 0, "matches": 0, "payments": 0})
    for p in all_payments:
        key = p["completed_at"].strftime("%Y-%m")
        monthly[key]["revenue"] += p["amount"]
        monthly[key]["payments"] += 1
    for m in all_matches:
        key = m["created_at"].strftime("%Y-%m")
        monthly[key]["matches"] += 1

    # Bölge bazlı
    region_revenue = defaultdict(lambda: {"matches": 0, "revenue": 0})
    for m in all_matches:
        region = m.get("region", "Bilinmiyor")
        region_revenue[region]["matches"] += 1
        region_revenue[region]["revenue"] += m.get("fee_amount", MATCH_FEE_TL)

    return {
        "total_revenue": total_revenue,
        "total_matches": total_matches,
        "paid_matches": paid_matches,
        "unpaid_matches": unpaid_matches,
        "monthly": dict(monthly),
        "region_breakdown": dict(region_revenue),
        "period_months": months,
    }


@api.get("/admin/region-stats")
async def admin_region_stats(admin: Dict[str, Any] = Depends(get_current_admin)):
    """Admin: Bölge bazlı istatistikler."""
    now = now_utc()
    result = {}
    for region_key, region_info in REGIONS.items():
        hotels = await db.hotels.count_documents({"region": region_key})
        active_listings = await db.availability_listings.count_documents({"region": region_key, "date_end": {"$gte": now}})
        total_listings = await db.availability_listings.count_documents({"region": region_key})
        result[region_key] = {
            "label": region_info["label"],
            "hotels": hotels,
            "active_listings": active_listings,
            "total_listings": total_listings,
        }
    return result


# =============================================================================
