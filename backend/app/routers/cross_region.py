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


# --- Cross-Region Stats & Matching -------------------------------------------
# =============================================================================

async def _empty_list():
    return []


@api.get("/stats/cross-region")
async def cross_region_stats(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """Bölgeler arası kapasite paylaşım istatistikleri."""
    now = now_utc()

    # Cross-region ilanlar + tüm eşleşmeler paralel.
    # Önceden her match için 3 ardışık find_one (listing + hotel_a + hotel_b)
    # yapılıyordu — N=5000 için >15k round-trip. Şimdi tek seferde $in ile çek,
    # bellekte sözlük ile çöz.
    cross_listings, all_matches = await asyncio.gather(
        db.availability_listings.find({
            "allow_cross_region": True,
            "date_end": {"$gte": now},
        }).to_list(length=500),
        db.matches.find({}).to_list(length=5000),
    )

    # Bölge bazlı cross-region dağılım
    region_cross = defaultdict(lambda: {"listings": 0, "total_pax": 0})
    for l in cross_listings:
        r = l.get("region", "Bilinmiyor")
        region_cross[r]["listings"] += 1
        region_cross[r]["total_pax"] += l.get("pax", 0)

    # Match'lerin referansladığı listing ve hotel id'lerini topla, tek $in ile çek.
    listing_ids = list({m.get("listing_id") for m in all_matches if m.get("listing_id")})
    hotel_ids = list({hid for m in all_matches for hid in (m.get("hotel_a_id"), m.get("hotel_b_id")) if hid})

    listings_map: Dict[Any, Dict[str, Any]] = {}
    hotels_map: Dict[Any, Dict[str, Any]] = {}
    if listing_ids or hotel_ids:
        listings_docs, hotels_docs = await asyncio.gather(
            db.availability_listings.find({"_id": {"$in": listing_ids}}, {"region": 1}).to_list(length=len(listing_ids)) if listing_ids else _empty_list(),
            db.hotels.find({"_id": {"$in": hotel_ids}}, {"region": 1}).to_list(length=len(hotel_ids)) if hotel_ids else _empty_list(),
        )
        listings_map = {d["_id"]: d for d in listings_docs}
        hotels_map = {d["_id"]: d for d in hotels_docs}

    cross_matches = []
    for m in all_matches:
        listing = listings_map.get(m.get("listing_id"))
        hotel_a = hotels_map.get(m.get("hotel_a_id"))
        hotel_b = hotels_map.get(m.get("hotel_b_id"))
        if listing and hotel_a and hotel_b:
            region_a = hotel_a.get("region", "")
            region_b = hotel_b.get("region", "")
            if region_a != region_b:
                cross_matches.append({
                    "from_region": region_a,
                    "to_region": region_b,
                    "listing_region": listing.get("region", ""),
                })

    # Bölge çiftleri
    pair_counts = defaultdict(int)
    for cm in cross_matches:
        pair_key = f"{cm['from_region']} → {cm['to_region']}"
        pair_counts[pair_key] += 1

    return {
        "total_cross_region_listings": len(cross_listings),
        "region_breakdown": dict(region_cross),
        "total_cross_region_matches": len(cross_matches),
        "region_pairs": dict(pair_counts),
        "regions": list(REGIONS.keys()),
    }


# =============================================================================
