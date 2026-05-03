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


# --- Performance Tests & Monitoring -----------------------------------------
# ============================================================================

@api.get("/performance/health")
async def performance_health():
    """Detaylı sağlık kontrolü — DB bağlantı, koleksiyon sayıları, yanıt süresi."""
    start = time.time()
    checks = {}

    # MongoDB bağlantı testi
    try:
        await db.command("ping")
        checks["mongodb"] = {"status": "ok", "latency_ms": round((time.time() - start) * 1000, 2)}
    except Exception as e:
        checks["mongodb"] = {"status": "error", "detail": str(e)}

    # Koleksiyon sayıları
    t0 = time.time()
    collection_counts = {}
    for coll_name in ["hotels", "availability_listings", "requests", "matches", "inventory", "daily_availability", "pricing_rules", "room_templates"]:
        try:
            count = await db[coll_name].estimated_document_count()
            collection_counts[coll_name] = count
        except Exception:
            collection_counts[coll_name] = -1
    checks["collections"] = {"counts": collection_counts, "query_time_ms": round((time.time() - t0) * 1000, 2)}

    total_time = round((time.time() - start) * 1000, 2)

    return {
        "status": "healthy" if all(c.get("status") != "error" for c in checks.values() if isinstance(c, dict) and "status" in c) else "degraded",
        "total_response_ms": total_time,
        "checks": checks,
        "timestamp": now_utc().isoformat(),
    }


@api.get("/performance/benchmark")
async def performance_benchmark(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """API endpoint performans benchmark'ı."""
    results = {}

    # 1. DB Read testi
    t0 = time.time()
    await db.hotels.find_one({"_id": current_hotel["_id"]})
    results["db_single_read"] = {"time_ms": round((time.time() - t0) * 1000, 2)}

    # 2. DB List testi
    t0 = time.time()
    cursor = db.availability_listings.find({}).limit(50)
    await cursor.to_list(length=50)
    results["db_list_50"] = {"time_ms": round((time.time() - t0) * 1000, 2)}

    # 3. DB Aggregation testi
    t0 = time.time()
    pipeline = [
        {"$group": {"_id": "$region", "count": {"$sum": 1}}},
    ]
    agg_cursor = db.availability_listings.aggregate(pipeline)
    await agg_cursor.to_list(length=100)
    results["db_aggregation"] = {"time_ms": round((time.time() - t0) * 1000, 2)}

    # 4. Complex query testi
    t0 = time.time()
    await db.availability_listings.find({
        "date_end": {"$gte": now_utc()},
        "is_locked": False,
    }).sort("created_at", -1).to_list(length=100)
    results["complex_query"] = {"time_ms": round((time.time() - t0) * 1000, 2)}

    # 5. Write testi (insert & delete)
    t0 = time.time()
    test_id = str(uuid.uuid4())
    await db["perf_test"].insert_one({"_id": test_id, "ts": now_utc()})
    await db["perf_test"].delete_one({"_id": test_id})
    results["db_write_delete"] = {"time_ms": round((time.time() - t0) * 1000, 2)}

    # 6. Inventory query testi
    t0 = time.time()
    await db.daily_availability.find({
        "hotel_id": current_hotel["_id"],
        "date": date.today().isoformat(),
    }).to_list(length=50)
    results["inventory_query"] = {"time_ms": round((time.time() - t0) * 1000, 2)}

    # Toplam
    total_ms = sum(r["time_ms"] for r in results.values())
    grade = "A" if total_ms < 100 else "B" if total_ms < 250 else "C" if total_ms < 500 else "D"

    return {
        "benchmarks": results,
        "total_ms": round(total_ms, 2),
        "grade": grade,
        "grade_description": {
            "A": "Mükemmel (<100ms)",
            "B": "İyi (<250ms)",
            "C": "Orta (<500ms)",
            "D": "İyileştirme gerekli (>500ms)",
        }[grade],
        "timestamp": now_utc().isoformat(),
    }


@api.get("/performance/db-indexes")
async def list_db_indexes(admin: Dict[str, Any] = Depends(get_current_admin)):
    """Mevcut DB indekslerini listele (sadece admin)."""
    indexes = {}
    for coll_name in ["hotels", "availability_listings", "requests", "matches", "inventory", "daily_availability", "pricing_rules"]:
        try:
            idx_list = await db[coll_name].index_information()
            indexes[coll_name] = {name: {"keys": list(info["key"])} for name, info in idx_list.items()}
        except Exception as e:
            indexes[coll_name] = {"error": str(e)}

    return indexes


