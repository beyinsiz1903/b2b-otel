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


# --- Performance Scores ------------------------------------------------------
# =============================================================================

@api.get("/stats/performance-scores")
async def performance_scores(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """Otel performans metrikleri."""
    hotel_id = current_hotel["_id"]
    now = now_utc()
    ninety_days = now - timedelta(days=90)

    # Gelen talepler + eşleşme sayısı paralel.
    incoming, match_count = await asyncio.gather(
        db.requests.find({"to_hotel_id": hotel_id, "created_at": {"$gte": ninety_days}}).to_list(length=1000),
        db.matches.count_documents({
            "$or": [{"hotel_a_id": hotel_id}, {"hotel_b_id": hotel_id}],
            "created_at": {"$gte": ninety_days},
        }),
    )
    total_incoming = len(incoming)
    accepted = sum(1 for r in incoming if r["status"] == "accepted")
    rejected = sum(1 for r in incoming if r["status"] == "rejected")
    alternative_offered = sum(1 for r in incoming if r["status"] in ("alternative_offered",))
    cancelled = sum(1 for r in incoming if r["status"] == "cancelled")
    pending = sum(1 for r in incoming if r["status"] == "pending")

    # Cevap süresi (ortalama)
    response_times = []
    for r in incoming:
        if r["status"] not in ("pending",) and r.get("updated_at") and r.get("created_at"):
            diff = (r["updated_at"] - r["created_at"]).total_seconds() / 3600  # saat
            response_times.append(diff)
    avg_response_hours = round(sum(response_times) / len(response_times), 1) if response_times else 0

    # Onay oranı
    approval_rate = round(accepted / total_incoming * 100, 1) if total_incoming > 0 else 0
    # İptal oranı
    cancellation_rate = round(cancelled / total_incoming * 100, 1) if total_incoming > 0 else 0

    # Skor hesapla (0-100)
    score = 50  # base
    if approval_rate > 70:
        score += 20
    elif approval_rate > 40:
        score += 10
    if avg_response_hours < 2:
        score += 15
    elif avg_response_hours < 6:
        score += 10
    if cancellation_rate < 10:
        score += 15
    elif cancellation_rate < 25:
        score += 5
    score = min(100, max(0, score))

    grade = "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 50 else "D"

    return {
        "score": score,
        "grade": grade,
        "period_days": 90,
        "total_incoming_requests": total_incoming,
        "accepted": accepted,
        "rejected": rejected,
        "alternative_offered": alternative_offered,
        "cancelled": cancelled,
        "pending": pending,
        "approval_rate": approval_rate,
        "cancellation_rate": cancellation_rate,
        "avg_response_hours": avg_response_hours,
        "match_count": match_count,
    }


# =============================================================================
