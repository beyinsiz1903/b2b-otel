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


# --- Auth endpoints ---------------------------------------------------------

@api.post("/auth/register-upload")
@limiter.limit("10/minute")
async def register_upload(request: Request, file: UploadFile = File(...)):
    """Kayıt sırasında belge yükleme (auth gerektirmez)."""
    allowed = {"application/pdf", "image/jpeg", "image/png", "image/webp"}
    mime = file.content_type or ""
    if mime not in allowed:
        raise HTTPException(status_code=400, detail="Sadece PDF, JPG, PNG veya WEBP yüklenebilir.")
    contents = await file.read()
    if len(contents) > 20 * 1024 * 1024:  # 20 MB
        raise HTTPException(status_code=400, detail="Dosya 20 MB'dan küçük olmalıdır.")
    import mimetypes as _mt
    ext = Path(file.filename or "doc.pdf").suffix.lower() or ".pdf"
    filename = f"doc_{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / "docs" / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        f.write(contents)
    return {"filename": filename, "original": file.filename, "url": f"/api/files/docs/{filename}"}


@api.get("/files/docs/{filename}")
async def serve_doc(filename: str, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """Belgeyi sadece admin veya belgeler kendine ait otele sun."""
    file_path = UPLOAD_DIR / "docs" / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Dosya bulunamadı")
    if not current_hotel.get("is_admin"):
        # Otel kendi belgesine erişebilir
        owner = await db.hotels.find_one({"documents": filename})
        if not owner or owner["_id"] != current_hotel["_id"]:
            raise HTTPException(status_code=403, detail="Yetkisiz erişim")
    return FileResponse(str(file_path))


@api.post("/auth/register", response_model=HotelPublic)
@limiter.limit("5/minute")
async def register(request: Request, hotel_in: HotelCreate):
    existing = await db.hotels.find_one({"email": hotel_in.email})
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bu e-posta zaten kayıtlı.")

    # Şifre güvenlik kontrolü
    validate_password(hotel_in.password)

    # Input sanitization
    hotel_in.name = sanitize_input(hotel_in.name) or hotel_in.name
    hotel_in.address = sanitize_input(hotel_in.address) or hotel_in.address
    hotel_in.concept = sanitize_input(hotel_in.concept) or hotel_in.concept

    hotel_id = str(uuid.uuid4())
    now = now_utc()
    count = await db.hotels.count_documents({})
    is_admin = count == 0  # İlk kayıt admin olur ve otomatik onaylanır
    approval_status = "approved" if is_admin else "pending_review"

    doc = {
        "_id": hotel_id,
        "name": hotel_in.name,
        "region": hotel_in.region,
        "micro_location": hotel_in.micro_location,
        "concept": hotel_in.concept,
        "address": hotel_in.address,
        "phone": hotel_in.phone,
        "whatsapp": hotel_in.whatsapp,
        "website": hotel_in.website,
        "contact_person": hotel_in.contact_person,
        "email": hotel_in.email,
        "password_hash": get_password_hash(hotel_in.password),
        "is_admin": is_admin,
        "approval_status": approval_status,
        "rejection_reason": None,
        "documents": hotel_in.documents or [],
        "created_at": now,
        "updated_at": now,
    }
    await db.hotels.insert_one(doc)
    await log_activity(hotel_id, "register", "hotel", hotel_id, {"approval_status": approval_status})

    return HotelPublic(
        id=hotel_id,
        name=hotel_in.name,
        region=hotel_in.region,
        micro_location=hotel_in.micro_location,
        concept=hotel_in.concept,
        address=hotel_in.address,
        phone=hotel_in.phone,
        whatsapp=hotel_in.whatsapp,
        website=hotel_in.website,
        contact_person=hotel_in.contact_person,
        email=hotel_in.email,
        is_admin=is_admin,
        approval_status=approval_status,
        created_at=now,
    )


@api.post("/auth/login", response_model=Token)
@limiter.limit("10/minute")
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    hotel = await db.hotels.find_one({"email": form_data.username})
    if not hotel or not verify_password(form_data.password, hotel["password_hash"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="E-posta veya şifre hatalı.")

    approval = hotel.get("approval_status", "approved")
    if approval == "pending_review":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PENDING_REVIEW: Başvurunuz henüz incelenmektedir. Onaylandıktan sonra giriş yapabilirsiniz."
        )
    if approval == "rejected":
        reason = hotel.get("rejection_reason", "")
        detail = "REJECTED: Başvurunuz reddedildi."
        if reason:
            detail += f" Sebep: {reason}"
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

    access_token = create_access_token({"sub": hotel["_id"]})
    return Token(access_token=access_token)


@api.get("/auth/me", response_model=HotelPublic)
async def me(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    return HotelPublic(
        id=current_hotel["_id"],
        name=current_hotel["name"],
        region=current_hotel["region"],
        micro_location=current_hotel["micro_location"],
        concept=current_hotel["concept"],
        address=current_hotel["address"],
        phone=current_hotel["phone"],
        whatsapp=current_hotel.get("whatsapp"),
        website=current_hotel.get("website"),
        contact_person=current_hotel.get("contact_person"),
        email=current_hotel["email"],
        is_admin=current_hotel.get("is_admin", False),
        approval_status=current_hotel.get("approval_status", "approved"),
        rejection_reason=current_hotel.get("rejection_reason"),
        created_at=current_hotel["created_at"],
    )


@api.put("/hotels/me", response_model=HotelPublic)
async def update_me(update: HotelMeUpdate, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    updates = {k: v for k, v in update.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        return await me(current_hotel)
    updates["updated_at"] = now_utc()
    await db.hotels.update_one({"_id": current_hotel["_id"]}, {"$set": updates})
    await log_activity(current_hotel["_id"], "update_profile", "hotel", current_hotel["_id"], {"fields": list(updates.keys())})
    refreshed = await db.hotels.find_one({"_id": current_hotel["_id"]})
    return await me(refreshed)


@api.post("/auth/change-password")
@limiter.limit("10/minute")
async def change_password(request: Request, req: ChangePasswordRequest, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    if not verify_password(req.current_password, current_hotel["password_hash"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mevcut şifre yanlış")
    # Yeni şifre güvenlik kontrolü
    validate_password(req.new_password)
    new_hash = get_password_hash(req.new_password)
    await db.hotels.update_one({"_id": current_hotel["_id"]}, {"$set": {"password_hash": new_hash, "updated_at": now_utc()}})
    return {"message": "Şifre güncellendi"}


@api.post("/auth/forgot-password")
@limiter.limit("5/minute")
async def forgot_password(request: Request, body: ForgotPasswordRequest):
    """Şifre sıfırlama isteği. E-posta sistemde varsa token üretilir.

    Güvenlik: kullanıcı sayımı sızdırmamak için her durumda 200 döner.
    Token DB'de hash'lenmiş şekilde saklanır; düz token yalnızca dev modunda
    response içinde döner. Üretimde e-posta sistemi entegre edilmeli.
    """
    import secrets, hashlib
    hotel = await db.hotels.find_one({"email": body.email.lower()})
    response = {"message": "Eğer e-posta sistemde kayıtlıysa sıfırlama bağlantısı gönderildi."}

    if hotel:
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        await db.password_reset_tokens.insert_one({
            "_id": str(uuid.uuid4()),
            "hotel_id": hotel["_id"],
            "token_hash": token_hash,
            "expires_at": now_utc() + timedelta(hours=1),
            "used_at": None,
            "created_at": now_utc(),
        })
        await log_activity(hotel["_id"], "password_reset_requested", "hotel", hotel["_id"], None)

        # E-posta gönderimi (Resend). Hata olsa bile response 200 döner — kullanıcı sayımı sızdırmaz.
        frontend_base = (
            os.environ.get("FRONTEND_URL")
            or (f"https://{os.environ['REPLIT_DEV_DOMAIN']}" if os.environ.get("REPLIT_DEV_DOMAIN") else None)
            or "http://localhost:3000"
        ).rstrip("/")
        reset_url = f"{frontend_base}/reset-password?token={raw_token}"
        subject, html, text = build_password_reset_email(reset_url, hotel.get("name"))
        try:
            await send_email(to=hotel["email"], subject=subject, html=html, text=text)
            logger.info("Password reset email sent to hotel_id=%s", hotel["_id"])
        except EmailNotConfiguredError as e:
            logger.warning("Resend not configured, skipping email: %s", e)
        except Exception as e:
            logger.exception("Password reset email send failed: %s", e)

        if os.environ.get("ENVIRONMENT", "development") != "production":
            response["debug_token"] = raw_token

    return response


@api.post("/auth/reset-password")
@limiter.limit("5/minute")
async def reset_password(request: Request, body: ResetPasswordRequest):
    """Token ile şifre sıfırla. Token tüketimi atomik yapılır (TOCTOU yok)."""
    import hashlib
    # Önce şifre formatını doğrula — token'ı boşa harcamayalım
    validate_password(body.new_password)

    token_hash = hashlib.sha256(body.token.encode()).hexdigest()
    now = now_utc()

    # ATOMIC tek kullanımlık tüketim
    record = await db.password_reset_tokens.find_one_and_update(
        {
            "token_hash": token_hash,
            "used_at": None,
            "expires_at": {"$gt": now},
        },
        {"$set": {"used_at": now}},
    )
    if not record:
        raise HTTPException(status_code=400, detail="Geçersiz veya süresi dolmuş token.")

    new_hash = get_password_hash(body.new_password)
    await db.hotels.update_one(
        {"_id": record["hotel_id"]},
        {"$set": {"password_hash": new_hash, "updated_at": now}},
    )
    await log_activity(record["hotel_id"], "password_reset_completed", "hotel", record["hotel_id"], None)
    return {"message": "Şifreniz başarıyla güncellendi."}


