import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status

from app.config import MATCH_FEE_TL, REGIONS, SUBSCRIPTION_PLANS
from app.db import db
from app.utils import now_utc


async def get_region_match_fee(region: str) -> float:
    """Bölge bazlı eşleşme ücretini döndürür."""
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


async def consume_match_quota(hotel_id: str) -> Optional[str]:
    """Atomik kontrol-ve-artır: kota varsa matches_used'ı 1 artır, yoksa 402 fırlat.

    Dönüş: tüketilen subscription `_id` (ücretsiz plan için None). Bu id refund'da
    kullanılır — böylece arada plan değişimi olsa bile doğru abonelikten düşülür.
    """
    sub = await db.subscriptions.find_one({"hotel_id": hotel_id, "status": "active"}, sort=[("started_at", -1)])
    if sub:
        max_matches = sub.get("max_matches", 0)
        if max_matches == -1:
            await db.subscriptions.update_one(
                {"_id": sub["_id"]},
                {"$inc": {"matches_used": 1}, "$set": {"updated_at": now_utc()}},
            )
            return sub["_id"]
        result = await db.subscriptions.update_one(
            {"_id": sub["_id"], "status": "active", "matches_used": {"$lt": max_matches}},
            {"$inc": {"matches_used": 1}, "$set": {"updated_at": now_utc()}},
        )
        if result.modified_count != 1:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Plan limitiniz ({max_matches} eşleşme/ay) doldu. Planınızı yükseltin."
            )
        return sub["_id"]

    free_plan = next((p for p in SUBSCRIPTION_PLANS if p["id"] == "free"), None)
    max_matches = free_plan["max_matches_per_month"] if free_plan else 5
    if max_matches == -1:
        return None
    month_start = datetime(now_utc().year, now_utc().month, 1, tzinfo=timezone.utc)
    used = await db.matches.count_documents({
        "$or": [{"hotel_a_id": hotel_id}, {"hotel_b_id": hotel_id}],
        "accepted_at": {"$gte": month_start},
        "status": {"$ne": "cancelled"},
    })
    if used >= max_matches:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Aylık ücretsiz eşleşme limitiniz ({max_matches}) doldu. Lütfen bir plana geçin."
        )
    return None


async def refund_match_quota(subscription_id: Optional[str]) -> None:
    """Tüketim sırasında dönen subscription_id ile (ya da hotel_id ile) kotayı geri ver."""
    if not subscription_id:
        return
    await db.subscriptions.update_one(
        {"_id": subscription_id, "matches_used": {"$gt": 0}},
        {"$inc": {"matches_used": -1}, "$set": {"updated_at": now_utc()}},
    )


async def refund_match_quota_by_hotel(hotel_id: str) -> None:
    """Eski iptal akışı için fallback: kabul eden tarafın aktif aboneliğinden düş."""
    await db.subscriptions.update_one(
        {"hotel_id": hotel_id, "status": "active", "matches_used": {"$gt": 0}},
        {"$inc": {"matches_used": -1}, "$set": {"updated_at": now_utc()}},
    )
