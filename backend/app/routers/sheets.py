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

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# Optional heavy deps used by some routers — imported lazily inside routes:
# google.oauth2.credentials, googleapiclient.discovery, google_auth_oauthlib.flow,
# google.auth.transport.requests, reportlab.* — left as inside-function imports
# in the original code where applicable. If a route uses them at module level,
# we add the import inside the chunk body.


# --- Google Sheets Integration ---------------------------------------------

def _get_frontend_url() -> str:
    backend_url = os.environ.get("REACT_APP_BACKEND_URL", "")
    # Backend URL'den frontend URL'yi çıkar (aynı domain, farklı port)
    # Ör: https://improvement-guide-2.preview.emergentagent.com
    return backend_url.replace(":8001", "").replace("/api", "").rstrip("/")

def _get_redirect_uri() -> str:
    backend_url = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
    base = backend_url.rstrip("/")
    if not base.endswith("/api"):
        base = base + "/api"
    return f"{base}/oauth/sheets/callback"


def _build_flow(client_id: str, client_secret: str) -> Flow:
    client_config = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [_get_redirect_uri()],
        }
    }
    return Flow.from_client_config(
        client_config,
        scopes=SHEETS_SCOPES,
        redirect_uri=_get_redirect_uri(),
    )


async def _get_sheets_credentials(hotel_id: str) -> Optional[Credentials]:
    """Token'ı DB'den al, gerekirse yenile."""
    token_doc = await db.sheets_tokens.find_one({"hotel_id": hotel_id})
    if not token_doc:
        return None
    config_doc = await db.sheets_config.find_one({"hotel_id": hotel_id})
    if not config_doc:
        return None

    expires_at = token_doc.get("expires_at")
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    creds = Credentials(
        token=token_doc["access_token"],
        refresh_token=token_doc.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=config_doc["client_id"],
        client_secret=config_doc["client_secret"],
        scopes=SHEETS_SCOPES,
    )

    # Token süresi dolmuşsa yenile
    if expires_at and datetime.now(timezone.utc) >= expires_at:
        try:
            await asyncio.to_thread(creds.refresh, GoogleAuthRequest())
            new_expires = datetime.now(timezone.utc) + timedelta(seconds=3600)
            await db.sheets_tokens.update_one(
                {"hotel_id": hotel_id},
                {"$set": {"access_token": creds.token, "expires_at": new_expires}},
            )
        except Exception:
            return None

    return creds


async def _get_or_create_spreadsheet(creds: Credentials, hotel_name: str, hotel_id: str) -> str:
    """Config'deki spreadsheet_id'yi döndür, yoksa yeni oluştur."""
    config = await db.sheets_config.find_one({"hotel_id": hotel_id})
    if config and config.get("spreadsheet_id"):
        return config["spreadsheet_id"]

    # Yeni spreadsheet oluştur
    def create_sheet():
        service = build("sheets", "v4", credentials=creds)
        body = {
            "properties": {"title": f"CapX – {hotel_name}"},
            "sheets": [
                {"properties": {"title": "Oda Tipleri"}},
                {"properties": {"title": "Müsaitlikler"}},
                {"properties": {"title": "Eşleşmeler"}},
            ],
        }
        result = service.spreadsheets().create(body=body, fields="spreadsheetId").execute()
        return result["spreadsheetId"]

    spreadsheet_id = await asyncio.to_thread(create_sheet)
    await db.sheets_config.update_one(
        {"hotel_id": hotel_id},
        {"$set": {"spreadsheet_id": spreadsheet_id}},
    )
    return spreadsheet_id


async def _write_sheet(creds: Credentials, spreadsheet_id: str, sheet_name: str, rows: List[List[Any]]) -> None:
    """Sayfayı tamamen sil ve yeniden yaz."""
    def do_write():
        service = build("sheets", "v4", credentials=creds)
        # Önce sayfayı temizle
        service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A1:Z10000",
        ).execute()
        if rows:
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption="USER_ENTERED",
                body={"values": rows},
            ).execute()
    await asyncio.to_thread(do_write)


# ── OAuth Endpoints ─────────────────────────────────────────────────────────

@api.get("/oauth/sheets/login")
async def sheets_oauth_login(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    config = await db.sheets_config.find_one({"hotel_id": current_hotel["_id"]})
    if not config or not config.get("client_id") or not config.get("client_secret"):
        raise HTTPException(status_code=400, detail="Önce Google Client ID ve Client Secret kaydedin.")

    flow = _build_flow(config["client_id"], config["client_secret"])
    auth_url, state = flow.authorization_url(access_type="offline", prompt="consent")

    # State → hotel_id eşlemesini geçici kaydet (10 dk TTL)
    await db.oauth_states.insert_one({
        "_id": state,
        "hotel_id": current_hotel["_id"],
        "created_at": now_utc(),
    })
    return {"auth_url": auth_url}


@api.get("/oauth/sheets/callback")
async def sheets_oauth_callback(code: str, state: str):
    state_doc = await db.oauth_states.find_one({"_id": state})
    if not state_doc:
        return _oauth_result_page("❌ Hata", "Geçersiz ya da süresi dolmuş OAuth isteği. Lütfen tekrar bağlanmayı deneyin.", success=False)

    hotel_id = state_doc["hotel_id"]
    config = await db.sheets_config.find_one({"hotel_id": hotel_id})
    if not config:
        return _oauth_result_page("❌ Hata", "Sheets yapılandırması bulunamadı.", success=False)

    flow = _build_flow(config["client_id"], config["client_secret"])

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            await asyncio.to_thread(flow.fetch_token, code=code)
    except Exception as e:
        return _oauth_result_page("❌ Token Hatası", f"Google'dan token alınamadı: {str(e)}", success=False)

    creds = flow.credentials

    # Google hesap e-postasını al
    google_email = None
    try:
        def get_email():
            service = build("oauth2", "v2", credentials=creds)
            return service.userinfo().get().execute().get("email")
        google_email = await asyncio.to_thread(get_email)
    except Exception:
        pass

    # Token kaydet
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=3600)
    await db.sheets_tokens.replace_one(
        {"hotel_id": hotel_id},
        {
            "hotel_id": hotel_id,
            "access_token": creds.token,
            "refresh_token": creds.refresh_token,
            "expires_at": expires_at,
            "google_email": google_email,
            "connected_at": now_utc(),
        },
        upsert=True,
    )
    await db.sheets_config.update_one(
        {"hotel_id": hotel_id},
        {"$set": {"google_email": google_email, "connected_at": now_utc()}},
    )
    await db.oauth_states.delete_one({"_id": state})
    await log_activity(hotel_id, "sheets_connect", "integration", hotel_id, {"email": google_email})

    return _oauth_result_page(
        "✅ Bağlantı Kuruldu!",
        f"Google Sheets hesabınız ({google_email or 'bilinmiyor'}) başarıyla bağlandı.<br>Bu sekmeyi kapatıp platforma dönebilirsiniz.",
        success=True,
    )


def _oauth_result_page(title: str, message: str, success: bool):
    """OAuth sonuç sayfası — sekmeyi otomatik kapatır."""
    from fastapi.responses import HTMLResponse
    color = "#166534" if success else "#991b1b"
    bg = "#dcfce7" if success else "#fee2e2"
    icon = "✅" if success else "❌"
    html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <title>{"Bağlantı Başarılı" if success else "Bağlantı Hatası"}</title>
  <style>
    body{{margin:0;font-family:system-ui,-apple-system,sans-serif;background:#f0f4f8;
         display:flex;align-items:center;justify-content:center;min-height:100vh;}}
    .card{{background:#fff;border-radius:1rem;padding:2.5rem 3rem;text-align:center;
           box-shadow:0 4px 24px rgba(0,0,0,.1);max-width:480px;width:90%;}}
    .icon{{font-size:3.5rem;margin-bottom:1rem;}}
    h1{{color:{color};font-size:1.4rem;margin:0 0 .75rem;}}
    p{{color:#4a5568;font-size:.95rem;line-height:1.6;margin:0 0 1.5rem;}}
    .btn{{background:#2e6b57;color:#fff;border:none;border-radius:.6rem;
          padding:.7rem 1.5rem;font-size:.95rem;cursor:pointer;font-family:inherit;}}
    .note{{font-size:.78rem;color:#9ca3af;margin-top:1rem;}}
    .timer{{font-size:.85rem;color:{color};font-weight:600;margin-bottom:1rem;}}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">{icon}</div>
    <h1>{title}</h1>
    <p>{message}</p>
    {"<div class='timer' id='t'>3 saniye sonra kapanıyor...</div>" if success else ""}
    <button class="btn" onclick="window.close()">Bu Sekmeyi Kapat</button>
    <p class="note">Sekme kapanmazsa manuel olarak kapatabilirsiniz.</p>
  </div>
  {"<script>let s=3;const el=document.getElementById('t');const iv=setInterval(()=>{{s--;if(el)el.textContent=s+' saniye sonra kapanıyor...';if(s<=0){{clearInterval(iv);window.close();}}}},1000);</script>" if success else ""}
</body>
</html>"""
    return HTMLResponse(content=html)


# ── Sheets Config Endpoints ─────────────────────────────────────────────────

@api.post("/sheets/config")
async def save_sheets_config(payload: SheetsConfigSave, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    await db.sheets_config.replace_one(
        {"hotel_id": current_hotel["_id"]},
        {
            "hotel_id": current_hotel["_id"],
            "client_id": payload.client_id,
            "client_secret": payload.client_secret,
            "spreadsheet_id": payload.spreadsheet_id or None,
            "updated_at": now_utc(),
        },
        upsert=True,
    )
    return {"message": "Yapılandırma kaydedildi. Şimdi Google ile bağlanabilirsiniz."}


@api.get("/sheets/config")
async def get_sheets_config(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    config = await db.sheets_config.find_one({"hotel_id": current_hotel["_id"]})
    token = await db.sheets_tokens.find_one({"hotel_id": current_hotel["_id"]})
    connected = token is not None
    if not config:
        return {
            "hotel_id": current_hotel["_id"],
            "client_id": None,
            "spreadsheet_id": None,
            "connected": False,
            "google_email": None,
            "connected_at": None,
        }
    # client_id'yi maskele
    cid = config.get("client_id", "")
    masked = cid[:12] + "..." if len(cid) > 12 else cid
    return {
        "hotel_id": current_hotel["_id"],
        "client_id": masked,
        "client_id_full": cid,   # form pre-fill için
        "client_secret_saved": bool(config.get("client_secret")),
        "spreadsheet_id": config.get("spreadsheet_id"),
        "connected": connected,
        "google_email": token.get("google_email") if token else None,
        "connected_at": token.get("connected_at").isoformat() if token and token.get("connected_at") else None,
    }


@api.delete("/sheets/disconnect")
async def sheets_disconnect(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    await db.sheets_tokens.delete_one({"hotel_id": current_hotel["_id"]})
    await log_activity(current_hotel["_id"], "sheets_disconnect", "integration", current_hotel["_id"], {})
    return {"message": "Google Sheets bağlantısı kesildi."}


# ── Sync Endpoints ──────────────────────────────────────────────────────────

@api.post("/sheets/sync/templates")
async def sync_templates_to_sheets(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    creds = await _get_sheets_credentials(current_hotel["_id"])
    if not creds:
        raise HTTPException(status_code=400, detail="Google Sheets bağlantısı yok. Önce bağlanın.")

    spreadsheet_id = await _get_or_create_spreadsheet(creds, current_hotel["name"], current_hotel["_id"])

    cursor = db.room_templates.find({"hotel_id": current_hotel["_id"]})
    templates = await cursor.to_list(length=500)

    headers = ["Şablon Adı", "Oda Tipi", "Bölge", "Mikro Lokasyon", "Konsept",
               "Kapasite", "Kişi Sayısı", "Kahvaltı Dahil", "Min. Konaklama (gece)",
               "Fiyat Önerisi (TL)", "Özellikler", "Kısıtlamalar", "Son Güncelleme"]
    rows = [headers]
    for t in templates:
        rows.append([
            t.get("name", ""),
            t.get("room_type", ""),
            t.get("region", ""),
            t.get("micro_location", ""),
            t.get("concept", ""),
            t.get("capacity_label", ""),
            t.get("pax", ""),
            "Evet" if t.get("breakfast_included") else "Hayır",
            t.get("min_nights", 1),
            t.get("price_suggestion", ""),
            ", ".join(t.get("features") or []),
            ", ".join(t.get("guest_restrictions") or []),
            t.get("updated_at", now_utc()).strftime("%d.%m.%Y %H:%M") if t.get("updated_at") else "",
        ])

    await _write_sheet(creds, spreadsheet_id, "Oda Tipleri", rows)
    await log_activity(current_hotel["_id"], "sheets_sync", "room_templates", current_hotel["_id"],
                       {"count": len(templates), "spreadsheet_id": spreadsheet_id})
    return {
        "message": f"{len(templates)} oda tipi senkronize edildi.",
        "spreadsheet_id": spreadsheet_id,
        "spreadsheet_url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}",
    }


@api.post("/sheets/sync/listings")
async def sync_listings_to_sheets(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    creds = await _get_sheets_credentials(current_hotel["_id"])
    if not creds:
        raise HTTPException(status_code=400, detail="Google Sheets bağlantısı yok. Önce bağlanın.")

    spreadsheet_id = await _get_or_create_spreadsheet(creds, current_hotel["name"], current_hotel["_id"])

    cursor = db.availability_listings.find({"hotel_id": current_hotel["_id"]}).sort("date_start", -1)
    listings = await cursor.to_list(length=500)

    headers = ["İlan ID", "Oda Tipi", "Konsept", "Bölge", "Mikro Lokasyon",
               "Kapasite", "Kişi", "Başlangıç", "Bitiş", "Gece Sayısı",
               "Fiyat (TL/gece)", "Kahvaltı", "Min. Gece", "Durum", "Kilitli",
               "Özellikler", "Kısıtlamalar", "Oluşturma Tarihi"]
    rows = [headers]
    for l in listings:
        date_start = l.get("date_start")
        date_end = l.get("date_end")
        rows.append([
            l.get("_id", "")[:8],
            l.get("room_type", ""),
            l.get("concept", ""),
            l.get("region", ""),
            l.get("micro_location", ""),
            l.get("capacity_label", ""),
            l.get("pax", ""),
            date_start.strftime("%d.%m.%Y") if date_start else "",
            date_end.strftime("%d.%m.%Y") if date_end else "",
            l.get("nights", ""),
            l.get("price_min", ""),
            "Evet" if l.get("breakfast_included") else "Hayır",
            l.get("min_nights", 1),
            l.get("availability_status", ""),
            "Evet" if l.get("is_locked") else "Hayır",
            ", ".join(l.get("features") or []),
            ", ".join(l.get("guest_restrictions") or []),
            l.get("created_at", now_utc()).strftime("%d.%m.%Y") if l.get("created_at") else "",
        ])

    await _write_sheet(creds, spreadsheet_id, "Müsaitlikler", rows)
    await log_activity(current_hotel["_id"], "sheets_sync", "listings", current_hotel["_id"],
                       {"count": len(listings), "spreadsheet_id": spreadsheet_id})
    return {
        "message": f"{len(listings)} müsaitlik ilanı senkronize edildi.",
        "spreadsheet_id": spreadsheet_id,
        "spreadsheet_url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}",
    }


@api.post("/sheets/sync/matches")
async def sync_matches_to_sheets(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    creds = await _get_sheets_credentials(current_hotel["_id"])
    if not creds:
        raise HTTPException(status_code=400, detail="Google Sheets bağlantısı yok. Önce bağlanın.")

    spreadsheet_id = await _get_or_create_spreadsheet(creds, current_hotel["name"], current_hotel["_id"])

    cursor = db.matches.find({"$or": [{"hotel_a_id": current_hotel["_id"]}, {"hotel_b_id": current_hotel["_id"]}]}).sort("accepted_at", -1)
    matches = await cursor.to_list(length=500)

    headers = ["Referans Kodu", "Kabul Tarihi", "Hizmet Bedeli (TL)", "Ödeme Durumu", "Oluşturma Tarihi"]
    rows = [headers]
    for m in matches:
        accepted = m.get("accepted_at")
        created = m.get("created_at")
        rows.append([
            m.get("reference_code", ""),
            accepted.strftime("%d.%m.%Y %H:%M") if accepted else "",
            m.get("fee_amount", ""),
            m.get("fee_status", ""),
            created.strftime("%d.%m.%Y") if created else "",
        ])

    await _write_sheet(creds, spreadsheet_id, "Eşleşmeler", rows)
    await log_activity(current_hotel["_id"], "sheets_sync", "matches", current_hotel["_id"],
                       {"count": len(matches), "spreadsheet_id": spreadsheet_id})
    return {
        "message": f"{len(matches)} eşleşme senkronize edildi.",
        "spreadsheet_id": spreadsheet_id,
        "spreadsheet_url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}",
    }


@api.post("/sheets/sync/all")
async def sync_all_to_sheets(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    r1 = await sync_templates_to_sheets(current_hotel)
    r2 = await sync_listings_to_sheets(current_hotel)
    r3 = await sync_matches_to_sheets(current_hotel)
    return {
        "message": "Tüm veriler senkronize edildi.",
        "spreadsheet_url": r1["spreadsheet_url"],
        "details": {"templates": r1["message"], "listings": r2["message"], "matches": r3["message"]},
    }


