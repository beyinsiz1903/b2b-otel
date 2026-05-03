from datetime import date
from typing import Any, Dict

from app.db import db


async def calculate_dynamic_price(hotel_id: str, room_type: str, target_date: date, base_price: float) -> Dict[str, Any]:
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
            weekend_days = rule.get("weekend_days", [4, 5, 6])
            applies = target_date.weekday() in weekend_days

        elif rule_type == "occupancy":
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
