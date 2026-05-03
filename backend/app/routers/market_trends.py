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


# --- Market Trends -----------------------------------------------------------
# =============================================================================

@api.get("/stats/market-trends")
async def market_trends(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """Bölge bazlı talep/arz dengesi görselleştirme."""
    now = now_utc()
    thirty_days_ago = now - timedelta(days=30)

    result = {}
    for region_key, region_info in REGIONS.items():
        # Aktif ilanlar (arz)
        supply = await db.availability_listings.count_documents({
            "region": region_key,
            "date_end": {"$gte": now},
        })
        # Son 30 gündeki talepler
        demand = await db.requests.count_documents({
            "created_at": {"$gte": thirty_days_ago},
        })
        # Bölgedeki eşleşmeler
        matches = await db.matches.count_documents({
            "region": region_key,
            "created_at": {"$gte": thirty_days_ago},
        })
        # Bölge eşleşmeleri (region alanı yoksa listing üzerinden)
        if matches == 0:
            listing_ids = []
            async for l in db.availability_listings.find({"region": region_key}, {"_id": 1}):
                listing_ids.append(l["_id"])
            if listing_ids:
                matches = await db.matches.count_documents({
                    "listing_id": {"$in": listing_ids},
                    "created_at": {"$gte": thirty_days_ago},
                })

        # Ortalama fiyat
        pipeline = [
            {"$match": {"region": region_key, "date_end": {"$gte": now}}},
            {"$group": {"_id": None, "avg_price": {"$avg": "$price_min"}, "count": {"$sum": 1}}},
        ]
        agg = await db.availability_listings.aggregate(pipeline).to_list(length=1)
        avg_price = agg[0]["avg_price"] if agg else 0

        result[region_key] = {
            "label": region_info["label"],
            "supply": supply,
            "demand": demand,
            "matches": matches,
            "avg_price": round(avg_price, 2),
            "match_fee": region_info["match_fee"],
            "balance": "dengeli" if abs(supply - demand) < 3 else ("talep_fazla" if demand > supply else "arz_fazla"),
        }

    return result


# =============================================================================
