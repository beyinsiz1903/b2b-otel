from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


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
    documents: Optional[List[str]] = None


class HotelPublic(HotelBase):
    id: str
    email: EmailStr
    is_admin: bool = False
    approval_status: str = "approved"
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


class RoomTemplateCreate(BaseModel):
    name: str
    room_type: str
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
    price_suggestion: Optional[float] = None
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


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class InventoryItemCreate(BaseModel):
    room_type: str
    room_type_name: str
    total_rooms: int = Field(ge=1)
    description: Optional[str] = None
    features: Optional[List[str]] = None
    capacity_label: Optional[str] = None
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
    inventory_id: str
    date_start: str
    date_end: str
    available_rooms: int = Field(ge=0)
    price_per_night: Optional[float] = None
    notes: Optional[str] = None


class DailyAvailabilityPublic(BaseModel):
    id: str
    hotel_id: str
    inventory_id: str
    date: str
    available_rooms: int
    booked_rooms: int
    total_rooms: int
    price_per_night: Optional[float] = None
    notes: Optional[str] = None


class PricingRuleCreate(BaseModel):
    name: str
    rule_type: str = Field(pattern="^(seasonal|weekend|occupancy|early_bird|last_minute|holiday)$")
    room_type: Optional[str] = None
    multiplier: float = Field(ge=0.1, le=5.0)
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    occupancy_threshold_min: Optional[float] = None
    occupancy_threshold_max: Optional[float] = None
    days_before_min: Optional[int] = None
    days_before_max: Optional[int] = None
    weekend_days: Optional[List[int]] = None
    is_active: bool = True
    priority: int = 0


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
    date_start: str
    date_end: str
    base_price: float
    pax: Optional[int] = None


class PaymentInitiate(BaseModel):
    match_id: str
    method: str = "credit_card"


class PaymentPublic(BaseModel):
    id: str
    hotel_id: str
    match_id: str
    amount: float
    currency: str = "TRY"
    status: str
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
    status: str
    created_at: datetime


class SubscriptionPublic(BaseModel):
    id: str
    hotel_id: str
    plan_id: str
    plan_name: str
    billing_cycle: str
    price: float
    max_matches: int
    matches_used: int
    status: str
    started_at: datetime
    expires_at: datetime
    cancelled_at: Optional[datetime] = None


class NotificationPublic(BaseModel):
    id: str
    hotel_id: str
    type: str
    title: str
    message: str
    is_read: bool
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime


class SheetsConfigSave(BaseModel):
    client_id: str
    client_secret: str
    spreadsheet_id: Optional[str] = None


class SheetsConfigPublic(BaseModel):
    hotel_id: str
    client_id: str
    spreadsheet_id: Optional[str] = None
    connected: bool
    google_email: Optional[str] = None
    connected_at: Optional[datetime] = None


class CheckAvailabilityRequest(BaseModel):
    """Tüm alanlar opsiyonel — query param fallback için boş body de kabul edilir."""
    room_type: Optional[str] = Field(default=None, min_length=1, max_length=64)
    date_start: Optional[str] = None
    date_end: Optional[str] = None


class PMSConnectResponse(BaseModel):
    api_key: str
    webhook_secret: str
    webhook_url: str
    sync_url: str


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


class PMSOutboundEventPublic(BaseModel):
    id: str
    event_type: str
    status: str
    attempts: int = 0
    callback_url: Optional[str] = None
    last_error: Optional[str] = None
    last_response_status: Optional[int] = None
    created_at: Optional[str] = None
    delivered_at: Optional[str] = None
    last_attempt_at: Optional[str] = None
    match_id: Optional[str] = None
    reference_code: Optional[str] = None


class PMSAvailabilityRoom(BaseModel):
    room_type: str = Field(..., min_length=1, max_length=64)
    pax: int = Field(..., ge=1, le=2000)
    price_min: Optional[float] = Field(default=None, ge=0)
    price_max: Optional[float] = Field(default=None, ge=0)
    currency: str = Field(default="TRY", max_length=8)
    notes: Optional[str] = Field(default=None, max_length=300)


class PMSAvailabilitySync(BaseModel):
    date_start: datetime
    date_end: datetime
    region: Optional[str] = Field(default=None, max_length=32)
    rooms: List[PMSAvailabilityRoom] = Field(..., min_length=1, max_length=50)
    auto_publish: bool = True
    external_ref: Optional[str] = Field(default=None, max_length=128)


class PMSReservationEvent(BaseModel):
    event_type: str = Field(..., pattern=r"^(reservation\.created|reservation\.updated|reservation\.cancelled)$")
    external_id: str = Field(..., min_length=1, max_length=128)
    room_type: Optional[str] = Field(default=None, max_length=64)
    pax: Optional[int] = Field(default=None, ge=1, le=2000)
    date_start: Optional[datetime] = None
    date_end: Optional[datetime] = None
    occurred_at: datetime
    payload: Optional[Dict[str, Any]] = None
