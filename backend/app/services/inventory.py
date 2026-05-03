import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict

from app.db import db
from app.utils import now_utc


async def decrement_inventory_on_match(listing_doc: Dict[str, Any]) -> None:
    """Eşleşme kabul edildiğinde envanter otomatik güncelle."""
    hotel_id = listing_doc.get("hotel_id")
    room_type = listing_doc.get("room_type")
    if not hotel_id or not room_type:
        return

    inv = await db.inventory.find_one({"hotel_id": hotel_id, "room_type": room_type})
    if not inv:
        return

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


async def increment_inventory_on_cancel(listing_doc: Dict[str, Any]) -> None:
    """Eşleşme iptal edildiğinde envanteri geri yükle (decrement_inventory'nin tersi)."""
    hotel_id = listing_doc.get("hotel_id")
    room_type = listing_doc.get("room_type")
    if not hotel_id or not room_type:
        return

    inv = await db.inventory.find_one({"hotel_id": hotel_id, "room_type": room_type})
    if not inv:
        return

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
            new_booked = max(existing.get("booked_rooms", 0) - 1, 0)
            new_available = min(existing.get("available_rooms", 0) + 1, inv["total_rooms"])
            await db.daily_availability.update_one(
                {"_id": existing["_id"]},
                {"$set": {"booked_rooms": new_booked, "available_rooms": new_available, "updated_at": now_utc()}}
            )
        current_d += timedelta(days=1)
