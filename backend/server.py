from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from typing import Any, Dict, List, Optional
from collections import defaultdict
import asyncio
import time
import warnings
import os
import uuid
import math
import json

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, APIRouter, status, Query, UploadFile, File, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Google Sheets
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials


# --- Env & DB setup ---------------------------------------------------------

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ.get("DB_NAME", "hotel_match_db")
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-secret-change")
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRE", "120"))
MATCH_FEE_TL = float(os.environ.get("MATCH_FEE_TL", "250.0"))

# --- Regions ---------------------------------------------------------------
REGIONS = {
    "Sapanca": {"prefix": "SPC", "match_fee": 250.0, "label": "Sapanca"},
    "Kartepe": {"prefix": "KTP", "match_fee": 250.0, "label": "Kartepe"},
    "Abant": {"prefix": "ABN", "match_fee": 200.0, "label": "Abant"},
    "Ayder": {"prefix": "AYD", "match_fee": 300.0, "label": "Ayder"},
    "Kas": {"prefix": "KAS", "match_fee": 350.0, "label": "Kaş"},
    "Alacati": {"prefix": "ALC", "match_fee": 300.0, "label": "Alaçatı"},
}

# --- Subscription Plans ---------------------------------------------------
SUBSCRIPTION_PLANS = [
    {"id": "free", "name": "Ücretsiz", "price_monthly": 0, "price_yearly": 0, "max_matches_per_month": 5, "features": ["Temel eşleşme", "5 eşleşme/ay", "Standart destek"]},
    {"id": "basic", "name": "Temel", "price_monthly": 1500, "price_yearly": 15000, "max_matches_per_month": 20, "features": ["20 eşleşme/ay", "Gelişmiş filtreler", "Öncelikli destek", "Raporlama"]},
    {"id": "premium", "name": "Premium", "price_monthly": 3500, "price_yearly": 35000, "max_matches_per_month": -1, "features": ["Sınırsız eşleşme", "Tüm filtreler", "7/24 destek", "Gelişmiş raporlama", "API erişimi", "Özel fiyatlandırma"]},
    {"id": "enterprise", "name": "Kurumsal", "price_monthly": 7500, "price_yearly": 75000, "max_matches_per_month": -1, "features": ["Sınırsız eşleşme", "Çoklu bölge", "Özel entegrasyon", "Dedike hesap yöneticisi", "SLA garantisi"]},
]

# --- Rate Limiter ----------------------------------------------------------
limiter = Limiter(key_func=get_remote_address)

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]


# --- Security ---------------------------------------------------------------

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def validate_password(password: str) -> None:
    """Şifre güvenlik kontrolü: en az 8 karakter, 1 büyük harf, 1 rakam."""
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Şifre en az 8 karakter olmalıdır.")
    if not any(c.isupper() for c in password):
        raise HTTPException(status_code=400, detail="Şifre en az 1 büyük harf içermelidir.")
    if not any(c.isdigit() for c in password):
        raise HTTPException(status_code=400, detail="Şifre en az 1 rakam içermelidir.")
    if not any(c.islower() for c in password):
        raise HTTPException(status_code=400, detail="Şifre en az 1 küçük harf içermelidir.")


import re as _re
import html as _html

def sanitize_input(text: Optional[str]) -> Optional[str]:
    """Temel XSS/HTML injection koruması."""
    if text is None:
        return None
    # HTML entity escape
    text = _html.escape(text)
    # Script tag removal
    text = _re.sub(r'<script[^>]*>.*?</script>', '', text, flags=_re.IGNORECASE | _re.DOTALL)
    return text.strip()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


async def get_current_hotel(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        hotel_id: str = payload.get("sub")
        if hotel_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    hotel = await db.hotels.find_one({"_id": hotel_id})
    if not hotel:
        raise credentials_exception
    return hotel


async def get_current_admin(current_hotel: Dict[str, Any] = Depends(get_current_hotel)) -> Dict[str, Any]:
    if not current_hotel.get("is_admin", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_hotel


# --- Serialization helpers --------------------------------------------------

def serialize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return doc
    out: Dict[str, Any] = {}
    for k, v in doc.items():
        if k == "_id":
            out["id"] = str(v)
        elif isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# --- Pydantic Schemas -------------------------------------------------------

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class HotelBase(BaseModel):
    name: str
    region: str
    micro_location: str
    concept: str
    address: str
    phone: str
    whatsapp: Optional[str] = None
    website: Optional[str] = None
    contact_person: Optional[str] = None


class HotelCreate(HotelBase):
    email: EmailStr
    password: str
    documents: Optional[List[str]] = None   # yüklenen belge dosya adları


class HotelPublic(HotelBase):
    id: str
    email: EmailStr
    is_admin: bool = False
    approval_status: str = "approved"        # pending_review | approved | rejected
    rejection_reason: Optional[str] = None
    created_at: datetime


class HotelMeUpdate(BaseModel):
    name: Optional[str] = None
    region: Optional[str] = None
    micro_location: Optional[str] = None
    concept: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    website: Optional[str] = None
    contact_person: Optional[str] = None


class AvailabilityListingCreate(BaseModel):
    region: str
    micro_location: str
    concept: str
    capacity_label: str
    pax: int
    date_start: datetime
    date_end: datetime
    nights: int
    price_min: float
    price_max: float
    availability_status: str = Field(pattern="^(available|limited|alternative)$")
    image_urls: Optional[List[str]] = None
    features: Optional[List[str]] = None
    notes: Optional[str] = None
    # New fields
    room_type: Optional[str] = None
    breakfast_included: Optional[bool] = False
    min_nights: Optional[int] = 1
    guest_restrictions: Optional[List[str]] = None
    template_id: Optional[str] = None
    allow_cross_region: Optional[bool] = False


class AvailabilityListingUpdate(BaseModel):
    region: Optional[str] = None
    micro_location: Optional[str] = None
    concept: Optional[str] = None
    capacity_label: Optional[str] = None
    pax: Optional[int] = None
    date_start: Optional[datetime] = None
    date_end: Optional[datetime] = None
    nights: Optional[int] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    availability_status: Optional[str] = None
    image_urls: Optional[List[str]] = None
    features: Optional[List[str]] = None
    notes: Optional[str] = None
    room_type: Optional[str] = None
    breakfast_included: Optional[bool] = None
    min_nights: Optional[int] = None
    guest_restrictions: Optional[List[str]] = None
    allow_cross_region: Optional[bool] = None


class AvailabilityListingPublic(BaseModel):
    id: str
    region: str
    micro_location: str
    concept: str
    capacity_label: str
    pax: int
    date_start: datetime
    date_end: datetime
    nights: int
    price_min: float
    price_max: float
    availability_status: str
    is_locked: bool
    image_urls: Optional[List[str]] = None
    features: Optional[List[str]] = None
    notes: Optional[str] = None
    room_type: Optional[str] = None
    breakfast_included: Optional[bool] = False
    min_nights: Optional[int] = 1
    guest_restrictions: Optional[List[str]] = None
    allow_cross_region: Optional[bool] = False


class AvailabilityListingMine(AvailabilityListingPublic):
    hotel_id: str
    template_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# --- Room Template Schemas --------------------------------------------------

class RoomTemplateCreate(BaseModel):
    name: str                                    # Şablon adı (Göl Manzaralı Bungalov)
    room_type: str                               # bungalov, suite, standart, villa, apart, dag_evi
    region: str
    micro_location: str
    concept: str
    capacity_label: str
    pax: int
    breakfast_included: bool = False
    min_nights: int = 1
    features: Optional[List[str]] = None
    guest_restrictions: Optional[List[str]] = None
    image_urls: Optional[List[str]] = None
    price_suggestion: Optional[float] = None    # Fiyat önerisi
    notes: Optional[str] = None


class RoomTemplateUpdate(BaseModel):
    name: Optional[str] = None
    room_type: Optional[str] = None
    region: Optional[str] = None
    micro_location: Optional[str] = None
    concept: Optional[str] = None
    capacity_label: Optional[str] = None
    pax: Optional[int] = None
    breakfast_included: Optional[bool] = None
    min_nights: Optional[int] = None
    features: Optional[List[str]] = None
    guest_restrictions: Optional[List[str]] = None
    image_urls: Optional[List[str]] = None
    price_suggestion: Optional[float] = None
    notes: Optional[str] = None


class RoomTemplatePublic(BaseModel):
    id: str
    hotel_id: str
    name: str
    room_type: str
    region: str
    micro_location: str
    concept: str
    capacity_label: str
    pax: int
    breakfast_included: bool
    min_nights: int
    features: Optional[List[str]] = None
    guest_restrictions: Optional[List[str]] = None
    image_urls: Optional[List[str]] = None
    price_suggestion: Optional[float] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class RequestCreate(BaseModel):
    listing_id: str
    guest_type: str = Field(pattern="^(family|couple|group)$")
    notes: Optional[str] = None
    confirm_window_minutes: int = 120


class AlternativePayload(BaseModel):
    notes: Optional[str] = None
    proposed_price_min: Optional[float] = None
    proposed_price_max: Optional[float] = None
    proposed_date_start: Optional[datetime] = None
    proposed_date_end: Optional[datetime] = None


class RequestPublic(BaseModel):
    id: str
    listing_id: str
    from_hotel_id: str
    to_hotel_id: str
    guest_type: str
    notes: Optional[str]
    confirm_window_minutes: int
    status: str
    alternative_payload: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


class AlternativeOffer(BaseModel):
    notes: Optional[str] = None
    proposed_price_min: Optional[float] = None
    proposed_price_max: Optional[float] = None
    proposed_date_start: Optional[datetime] = None
    proposed_date_end: Optional[datetime] = None


class MatchPublic(BaseModel):
    id: str
    request_id: str
    listing_id: str
    hotel_a_id: str
    hotel_b_id: str
    reference_code: str
    fee_amount: float
    fee_status: str
    accepted_at: datetime
    created_at: datetime


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


# --- Inventory Schemas ------------------------------------------------------

class InventoryItemCreate(BaseModel):
    room_type: str                               # bungalov, suite, standart, villa, apart, dag_evi
    room_type_name: str                          # Göl Manzaralı Bungalov
    total_rooms: int = Field(ge=1)
    description: Optional[str] = None
    features: Optional[List[str]] = None
    capacity_label: Optional[str] = None         # 2+1, 3+1, etc
    pax: Optional[int] = None
    image_urls: Optional[List[str]] = None


class InventoryItemUpdate(BaseModel):
    room_type_name: Optional[str] = None
    total_rooms: Optional[int] = None
    description: Optional[str] = None
    features: Optional[List[str]] = None
    capacity_label: Optional[str] = None
    pax: Optional[int] = None
    image_urls: Optional[List[str]] = None


class InventoryItemPublic(BaseModel):
    id: str
    hotel_id: str
    room_type: str
    room_type_name: str
    total_rooms: int
    description: Optional[str] = None
    features: Optional[List[str]] = None
    capacity_label: Optional[str] = None
    pax: Optional[int] = None
    image_urls: Optional[List[str]] = None
    created_at: datetime
    updated_at: datetime


class AvailabilityBulkSet(BaseModel):
    """Toplu tarih aralığı müsaitlik ayarı"""
    inventory_id: str
    date_start: str                              # YYYY-MM-DD
    date_end: str                                # YYYY-MM-DD
    available_rooms: int = Field(ge=0)
    price_per_night: Optional[float] = None
    notes: Optional[str] = None


class DailyAvailabilityPublic(BaseModel):
    id: str
    hotel_id: str
    inventory_id: str
    date: str                                    # YYYY-MM-DD
    available_rooms: int
    booked_rooms: int
    total_rooms: int
    price_per_night: Optional[float] = None
    notes: Optional[str] = None


# --- Pricing Engine Schemas -------------------------------------------------

class PricingRuleCreate(BaseModel):
    name: str
    rule_type: str = Field(pattern="^(seasonal|weekend|occupancy|early_bird|last_minute|holiday)$")
    room_type: Optional[str] = None              # None = tüm oda tipleri
    multiplier: float = Field(ge=0.1, le=5.0)    # Fiyat çarpanı (1.0 = değişiklik yok)
    # Seasonal params
    date_start: Optional[str] = None             # YYYY-MM-DD
    date_end: Optional[str] = None               # YYYY-MM-DD
    # Occupancy params
    occupancy_threshold_min: Optional[float] = None  # 0.0-1.0
    occupancy_threshold_max: Optional[float] = None  # 0.0-1.0
    # Early bird / last minute params
    days_before_min: Optional[int] = None
    days_before_max: Optional[int] = None
    # Weekend days (0=Mon ... 6=Sun)
    weekend_days: Optional[List[int]] = None
    is_active: bool = True
    priority: int = 0                            # Yüksek = öncelikli


class PricingRuleUpdate(BaseModel):
    name: Optional[str] = None
    rule_type: Optional[str] = None
    room_type: Optional[str] = None
    multiplier: Optional[float] = None
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    occupancy_threshold_min: Optional[float] = None
    occupancy_threshold_max: Optional[float] = None
    days_before_min: Optional[int] = None
    days_before_max: Optional[int] = None
    weekend_days: Optional[List[int]] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None


class PricingRulePublic(BaseModel):
    id: str
    hotel_id: str
    name: str
    rule_type: str
    room_type: Optional[str] = None
    multiplier: float
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    occupancy_threshold_min: Optional[float] = None
    occupancy_threshold_max: Optional[float] = None
    days_before_min: Optional[int] = None
    days_before_max: Optional[int] = None
    weekend_days: Optional[List[int]] = None
    is_active: bool
    priority: int
    created_at: datetime
    updated_at: datetime


class PriceCalculateRequest(BaseModel):
    room_type: str
    date_start: str                              # YYYY-MM-DD
    date_end: str                                # YYYY-MM-DD
    base_price: float
    pax: Optional[int] = None


# --- Payment & Invoice & Subscription Schemas ------------------------------

class PaymentInitiate(BaseModel):
    match_id: str
    method: str = "credit_card"                  # credit_card, bank_transfer, mock

class PaymentPublic(BaseModel):
    id: str
    hotel_id: str
    match_id: str
    amount: float
    currency: str = "TRY"
    status: str                                  # pending, completed, failed, refunded
    method: str
    reference_code: Optional[str] = None
    invoice_id: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

class InvoicePublic(BaseModel):
    id: str
    hotel_id: str
    payment_id: str
    match_id: str
    invoice_number: str
    hotel_name: str
    hotel_address: str
    items: List[Dict[str, Any]]
    subtotal: float
    tax_rate: float
    tax_amount: float
    total: float
    currency: str = "TRY"
    status: str                                  # issued, paid, cancelled
    created_at: datetime

class SubscriptionPublic(BaseModel):
    id: str
    hotel_id: str
    plan_id: str
    plan_name: str
    billing_cycle: str                           # monthly, yearly
    price: float
    max_matches: int
    matches_used: int
    status: str                                  # active, cancelled, expired
    started_at: datetime
    expires_at: datetime
    cancelled_at: Optional[datetime] = None

class NotificationPublic(BaseModel):
    id: str
    hotel_id: str
    type: str                                    # request_received, match_created, payment_received, alternative_offered, etc.
    title: str
    message: str
    is_read: bool
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime


# --- Google Sheets Schemas --------------------------------------------------

class SheetsConfigSave(BaseModel):
    client_id: str
    client_secret: str
    spreadsheet_id: Optional[str] = None   # boş ise otomatik oluşturulur

class SheetsConfigPublic(BaseModel):
    hotel_id: str
    client_id: str          # maskelenir: sadece başı gösterilir
    spreadsheet_id: Optional[str] = None
    connected: bool         # token var mı?
    google_email: Optional[str] = None
    connected_at: Optional[datetime] = None

SHEETS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


# --- Activity logging & counters -------------------------------------------

async def log_activity(actor_hotel_id: str, action: str, entity: str, entity_id: str, metadata: Optional[Dict[str, Any]] = None) -> None:
    doc = {
        "actor_hotel_id": actor_hotel_id,
        "action": action,
        "entity": entity,
        "entity_id": entity_id,
        "metadata": metadata or {},
        "created_at": now_utc(),
    }
    await db.activity_logs.insert_one(doc)


async def next_reference_code(region: str) -> str:
    region_info = REGIONS.get(region)
    if region_info:
        region_prefix = region_info["prefix"]
    else:
        region_prefix = "SPC" if region.lower().startswith("sapanca") else "KTP"
    year = datetime.now(timezone.utc).year
    key = f"{region_prefix}-{year}"
    res = await db.counters.find_one_and_update(
        {"_id": key},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True,
    )
    seq = res.get("seq", 1)
    return f"{region_prefix}-{year}-{seq:05d}"


# --- FastAPI app & router ---------------------------------------------------

app = FastAPI(title="Hotel-to-Hotel Capacity Exchange Platform")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
api = APIRouter(prefix="/api")


# --- Notification Helper ---------------------------------------------------

async def create_notification(hotel_id: str, ntype: str, title: str, message: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    doc = {
        "_id": str(uuid.uuid4()),
        "hotel_id": hotel_id,
        "type": ntype,
        "title": title,
        "message": message,
        "is_read": False,
        "metadata": metadata or {},
        "created_at": now_utc(),
    }
    await db.notifications.insert_one(doc)
    return doc["_id"]


async def get_region_match_fee(region: str) -> float:
    """Bölge bazlı eşleşme ücretini döndürür."""
    # Önce admin tarafından ayarlanmış bölge fiyatını kontrol et
    custom = await db.region_pricing.find_one({"_id": region})
    if custom and "match_fee" in custom:
        return float(custom["match_fee"])
    region_info = REGIONS.get(region)
    if region_info:
        return region_info["match_fee"]
    return MATCH_FEE_TL


async def auto_create_invoice(hotel_id: str, payment_id: str, match_id: str, amount: float) -> str:
    """Ödeme tamamlandığında otomatik fatura oluşturur."""
    hotel = await db.hotels.find_one({"_id": hotel_id})
    hotel_name = hotel.get("name", "Bilinmeyen Otel") if hotel else "Bilinmeyen Otel"
    hotel_addr = hotel.get("address", "") if hotel else ""

    # Invoice numarası oluştur
    year = datetime.now(timezone.utc).year
    seq_key = f"INV-{year}"
    seq_res = await db.counters.find_one_and_update(
        {"_id": seq_key}, {"$inc": {"seq": 1}}, upsert=True, return_document=True
    )
    seq = seq_res.get("seq", 1)
    invoice_number = f"INV-{year}-{seq:06d}"

    tax_rate = 0.20
    subtotal = amount
    tax_amount = round(subtotal * tax_rate, 2)
    total = round(subtotal + tax_amount, 2)

    doc = {
        "_id": str(uuid.uuid4()),
        "hotel_id": hotel_id,
        "payment_id": payment_id,
        "match_id": match_id,
        "invoice_number": invoice_number,
        "hotel_name": hotel_name,
        "hotel_address": hotel_addr,
        "items": [{"description": "Kapasite Eşleşme Ücreti", "quantity": 1, "unit_price": amount, "total": amount}],
        "subtotal": subtotal,
        "tax_rate": tax_rate,
        "tax_amount": tax_amount,
        "total": total,
        "currency": "TRY",
        "status": "issued",
        "created_at": now_utc(),
    }
    await db.invoices.insert_one(doc)
    return doc["_id"]


# --- Auth endpoints ---------------------------------------------------------

@api.post("/auth/register-upload")
async def register_upload(file: UploadFile = File(...)):
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
async def change_password(req: ChangePasswordRequest, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    if not verify_password(req.current_password, current_hotel["password_hash"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mevcut şifre yanlış")
    # Yeni şifre güvenlik kontrolü
    validate_password(req.new_password)
    new_hash = get_password_hash(req.new_password)
    await db.hotels.update_one({"_id": current_hotel["_id"]}, {"$set": {"password_hash": new_hash, "updated_at": now_utc()}})
    return {"message": "Şifre güncellendi"}


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

    now = now_utc()
    await db.requests.update_one({"_id": req["_id"]}, {"$set": {"status": "accepted", "updated_at": now}})
    await db.availability_listings.update_one({"_id": listing["_id"]}, {"$set": {"is_locked": False, "lock_request_id": None, "updated_at": now}})

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
        "accepted_at": now,
        "created_at": now,
    }
    await db.matches.insert_one(match_doc)
    await log_activity(current_hotel["_id"], "accept", "request", req["_id"], {"match_id": match_id})

    # Envanter otomatik güncelle
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

    now = now_utc()
    await db.requests.update_one({"_id": req["_id"]}, {"$set": {"status": "accepted", "updated_at": now}})
    await db.availability_listings.update_one({"_id": listing["_id"]}, {"$set": {"is_locked": False, "lock_request_id": None, "updated_at": now}})

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
        "accepted_at": now,
        "created_at": now,
    }
    await db.matches.insert_one(match_doc)
    await log_activity(current_hotel["_id"], "accept_alternative", "request", req["_id"], {"match_id": match_id})

    # Envanter otomatik güncelle
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
            "self": serialize_doc(hotel_a if hotel_a["_id"] == current_hotel["_id"] else hotel_b),
            "other": serialize_doc(hotel_b if hotel_a["_id"] == current_hotel["_id"] else hotel_a),
        },
    }


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


# --- Admin endpoints --------------------------------------------------------

@api.get("/admin/overview")
async def admin_overview(admin: Dict[str, Any] = Depends(get_current_admin)):
    total_hotels = await db.hotels.count_documents({})
    total_listings = await db.availability_listings.count_documents({})
    total_requests = await db.requests.count_documents({})
    total_matches = await db.matches.count_documents({})

    # Fee totals
    matches_cursor = db.matches.find({})
    matches = await matches_cursor.to_list(length=10000)
    total_fees = sum(m.get("fee_amount", 0) for m in matches)
    paid_fees = sum(m.get("fee_amount", 0) for m in matches if m.get("fee_status") == "paid")
    due_fees = sum(m.get("fee_amount", 0) for m in matches if m.get("fee_status") == "due")

    # Recent activity
    recent_logs_cursor = db.activity_logs.find({}).sort("created_at", -1).limit(20)
    recent_logs = await recent_logs_cursor.to_list(length=20)
    for log in recent_logs:
        log["id"] = str(log.pop("_id"))
        if isinstance(log.get("created_at"), datetime):
            log["created_at"] = log["created_at"].isoformat()

    return {
        "total_hotels": total_hotels,
        "total_listings": total_listings,
        "total_requests": total_requests,
        "total_matches": total_matches,
        "total_fees": total_fees,
        "paid_fees": paid_fees,
        "due_fees": due_fees,
        "recent_activity": recent_logs,
    }


@api.get("/admin/hotels")
async def admin_list_hotels(
    status_filter: Optional[str] = None,  # pending_review | approved | rejected | all
    admin: Dict[str, Any] = Depends(get_current_admin)
):
    query = {}
    if status_filter and status_filter != "all":
        query["approval_status"] = status_filter
    cursor = db.hotels.find(query).sort("created_at", -1)
    docs = await cursor.to_list(length=1000)
    result = []
    for doc in docs:
        hotel_id = doc["_id"]
        match_count = await db.matches.count_documents({"$or": [{"hotel_a_id": hotel_id}, {"hotel_b_id": hotel_id}]})
        listing_count = await db.availability_listings.count_documents({"hotel_id": hotel_id})
        result.append({
            "id": hotel_id,
            "name": doc["name"],
            "email": doc["email"],
            "region": doc["region"],
            "concept": doc["concept"],
            "phone": doc["phone"],
            "address": doc.get("address", ""),
            "contact_person": doc.get("contact_person", ""),
            "is_admin": doc.get("is_admin", False),
            "approval_status": doc.get("approval_status", "approved"),
            "rejection_reason": doc.get("rejection_reason"),
            "documents": doc.get("documents", []),
            "created_at": doc["created_at"].isoformat() if isinstance(doc.get("created_at"), datetime) else None,
            "match_count": match_count,
            "listing_count": listing_count,
        })
    return result


@api.put("/admin/hotels/{hotel_id}/approve")
async def admin_approve_hotel(hotel_id: str, admin: Dict[str, Any] = Depends(get_current_admin)):
    hotel = await db.hotels.find_one({"_id": hotel_id})
    if not hotel:
        raise HTTPException(status_code=404, detail="Otel bulunamadı")
    await db.hotels.update_one(
        {"_id": hotel_id},
        {"$set": {"approval_status": "approved", "rejection_reason": None, "updated_at": now_utc()}}
    )
    await log_activity(admin["_id"], "approve_hotel", "hotel", hotel_id, {"hotel_name": hotel.get("name")})
    return {"id": hotel_id, "approval_status": "approved", "message": f"{hotel.get('name')} onaylandı."}


@api.put("/admin/hotels/{hotel_id}/reject")
async def admin_reject_hotel(hotel_id: str, body: Dict[str, str], admin: Dict[str, Any] = Depends(get_current_admin)):
    hotel = await db.hotels.find_one({"_id": hotel_id})
    if not hotel:
        raise HTTPException(status_code=404, detail="Otel bulunamadı")
    reason = body.get("reason", "")
    await db.hotels.update_one(
        {"_id": hotel_id},
        {"$set": {"approval_status": "rejected", "rejection_reason": reason, "updated_at": now_utc()}}
    )
    await log_activity(admin["_id"], "reject_hotel", "hotel", hotel_id, {"reason": reason})
    return {"id": hotel_id, "approval_status": "rejected", "message": f"{hotel.get('name')} reddedildi."}


@api.get("/admin/matches")
async def admin_list_matches(admin: Dict[str, Any] = Depends(get_current_admin)):
    cursor = db.matches.find({}).sort("created_at", -1).limit(200)
    docs = await cursor.to_list(length=200)
    result = []
    for d in docs:
        hotel_a = await db.hotels.find_one({"_id": d["hotel_a_id"]})
        hotel_b = await db.hotels.find_one({"_id": d["hotel_b_id"]})
        result.append({
            "id": d["_id"],
            "reference_code": d["reference_code"],
            "hotel_a_name": hotel_a["name"] if hotel_a else "?",
            "hotel_b_name": hotel_b["name"] if hotel_b else "?",
            "fee_amount": d["fee_amount"],
            "fee_status": d["fee_status"],
            "accepted_at": d["accepted_at"].isoformat() if isinstance(d.get("accepted_at"), datetime) else None,
        })
    return result


@api.put("/admin/hotels/{hotel_id}/toggle-admin")
async def admin_toggle_admin(hotel_id: str, admin: Dict[str, Any] = Depends(get_current_admin)):
    hotel = await db.hotels.find_one({"_id": hotel_id})
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    new_val = not hotel.get("is_admin", False)
    await db.hotels.update_one({"_id": hotel_id}, {"$set": {"is_admin": new_val, "updated_at": now_utc()}})
    return {"id": hotel_id, "is_admin": new_val}


@api.put("/admin/matches/{match_id}/fee-status")
async def admin_update_fee_status(match_id: str, body: Dict[str, str], admin: Dict[str, Any] = Depends(get_current_admin)):
    new_status = body.get("fee_status")
    if new_status not in ("due", "paid", "waived"):
        raise HTTPException(status_code=400, detail="Invalid fee_status")
    await db.matches.update_one({"_id": match_id}, {"$set": {"fee_status": new_status}})
    return {"id": match_id, "fee_status": new_status}


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


# --- File Upload ------------------------------------------------------------

import shutil
import mimetypes

UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_FILE_SIZE_MB = 10


@api.post("/upload-image")
async def upload_image(
    file: UploadFile = File(...),
    current_hotel: Dict[str, Any] = Depends(get_current_hotel),
):
    # MIME type kontrolü
    mime = file.content_type or mimetypes.guess_type(file.filename or "")[0] or ""
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Sadece JPG, PNG, WEBP veya GIF yükleyebilirsiniz.")

    # Boyut kontrolü (chunk okuyarak)
    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    contents = await file.read()
    if len(contents) > max_bytes:
        raise HTTPException(status_code=400, detail=f"Dosya boyutu {MAX_FILE_SIZE_MB} MB'dan küçük olmalıdır.")

    # Benzersiz dosya adı
    ext = Path(file.filename or "image.jpg").suffix.lower() or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / filename

    with open(dest, "wb") as f:
        f.write(contents)

    await log_activity(current_hotel["_id"], "upload_image", "file", filename, {"original": file.filename})
    return {"filename": filename, "url": f"/api/files/{filename}"}


@api.get("/files/{filename}")
async def serve_file(filename: str):
    file_path = UPLOAD_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Dosya bulunamadı")
    # Path traversal önlemi
    if UPLOAD_DIR not in file_path.parents and file_path.parent != UPLOAD_DIR:
        raise HTTPException(status_code=403, detail="Yasak")
    return FileResponse(str(file_path))


# ============================================================================
# --- Hotel Inventory System -------------------------------------------------
# ============================================================================

def inventory_to_public(doc: Dict[str, Any]) -> InventoryItemPublic:
    return InventoryItemPublic(
        id=doc["_id"],
        hotel_id=doc["hotel_id"],
        room_type=doc["room_type"],
        room_type_name=doc["room_type_name"],
        total_rooms=doc["total_rooms"],
        description=doc.get("description"),
        features=doc.get("features"),
        capacity_label=doc.get("capacity_label"),
        pax=doc.get("pax"),
        image_urls=doc.get("image_urls"),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


@api.post("/inventory", response_model=InventoryItemPublic)
async def create_inventory_item(payload: InventoryItemCreate, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """Yeni oda tipi envanteri oluştur."""
    inv_id = str(uuid.uuid4())
    now = now_utc()
    doc = {
        "_id": inv_id,
        "hotel_id": current_hotel["_id"],
        "room_type": payload.room_type,
        "room_type_name": payload.room_type_name,
        "total_rooms": payload.total_rooms,
        "description": payload.description,
        "features": payload.features or [],
        "capacity_label": payload.capacity_label,
        "pax": payload.pax,
        "image_urls": payload.image_urls or [],
        "created_at": now,
        "updated_at": now,
    }
    await db.inventory.insert_one(doc)
    await log_activity(current_hotel["_id"], "create", "inventory", inv_id, {"room_type": payload.room_type, "total_rooms": payload.total_rooms})
    return inventory_to_public(doc)


@api.get("/inventory", response_model=List[InventoryItemPublic])
async def list_inventory(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """Otelin tüm envanter kalemlerini listele."""
    cursor = db.inventory.find({"hotel_id": current_hotel["_id"]}).sort("created_at", -1)
    docs = await cursor.to_list(length=200)
    return [inventory_to_public(d) for d in docs]


@api.get("/inventory/{inv_id}", response_model=InventoryItemPublic)
async def get_inventory_item(inv_id: str, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    doc = await db.inventory.find_one({"_id": inv_id, "hotel_id": current_hotel["_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Envanter kalemi bulunamadı")
    return inventory_to_public(doc)


@api.put("/inventory/{inv_id}", response_model=InventoryItemPublic)
async def update_inventory_item(inv_id: str, payload: InventoryItemUpdate, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    doc = await db.inventory.find_one({"_id": inv_id, "hotel_id": current_hotel["_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Envanter kalemi bulunamadı")

    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        return inventory_to_public(doc)
    updates["updated_at"] = now_utc()
    await db.inventory.update_one({"_id": inv_id}, {"$set": updates})
    await log_activity(current_hotel["_id"], "update", "inventory", inv_id, {"fields": list(updates.keys())})
    refreshed = await db.inventory.find_one({"_id": inv_id})
    return inventory_to_public(refreshed)


@api.delete("/inventory/{inv_id}")
async def delete_inventory_item(inv_id: str, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    doc = await db.inventory.find_one({"_id": inv_id, "hotel_id": current_hotel["_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Envanter kalemi bulunamadı")
    # İlişkili günlük müsaitlikleri de sil
    await db.daily_availability.delete_many({"inventory_id": inv_id})
    await db.inventory.delete_one({"_id": inv_id})
    await log_activity(current_hotel["_id"], "delete", "inventory", inv_id, {})
    return {"message": "Envanter kalemi ve ilişkili müsaitlikler silindi"}


@api.post("/inventory/availability/bulk")
async def set_availability_bulk(payload: AvailabilityBulkSet, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """Tarih aralığı için toplu müsaitlik ayarla."""
    inv = await db.inventory.find_one({"_id": payload.inventory_id, "hotel_id": current_hotel["_id"]})
    if not inv:
        raise HTTPException(status_code=404, detail="Envanter kalemi bulunamadı")

    if payload.available_rooms > inv["total_rooms"]:
        raise HTTPException(status_code=400, detail=f"Müsait oda sayısı toplam oda sayısından ({inv['total_rooms']}) fazla olamaz")

    try:
        d_start = date.fromisoformat(payload.date_start)
        d_end = date.fromisoformat(payload.date_end)
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz tarih formatı. YYYY-MM-DD kullanın.")

    if d_start > d_end:
        raise HTTPException(status_code=400, detail="Başlangıç tarihi bitiş tarihinden sonra olamaz")

    if (d_end - d_start).days > 365:
        raise HTTPException(status_code=400, detail="En fazla 365 günlük aralık ayarlanabilir")

    updated_count = 0
    current_date = d_start
    while current_date <= d_end:
        date_str = current_date.isoformat()
        existing = await db.daily_availability.find_one({
            "inventory_id": payload.inventory_id,
            "date": date_str,
        })

        booked = existing.get("booked_rooms", 0) if existing else 0
        if payload.available_rooms < booked:
            raise HTTPException(
                status_code=400,
                detail=f"{date_str} tarihinde {booked} oda zaten rezerveli. Müsait oda sayısı bundan az olamaz."
            )

        avail_doc = {
            "hotel_id": current_hotel["_id"],
            "inventory_id": payload.inventory_id,
            "date": date_str,
            "available_rooms": payload.available_rooms,
            "booked_rooms": booked,
            "total_rooms": inv["total_rooms"],
            "price_per_night": payload.price_per_night,
            "notes": payload.notes,
            "updated_at": now_utc(),
        }

        if existing:
            await db.daily_availability.update_one({"_id": existing["_id"]}, {"$set": avail_doc})
        else:
            avail_doc["_id"] = str(uuid.uuid4())
            avail_doc["created_at"] = now_utc()
            await db.daily_availability.insert_one(avail_doc)

        updated_count += 1
        current_date += timedelta(days=1)

    await log_activity(current_hotel["_id"], "bulk_availability", "inventory", payload.inventory_id,
                       {"date_start": payload.date_start, "date_end": payload.date_end, "available_rooms": payload.available_rooms, "days": updated_count})

    return {"message": f"{updated_count} günlük müsaitlik güncellendi", "days_updated": updated_count}


@api.get("/inventory/{inv_id}/calendar")
async def get_inventory_calendar(
    inv_id: str,
    month: Optional[str] = None,  # YYYY-MM
    current_hotel: Dict[str, Any] = Depends(get_current_hotel),
):
    """Belirli envanter kalemi için takvim görünümü."""
    inv = await db.inventory.find_one({"_id": inv_id, "hotel_id": current_hotel["_id"]})
    if not inv:
        raise HTTPException(status_code=404, detail="Envanter kalemi bulunamadı")

    if month:
        try:
            year, mon = map(int, month.split("-"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Geçersiz ay formatı. YYYY-MM kullanın.")
    else:
        now = now_utc()
        year, mon = now.year, now.month

    # Ayın ilk ve son günü
    first_day = date(year, mon, 1)
    if mon == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, mon + 1, 1) - timedelta(days=1)

    cursor = db.daily_availability.find({
        "inventory_id": inv_id,
        "date": {"$gte": first_day.isoformat(), "$lte": last_day.isoformat()},
    }).sort("date", 1)
    docs = await cursor.to_list(length=31)

    # Tüm günleri doldur
    calendar_data = {}
    current_d = first_day
    while current_d <= last_day:
        calendar_data[current_d.isoformat()] = {
            "date": current_d.isoformat(),
            "available_rooms": inv["total_rooms"],
            "booked_rooms": 0,
            "total_rooms": inv["total_rooms"],
            "price_per_night": None,
            "has_data": False,
        }
        current_d += timedelta(days=1)

    for d in docs:
        calendar_data[d["date"]] = {
            "date": d["date"],
            "available_rooms": d["available_rooms"],
            "booked_rooms": d.get("booked_rooms", 0),
            "total_rooms": d.get("total_rooms", inv["total_rooms"]),
            "price_per_night": d.get("price_per_night"),
            "has_data": True,
        }

    return {
        "inventory_id": inv_id,
        "room_type_name": inv["room_type_name"],
        "room_type": inv["room_type"],
        "total_rooms": inv["total_rooms"],
        "month": f"{year}-{mon:02d}",
        "days": list(calendar_data.values()),
    }


@api.get("/inventory/summary/all")
async def get_inventory_summary(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """Otelin tüm envanter özeti - bugünkü durum."""
    today_str = date.today().isoformat()
    inv_cursor = db.inventory.find({"hotel_id": current_hotel["_id"]})
    inventories = await inv_cursor.to_list(length=200)

    summary = []
    for inv in inventories:
        # Bugünkü müsaitlik
        today_avail = await db.daily_availability.find_one({
            "inventory_id": inv["_id"],
            "date": today_str,
        })

        # Bu ay toplam rezervasyon sayısı
        now = now_utc()
        first_of_month = date(now.year, now.month, 1).isoformat()
        if now.month == 12:
            last_of_month = date(now.year + 1, 1, 1).isoformat()
        else:
            last_of_month = date(now.year, now.month + 1, 1).isoformat()

        month_cursor = db.daily_availability.find({
            "inventory_id": inv["_id"],
            "date": {"$gte": first_of_month, "$lt": last_of_month},
            "booked_rooms": {"$gt": 0},
        })
        month_bookings = await month_cursor.to_list(length=31)
        total_booked_nights = sum(d.get("booked_rooms", 0) for d in month_bookings)

        # Doluluk oranı hesapla
        total_capacity_this_month = inv["total_rooms"] * 30
        occupancy_rate = round(total_booked_nights / total_capacity_this_month * 100, 1) if total_capacity_this_month > 0 else 0

        summary.append({
            "inventory_id": inv["_id"],
            "room_type": inv["room_type"],
            "room_type_name": inv["room_type_name"],
            "total_rooms": inv["total_rooms"],
            "today_available": today_avail["available_rooms"] if today_avail else inv["total_rooms"],
            "today_booked": today_avail.get("booked_rooms", 0) if today_avail else 0,
            "today_price": today_avail.get("price_per_night") if today_avail else None,
            "month_booked_nights": total_booked_nights,
            "occupancy_rate": occupancy_rate,
            "capacity_label": inv.get("capacity_label"),
            "pax": inv.get("pax"),
        })

    return {"hotel_id": current_hotel["_id"], "date": today_str, "items": summary}


# --- Auto-update inventory on match acceptance ---
async def _decrement_inventory_on_match(listing_doc: Dict[str, Any]) -> None:
    """Eşleşme kabul edildiğinde envanter otomatik güncelle."""
    hotel_id = listing_doc.get("hotel_id")
    room_type = listing_doc.get("room_type")
    if not hotel_id or not room_type:
        return

    # İlgili envanter kalemini bul
    inv = await db.inventory.find_one({"hotel_id": hotel_id, "room_type": room_type})
    if not inv:
        return

    # Tarih aralığındaki her gün için booked_rooms artır
    date_start = listing_doc.get("date_start")
    date_end = listing_doc.get("date_end")
    if not date_start or not date_end:
        return

    if isinstance(date_start, datetime):
        d_start = date_start.date()
    else:
        d_start = date.fromisoformat(str(date_start)[:10])

    if isinstance(date_end, datetime):
        d_end = date_end.date()
    else:
        d_end = date.fromisoformat(str(date_end)[:10])

    current_d = d_start
    while current_d <= d_end:
        date_str = current_d.isoformat()
        existing = await db.daily_availability.find_one({
            "inventory_id": inv["_id"],
            "date": date_str,
        })

        if existing:
            new_booked = existing.get("booked_rooms", 0) + 1
            new_available = max(existing.get("available_rooms", inv["total_rooms"]) - 1, 0)
            await db.daily_availability.update_one(
                {"_id": existing["_id"]},
                {"$set": {"booked_rooms": new_booked, "available_rooms": new_available, "updated_at": now_utc()}}
            )
        else:
            await db.daily_availability.insert_one({
                "_id": str(uuid.uuid4()),
                "hotel_id": hotel_id,
                "inventory_id": inv["_id"],
                "date": date_str,
                "available_rooms": max(inv["total_rooms"] - 1, 0),
                "booked_rooms": 1,
                "total_rooms": inv["total_rooms"],
                "price_per_night": None,
                "notes": None,
                "created_at": now_utc(),
                "updated_at": now_utc(),
            })

        current_d += timedelta(days=1)


@api.post("/inventory/check-availability")
async def check_availability(
    room_type: str,
    date_start: str,
    date_end: str,
    current_hotel: Dict[str, Any] = Depends(get_current_hotel),
):
    """Belirli tarih aralığında oda tipi müsaitliğini kontrol et (overbooking engelleme)."""
    inv = await db.inventory.find_one({"hotel_id": current_hotel["_id"], "room_type": room_type})
    if not inv:
        return {"available": True, "message": "Bu oda tipi için envanter tanımı yok, ilan oluşturulabilir", "min_available": None}

    try:
        d_start = date.fromisoformat(date_start)
        d_end = date.fromisoformat(date_end)
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz tarih formatı")

    min_available = inv["total_rooms"]
    problem_dates = []
    current_d = d_start
    while current_d <= d_end:
        date_str = current_d.isoformat()
        avail = await db.daily_availability.find_one({
            "inventory_id": inv["_id"],
            "date": date_str,
        })
        if avail:
            available = avail.get("available_rooms", inv["total_rooms"])
            if available < min_available:
                min_available = available
            if available <= 0:
                problem_dates.append(date_str)

        current_d += timedelta(days=1)

    return {
        "available": min_available > 0,
        "min_available": min_available,
        "total_rooms": inv["total_rooms"],
        "problem_dates": problem_dates,
        "message": "Müsait" if min_available > 0 else f"Bu tarih aralığında müsait oda yok: {', '.join(problem_dates[:5])}",
    }


# ============================================================================
# --- Advanced Pricing Engine ------------------------------------------------
# ============================================================================

def pricing_rule_to_public(doc: Dict[str, Any]) -> PricingRulePublic:
    return PricingRulePublic(
        id=doc["_id"],
        hotel_id=doc["hotel_id"],
        name=doc["name"],
        rule_type=doc["rule_type"],
        room_type=doc.get("room_type"),
        multiplier=doc["multiplier"],
        date_start=doc.get("date_start"),
        date_end=doc.get("date_end"),
        occupancy_threshold_min=doc.get("occupancy_threshold_min"),
        occupancy_threshold_max=doc.get("occupancy_threshold_max"),
        days_before_min=doc.get("days_before_min"),
        days_before_max=doc.get("days_before_max"),
        weekend_days=doc.get("weekend_days"),
        is_active=doc.get("is_active", True),
        priority=doc.get("priority", 0),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


@api.post("/pricing/rules", response_model=PricingRulePublic)
async def create_pricing_rule(payload: PricingRuleCreate, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    rule_id = str(uuid.uuid4())
    now = now_utc()
    doc = {
        "_id": rule_id,
        "hotel_id": current_hotel["_id"],
        **payload.model_dump(),
        "created_at": now,
        "updated_at": now,
    }
    await db.pricing_rules.insert_one(doc)
    await log_activity(current_hotel["_id"], "create", "pricing_rule", rule_id, {"name": payload.name, "type": payload.rule_type})
    return pricing_rule_to_public(doc)


@api.get("/pricing/rules", response_model=List[PricingRulePublic])
async def list_pricing_rules(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    cursor = db.pricing_rules.find({"hotel_id": current_hotel["_id"]}).sort("priority", -1)
    docs = await cursor.to_list(length=100)
    return [pricing_rule_to_public(d) for d in docs]


@api.put("/pricing/rules/{rule_id}", response_model=PricingRulePublic)
async def update_pricing_rule(rule_id: str, payload: PricingRuleUpdate, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    doc = await db.pricing_rules.find_one({"_id": rule_id, "hotel_id": current_hotel["_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Fiyatlama kuralı bulunamadı")

    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items()}
    if not updates:
        return pricing_rule_to_public(doc)
    updates["updated_at"] = now_utc()
    await db.pricing_rules.update_one({"_id": rule_id}, {"$set": updates})
    refreshed = await db.pricing_rules.find_one({"_id": rule_id})
    return pricing_rule_to_public(refreshed)


@api.delete("/pricing/rules/{rule_id}")
async def delete_pricing_rule(rule_id: str, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    doc = await db.pricing_rules.find_one({"_id": rule_id, "hotel_id": current_hotel["_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Fiyatlama kuralı bulunamadı")
    await db.pricing_rules.delete_one({"_id": rule_id})
    return {"message": "Fiyatlama kuralı silindi"}


async def _calculate_dynamic_price(hotel_id: str, room_type: str, target_date: date, base_price: float) -> Dict[str, Any]:
    """Belirli bir gün için dinamik fiyat hesapla."""
    rules_cursor = db.pricing_rules.find({
        "hotel_id": hotel_id,
        "is_active": True,
        "$or": [{"room_type": room_type}, {"room_type": None}],
    }).sort("priority", -1)
    rules = await rules_cursor.to_list(length=50)

    applied_rules = []
    final_multiplier = 1.0
    target_str = target_date.isoformat()
    today = date.today()
    days_until = (target_date - today).days

    for rule in rules:
        applies = False
        rule_type = rule["rule_type"]

        if rule_type == "seasonal":
            rs = rule.get("date_start")
            re = rule.get("date_end")
            if rs and re:
                applies = rs <= target_str <= re

        elif rule_type == "weekend":
            weekend_days = rule.get("weekend_days", [4, 5, 6])  # Cuma, Cumartesi, Pazar
            applies = target_date.weekday() in weekend_days

        elif rule_type == "occupancy":
            # Doluluk oranına bakarak karar ver
            inv = await db.inventory.find_one({"hotel_id": hotel_id, "room_type": room_type})
            if inv:
                avail = await db.daily_availability.find_one({"inventory_id": inv["_id"], "date": target_str})
                if avail and avail.get("total_rooms", 0) > 0:
                    occupancy = avail.get("booked_rooms", 0) / avail["total_rooms"]
                    occ_min = rule.get("occupancy_threshold_min", 0)
                    occ_max = rule.get("occupancy_threshold_max", 1)
                    applies = occ_min <= occupancy <= occ_max

        elif rule_type == "early_bird":
            db_min = rule.get("days_before_min", 30)
            db_max = rule.get("days_before_max", 365)
            applies = db_min <= days_until <= db_max

        elif rule_type == "last_minute":
            db_min = rule.get("days_before_min", 0)
            db_max = rule.get("days_before_max", 7)
            applies = db_min <= days_until <= db_max

        elif rule_type == "holiday":
            rs = rule.get("date_start")
            re = rule.get("date_end")
            if rs and re:
                applies = rs <= target_str <= re

        if applies:
            final_multiplier *= rule["multiplier"]
            applied_rules.append({
                "rule_id": rule["_id"],
                "name": rule["name"],
                "type": rule_type,
                "multiplier": rule["multiplier"],
            })

    calculated_price = round(base_price * final_multiplier, 2)

    return {
        "base_price": base_price,
        "final_price": calculated_price,
        "final_multiplier": round(final_multiplier, 4),
        "applied_rules": applied_rules,
        "date": target_str,
    }


@api.post("/pricing/calculate")
async def calculate_price(payload: PriceCalculateRequest, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """Tarih aralığı için dinamik fiyat hesapla."""
    try:
        d_start = date.fromisoformat(payload.date_start)
        d_end = date.fromisoformat(payload.date_end)
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz tarih formatı")

    if d_start > d_end:
        raise HTTPException(status_code=400, detail="Başlangıç tarihi bitiş tarihinden sonra olamaz")

    days = []
    total_price = 0.0
    current_d = d_start
    while current_d <= d_end:
        day_result = await _calculate_dynamic_price(
            current_hotel["_id"], payload.room_type, current_d, payload.base_price
        )
        days.append(day_result)
        total_price += day_result["final_price"]
        current_d += timedelta(days=1)

    night_count = len(days)
    avg_price = round(total_price / night_count, 2) if night_count > 0 else 0

    return {
        "room_type": payload.room_type,
        "date_start": payload.date_start,
        "date_end": payload.date_end,
        "base_price": payload.base_price,
        "total_price": round(total_price, 2),
        "average_price": avg_price,
        "night_count": night_count,
        "daily_breakdown": days,
    }


@api.get("/pricing/market-comparison")
async def market_comparison(
    room_type: Optional[str] = None,
    region: Optional[str] = None,
    current_hotel: Dict[str, Any] = Depends(get_current_hotel),
):
    """Piyasa karşılaştırması - benzer ilanlara göre fiyat önerisi."""
    query: Dict[str, Any] = {}
    if room_type:
        query["room_type"] = room_type
    if region:
        query["region"] = region

    # Aktif ilanları al (süresi geçmemiş)
    query["date_end"] = {"$gte": now_utc()}
    cursor = db.availability_listings.find(query).sort("created_at", -1).limit(100)
    listings = await cursor.to_list(length=100)

    if not listings:
        return {
            "room_type": room_type,
            "region": region,
            "sample_size": 0,
            "avg_price_min": None,
            "avg_price_max": None,
            "min_price": None,
            "max_price": None,
            "median_price": None,
            "my_avg_price": None,
            "recommendation": "Yeterli veri yok",
        }

    # Kendi ilanlarım vs. piyasa
    my_listings = [l for l in listings if l["hotel_id"] == current_hotel["_id"]]
    other_listings = [l for l in listings if l["hotel_id"] != current_hotel["_id"]]

    all_prices_min = [l["price_min"] for l in listings if l.get("price_min")]
    all_prices_max = [l["price_max"] for l in listings if l.get("price_max")]

    avg_min = round(sum(all_prices_min) / len(all_prices_min), 2) if all_prices_min else None
    avg_max = round(sum(all_prices_max) / len(all_prices_max), 2) if all_prices_max else None

    sorted_prices = sorted(all_prices_min)
    median_price = sorted_prices[len(sorted_prices) // 2] if sorted_prices else None

    my_prices = [l["price_min"] for l in my_listings if l.get("price_min")]
    my_avg = round(sum(my_prices) / len(my_prices), 2) if my_prices else None

    # Öneri
    recommendation = "Fiyatlarınız piyasa ortalamasında"
    if my_avg and avg_min:
        if my_avg > avg_min * 1.2:
            recommendation = "Fiyatlarınız piyasa ortalamasının %20'den fazla üstünde. İndirim düşünebilirsiniz."
        elif my_avg < avg_min * 0.8:
            recommendation = "Fiyatlarınız piyasa ortalamasının %20'den fazla altında. Fiyat artışı düşünebilirsiniz."

    return {
        "room_type": room_type,
        "region": region,
        "sample_size": len(listings),
        "my_listing_count": len(my_listings),
        "other_listing_count": len(other_listings),
        "avg_price_min": avg_min,
        "avg_price_max": avg_max,
        "min_price": min(all_prices_min) if all_prices_min else None,
        "max_price": max(all_prices_max) if all_prices_max else None,
        "median_price": median_price,
        "my_avg_price": my_avg,
        "recommendation": recommendation,
    }


@api.get("/pricing/history")
async def price_history(
    room_type: Optional[str] = None,
    months: int = 6,
    current_hotel: Dict[str, Any] = Depends(get_current_hotel),
):
    """Fiyat geçmişi - son N ay."""
    query: Dict[str, Any] = {"hotel_id": current_hotel["_id"]}
    if room_type:
        query["room_type"] = room_type

    # Son N ay
    now = now_utc()
    cutoff = now - timedelta(days=months * 30)
    query["created_at"] = {"$gte": cutoff}

    cursor = db.availability_listings.find(query).sort("created_at", -1)
    listings = await cursor.to_list(length=500)

    monthly_data: Dict[str, Dict[str, Any]] = {}
    for l in listings:
        month_key = l["created_at"].strftime("%Y-%m")
        if month_key not in monthly_data:
            monthly_data[month_key] = {"prices_min": [], "prices_max": [], "count": 0}
        monthly_data[month_key]["prices_min"].append(l.get("price_min", 0))
        monthly_data[month_key]["prices_max"].append(l.get("price_max", 0))
        monthly_data[month_key]["count"] += 1

    history = []
    for month_key in sorted(monthly_data.keys()):
        data = monthly_data[month_key]
        history.append({
            "month": month_key,
            "avg_price_min": round(sum(data["prices_min"]) / len(data["prices_min"]), 2),
            "avg_price_max": round(sum(data["prices_max"]) / len(data["prices_max"]), 2),
            "listing_count": data["count"],
            "min_price": min(data["prices_min"]),
            "max_price": max(data["prices_max"]),
        })

    return {"room_type": room_type, "months": months, "history": history}


# ============================================================================
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


# --- DB Indexes setup -------------------------------------------------------

async def ensure_indexes():
    """Performans indekslerini oluştur."""
    try:
        # Hotels
        await db.hotels.create_index("email", unique=True)
        await db.hotels.create_index("region")
        await db.hotels.create_index("approval_status")

        # Availability Listings
        await db.availability_listings.create_index("hotel_id")
        await db.availability_listings.create_index("region")
        await db.availability_listings.create_index("room_type")
        await db.availability_listings.create_index("date_end")
        await db.availability_listings.create_index("availability_status")
        await db.availability_listings.create_index("created_at")
        await db.availability_listings.create_index([("region", 1), ("date_end", -1)])
        await db.availability_listings.create_index([("hotel_id", 1), ("created_at", -1)])

        # Requests
        await db.requests.create_index("from_hotel_id")
        await db.requests.create_index("to_hotel_id")
        await db.requests.create_index("listing_id")
        await db.requests.create_index("status")
        await db.requests.create_index([("from_hotel_id", 1), ("created_at", -1)])
        await db.requests.create_index([("to_hotel_id", 1), ("created_at", -1)])

        # Matches
        await db.matches.create_index("hotel_a_id")
        await db.matches.create_index("hotel_b_id")
        await db.matches.create_index([("hotel_a_id", 1), ("hotel_b_id", 1)])
        await db.matches.create_index("accepted_at")

        # Inventory
        await db.inventory.create_index("hotel_id")
        await db.inventory.create_index([("hotel_id", 1), ("room_type", 1)])

        # Daily Availability
        await db.daily_availability.create_index("inventory_id")
        await db.daily_availability.create_index("hotel_id")
        await db.daily_availability.create_index("date")
        await db.daily_availability.create_index([("inventory_id", 1), ("date", 1)], unique=True)

        # Pricing Rules
        await db.pricing_rules.create_index("hotel_id")
        await db.pricing_rules.create_index([("hotel_id", 1), ("is_active", 1), ("priority", -1)])

        # Activity Logs
        await db.activity_logs.create_index("actor_hotel_id")
        await db.activity_logs.create_index("created_at")

        # Room Templates
        await db.room_templates.create_index("hotel_id")

        # Payments
        await db.payments.create_index("hotel_id")
        await db.payments.create_index("match_id")
        await db.payments.create_index([("hotel_id", 1), ("status", 1)])

        # Invoices
        await db.invoices.create_index("hotel_id")
        await db.invoices.create_index("payment_id")
        await db.invoices.create_index("invoice_number", unique=True)

        # Subscriptions
        await db.subscriptions.create_index("hotel_id")
        await db.subscriptions.create_index([("hotel_id", 1), ("status", 1)])

        # Notifications
        await db.notifications.create_index("hotel_id")
        await db.notifications.create_index([("hotel_id", 1), ("is_read", 1)])
        await db.notifications.create_index([("hotel_id", 1), ("created_at", -1)])

        # KVKK Requests
        await db.kvkk_requests.create_index("hotel_id")

    except Exception as e:
        print(f"Index creation warning: {e}")


# =============================================================================
# --- Payment System (Mock) --------------------------------------------------
# =============================================================================

@api.post("/payments/initiate")
@limiter.limit("10/minute")
async def initiate_payment(request: Request, payload: PaymentInitiate, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """Eşleşme için ödeme başlat (MOCK)."""
    match = await db.matches.find_one({"_id": payload.match_id})
    if not match:
        raise HTTPException(status_code=404, detail="Eşleşme bulunamadı")
    if match["hotel_a_id"] != current_hotel["_id"] and match["hotel_b_id"] != current_hotel["_id"]:
        raise HTTPException(status_code=403, detail="Bu eşleşme size ait değil")
    if match["fee_status"] == "paid":
        raise HTTPException(status_code=400, detail="Bu eşleşme zaten ödenmiş")

    # Mevcut ödeme var mı?
    existing = await db.payments.find_one({"match_id": payload.match_id, "hotel_id": current_hotel["_id"], "status": {"$in": ["pending", "completed"]}})
    if existing:
        raise HTTPException(status_code=400, detail="Bu eşleşme için zaten bir ödeme mevcut")

    payment_id = str(uuid.uuid4())
    now = now_utc()
    doc = {
        "_id": payment_id,
        "hotel_id": current_hotel["_id"],
        "match_id": payload.match_id,
        "amount": match["fee_amount"],
        "currency": "TRY",
        "status": "pending",
        "method": payload.method,
        "reference_code": f"PAY-{uuid.uuid4().hex[:8].upper()}",
        "invoice_id": None,
        "created_at": now,
        "completed_at": None,
    }
    await db.payments.insert_one(doc)
    return serialize_doc(doc)


@api.post("/payments/{payment_id}/complete")
async def complete_payment(payment_id: str, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """Ödemeyi tamamla (MOCK - gerçek ödeme entegrasyonu yerine)."""
    payment = await db.payments.find_one({"_id": payment_id})
    if not payment:
        raise HTTPException(status_code=404, detail="Ödeme bulunamadı")
    if payment["hotel_id"] != current_hotel["_id"]:
        raise HTTPException(status_code=403, detail="Bu ödeme size ait değil")
    if payment["status"] != "pending":
        raise HTTPException(status_code=400, detail="Bu ödeme tamamlanamaz")

    now = now_utc()
    # Fatura oluştur
    invoice_id = await auto_create_invoice(current_hotel["_id"], payment_id, payment["match_id"], payment["amount"])

    await db.payments.update_one({"_id": payment_id}, {"$set": {"status": "completed", "completed_at": now, "invoice_id": invoice_id}})
    await db.matches.update_one({"_id": payment["match_id"]}, {"$set": {"fee_status": "paid"}})

    # Bildirim
    await create_notification(current_hotel["_id"], "payment_completed", "Ödeme Tamamlandı", f"₺{payment['amount']:.2f} tutarındaki ödemeniz başarıyla alındı.", {"payment_id": payment_id})

    updated = await db.payments.find_one({"_id": payment_id})
    return serialize_doc(updated)


@api.get("/payments")
async def list_payments(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """Otelimin ödemeleri."""
    cursor = db.payments.find({"hotel_id": current_hotel["_id"]}).sort("created_at", -1)
    docs = await cursor.to_list(length=200)
    return [serialize_doc(d) for d in docs]


@api.get("/payments/{payment_id}")
async def get_payment(payment_id: str, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    payment = await db.payments.find_one({"_id": payment_id})
    if not payment:
        raise HTTPException(status_code=404, detail="Ödeme bulunamadı")
    if payment["hotel_id"] != current_hotel["_id"] and not current_hotel.get("is_admin"):
        raise HTTPException(status_code=403, detail="Yetkisiz")
    return serialize_doc(payment)


# =============================================================================
# --- Invoice System ----------------------------------------------------------
# =============================================================================

@api.get("/invoices")
async def list_invoices(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """Faturalarım."""
    cursor = db.invoices.find({"hotel_id": current_hotel["_id"]}).sort("created_at", -1)
    docs = await cursor.to_list(length=200)
    return [serialize_doc(d) for d in docs]


@api.get("/invoices/{invoice_id}")
async def get_invoice(invoice_id: str, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    invoice = await db.invoices.find_one({"_id": invoice_id})
    if not invoice:
        raise HTTPException(status_code=404, detail="Fatura bulunamadı")
    if invoice["hotel_id"] != current_hotel["_id"] and not current_hotel.get("is_admin"):
        raise HTTPException(status_code=403, detail="Yetkisiz")
    return serialize_doc(invoice)


# =============================================================================
# --- Subscription System -----------------------------------------------------
# =============================================================================

@api.get("/subscriptions/plans")
async def list_subscription_plans():
    """Mevcut abonelik planlarını listele."""
    return SUBSCRIPTION_PLANS


@api.post("/subscriptions/subscribe")
async def subscribe(body: Dict[str, str], current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """Bir plana abone ol."""
    plan_id = body.get("plan_id", "free")
    billing_cycle = body.get("billing_cycle", "monthly")

    plan = next((p for p in SUBSCRIPTION_PLANS if p["id"] == plan_id), None)
    if not plan:
        raise HTTPException(status_code=400, detail="Geçersiz plan")

    # Mevcut aktif abonelik varsa iptal et
    await db.subscriptions.update_many(
        {"hotel_id": current_hotel["_id"], "status": "active"},
        {"$set": {"status": "cancelled", "cancelled_at": now_utc()}}
    )

    now = now_utc()
    price = plan["price_yearly"] if billing_cycle == "yearly" else plan["price_monthly"]
    expires_at = now + timedelta(days=365 if billing_cycle == "yearly" else 30)

    sub_id = str(uuid.uuid4())
    doc = {
        "_id": sub_id,
        "hotel_id": current_hotel["_id"],
        "plan_id": plan_id,
        "plan_name": plan["name"],
        "billing_cycle": billing_cycle,
        "price": price,
        "max_matches": plan["max_matches_per_month"],
        "matches_used": 0,
        "status": "active",
        "started_at": now,
        "expires_at": expires_at,
        "cancelled_at": None,
    }
    await db.subscriptions.insert_one(doc)

    await create_notification(current_hotel["_id"], "subscription_created", "Abonelik Aktif", f"{plan['name']} planına abone oldunuz.", {"subscription_id": sub_id})
    return serialize_doc(doc)


@api.get("/subscriptions/my")
async def my_subscription(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """Aktif aboneliğimi getir."""
    sub = await db.subscriptions.find_one({"hotel_id": current_hotel["_id"], "status": "active"}, sort=[("started_at", -1)])
    if not sub:
        return {"plan_id": "free", "plan_name": "Ücretsiz", "max_matches": 5, "matches_used": 0, "status": "active"}
    return serialize_doc(sub)


@api.post("/subscriptions/cancel")
async def cancel_subscription(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """Aboneliği iptal et."""
    sub = await db.subscriptions.find_one({"hotel_id": current_hotel["_id"], "status": "active"})
    if not sub:
        raise HTTPException(status_code=400, detail="Aktif abonelik yok")
    await db.subscriptions.update_one({"_id": sub["_id"]}, {"$set": {"status": "cancelled", "cancelled_at": now_utc()}})
    return {"message": "Abonelik iptal edildi"}


# =============================================================================
# --- Notification System -----------------------------------------------------
# =============================================================================

@api.get("/notifications")
async def list_notifications(
    limit: int = 50,
    skip: int = 0,
    unread_only: bool = False,
    current_hotel: Dict[str, Any] = Depends(get_current_hotel),
):
    query = {"hotel_id": current_hotel["_id"]}
    if unread_only:
        query["is_read"] = False
    cursor = db.notifications.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [serialize_doc(d) for d in docs]


@api.get("/notifications/unread-count")
async def notification_unread_count(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    count = await db.notifications.count_documents({"hotel_id": current_hotel["_id"], "is_read": False})
    return {"count": count}


@api.put("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    result = await db.notifications.update_one(
        {"_id": notification_id, "hotel_id": current_hotel["_id"]},
        {"$set": {"is_read": True}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Bildirim bulunamadı")
    return {"message": "Okundu olarak işaretlendi"}


@api.put("/notifications/read-all")
async def mark_all_notifications_read(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    await db.notifications.update_many(
        {"hotel_id": current_hotel["_id"], "is_read": False},
        {"$set": {"is_read": True}}
    )
    return {"message": "Tüm bildirimler okundu olarak işaretlendi"}


# =============================================================================
# --- Revenue Reports ---------------------------------------------------------
# =============================================================================

@api.get("/reports/revenue")
async def revenue_report(
    period: str = "monthly",
    months: int = 6,
    current_hotel: Dict[str, Any] = Depends(get_current_hotel),
):
    """Otelimin gelir raporu."""
    now = now_utc()
    start_date = now - timedelta(days=months * 30)

    # Ödemelerim
    payments = await db.payments.find({
        "hotel_id": current_hotel["_id"],
        "status": "completed",
        "completed_at": {"$gte": start_date},
    }).to_list(length=1000)

    # Eşleşmelerim (gelir kaynağı olarak)
    my_matches = await db.matches.find({
        "$or": [{"hotel_a_id": current_hotel["_id"]}, {"hotel_b_id": current_hotel["_id"]}],
        "created_at": {"$gte": start_date},
    }).to_list(length=1000)

    monthly_data = defaultdict(lambda: {"payments": 0, "payment_count": 0, "matches": 0, "revenue": 0})
    for p in payments:
        key = p["completed_at"].strftime("%Y-%m")
        monthly_data[key]["payments"] += p["amount"]
        monthly_data[key]["payment_count"] += 1

    for m in my_matches:
        key = m["created_at"].strftime("%Y-%m")
        monthly_data[key]["matches"] += 1
        monthly_data[key]["revenue"] += m.get("fee_amount", MATCH_FEE_TL)

    total_payments = sum(p["amount"] for p in payments)
    total_matches = len(my_matches)

    return {
        "total_payments": total_payments,
        "total_matches": total_matches,
        "monthly": dict(monthly_data),
        "period_months": months,
    }


# =============================================================================
# --- Market Trends -----------------------------------------------------------
# =============================================================================

@api.get("/stats/market-trends")
async def market_trends(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """Bölge bazlı talep/arz dengesi görselleştirme."""
    now = now_utc()
    thirty_days_ago = now - timedelta(days=30)

    result = {}
    for region_key, region_info in REGIONS.items():
        # Aktif ilanlar (arz)
        supply = await db.availability_listings.count_documents({
            "region": region_key,
            "date_end": {"$gte": now},
        })
        # Son 30 gündeki talepler
        demand = await db.requests.count_documents({
            "created_at": {"$gte": thirty_days_ago},
        })
        # Bölgedeki eşleşmeler
        matches = await db.matches.count_documents({
            "region": region_key,
            "created_at": {"$gte": thirty_days_ago},
        })
        # Bölge eşleşmeleri (region alanı yoksa listing üzerinden)
        if matches == 0:
            listing_ids = []
            async for l in db.availability_listings.find({"region": region_key}, {"_id": 1}):
                listing_ids.append(l["_id"])
            if listing_ids:
                matches = await db.matches.count_documents({
                    "listing_id": {"$in": listing_ids},
                    "created_at": {"$gte": thirty_days_ago},
                })

        # Ortalama fiyat
        pipeline = [
            {"$match": {"region": region_key, "date_end": {"$gte": now}}},
            {"$group": {"_id": None, "avg_price": {"$avg": "$price_min"}, "count": {"$sum": 1}}},
        ]
        agg = await db.availability_listings.aggregate(pipeline).to_list(length=1)
        avg_price = agg[0]["avg_price"] if agg else 0

        result[region_key] = {
            "label": region_info["label"],
            "supply": supply,
            "demand": demand,
            "matches": matches,
            "avg_price": round(avg_price, 2),
            "match_fee": region_info["match_fee"],
            "balance": "dengeli" if abs(supply - demand) < 3 else ("talep_fazla" if demand > supply else "arz_fazla"),
        }

    return result


# =============================================================================
# --- Performance Scores ------------------------------------------------------
# =============================================================================

@api.get("/stats/performance-scores")
async def performance_scores(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """Otel performans metrikleri."""
    hotel_id = current_hotel["_id"]
    now = now_utc()
    ninety_days = now - timedelta(days=90)

    # Gelen talepler
    incoming = await db.requests.find({"to_hotel_id": hotel_id, "created_at": {"$gte": ninety_days}}).to_list(length=1000)
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

    # Eşleşme sayısı
    match_count = await db.matches.count_documents({
        "$or": [{"hotel_a_id": hotel_id}, {"hotel_b_id": hotel_id}],
        "created_at": {"$gte": ninety_days},
    })

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
# --- KVKK Compliance ---------------------------------------------------------
# =============================================================================

@api.get("/kvkk/export")
async def kvkk_export_data(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """KVKK - Tüm kişisel verilerimi dışa aktar."""
    hotel_id = current_hotel["_id"]

    hotel = await db.hotels.find_one({"_id": hotel_id})
    listings = await db.availability_listings.find({"hotel_id": hotel_id}).to_list(length=1000)
    requests_out = await db.requests.find({"from_hotel_id": hotel_id}).to_list(length=1000)
    requests_in = await db.requests.find({"to_hotel_id": hotel_id}).to_list(length=1000)
    matches = await db.matches.find({"$or": [{"hotel_a_id": hotel_id}, {"hotel_b_id": hotel_id}]}).to_list(length=1000)
    payments = await db.payments.find({"hotel_id": hotel_id}).to_list(length=500)
    invoices = await db.invoices.find({"hotel_id": hotel_id}).to_list(length=500)
    notifications = await db.notifications.find({"hotel_id": hotel_id}).to_list(length=500)

    return {
        "export_date": now_utc().isoformat(),
        "hotel": serialize_doc(hotel) if hotel else None,
        "listings_count": len(listings),
        "listings": [serialize_doc(l) for l in listings],
        "outgoing_requests_count": len(requests_out),
        "outgoing_requests": [serialize_doc(r) for r in requests_out],
        "incoming_requests_count": len(requests_in),
        "incoming_requests": [serialize_doc(r) for r in requests_in],
        "matches_count": len(matches),
        "matches": [serialize_doc(m) for m in matches],
        "payments_count": len(payments),
        "payments": [serialize_doc(p) for p in payments],
        "invoices_count": len(invoices),
        "invoices": [serialize_doc(i) for i in invoices],
        "notifications_count": len(notifications),
    }


@api.post("/kvkk/delete-request")
async def kvkk_delete_request(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """KVKK - Hesap silme talebi oluştur."""
    hotel_id = current_hotel["_id"]
    existing = await db.kvkk_requests.find_one({"hotel_id": hotel_id, "status": "pending"})
    if existing:
        return {"message": "Zaten bekleyen bir silme talebiniz var", "request_id": existing["_id"]}

    req_id = str(uuid.uuid4())
    await db.kvkk_requests.insert_one({
        "_id": req_id,
        "hotel_id": hotel_id,
        "type": "account_deletion",
        "status": "pending",
        "created_at": now_utc(),
    })
    await create_notification(hotel_id, "kvkk_request", "Silme Talebi Alındı", "Hesap silme talebiniz alınmıştır. 30 gün içinde işleme alınacaktır.", {"request_id": req_id})
    return {"message": "Silme talebi oluşturuldu. 30 gün içinde işleme alınacaktır.", "request_id": req_id}


# =============================================================================
# --- Regions Info & Admin Region Pricing -------------------------------------
# =============================================================================

@api.get("/regions")
async def list_regions():
    """Tüm bölgeleri listele."""
    result = []
    for key, info in REGIONS.items():
        # Admin tarafından özelleştirilmiş fiyat kontrolü
        custom = await db.region_pricing.find_one({"_id": key})
        fee = custom["match_fee"] if custom and "match_fee" in custom else info["match_fee"]
        result.append({
            "id": key,
            "label": info["label"],
            "prefix": info["prefix"],
            "match_fee": fee,
        })
    return result


@api.get("/admin/region-pricing")
async def admin_get_region_pricing(admin: Dict[str, Any] = Depends(get_current_admin)):
    """Admin: Bölge bazlı fiyatlandırma."""
    result = []
    for key, info in REGIONS.items():
        custom = await db.region_pricing.find_one({"_id": key})
        result.append({
            "region": key,
            "label": info["label"],
            "default_fee": info["match_fee"],
            "custom_fee": custom.get("match_fee") if custom else None,
            "active_fee": custom["match_fee"] if custom and "match_fee" in custom else info["match_fee"],
        })
    return result


@api.put("/admin/region-pricing/{region}")
async def admin_update_region_pricing(region: str, body: Dict[str, Any], admin: Dict[str, Any] = Depends(get_current_admin)):
    """Admin: Bölge eşleşme ücretini güncelle."""
    if region not in REGIONS:
        raise HTTPException(status_code=400, detail="Geçersiz bölge")
    match_fee = body.get("match_fee")
    if match_fee is None or match_fee < 0:
        raise HTTPException(status_code=400, detail="Geçerli bir ücret girin")
    await db.region_pricing.update_one(
        {"_id": region},
        {"$set": {"match_fee": float(match_fee), "updated_at": now_utc(), "updated_by": admin["_id"]}},
        upsert=True,
    )
    return {"message": f"{region} bölgesi eşleşme ücreti ₺{match_fee:.2f} olarak güncellendi"}


# =============================================================================
# --- Admin Revenue Dashboard -------------------------------------------------
# =============================================================================

@api.get("/admin/revenue")
async def admin_revenue(
    months: int = 6,
    admin: Dict[str, Any] = Depends(get_current_admin),
):
    """Admin: Platform gelir genel bakışı."""
    now = now_utc()
    start_date = now - timedelta(days=months * 30)

    all_payments = await db.payments.find({
        "status": "completed",
        "completed_at": {"$gte": start_date},
    }).to_list(length=5000)

    all_matches = await db.matches.find({
        "created_at": {"$gte": start_date},
    }).to_list(length=5000)

    total_revenue = sum(p["amount"] for p in all_payments)
    total_matches = len(all_matches)
    paid_matches = sum(1 for m in all_matches if m.get("fee_status") == "paid")
    unpaid_matches = total_matches - paid_matches

    # Aylık kırılım
    monthly = defaultdict(lambda: {"revenue": 0, "matches": 0, "payments": 0})
    for p in all_payments:
        key = p["completed_at"].strftime("%Y-%m")
        monthly[key]["revenue"] += p["amount"]
        monthly[key]["payments"] += 1
    for m in all_matches:
        key = m["created_at"].strftime("%Y-%m")
        monthly[key]["matches"] += 1

    # Bölge bazlı
    region_revenue = defaultdict(lambda: {"matches": 0, "revenue": 0})
    for m in all_matches:
        region = m.get("region", "Bilinmiyor")
        region_revenue[region]["matches"] += 1
        region_revenue[region]["revenue"] += m.get("fee_amount", MATCH_FEE_TL)

    return {
        "total_revenue": total_revenue,
        "total_matches": total_matches,
        "paid_matches": paid_matches,
        "unpaid_matches": unpaid_matches,
        "monthly": dict(monthly),
        "region_breakdown": dict(region_revenue),
        "period_months": months,
    }


@api.get("/admin/region-stats")
async def admin_region_stats(admin: Dict[str, Any] = Depends(get_current_admin)):
    """Admin: Bölge bazlı istatistikler."""
    now = now_utc()
    result = {}
    for region_key, region_info in REGIONS.items():
        hotels = await db.hotels.count_documents({"region": region_key})
        active_listings = await db.availability_listings.count_documents({"region": region_key, "date_end": {"$gte": now}})
        total_listings = await db.availability_listings.count_documents({"region": region_key})
        result[region_key] = {
            "label": region_info["label"],
            "hotels": hotels,
            "active_listings": active_listings,
            "total_listings": total_listings,
        }
    return result


# =============================================================================
# --- Request Statistics (Enhanced) -------------------------------------------
# =============================================================================

@api.get("/stats/requests")
async def request_statistics(
    period_days: int = 30,
    current_hotel: Dict[str, Any] = Depends(get_current_hotel),
):
    """Detaylı talep istatistikleri."""
    hotel_id = current_hotel["_id"]
    now = now_utc()
    start_date = now - timedelta(days=period_days)

    incoming = await db.requests.find({"to_hotel_id": hotel_id, "created_at": {"$gte": start_date}}).to_list(length=1000)
    outgoing = await db.requests.find({"from_hotel_id": hotel_id, "created_at": {"$gte": start_date}}).to_list(length=1000)

    def count_by_status(reqs):
        counts = defaultdict(int)
        for r in reqs:
            counts[r["status"]] += 1
        return dict(counts)

    # Günlük kırılım
    daily_incoming = defaultdict(int)
    for r in incoming:
        key = r["created_at"].strftime("%Y-%m-%d")
        daily_incoming[key] += 1

    return {
        "period_days": period_days,
        "incoming": {
            "total": len(incoming),
            "by_status": count_by_status(incoming),
            "daily": dict(daily_incoming),
        },
        "outgoing": {
            "total": len(outgoing),
            "by_status": count_by_status(outgoing),
        },
        "acceptance_rate": round(sum(1 for r in incoming if r["status"] == "accepted") / len(incoming) * 100, 1) if incoming else 0,
        "missed_rate": round(sum(1 for r in incoming if r["status"] in ("rejected", "cancelled", "expired")) / len(incoming) * 100, 1) if incoming else 0,
    }


# =============================================================================
# --- Cross-Region Stats & Matching -------------------------------------------
# =============================================================================

@api.get("/stats/cross-region")
async def cross_region_stats(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """Bölgeler arası kapasite paylaşım istatistikleri."""
    now = now_utc()

    # Cross-region ilanlar
    cross_listings = await db.availability_listings.find({
        "allow_cross_region": True,
        "date_end": {"$gte": now},
    }).to_list(length=500)

    # Bölge bazlı cross-region dağılım
    region_cross = defaultdict(lambda: {"listings": 0, "total_pax": 0})
    for l in cross_listings:
        r = l.get("region", "Bilinmiyor")
        region_cross[r]["listings"] += 1
        region_cross[r]["total_pax"] += l.get("pax", 0)

    # Tüm bölge çiftleri arası eşleşme sayısı
    cross_matches = []
    all_matches = await db.matches.find({}).to_list(length=5000)
    for m in all_matches:
        listing = await db.availability_listings.find_one({"_id": m.get("listing_id")})
        if listing:
            listing_region = listing.get("region", "")
            hotel_a = await db.hotels.find_one({"_id": m.get("hotel_a_id")})
            hotel_b = await db.hotels.find_one({"_id": m.get("hotel_b_id")})
            if hotel_a and hotel_b:
                region_a = hotel_a.get("region", "")
                region_b = hotel_b.get("region", "")
                if region_a != region_b:
                    cross_matches.append({
                        "from_region": region_a,
                        "to_region": region_b,
                        "listing_region": listing_region,
                    })

    # Bölge çiftleri
    pair_counts = defaultdict(int)
    for cm in cross_matches:
        pair_key = f"{cm['from_region']} → {cm['to_region']}"
        pair_counts[pair_key] += 1

    return {
        "total_cross_region_listings": len(cross_listings),
        "region_breakdown": dict(region_cross),
        "total_cross_region_matches": len(cross_matches),
        "region_pairs": dict(pair_counts),
        "regions": list(REGIONS.keys()),
    }


# Healthcheck / root

@api.get("/")
async def root() -> Dict[str, str]:
    return {"message": "CapX Multi-Region API v4"}


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Uygulama başlangıcında indeksleri oluştur."""
    await ensure_indexes()


@app.on_event("shutdown")
async def shutdown_db_client() -> None:
    client.close()
