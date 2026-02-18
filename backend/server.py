from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import asyncio
import warnings
import os
import uuid

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, APIRouter, status, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field

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

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]


# --- Security ---------------------------------------------------------------

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


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
api = APIRouter(prefix="/api")


# --- Auth endpoints ---------------------------------------------------------

@api.post("/auth/register", response_model=HotelPublic)
async def register(hotel_in: HotelCreate):
    existing = await db.hotels.find_one({"email": hotel_in.email})
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    hotel_id = str(uuid.uuid4())
    now = now_utc()
    # Count hotels to determine if first user (make admin)
    count = await db.hotels.count_documents({})
    is_admin = count == 0  # First registered hotel is admin

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
        "created_at": now,
        "updated_at": now,
    }
    await db.hotels.insert_one(doc)
    await log_activity(hotel_id, "register", "hotel", hotel_id, {})

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
        created_at=now,
    )


@api.post("/auth/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    hotel = await db.hotels.find_one({"email": form_data.username})
    if not hotel or not verify_password(form_data.password, hotel["password_hash"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect email or password")

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
        template_id=doc.get("template_id"),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


@api.get("/listings", response_model=List[AvailabilityListingPublic])
async def list_listings(
    region: Optional[str] = None,
    concept: Optional[str] = None,
    mine: bool = False,
    hide_expired: bool = True,
    pax_min: Optional[int] = None,
    price_max: Optional[float] = None,
    avail_status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    current_hotel: Dict[str, Any] = Depends(get_current_hotel),
):
    query: Dict[str, Any] = {}
    if region:
        query["region"] = region
    if concept:
        query["concept"] = {"$regex": concept, "$options": "i"}
    if mine:
        query["hotel_id"] = current_hotel["_id"]
    if hide_expired and not mine:
        query["date_end"] = {"$gte": now_utc()}
    if pax_min is not None:
        query["pax"] = {"$gte": pax_min}
    if price_max is not None:
        query["price_min"] = {"$lte": price_max}
    if avail_status:
        query["availability_status"] = avail_status
    if date_from:
        try:
            df = datetime.fromisoformat(date_from)
            query.setdefault("date_start", {})["$gte"] = df
        except Exception:
            pass
    if date_to:
        try:
            dt = datetime.fromisoformat(date_to)
            query.setdefault("date_end", {})["$lte"] = dt
        except Exception:
            pass

    cursor = db.availability_listings.find(query).sort("created_at", -1)
    docs = await cursor.to_list(length=500)
    return [listing_to_public(d) for d in docs]


@api.get("/listings/mine", response_model=List[AvailabilityListingMine])
async def list_mine_listings(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    cursor = db.availability_listings.find({"hotel_id": current_hotel["_id"]}).sort("created_at", -1)
    docs = await cursor.to_list(length=500)
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
async def list_outgoing_requests(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    cursor = db.requests.find({"from_hotel_id": current_hotel["_id"]}).sort("created_at", -1)
    docs = await cursor.to_list(length=500)
    return [request_to_public(d) for d in docs]


@api.get("/requests/incoming", response_model=List[RequestPublic])
async def list_incoming_requests(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    cursor = db.requests.find({"to_hotel_id": current_hotel["_id"]}).sort("created_at", -1)
    docs = await cursor.to_list(length=500)
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
    match_id = str(uuid.uuid4())
    match_doc = {
        "_id": match_id,
        "request_id": req["_id"],
        "listing_id": listing["_id"],
        "hotel_a_id": req["from_hotel_id"],
        "hotel_b_id": req["to_hotel_id"],
        "reference_code": ref_code,
        "fee_amount": MATCH_FEE_TL,
        "fee_status": "due",
        "accepted_at": now,
        "created_at": now,
    }
    await db.matches.insert_one(match_doc)
    await log_activity(current_hotel["_id"], "accept", "request", req["_id"], {"match_id": match_id})

    return MatchPublic(
        id=match_id,
        request_id=req["_id"],
        listing_id=listing["_id"],
        hotel_a_id=req["from_hotel_id"],
        hotel_b_id=req["to_hotel_id"],
        reference_code=ref_code,
        fee_amount=MATCH_FEE_TL,
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
    match_id = str(uuid.uuid4())
    match_doc = {
        "_id": match_id,
        "request_id": req["_id"],
        "listing_id": listing["_id"],
        "hotel_a_id": req["from_hotel_id"],
        "hotel_b_id": req["to_hotel_id"],
        "reference_code": ref_code,
        "fee_amount": MATCH_FEE_TL,
        "fee_status": "due",
        "accepted_at": now,
        "created_at": now,
    }
    await db.matches.insert_one(match_doc)
    await log_activity(current_hotel["_id"], "accept_alternative", "request", req["_id"], {"match_id": match_id})

    return MatchPublic(
        id=match_id,
        request_id=req["_id"],
        listing_id=listing["_id"],
        hotel_a_id=req["from_hotel_id"],
        hotel_b_id=req["to_hotel_id"],
        reference_code=ref_code,
        fee_amount=MATCH_FEE_TL,
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
async def list_matches(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    cursor = db.matches.find({"$or": [{"hotel_a_id": current_hotel["_id"]}, {"hotel_b_id": current_hotel["_id"]}]}).sort("created_at", -1)
    docs = await cursor.to_list(length=500)
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
    active_listings = sum(1 for l in listings if l.get("date_end", now_utc()) >= now)
    expired_listings = sum(1 for l in listings if l.get("date_end", now_utc()) < now)

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
async def admin_list_hotels(admin: Dict[str, Any] = Depends(get_current_admin)):
    cursor = db.hotels.find({}).sort("created_at", -1)
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
            "is_admin": doc.get("is_admin", False),
            "created_at": doc["created_at"].isoformat() if isinstance(doc.get("created_at"), datetime) else None,
            "match_count": match_count,
            "listing_count": listing_count,
        })
    return result


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
    # Ör: https://xxx.preview.emergentagent.com
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


# Healthcheck / root

@api.get("/")
async def root() -> Dict[str, str]:
    return {"message": "CapX Sapanca-Kartepe API v2"}


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client() -> None:
    client.close()
