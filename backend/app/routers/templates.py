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


# --- Room Templates ---------------------------------------------------------

def template_to_public(doc: Dict[str, Any]) -> RoomTemplatePublic:
    return RoomTemplatePublic(
        id=doc["_id"],
        hotel_id=doc["hotel_id"],
        name=doc["name"],
        room_type=doc["room_type"],
        region=doc["region"],
        micro_location=doc["micro_location"],
        concept=doc["concept"],
        capacity_label=doc["capacity_label"],
        pax=doc["pax"],
        breakfast_included=doc.get("breakfast_included", False),
        min_nights=doc.get("min_nights", 1),
        features=doc.get("features"),
        guest_restrictions=doc.get("guest_restrictions"),
        image_urls=doc.get("image_urls"),
        price_suggestion=doc.get("price_suggestion"),
        notes=doc.get("notes"),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


@api.get("/room-templates", response_model=List[RoomTemplatePublic])
async def list_room_templates(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    cursor = db.room_templates.find({"hotel_id": current_hotel["_id"]}).sort("created_at", -1)
    docs = await cursor.to_list(length=100)
    return [template_to_public(d) for d in docs]


@api.post("/room-templates", response_model=RoomTemplatePublic)
async def create_room_template(payload: RoomTemplateCreate, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    tpl_id = str(uuid.uuid4())
    now = now_utc()
    payload_dict = payload.model_dump()
    if payload_dict.get("features") is None:
        payload_dict["features"] = []
    if payload_dict.get("guest_restrictions") is None:
        payload_dict["guest_restrictions"] = []
    if payload_dict.get("image_urls") is None:
        payload_dict["image_urls"] = []

    doc = {
        "_id": tpl_id,
        "hotel_id": current_hotel["_id"],
        **payload_dict,
        "created_at": now,
        "updated_at": now,
    }
    await db.room_templates.insert_one(doc)
    await log_activity(current_hotel["_id"], "create", "room_template", tpl_id, {"name": payload.name})
    return template_to_public(doc)


@api.put("/room-templates/{template_id}", response_model=RoomTemplatePublic)
async def update_room_template(template_id: str, payload: RoomTemplateUpdate, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    tpl = await db.room_templates.find_one({"_id": template_id})
    if not tpl:
        raise HTTPException(status_code=404, detail="Şablon bulunamadı")
    if tpl["hotel_id"] != current_hotel["_id"]:
        raise HTTPException(status_code=403, detail="Bu şablona erişim yetkiniz yok")

    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items()}
    if not updates:
        return template_to_public(tpl)
    updates["updated_at"] = now_utc()
    await db.room_templates.update_one({"_id": template_id}, {"$set": updates})
    await log_activity(current_hotel["_id"], "update", "room_template", template_id, {"fields": list(updates.keys())})
    refreshed = await db.room_templates.find_one({"_id": template_id})
    return template_to_public(refreshed)


@api.delete("/room-templates/{template_id}")
async def delete_room_template(template_id: str, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    tpl = await db.room_templates.find_one({"_id": template_id})
    if not tpl:
        raise HTTPException(status_code=404, detail="Şablon bulunamadı")
    if tpl["hotel_id"] != current_hotel["_id"]:
        raise HTTPException(status_code=403, detail="Bu şablona erişim yetkiniz yok")
    await db.room_templates.delete_one({"_id": template_id})
    await log_activity(current_hotel["_id"], "delete", "room_template", template_id, {})
    return {"message": "Şablon silindi"}


