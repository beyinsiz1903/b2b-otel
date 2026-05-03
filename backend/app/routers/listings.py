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


# --- Listings endpoints -----------------------------------------------------

@api.post("/listings", response_model=AvailabilityListingMine)
async def create_listing(payload: AvailabilityListingCreate, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    listing_id = str(uuid.uuid4())
    now = now_utc()
    payload_dict = payload.model_dump()
    if payload_dict.get("image_urls") is None:
        payload_dict["image_urls"] = []
    if payload_dict.get("features") is None:
        payload_dict["features"] = []
    if payload_dict.get("guest_restrictions") is None:
        payload_dict["guest_restrictions"] = []

    doc = {
        "_id": listing_id,
        "hotel_id": current_hotel["_id"],
        **payload_dict,
        "is_locked": False,
        "lock_request_id": None,
        "created_at": now,
        "updated_at": now,
    }
    await db.availability_listings.insert_one(doc)
    await log_activity(current_hotel["_id"], "create", "availability_listing", listing_id, {"status": payload.availability_status})
    return AvailabilityListingMine(
        id=listing_id,
        hotel_id=current_hotel["_id"],
        **payload_dict,
        is_locked=False,
        created_at=now,
        updated_at=now
    )


def listing_to_public(doc: Dict[str, Any]) -> AvailabilityListingPublic:
    return AvailabilityListingPublic(
        id=doc["_id"],
        region=doc["region"],
        micro_location=doc["micro_location"],
        concept=doc["concept"],
        capacity_label=doc["capacity_label"],
        pax=doc["pax"],
        date_start=doc["date_start"],
        date_end=doc["date_end"],
        nights=doc["nights"],
        price_min=doc["price_min"],
        price_max=doc["price_max"],
        availability_status=doc["availability_status"],
        is_locked=doc.get("is_locked", False),
        image_urls=doc.get("image_urls"),
        features=doc.get("features"),
        notes=doc.get("notes"),
        room_type=doc.get("room_type"),
        breakfast_included=doc.get("breakfast_included", False),
        min_nights=doc.get("min_nights", 1),
        guest_restrictions=doc.get("guest_restrictions"),
        allow_cross_region=doc.get("allow_cross_region", False),
    )


def listing_to_mine(doc: Dict[str, Any]) -> AvailabilityListingMine:
    return AvailabilityListingMine(
        id=doc["_id"],
        hotel_id=doc["hotel_id"],
        region=doc["region"],
        micro_location=doc["micro_location"],
        concept=doc["concept"],
        capacity_label=doc["capacity_label"],
        pax=doc["pax"],
        date_start=doc["date_start"],
        date_end=doc["date_end"],
        nights=doc["nights"],
        price_min=doc["price_min"],
        price_max=doc["price_max"],
        availability_status=doc["availability_status"],
        is_locked=doc.get("is_locked", False),
        image_urls=doc.get("image_urls"),
        features=doc.get("features"),
        notes=doc.get("notes"),
        room_type=doc.get("room_type"),
        breakfast_included=doc.get("breakfast_included", False),
        min_nights=doc.get("min_nights", 1),
        guest_restrictions=doc.get("guest_restrictions"),
        allow_cross_region=doc.get("allow_cross_region", False),
        template_id=doc.get("template_id"),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


@api.get("/listings", response_model=List[AvailabilityListingPublic])
async def list_listings(
    response: Response,
    region: Optional[str] = None,
    concept: Optional[str] = None,
    mine: bool = False,
    hide_expired: bool = True,
    pax_min: Optional[int] = None,
    pax_max: Optional[int] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    avail_status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    features: Optional[str] = None,
    room_type: Optional[str] = None,
    breakfast_included: Optional[bool] = None,
    include_cross_region: Optional[bool] = False,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    current_hotel: Dict[str, Any] = Depends(get_current_hotel),
):
    query: Dict[str, Any] = {}
    if region:
        if include_cross_region:
            # Bölge filtresi + cross-region ilanları dahil et
            query["$or"] = [
                {"region": region},
                {"allow_cross_region": True},
            ]
        else:
            query["region"] = region
    if concept:
        query["concept"] = {"$regex": concept, "$options": "i"}
    if mine:
        query["hotel_id"] = current_hotel["_id"]
    if hide_expired and not mine:
        query["date_end"] = {"$gte": now_utc()}
    if pax_min is not None:
        query.setdefault("pax", {})["$gte"] = pax_min
    if pax_max is not None:
        query.setdefault("pax", {})["$lte"] = pax_max
    if price_min is not None:
        query.setdefault("price_max", {})["$gte"] = price_min
    if price_max is not None:
        query.setdefault("price_min", {})["$lte"] = price_max
    if avail_status:
        query["availability_status"] = avail_status
    if date_from:
        try:
            df = datetime.fromisoformat(date_from)
            query.setdefault("date_end", {})["$gte"] = df
        except Exception:
            pass
    if date_to:
        try:
            dt = datetime.fromisoformat(date_to)
            query.setdefault("date_start", {})["$lte"] = dt
        except Exception:
            pass
    if features:
        feature_list = [f.strip() for f in features.split(",") if f.strip()]
        if feature_list:
            query["features"] = {"$all": feature_list}
    if room_type:
        query["room_type"] = room_type
    if breakfast_included is not None:
        query["breakfast_included"] = breakfast_included

    # Full-text search across multiple fields
    if search:
        search_regex = {"$regex": search, "$options": "i"}
        query["$or"] = query.get("$or", []) + [
            {"concept": search_regex},
            {"micro_location": search_regex},
            {"notes": search_regex},
            {"room_type": search_regex},
            {"capacity_label": search_regex},
        ]

    # Pagination: get total count
    total = await db.availability_listings.count_documents(query)
    response.headers["X-Total-Count"] = str(total)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"

    cursor = db.availability_listings.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [listing_to_public(d) for d in docs]


@api.get("/listings/mine", response_model=List[AvailabilityListingMine])
async def list_mine_listings(response: Response, skip: int = 0, limit: int = 100, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    query = {"hotel_id": current_hotel["_id"]}
    total = await db.availability_listings.count_documents(query)
    response.headers["X-Total-Count"] = str(total)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    cursor = db.availability_listings.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [listing_to_mine(d) for d in docs]


@api.get("/listings/{listing_id}")
async def get_listing(listing_id: str, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    listing = await db.availability_listings.find_one({"_id": listing_id})
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    return listing_to_public(listing)


@api.put("/listings/{listing_id}", response_model=AvailabilityListingMine)
async def update_listing(listing_id: str, payload: AvailabilityListingUpdate, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    listing = await db.availability_listings.find_one({"_id": listing_id})
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    if listing["hotel_id"] != current_hotel["_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to edit this listing")
    if listing.get("is_locked"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot edit a locked listing")

    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        return listing_to_mine(listing)
    updates["updated_at"] = now_utc()
    await db.availability_listings.update_one({"_id": listing_id}, {"$set": updates})
    await log_activity(current_hotel["_id"], "update", "availability_listing", listing_id, {"fields": list(updates.keys())})
    refreshed = await db.availability_listings.find_one({"_id": listing_id})
    return listing_to_mine(refreshed)


@api.delete("/listings/{listing_id}")
async def delete_listing(listing_id: str, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    listing = await db.availability_listings.find_one({"_id": listing_id})
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    if listing["hotel_id"] != current_hotel["_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this listing")
    if listing.get("is_locked"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete a locked listing. Cancel the pending request first.")

    await db.availability_listings.delete_one({"_id": listing_id})
    await log_activity(current_hotel["_id"], "delete", "availability_listing", listing_id, {})
    return {"message": "Listing deleted"}


