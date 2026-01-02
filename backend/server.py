from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import os
import uuid

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, APIRouter, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field


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


class HotelPublic(HotelBase):
    id: str
    email: EmailStr
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


class AvailabilityListingMine(AvailabilityListingPublic):
    created_at: datetime
    updated_at: datetime


class RequestCreate(BaseModel):
    listing_id: str
    guest_type: str = Field(pattern="^(family|couple|group)$")
    notes: Optional[str] = None
    confirm_window_minutes: int = 120


class RequestPublic(BaseModel):
    id: str
    listing_id: str
    from_hotel_id: str
    to_hotel_id: str
    guest_type: str
    notes: Optional[str]
    confirm_window_minutes: int
    status: str
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
        created_at=current_hotel["created_at"],
    )


@api.put("/hotels/me", response_model=HotelPublic)
async def update_me(update: HotelMeUpdate, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    updates = {k: v for k, v in update.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        return await me(current_hotel)  # type: ignore[arg-type]
    updates["updated_at"] = now_utc()
    await db.hotels.update_one({"_id": current_hotel["_id"]}, {"$set": updates})
    await log_activity(current_hotel["_id"], "update_profile", "hotel", current_hotel["_id"], {"fields": list(updates.keys())})
    refreshed = await db.hotels.find_one({"_id": current_hotel["_id"]})
    return await me(refreshed)  # type: ignore[arg-type]


# --- Listings endpoints -----------------------------------------------------

@api.post("/listings", response_model=AvailabilityListingMine)
async def create_listing(payload: AvailabilityListingCreate, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    listing_id = str(uuid.uuid4())
    now = now_utc()
    doc = {
        "_id": listing_id,
        "hotel_id": current_hotel["_id"],
        **payload.model_dump(),
        "is_locked": False,
        "lock_request_id": None,
        "created_at": now,
        "updated_at": now,
    }
    await db.availability_listings.insert_one(doc)
    await log_activity(current_hotel["_id"], "create", "availability_listing", listing_id, {"status": payload.availability_status})
    return AvailabilityListingMine(id=listing_id, **payload.model_dump(), is_locked=False, created_at=now, updated_at=now)


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
    )


@api.get("/listings", response_model=List[AvailabilityListingPublic])
async def list_listings(
    region: Optional[str] = None,
    concept: Optional[str] = None,
    mine: bool = False,
    current_hotel: Dict[str, Any] = Depends(get_current_hotel),
):
    query: Dict[str, Any] = {}
    if region:
        query["region"] = region
    if concept:
        query["concept"] = concept
    if mine:
        query["hotel_id"] = current_hotel["_id"]

    cursor = db.availability_listings.find(query)
    docs = await cursor.to_list(length=500)
    return [listing_to_public(d) for d in docs]


@api.get("/listings/{listing_id}")
async def get_listing(listing_id: str, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    listing = await db.availability_listings.find_one({"_id": listing_id})
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

    # Always anonymous, even for owner here – owner can use mine=true list if needed
    return listing_to_public(listing)


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
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


@api.get("/requests/outgoing", response_model=List[RequestPublic])
async def list_outgoing_requests(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    cursor = db.requests.find({"from_hotel_id": current_hotel["_id"]})
    docs = await cursor.to_list(length=500)
    return [request_to_public(d) for d in docs]


@api.get("/requests/incoming", response_model=List[RequestPublic])
async def list_incoming_requests(current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    cursor = db.requests.find({"to_hotel_id": current_hotel["_id"]})
    docs = await cursor.to_list(length=500)
    return [request_to_public(d) for d in docs]


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
    cursor = db.matches.find({"$or": [{"hotel_a_id": current_hotel["_id"]}, {"hotel_b_id": current_hotel["_id"]}]})
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

    # Progressive disclosure: now reveal both hotels
    hotel_a = await db.hotels.find_one({"_id": d["hotel_a_id"]})
    hotel_b = await db.hotels.find_one({"_id": d["hotel_b_id"]})

    return {
        "id": d["_id"],
        "request_id": d["request_id"],
        "listing_id": d["listing_id"],
        "reference_code": d["reference_code"],
        "fee_amount": d["fee_amount"],
        "fee_status": d["fee_status"],
        "accepted_at": d["accepted_at"].isoformat(),
        "created_at": d["created_at"].isoformat(),
        "counterparty": {
            "self": serialize_doc(hotel_a if hotel_a["_id"] == current_hotel["_id"] else hotel_b),
            "other": serialize_doc(hotel_b if hotel_a["_id"] == current_hotel["_id"] else hotel_a),
        },
    }


# Healthcheck / root

@api.get("/")
async def root() -> Dict[str, str]:
    return {"message": "CapX Sapanca-Kartepe API"}


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
