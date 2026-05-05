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
    PMSCallbackUpdate, PMSConnectResponse, PMSOutboundEventPublic,
    PMSReservationEvent, PMSStatusResponse,
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


# --- PMS Integration (Syroce / generic PMS) — /integrations/v1/pms/* ---------
# =============================================================================
# CapX'in dış PMS sistemleriyle (Syroce vb.) konuşmasını sağlar.
# - Otel admin'i CapX'te bir API key üretir → PMS'e yapıştırır
# - PMS, CapX'e müsaitlik snapshot'ı push'lar; CapX otomatik availability_listings yaratır/günceller
# - PMS, rezervasyon olaylarını HMAC imzalı webhook ile bildirir
# - Eşleşme oluştuğunda CapX, PMS'e webhook gönderebilir (callback URL otelin saklar)
#
# Auth modeli:
#   • Otel admin'i (JWT)  → /connect, /status, /disconnect
#   • PMS sistemi (Bearer API key) → /availability/sync, /reservation/event
#   • Reservation event ayrıca X-CapX-Signature header'ı ile HMAC-SHA256 imzalı
# =============================================================================
import hmac as _pms_hmac
import hashlib as _pms_hashlib
import secrets as _pms_secrets


class PMSConnectResponse(BaseModel):
    api_key: str             # Sadece bu çağrıda dönülür; sonra hash'li saklanır
    webhook_secret: str      # PMS bunu kullanarak event payload'ını imzalar
    webhook_url: str         # PMS'in çağıracağı URL
    sync_url: str            # PMS'in availability push'layacağı URL


class PMSStatusResponse(BaseModel):
    connected: bool
    api_key_last4: Optional[str] = None
    connected_at: Optional[datetime] = None
    last_sync_at: Optional[datetime] = None
    last_event_at: Optional[datetime] = None
    callback_url: Optional[str] = None
    sync_count: int = 0
    event_count: int = 0


class PMSCallbackUpdate(BaseModel):
    callback_url: Optional[str] = Field(default=None, max_length=512)


class PMSAvailabilityRoom(BaseModel):
    """Tek bir oda tipi/satış birimi için boş kapasite."""
    room_type: str = Field(..., min_length=1, max_length=64)
    pax: int = Field(..., ge=1, le=2000)
    price_min: Optional[float] = Field(default=None, ge=0)
    price_max: Optional[float] = Field(default=None, ge=0)
    currency: str = Field(default="TRY", max_length=8)
    notes: Optional[str] = Field(default=None, max_length=300)


class PMSAvailabilitySync(BaseModel):
    """PMS'ten gelen müsaitlik snapshot'ı."""
    date_start: datetime
    date_end: datetime
    region: Optional[str] = Field(default=None, max_length=32)
    rooms: List[PMSAvailabilityRoom] = Field(..., min_length=1, max_length=50)
    auto_publish: bool = True
    external_ref: Optional[str] = Field(default=None, max_length=128)  # PMS'in kendi referansı


class PMSReservationEvent(BaseModel):
    """PMS'ten gelen rezervasyon olayı (yeni rez / iptal / değişiklik)."""
    event_type: str = Field(..., pattern=r"^(reservation\.created|reservation\.updated|reservation\.cancelled)$")
    external_id: str = Field(..., min_length=1, max_length=128)
    room_type: Optional[str] = Field(default=None, max_length=64)
    pax: Optional[int] = Field(default=None, ge=1, le=2000)
    date_start: Optional[datetime] = None
    date_end: Optional[datetime] = None
    occurred_at: datetime
    payload: Optional[Dict[str, Any]] = None  # Ham PMS payload'ı (debug/audit)


def _pms_hash_key(plain: str) -> str:
    return _pms_hashlib.sha256(plain.encode("utf-8")).hexdigest()


def _pms_constant_time_eq(a: str, b: str) -> bool:
    return _pms_hmac.compare_digest((a or "").encode("utf-8"), (b or "").encode("utf-8"))


async def _pms_auth_by_api_key(authorization: Optional[str]) -> Dict[str, Any]:
    """PMS sistemi için Bearer API key doğrulaması.

    Anahtar veritabanında SHA-256 hash olarak tutulur; ham anahtar yalnızca
    /connect çağrısının dönüşünde gösterilir.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Bearer token gerekli")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Geçersiz token")
    token_hash = _pms_hash_key(token)
    integ = await db.pms_integrations.find_one({"api_key_hash": token_hash, "status": "active"})
    if not integ:
        raise HTTPException(status_code=401, detail="Geçersiz veya pasif API anahtarı")
    return integ


def _pms_verify_hmac(secret: str, body_bytes: bytes, signature_header: Optional[str]) -> None:
    """X-CapX-Signature: sha256=<hex> formatını doğrula."""
    if not signature_header:
        raise HTTPException(status_code=401, detail="X-CapX-Signature header eksik")
    sig = signature_header.strip()
    if sig.startswith("sha256="):
        sig = sig[len("sha256="):]
    expected = _pms_hmac.new(secret.encode("utf-8"), body_bytes, _pms_hashlib.sha256).hexdigest()
    if not _pms_constant_time_eq(expected, sig):
        raise HTTPException(status_code=401, detail="İmza doğrulanamadı")


@api.post("/integrations/v1/pms/connect", response_model=PMSConnectResponse)
@limiter.limit("10/minute")
async def pms_connect(request: Request, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """Otel için PMS bağlantısı oluşturur veya anahtarı yeniden üretir.

    Eski anahtar derhal geçersiz olur (rotation senaryosu). Ham anahtar bir
    daha gösterilmez — otelin PMS'inde güvenli yere kaydetmesi gerekir.
    """
    api_key = "capx_pk_" + _pms_secrets.token_urlsafe(32)
    webhook_secret = "capx_ws_" + _pms_secrets.token_urlsafe(32)
    now = now_utc()
    base = (os.environ.get("PUBLIC_BASE_URL") or "").rstrip("/")
    sync_url = f"{base}/api/integrations/v1/pms/availability/sync"
    webhook_url = f"{base}/api/integrations/v1/pms/reservation/event"

    await db.pms_integrations.update_one(
        {"hotel_id": current_hotel["_id"]},
        {
            "$set": {
                "hotel_id": current_hotel["_id"],
                "api_key_hash": _pms_hash_key(api_key),
                "api_key_last4": api_key[-4:],
                "webhook_secret": webhook_secret,  # PMS imzalama için
                "status": "active",
                "rotated_at": now,
                "updated_at": now,
            },
            "$setOnInsert": {
                "connected_at": now,
                "sync_count": 0,
                "event_count": 0,
                "callback_url": None,
                "last_sync_at": None,
                "last_event_at": None,
            },
        },
        upsert=True,
    )
    await log_activity(current_hotel["_id"], "pms_connect", "integration", current_hotel["_id"], {"rotated": True})
    return PMSConnectResponse(
        api_key=api_key,
        webhook_secret=webhook_secret,
        webhook_url=webhook_url,
        sync_url=sync_url,
    )


@api.get("/integrations/v1/pms/status", response_model=PMSStatusResponse)
async def pms_status(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    integ = await db.pms_integrations.find_one({"hotel_id": current_hotel["_id"]})
    if not integ or integ.get("status") != "active":
        return PMSStatusResponse(connected=False)
    return PMSStatusResponse(
        connected=True,
        api_key_last4=integ.get("api_key_last4"),
        connected_at=integ.get("connected_at"),
        last_sync_at=integ.get("last_sync_at"),
        last_event_at=integ.get("last_event_at"),
        callback_url=integ.get("callback_url"),
        sync_count=integ.get("sync_count", 0),
        event_count=integ.get("event_count", 0),
    )


@api.put("/integrations/v1/pms/callback")
async def pms_set_callback(payload: PMSCallbackUpdate, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """CapX → PMS yönünde olay bildirimi için callback URL'i ayarla.

    SSRF koruması: private/loopback/link-local IP'ler ve metadata endpoint'leri
    reddedilir. Dev için `PMS_ALLOW_LOOPBACK_CALLBACK=1` env değişkeni
    loopback/private IP'lere izin verir.
    """
    url = (payload.callback_url or "").strip() or None
    if url:
        from app.services.pms_outbound import validate_callback_url as _validate_cb
        ok, reason = _validate_cb(url)
        if not ok:
            raise HTTPException(status_code=400, detail=reason)
    await db.pms_integrations.update_one(
        {"hotel_id": current_hotel["_id"]},
        {"$set": {"callback_url": url, "updated_at": now_utc()}},
    )
    return {"callback_url": url}


@api.get("/integrations/v1/pms/events", response_model=List[PMSOutboundEventPublic])
async def pms_list_outbound_events(
    limit: int = Query(default=50, ge=1, le=200),
    current_hotel: Dict[str, Any] = Depends(get_current_hotel),
):
    """CapX → PMS yönünde gönderilen webhook olaylarının listesi (son N)."""
    from app.services.pms_outbound import list_events as _pms_list_events
    items = await _pms_list_events(current_hotel["_id"], limit=limit)
    return [PMSOutboundEventPublic(**it) for it in items]


@api.post("/integrations/v1/pms/events/{event_id}/retry")
async def pms_retry_outbound_event(
    event_id: str,
    current_hotel: Dict[str, Any] = Depends(get_current_hotel),
):
    """Başarısız (veya beklemede kalmış) bir CapX → PMS olayını yeniden gönder."""
    from app.services.pms_outbound import retry_event as _pms_retry_event
    try:
        return await _pms_retry_event(event_id, current_hotel["_id"])
    except LookupError as e:
        code = str(e)
        if code == "event_not_found":
            raise HTTPException(status_code=404, detail="Olay bulunamadı")
        if code == "pms_disconnected":
            raise HTTPException(status_code=409, detail="PMS bağlantısı veya callback URL tanımlı değil")
        raise HTTPException(status_code=400, detail=code)


@api.post("/integrations/v1/pms/disconnect")
async def pms_disconnect(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    await db.pms_integrations.update_one(
        {"hotel_id": current_hotel["_id"]},
        {"$set": {"status": "revoked", "revoked_at": now_utc(), "updated_at": now_utc()}},
    )
    await log_activity(current_hotel["_id"], "pms_disconnect", "integration", current_hotel["_id"], {})
    return {"status": "revoked"}


def _pms_tenant_rate_key(request: Request) -> str:
    """Per-tenant rate limit key: API key SHA-256 ilk 16 hex.

    PMS endpoint'leri Bearer api_key ile auth olur; aynı key'in farklı IP'lerden
    paralel çağrılarını tek tenant olarak sayalım diye key_func'u override ediyoruz.
    Auth yoksa IP'ye düşer (auth dependency zaten 401 atacak).
    """
    auth = request.headers.get("authorization", "") or ""
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            return "pms:" + hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
    from slowapi.util import get_remote_address
    return get_remote_address(request)


@api.post("/integrations/v1/pms/availability/sync")
@limiter.limit("10/minute", key_func=_pms_tenant_rate_key)
async def pms_availability_sync(
    request: Request,
    payload: PMSAvailabilitySync,
    authorization: Optional[str] = Header(default=None),
):
    """PMS → CapX: müsaitlik snapshot'ı push'la.

    `auto_publish=True` ise her oda tipi için aktif `availability_listings` kaydı
    upsert edilir (PMS dış referansı `external_ref` üzerinden). Aksi halde sadece
    snapshot saklanır; otel admin'i daha sonra "yayınla"yabilir.
    """
    integ = await _pms_auth_by_api_key(authorization)
    hotel_id = integ["hotel_id"]
    hotel = await db.hotels.find_one({"_id": hotel_id})
    if not hotel:
        raise HTTPException(status_code=404, detail="Otel bulunamadı")

    if payload.date_end <= payload.date_start:
        raise HTTPException(status_code=400, detail="date_end > date_start olmalı")

    region = payload.region or hotel.get("region") or "Sapanca"
    now = now_utc()

    snapshot_id = str(uuid.uuid4())
    await db.pms_availability_snapshots.insert_one({
        "_id": snapshot_id,
        "hotel_id": hotel_id,
        "external_ref": payload.external_ref,
        "date_start": payload.date_start,
        "date_end": payload.date_end,
        "region": region,
        "rooms": [r.model_dump() for r in payload.rooms],
        "auto_published": False,
        "received_at": now,
    })

    published_listings: List[str] = []
    if payload.auto_publish:
        for room in payload.rooms:
            # PMS dış referansı + room_type ile idempotent upsert
            ext_key = f"{payload.external_ref or snapshot_id}:{room.room_type}"
            listing_doc = {
                "hotel_id": hotel_id,
                "region": region,
                "room_type": room.room_type,
                "date_start": payload.date_start,
                "date_end": payload.date_end,
                "pax": room.pax,
                "price_min": room.price_min,
                "price_max": room.price_max,
                "currency": room.currency,
                "notes": (room.notes or "")[:300],
                "is_locked": False,
                "lock_request_id": None,
                "source": "pms",
                "pms_external_ref": ext_key,
                "updated_at": now,
            }
            # Atomik upsert — paralel iki sync race'inde unique index DuplicateKeyError'a düşmez
            # çünkü update_one(upsert=True) tek operasyon olarak çalışır.
            res = await db.availability_listings.find_one_and_update(
                {"hotel_id": hotel_id, "pms_external_ref": ext_key},
                {
                    "$set": listing_doc,
                    "$setOnInsert": {
                        "_id": str(uuid.uuid4()),
                        "created_at": now,
                        "availability_status": "open",
                        "allow_cross_region": False,
                    },
                },
                upsert=True,
                return_document=True,  # pymongo: ReturnDocument.AFTER
            )
            if res:
                published_listings.append(res["_id"])

        await db.pms_availability_snapshots.update_one(
            {"_id": snapshot_id},
            {"$set": {"auto_published": True, "published_listing_ids": published_listings}},
        )

    await db.pms_integrations.update_one(
        {"hotel_id": hotel_id},
        {"$set": {"last_sync_at": now}, "$inc": {"sync_count": 1}},
    )
    return {
        "snapshot_id": snapshot_id,
        "published_listing_ids": published_listings,
        "auto_published": payload.auto_publish,
    }


@api.post("/integrations/v1/pms/reservation/event")
@limiter.limit("50/second", key_func=_pms_tenant_rate_key)
async def pms_reservation_event(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_capx_signature: Optional[str] = Header(default=None, alias="X-CapX-Signature"),
    x_capx_event_id: Optional[str] = Header(default=None, alias="X-CapX-Event-Id"),
):
    """PMS → CapX: HMAC-SHA256 imzalı rezervasyon olay webhook'u.

    İdempotent: aynı `X-CapX-Event-Id` ile gelen tekrarlar yutulur.
    """
    integ = await _pms_auth_by_api_key(authorization)
    body_bytes = await request.body()
    _pms_verify_hmac(integ["webhook_secret"], body_bytes, x_capx_signature)

    try:
        body_json = json.loads(body_bytes.decode("utf-8"))
        event = PMSReservationEvent(**body_json)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Geçersiz payload: {e}")

    hotel_id = integ["hotel_id"]
    event_id = (x_capx_event_id or "").strip() or str(uuid.uuid4())

    # İdempotent kayıt — duplicate gelirse 200 döner ama yeni iş yapılmaz
    try:
        await db.pms_reservation_events.insert_one({
            "_id": event_id,
            "hotel_id": hotel_id,
            "event_type": event.event_type,
            "external_id": event.external_id,
            "room_type": event.room_type,
            "pax": event.pax,
            "date_start": event.date_start,
            "date_end": event.date_end,
            "occurred_at": event.occurred_at,
            "payload": event.payload,
            "received_at": now_utc(),
        })
        is_new = True
    except DuplicateKeyError:
        is_new = False

    if is_new:
        await db.pms_integrations.update_one(
            {"hotel_id": hotel_id},
            {"$set": {"last_event_at": now_utc()}, "$inc": {"event_count": 1}},
        )
        # İptal olayında: o PMS dış referansına bağlı aktif ilanları (varsa) kapat
        if event.event_type == "reservation.cancelled" and event.external_id:
            await db.availability_listings.update_many(
                {"hotel_id": hotel_id, "pms_external_ref": {"$regex": f"^{event.external_id}:"}, "is_locked": False},
                {"$set": {"availability_status": "closed_by_pms", "updated_at": now_utc()}},
            )

    return {"received": True, "event_id": event_id, "duplicate": not is_new}


@api.get("/integrations/v1/pms/recent")
async def pms_recent_activity(
    limit: int = 20,
    current_hotel: Dict[str, Any] = Depends(get_current_hotel),
):
    """Otel admin paneli için son sync + event listesi (debug)."""
    limit = max(1, min(limit, 100))
    snaps = await db.pms_availability_snapshots.find({"hotel_id": current_hotel["_id"]}).sort("received_at", -1).limit(limit).to_list(length=limit)
    events = await db.pms_reservation_events.find({"hotel_id": current_hotel["_id"]}).sort("received_at", -1).limit(limit).to_list(length=limit)
    for d in snaps + events:
        d.pop("_id", None) if False else None  # _id bilgisini koru
    return {"snapshots": snaps, "events": events}


# Healthcheck / root

@api.get("/")
async def root() -> Dict[str, str]:
    return {"message": "CapX Multi-Region API v4"}


# app-level wiring (CORS, include_router, startup/shutdown) moved to app/main.py
