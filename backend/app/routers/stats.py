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


# --- Stats / Reporting ------------------------------------------------------

@api.get("/stats")
async def get_stats(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    hotel_id = current_hotel["_id"]
    now = now_utc()

    # All matches
    matches_cursor = db.matches.find({"$or": [{"hotel_a_id": hotel_id}, {"hotel_b_id": hotel_id}]})
    matches = await matches_cursor.to_list(length=1000)

    # All requests
    outgoing_cursor = db.requests.find({"from_hotel_id": hotel_id})
    incoming_cursor = db.requests.find({"to_hotel_id": hotel_id})
    outgoing = await outgoing_cursor.to_list(length=1000)
    incoming = await incoming_cursor.to_list(length=1000)

    # My listings
    listings_cursor = db.availability_listings.find({"hotel_id": hotel_id})
    listings = await listings_cursor.to_list(length=1000)

    # Monthly breakdown (last 6 months)
    monthly_matches: Dict[str, int] = {}
    monthly_fees: Dict[str, float] = {}
    for m in matches:
        if m.get("accepted_at"):
            key = m["accepted_at"].strftime("%Y-%m")
            monthly_matches[key] = monthly_matches.get(key, 0) + 1
            monthly_fees[key] = monthly_fees.get(key, 0.0) + m.get("fee_amount", 0.0)

    # Request stats
    total_outgoing = len(outgoing)
    total_incoming = len(incoming)
    accepted_outgoing = sum(1 for r in outgoing if r["status"] == "accepted")
    accepted_incoming = sum(1 for r in incoming if r["status"] == "accepted")
    pending_incoming = sum(1 for r in incoming if r["status"] == "pending")

    # Current month
    current_month_key = now.strftime("%Y-%m")
    this_month_matches = monthly_matches.get(current_month_key, 0)
    this_month_fees = monthly_fees.get(current_month_key, 0.0)

    # Total fees
    total_fees = sum(m.get("fee_amount", 0) for m in matches)

    # Active listings
    def _safe_date(d):
        """Ensure datetime is timezone-aware for comparison."""
        if d and d.tzinfo is None:
            return d.replace(tzinfo=timezone.utc)
        return d or now

    active_listings = sum(1 for l in listings if _safe_date(l.get("date_end")) >= now)
    expired_listings = sum(1 for l in listings if _safe_date(l.get("date_end")) < now)

    # Region breakdown for matches
    region_counts: Dict[str, int] = {}
    for m in matches:
        listing_doc = await db.availability_listings.find_one({"_id": m["listing_id"]})
        if listing_doc:
            r = listing_doc.get("region", "Bilinmiyor")
            region_counts[r] = region_counts.get(r, 0) + 1

    return {
        "total_matches": len(matches),
        "total_outgoing_requests": total_outgoing,
        "total_incoming_requests": total_incoming,
        "accepted_outgoing": accepted_outgoing,
        "accepted_incoming": accepted_incoming,
        "pending_incoming": pending_incoming,
        "this_month_matches": this_month_matches,
        "this_month_fees": this_month_fees,
        "total_fees": total_fees,
        "active_listings": active_listings,
        "expired_listings": expired_listings,
        "monthly_matches": monthly_matches,
        "monthly_fees": monthly_fees,
        "region_counts": region_counts,
        "acceptance_rate_outgoing": round(accepted_outgoing / total_outgoing * 100, 1) if total_outgoing > 0 else 0,
        "acceptance_rate_incoming": round(accepted_incoming / total_incoming * 100, 1) if total_incoming > 0 else 0,
    }


