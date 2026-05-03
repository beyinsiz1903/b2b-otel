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
async def list_payments(response: Response, skip: int = 0, limit: int = 50, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """Otelimin ödemeleri."""
    query = {"hotel_id": current_hotel["_id"]}
    total = await db.payments.count_documents(query)
    response.headers["X-Total-Count"] = str(total)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    cursor = db.payments.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
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
async def list_invoices(response: Response, skip: int = 0, limit: int = 50, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """Faturalarım."""
    query = {"hotel_id": current_hotel["_id"]}
    total = await db.invoices.count_documents(query)
    response.headers["X-Total-Count"] = str(total)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    cursor = db.invoices.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [serialize_doc(d) for d in docs]


@api.get("/invoices/{invoice_id}")
async def get_invoice(invoice_id: str, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    invoice = await db.invoices.find_one({"_id": invoice_id})
    if not invoice:
        raise HTTPException(status_code=404, detail="Fatura bulunamadı")
    if invoice["hotel_id"] != current_hotel["_id"] and not current_hotel.get("is_admin"):
        raise HTTPException(status_code=403, detail="Yetkisiz")
    return serialize_doc(invoice)


# --- PDF Invoice Export -------------------------------------------------------

@api.get("/invoices/{invoice_id}/pdf")
async def download_invoice_pdf(invoice_id: str, current_hotel: Dict[str, Any] = Depends(get_current_hotel)):
    """Faturayı PDF olarak indir."""
    from fpdf import FPDF
    import io

    invoice = await db.invoices.find_one({"_id": invoice_id})
    if not invoice:
        raise HTTPException(status_code=404, detail="Fatura bulunamadı")
    if invoice["hotel_id"] != current_hotel["_id"] and not current_hotel.get("is_admin"):
        raise HTTPException(status_code=403, detail="Yetkisiz")

    pdf = FPDF()
    pdf.add_page()

    # Header
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, "CapX Platform - Fatura", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(8)

    # Invoice info
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(50, 8, "Fatura No:", new_x="RIGHT")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, str(invoice.get("invoice_number", "")), new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(50, 8, "Tarih:", new_x="RIGHT")
    pdf.set_font("Helvetica", "", 11)
    created = invoice.get("created_at")
    date_str = created.strftime("%d.%m.%Y") if created else "-"
    pdf.cell(0, 8, date_str, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(50, 8, "Otel:", new_x="RIGHT")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, str(invoice.get("hotel_name", "")), new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(50, 8, "Adres:", new_x="RIGHT")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, str(invoice.get("hotel_address", "")), new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(50, 8, "Durum:", new_x="RIGHT")
    pdf.set_font("Helvetica", "", 11)
    status_map = {"issued": "Kesildi", "paid": "Odendi", "cancelled": "Iptal"}
    pdf.cell(0, 8, status_map.get(invoice.get("status", ""), invoice.get("status", "")), new_x="LMARGIN", new_y="NEXT")

    pdf.ln(8)

    # Items table
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(230, 240, 235)
    pdf.cell(90, 8, "Aciklama", border=1, fill=True, new_x="RIGHT")
    pdf.cell(25, 8, "Miktar", border=1, fill=True, align="C", new_x="RIGHT")
    pdf.cell(35, 8, "Birim Fiyat", border=1, fill=True, align="R", new_x="RIGHT")
    pdf.cell(35, 8, "Toplam", border=1, fill=True, align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 10)
    for item in invoice.get("items", []):
        pdf.cell(90, 8, str(item.get("description", "")), border=1, new_x="RIGHT")
        pdf.cell(25, 8, str(item.get("quantity", 1)), border=1, align="C", new_x="RIGHT")
        pdf.cell(35, 8, f"TL {item.get('unit_price', 0):.2f}", border=1, align="R", new_x="RIGHT")
        pdf.cell(35, 8, f"TL {item.get('total', 0):.2f}", border=1, align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(4)

    # Totals
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(150, 8, "Ara Toplam:", align="R", new_x="RIGHT")
    pdf.cell(35, 8, f"TL {invoice.get('subtotal', 0):.2f}", align="R", new_x="LMARGIN", new_y="NEXT")

    tax_rate = invoice.get("tax_rate", 0.20)
    pdf.cell(150, 8, f"KDV (%{int(tax_rate*100)}):", align="R", new_x="RIGHT")
    pdf.cell(35, 8, f"TL {invoice.get('tax_amount', 0):.2f}", align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(150, 10, "GENEL TOPLAM:", align="R", new_x="RIGHT")
    pdf.cell(35, 10, f"TL {invoice.get('total', 0):.2f}", align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(12)
    pdf.set_font("Helvetica", "I", 8)
    pdf.cell(0, 6, "Bu fatura CapX Platform tarafindan otomatik olusturulmustur.", align="C")

    # Return PDF as file download
    pdf_bytes = pdf.output()
    return Response(
        content=bytes(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="fatura-{invoice.get("invoice_number", invoice_id)}.pdf"'
        }
    )


