from datetime import datetime, timezone
from typing import Any, Dict, Optional
import html as _html
import re as _re

from app.config import REGIONS
from app.db import db


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


def sanitize_input(text: Optional[str]) -> Optional[str]:
    """Temel XSS/HTML injection koruması."""
    if text is None:
        return None
    text = _html.escape(text)
    text = _re.sub(r'<script[^>]*>.*?</script>', '', text, flags=_re.IGNORECASE | _re.DOTALL)
    return text.strip()


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
