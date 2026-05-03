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


# --- WebSocket Real-time Notifications ----------------------------------------
# =============================================================================

_ws_router = APIRouter()


@_ws_router.websocket("/api/ws/notifications")
async def websocket_notifications(websocket: WebSocket, token: Optional[str] = Query(None)):
    """Gerçek zamanlı bildirim WebSocket endpoint'i.
    Bağlantı: ws://host/api/ws/notifications?token=JWT_TOKEN
    """
    if not token:
        await websocket.close(code=4001, reason="Token gerekli")
        return

    # Token doğrulama
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        hotel_id = payload.get("sub")
        if not hotel_id:
            await websocket.close(code=4001, reason="Geçersiz token")
            return
    except JWTError:
        await websocket.close(code=4001, reason="Geçersiz veya süresi dolmuş token")
        return

    # Hotel var mı kontrol
    hotel = await db.hotels.find_one({"_id": hotel_id})
    if not hotel:
        await websocket.close(code=4001, reason="Otel bulunamadı")
        return

    # Bağlantıyı kaydet
    await ws_manager.connect(hotel_id, websocket)
    await log_activity(hotel_id, "ws_connect", "websocket", hotel_id, {})

    try:
        # Bağlantı onay mesajı gönder
        await websocket.send_json({
            "type": "connected",
            "data": {
                "hotel_id": hotel_id,
                "hotel_name": hotel.get("name", ""),
                "message": "Gerçek zamanlı bildirimler aktif",
                "online_count": ws_manager.get_online_count(),
            }
        })

        # Okunmamış bildirim sayısını gönder
        unread = await db.notifications.count_documents({"hotel_id": hotel_id, "is_read": False})
        await websocket.send_json({
            "type": "unread_count",
            "data": {"count": unread}
        })

        # Bağlantıyı canlı tut - client mesajlarını dinle
        while True:
            try:
                data = await websocket.receive_json()
                msg_type = data.get("type", "")

                if msg_type == "ping":
                    await websocket.send_json({"type": "pong", "data": {"timestamp": now_utc().isoformat()}})

                elif msg_type == "mark_read":
                    notif_id = data.get("data", {}).get("notification_id")
                    if notif_id:
                        await db.notifications.update_one(
                            {"_id": notif_id, "hotel_id": hotel_id},
                            {"$set": {"is_read": True}}
                        )
                        unread = await db.notifications.count_documents({"hotel_id": hotel_id, "is_read": False})
                        await websocket.send_json({"type": "unread_count", "data": {"count": unread}})

                elif msg_type == "mark_all_read":
                    await db.notifications.update_many(
                        {"hotel_id": hotel_id, "is_read": False},
                        {"$set": {"is_read": True}}
                    )
                    await websocket.send_json({"type": "unread_count", "data": {"count": 0}})

                elif msg_type == "get_unread_count":
                    unread = await db.notifications.count_documents({"hotel_id": hotel_id, "is_read": False})
                    await websocket.send_json({"type": "unread_count", "data": {"count": unread}})

            except WebSocketDisconnect:
                break
            except Exception:
                # JSON parse hatası vb. - bağlantıyı kapat
                break

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        ws_manager.disconnect(hotel_id, websocket)


# --- WebSocket Status (Admin) ------------------------------------------------

@_ws_router.get("/api/ws/status")
async def ws_status(admin: Dict[str, Any] = Depends(get_current_admin)):
    """Admin: WebSocket bağlantı durumu."""
    online_hotels = ws_manager.get_online_hotels()
    hotel_names = {}
    if online_hotels:
        cursor = db.hotels.find({"_id": {"$in": online_hotels}}, {"_id": 1, "name": 1})
        async for h in cursor:
            hotel_names[h["_id"]] = h["name"]

    return {
        "online_connections": ws_manager.get_online_count(),
        "online_hotels": [
            {"hotel_id": hid, "name": hotel_names.get(hid, "Bilinmiyor")}
            for hid in online_hotels
        ],
    }


# =============================================================================
