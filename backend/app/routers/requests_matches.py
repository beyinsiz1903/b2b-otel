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


# --- Requests & Matches -----------------------------------------------------

REQUEST_STATUS_OPEN = {"pending", "alternative_offered"}


@api.post("/requests", response_model=RequestPublic)
async def create_request(payload: RequestCreate, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    listing = await db.availability_listings.find_one({"_id": payload.listing_id})
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    if listing.get("hotel_id") == current_hotel["_id"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot request your own listing")
    if listing.get("is_locked"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Listing is already locked by another request")

    req_id = str(uuid.uuid4())
    now = now_utc()
    req_doc = {
        "_id": req_id,
        "listing_id": payload.listing_id,
        "from_hotel_id": current_hotel["_id"],
        "to_hotel_id": listing["hotel_id"],
        "guest_type": payload.guest_type,
        "notes": payload.notes,
        "confirm_window_minutes": payload.confirm_window_minutes,
        "status": "pending",
        "alternative_payload": None,
        "created_at": now,
        "updated_at": now,
    }
    await db.requests.insert_one(req_doc)
    await db.availability_listings.update_one({"_id": listing["_id"]}, {"$set": {"is_locked": True, "lock_request_id": req_id, "updated_at": now}})
    await log_activity(current_hotel["_id"], "create", "request", req_id, {"listing_id": payload.listing_id})

    # Bildirim oluştur
    await create_notification(listing["hotel_id"], "request_received", "Yeni Talep Alındı", f"{current_hotel['name']} otelinden yeni bir kapasite talebi aldınız.", {"request_id": req_id})

    return RequestPublic(
        id=req_id,
        listing_id=payload.listing_id,
        from_hotel_id=current_hotel["_id"],
        to_hotel_id=listing["hotel_id"],
        guest_type=payload.guest_type,
        notes=payload.notes,
        confirm_window_minutes=payload.confirm_window_minutes,
        status="pending",
        alternative_payload=None,
        created_at=now,
        updated_at=now,
    )


def request_to_public(doc: Dict[str, Any]) -> RequestPublic:
    return RequestPublic(
        id=doc["_id"],
        listing_id=doc["listing_id"],
        from_hotel_id=doc["from_hotel_id"],
        to_hotel_id=doc["to_hotel_id"],
        guest_type=doc["guest_type"],
        notes=doc.get("notes"),
        confirm_window_minutes=doc["confirm_window_minutes"],
        status=doc["status"],
        alternative_payload=doc.get("alternative_payload"),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


@api.get("/requests/outgoing", response_model=List[RequestPublic])
async def list_outgoing_requests(response: Response, skip: int = 0, limit: int = 50, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    query = {"from_hotel_id": current_hotel["_id"]}
    total = await db.requests.count_documents(query)
    response.headers["X-Total-Count"] = str(total)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    cursor = db.requests.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [request_to_public(d) for d in docs]


@api.get("/requests/incoming", response_model=List[RequestPublic])
async def list_incoming_requests(response: Response, skip: int = 0, limit: int = 50, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    query = {"to_hotel_id": current_hotel["_id"]}
    total = await db.requests.count_documents(query)
    response.headers["X-Total-Count"] = str(total)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    cursor = db.requests.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [request_to_public(d) for d in docs]


@api.get("/requests/{request_id}", response_model=RequestPublic)
async def get_request(request_id: str, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    req = await db.requests.find_one({"_id": request_id})
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if req["from_hotel_id"] != current_hotel["_id"] and req["to_hotel_id"] != current_hotel["_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this request")
    return request_to_public(req)


async def _get_request_for_action(req_id: str, current_hotel: Dict[str, Any]) -> Dict[str, Any]:
    req = await db.requests.find_one({"_id": req_id})
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if req["to_hotel_id"] != current_hotel["_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this request")
    if req["status"] not in REQUEST_STATUS_OPEN:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request is not in an actionable state")
    return req


@api.post("/requests/{request_id}/accept", response_model=MatchPublic)
async def accept_request(request_id: str, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    req = await _get_request_for_action(request_id, current_hotel)
    listing = await db.availability_listings.find_one({"_id": req["listing_id"]})
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

    # Plan kotasını kontrol et + atomik tüket (kabul eden taraf için)
    consumed_sub_id = await _consume_match_quota(current_hotel["_id"])
    prior_status = req["status"]  # Rollback için sakla

    try:
        now = now_utc()
        # ATOMIC talep durumu geçişi
        transition = await db.requests.update_one(
            {"_id": req["_id"], "status": {"$in": list(REQUEST_STATUS_OPEN)}},
            {"$set": {"status": "accepted", "updated_at": now}},
        )
        if transition.modified_count != 1:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu talep bu sırada başka bir aksiyon aldı.")

        unlock = await db.availability_listings.update_one(
            {"_id": listing["_id"]},
            {"$set": {"is_locked": False, "lock_request_id": None, "updated_at": now}},
        )
        if unlock.matched_count != 1:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing bu sırada silindi")
    except Exception:
        # Geçiş öncesi/sırası başarısızlık → kota'yı geri ver, talep durumunu geri al
        await _refund_match_quota(consumed_sub_id)
        await db.requests.update_one(
            {"_id": req["_id"], "status": "accepted"},
            {"$set": {"status": prior_status, "updated_at": now_utc()}},
        )
        raise

    ref_code = await next_reference_code(listing["region"])
    fee_amount = await get_region_match_fee(listing["region"])
    match_id = str(uuid.uuid4())
    match_doc = {
        "_id": match_id,
        "request_id": req["_id"],
        "listing_id": listing["_id"],
        "hotel_a_id": req["from_hotel_id"],
        "hotel_b_id": req["to_hotel_id"],
        "reference_code": ref_code,
        "fee_amount": fee_amount,
        "fee_status": "due",
        "region": listing.get("region", "Sapanca"),
        "status": "active",
        "inventory_decremented": True,
        "accepted_by_hotel_id": current_hotel["_id"],
        "accepted_by_subscription_id": consumed_sub_id,
        "accepted_at": now,
        "created_at": now,
    }
    try:
        await db.matches.insert_one(match_doc)
    except DuplicateKeyError:
        await _refund_match_quota(consumed_sub_id)
        await db.requests.update_one(
            {"_id": req["_id"], "status": "accepted"},
            {"$set": {"status": prior_status, "updated_at": now_utc()}},
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu talep için zaten bir eşleşme var.")
    except Exception:
        # Beklenmedik DB/ağ hatası → kotayı geri ver, talep durumunu geri al
        await _refund_match_quota(consumed_sub_id)
        await db.requests.update_one(
            {"_id": req["_id"], "status": "accepted"},
            {"$set": {"status": prior_status, "updated_at": now_utc()}},
        )
        raise
    await log_activity(current_hotel["_id"], "accept", "request", req["_id"], {"match_id": match_id})

    # Envanter otomatik güncelle (kota zaten _consume_match_quota ile artırıldı)
    await _decrement_inventory_on_match(listing)

    # Bildirimler oluştur
    await create_notification(req["from_hotel_id"], "match_created", "Eşleşme Oluştu!", f"Talebiniz kabul edildi. Referans: {ref_code}", {"match_id": match_id})
    await create_notification(req["to_hotel_id"], "match_created", "Eşleşme Onaylandı", f"Talep kabul edildi. Referans: {ref_code}", {"match_id": match_id})

    return MatchPublic(
        id=match_id,
        request_id=req["_id"],
        listing_id=listing["_id"],
        hotel_a_id=req["from_hotel_id"],
        hotel_b_id=req["to_hotel_id"],
        reference_code=ref_code,
        fee_amount=fee_amount,
        fee_status="due",
        accepted_at=now,
        created_at=now,
    )


@api.post("/requests/{request_id}/reject", response_model=RequestPublic)
async def reject_request(request_id: str, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    req = await _get_request_for_action(request_id, current_hotel)
    listing = await db.availability_listings.find_one({"_id": req["listing_id"]})
    now = now_utc()
    await db.requests.update_one({"_id": req["_id"]}, {"$set": {"status": "rejected", "updated_at": now}})
    if listing:
        await db.availability_listings.update_one({"_id": listing["_id"]}, {"$set": {"is_locked": False, "lock_request_id": None, "updated_at": now}})
    await log_activity(current_hotel["_id"], "reject", "request", req["_id"], None)
    refreshed = await db.requests.find_one({"_id": req["_id"]})
    return request_to_public(refreshed)


@api.post("/requests/{request_id}/offer-alternative", response_model=RequestPublic)
async def offer_alternative(request_id: str, alt: AlternativeOffer, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    req = await _get_request_for_action(request_id, current_hotel)
    now = now_utc()
    alt_payload = alt.model_dump(exclude_unset=True)
    await db.requests.update_one(
        {"_id": req["_id"]},
        {"$set": {"status": "alternative_offered", "alternative_payload": alt_payload, "updated_at": now}},
    )
    await log_activity(current_hotel["_id"], "offer_alternative", "request", req["_id"], alt_payload)
    # Bildirim oluştur
    await create_notification(req["from_hotel_id"], "alternative_offered", "Alternatif Teklif Aldınız", "Talebiniz için alternatif bir teklif sunuldu.", {"request_id": req["_id"]})
    refreshed = await db.requests.find_one({"_id": req["_id"]})
    return request_to_public(refreshed)


@api.post("/requests/{request_id}/accept-alternative", response_model=MatchPublic)
async def accept_alternative(request_id: str, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    req = await db.requests.find_one({"_id": request_id})
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if req["from_hotel_id"] != current_hotel["_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to accept alternative")
    if req["status"] != "alternative_offered":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request is not in alternative_offered state")

    listing = await db.availability_listings.find_one({"_id": req["listing_id"]})
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

    # Plan kotasını kontrol et + atomik tüket
    consumed_sub_id = await _consume_match_quota(current_hotel["_id"])

    try:
        now = now_utc()
        transition = await db.requests.update_one(
            {"_id": req["_id"], "status": "alternative_offered"},
            {"$set": {"status": "accepted", "updated_at": now}},
        )
        if transition.modified_count != 1:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu talep bu sırada başka bir aksiyon aldı.")
        unlock = await db.availability_listings.update_one(
            {"_id": listing["_id"]},
            {"$set": {"is_locked": False, "lock_request_id": None, "updated_at": now}},
        )
        if unlock.matched_count != 1:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing bu sırada silindi")
    except Exception:
        await _refund_match_quota(consumed_sub_id)
        await db.requests.update_one(
            {"_id": req["_id"], "status": "accepted"},
            {"$set": {"status": "alternative_offered", "updated_at": now_utc()}},
        )
        raise

    ref_code = await next_reference_code(listing["region"])
    fee_amount = await get_region_match_fee(listing["region"])
    match_id = str(uuid.uuid4())
    match_doc = {
        "_id": match_id,
        "request_id": req["_id"],
        "listing_id": listing["_id"],
        "hotel_a_id": req["from_hotel_id"],
        "hotel_b_id": req["to_hotel_id"],
        "reference_code": ref_code,
        "fee_amount": fee_amount,
        "fee_status": "due",
        "region": listing.get("region", "Sapanca"),
        "status": "active",
        "inventory_decremented": True,
        "accepted_by_hotel_id": current_hotel["_id"],
        "accepted_by_subscription_id": consumed_sub_id,
        "accepted_at": now,
        "created_at": now,
    }
    try:
        await db.matches.insert_one(match_doc)
    except DuplicateKeyError:
        await _refund_match_quota(consumed_sub_id)
        await db.requests.update_one(
            {"_id": req["_id"], "status": "accepted"},
            {"$set": {"status": "alternative_offered", "updated_at": now_utc()}},
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu talep için zaten bir eşleşme var.")
    except Exception:
        await _refund_match_quota(consumed_sub_id)
        await db.requests.update_one(
            {"_id": req["_id"], "status": "accepted"},
            {"$set": {"status": "alternative_offered", "updated_at": now_utc()}},
        )
        raise
    await log_activity(current_hotel["_id"], "accept_alternative", "request", req["_id"], {"match_id": match_id})

    # Envanter otomatik güncelle (kota zaten _consume_match_quota ile artırıldı)
    await _decrement_inventory_on_match(listing)

    # Bildirimler
    await create_notification(req["to_hotel_id"], "match_created", "Alternatif Kabul Edildi", f"Alternatif teklifiniz kabul edildi. Referans: {ref_code}", {"match_id": match_id})

    return MatchPublic(
        id=match_id,
        request_id=req["_id"],
        listing_id=listing["_id"],
        hotel_a_id=req["from_hotel_id"],
        hotel_b_id=req["to_hotel_id"],
        reference_code=ref_code,
        fee_amount=fee_amount,
        fee_status="due",
        accepted_at=now,
        created_at=now,
    )


@api.post("/requests/{request_id}/reject-alternative", response_model=RequestPublic)
async def reject_alternative(request_id: str, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """Requester rejects the alternative offer — unlocks listing and marks request rejected."""
    req = await db.requests.find_one({"_id": request_id})
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if req["from_hotel_id"] != current_hotel["_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    if req["status"] != "alternative_offered":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request is not in alternative_offered state")

    now = now_utc()
    await db.requests.update_one({"_id": req["_id"]}, {"$set": {"status": "rejected", "updated_at": now}})
    listing = await db.availability_listings.find_one({"_id": req["listing_id"]})
    if listing:
        await db.availability_listings.update_one({"_id": listing["_id"]}, {"$set": {"is_locked": False, "lock_request_id": None, "updated_at": now}})
    await log_activity(current_hotel["_id"], "reject_alternative", "request", req["_id"], None)
    refreshed = await db.requests.find_one({"_id": req["_id"]})
    return request_to_public(refreshed)


@api.post("/requests/{request_id}/cancel", response_model=RequestPublic)
async def cancel_request(request_id: str, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    req = await db.requests.find_one({"_id": request_id})
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if req["from_hotel_id"] != current_hotel["_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to cancel this request")
    if req["status"] not in REQUEST_STATUS_OPEN:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request cannot be cancelled in its current state")

    now = now_utc()
    await db.requests.update_one({"_id": req["_id"]}, {"$set": {"status": "cancelled", "updated_at": now}})
    listing = await db.availability_listings.find_one({"_id": req["listing_id"]})
    if listing:
        await db.availability_listings.update_one({"_id": listing["_id"]}, {"$set": {"is_locked": False, "lock_request_id": None, "updated_at": now}})
    await log_activity(current_hotel["_id"], "cancel", "request", req["_id"], None)
    refreshed = await db.requests.find_one({"_id": req["_id"]})
    return request_to_public(refreshed)


@api.post("/matches/{match_id}/cancel", response_model=MatchPublic)
async def cancel_match(
    match_id: str,
    body: Optional[Dict[str, str]] = None,
    current_hotel: Dict[str, Any] = Depends(get_current_hotel),
):
    """Kabul edilmiş bir eşleşmeyi iptal et.

    - İki taraftan herhangi biri iptal edebilir.
    - Envanter geri yüklenir (idempotent: `inventory_decremented` flag'i kontrol edilir).
    - Karşı tarafa bildirim gönderilir.
    """
    match = await db.matches.find_one({"_id": match_id})
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Eşleşme bulunamadı")

    if current_hotel["_id"] not in {match.get("hotel_a_id"), match.get("hotel_b_id")}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu eşleşmeyi iptal etme yetkiniz yok")

    if match.get("status") == "cancelled":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Eşleşme zaten iptal edilmiş")

    reason = (body or {}).get("reason", "")
    now = now_utc()

    # ATOMIC durum geçişi: yalnızca bir paralel istek başarılı olabilir.
    update_result = await db.matches.update_one(
        {"_id": match_id, "status": {"$ne": "cancelled"}},
        {"$set": {
            "status": "cancelled",
            "cancelled_at": now,
            "cancelled_by": current_hotel["_id"],
            "cancel_reason": sanitize_input(reason) or "",
            "updated_at": now,
        }},
    )
    if update_result.modified_count != 1:
        # Başka bir istek bizden önce iptal etti.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Eşleşme bu sırada başka bir taraf tarafından iptal edildi")

    # Envanteri geri yükle (idempotent: ikinci $set yalnızca flag hâlâ True ise iade etsin)
    flag_consume = await db.matches.update_one(
        {"_id": match_id, "inventory_decremented": True},
        {"$set": {"inventory_decremented": False}},
    )
    if flag_consume.modified_count == 1:
        listing = await db.availability_listings.find_one({"_id": match.get("listing_id")})
        if listing:
            await _increment_inventory_on_cancel(listing)

    # Talep durumunu da güncelle
    if match.get("request_id"):
        await db.requests.update_one(
            {"_id": match["request_id"]},
            {"$set": {"status": "cancelled", "updated_at": now}},
        )

    # Aboneliğin matches_used sayacını yalnızca kabul eden tarafın aboneliğinden düş.
    sub_id = match.get("accepted_by_subscription_id")
    if sub_id:
        await _refund_match_quota(sub_id)
    elif match.get("accepted_by_hotel_id"):
        # Eski (sub_id'siz) eşleşmeler için fallback
        await _refund_match_quota_by_hotel(match["accepted_by_hotel_id"])

    other_id = match["hotel_b_id"] if current_hotel["_id"] == match["hotel_a_id"] else match["hotel_a_id"]
    await create_notification(
        other_id,
        "match_cancelled",
        "Eşleşme İptal Edildi",
        f"{match.get('reference_code', '')} referanslı eşleşme karşı taraf tarafından iptal edildi." + (f" Sebep: {reason}" if reason else ""),
        {"match_id": match_id},
    )
    await log_activity(current_hotel["_id"], "cancel_match", "match", match_id, {"reason": reason})

    refreshed = await db.matches.find_one({"_id": match_id})
    return MatchPublic(
        id=refreshed["_id"],
        request_id=refreshed["request_id"],
        listing_id=refreshed["listing_id"],
        hotel_a_id=refreshed["hotel_a_id"],
        hotel_b_id=refreshed["hotel_b_id"],
        reference_code=refreshed["reference_code"],
        fee_amount=refreshed["fee_amount"],
        fee_status=refreshed["fee_status"],
        accepted_at=refreshed["accepted_at"],
        created_at=refreshed["created_at"],
    )


@api.get("/matches", response_model=List[MatchPublic])
async def list_matches(response: Response, skip: int = 0, limit: int = 50, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    query = {"$or": [{"hotel_a_id": current_hotel["_id"]}, {"hotel_b_id": current_hotel["_id"]}]}
    total = await db.matches.count_documents(query)
    response.headers["X-Total-Count"] = str(total)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    cursor = db.matches.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [
        MatchPublic(
            id=d["_id"],
            request_id=d["request_id"],
            listing_id=d["listing_id"],
            hotel_a_id=d["hotel_a_id"],
            hotel_b_id=d["hotel_b_id"],
            reference_code=d["reference_code"],
            fee_amount=d["fee_amount"],
            fee_status=d["fee_status"],
            accepted_at=d["accepted_at"],
            created_at=d["created_at"],
        )
        for d in docs
    ]


@api.get("/matches/{match_id}")
async def get_match(match_id: str, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    d = await db.matches.find_one({"_id": match_id})
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    if current_hotel["_id"] not in {d["hotel_a_id"], d["hotel_b_id"]}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this match")

    hotel_a = await db.hotels.find_one({"_id": d["hotel_a_id"]})
    hotel_b = await db.hotels.find_one({"_id": d["hotel_b_id"]})
    listing = await db.availability_listings.find_one({"_id": d["listing_id"]})

    # Null-guard: taraflardan biri silinmiş olabilir → silinmiş otel için minimal stub döner
    def _hotel_stub(hotel_id: str) -> Dict[str, Any]:
        return {"id": hotel_id, "name": "Silinmiş otel", "deleted": True}

    am_a = (current_hotel["_id"] == d["hotel_a_id"])
    self_doc = serialize_doc(hotel_a) if am_a and hotel_a else (
        serialize_doc(hotel_b) if hotel_b else _hotel_stub(d["hotel_b_id"])
    )
    if am_a and not hotel_a:
        self_doc = _hotel_stub(d["hotel_a_id"])
    other_doc = serialize_doc(hotel_b) if am_a and hotel_b else (
        serialize_doc(hotel_a) if hotel_a else _hotel_stub(d["hotel_a_id"])
    )
    if am_a and not hotel_b:
        other_doc = _hotel_stub(d["hotel_b_id"])

    return {
        "id": d["_id"],
        "request_id": d["request_id"],
        "listing_id": d["listing_id"],
        "reference_code": d["reference_code"],
        "fee_amount": d["fee_amount"],
        "fee_status": d["fee_status"],
        "accepted_at": d["accepted_at"].isoformat(),
        "created_at": d["created_at"].isoformat(),
        "listing_snapshot": {
            "region": listing.get("region") if listing else None,
            "micro_location": listing.get("micro_location") if listing else None,
            "concept": listing.get("concept") if listing else None,
            "capacity_label": listing.get("capacity_label") if listing else None,
            "pax": listing.get("pax") if listing else None,
            "date_start": listing.get("date_start").isoformat() if listing and listing.get("date_start") else None,
            "date_end": listing.get("date_end").isoformat() if listing and listing.get("date_end") else None,
            "nights": listing.get("nights") if listing else None,
            "price_min": listing.get("price_min") if listing else None,
        } if listing else None,
        "counterparty": {
            "self": self_doc,
            "other": other_doc,
        },
    }


