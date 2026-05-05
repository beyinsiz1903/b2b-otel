"""CapX → PMS outbound webhook publisher.

CapX'te bir eşleşme oluştuğunda/iptal edildiğinde, ilgili otelin PMS'ine
imzalı bir webhook gönderir. Güvenilir teslimat için **outbox pattern**
kullanılır: olay önce DB'ye yazılır (`pms_outbound_events`), sonra arka
planda teslimat denenir. 4 deneme + 2s/10s/30s eksponansiyel backoff.

**Concurrency güvenliği:** Her event'in `dispatch_id` alanı vardır. Aktif
delivery task'ı sadece kendi token'ı ile çalışır. `retry_event` veya startup
recovery yeni token üretir → eski task ilk fırsatta abort eder, duplicate
POST riski ortadan kalkar.

**Restart dayanımı:** Süreç yeniden başlatıldığında `recover_pending_events()`
yetim kalmış (`pending`/`in_flight`) event'leri toplar ve yeni task spawn eder.

**SSRF koruması:** `validate_callback_url` private/loopback/link-local IP'leri
ve metadata endpoint'lerini reddeder. Dev için `PMS_ALLOW_LOOPBACK_CALLBACK=1`
env değişkeni loopback/private adreslere izin verir.

PMS tarafının uygulaması gerekenler (alıcı kontrat):
- POST <callback_url>  body=JSON
- Header `X-CapX-Event-Id`     : olay id'si — idempotent saklama
- Header `X-CapX-Event-Type`   : "match.created" | "match.cancelled"
- Header `X-CapX-Signature`    : "sha256=<hex>" — webhook_secret ile body'nin HMAC'i
- 2xx döndürürse delivered, aksi halde retry edilir.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import json
import os
import socket
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import aiohttp

from app.config import logger
from app.db import db
from app.utils import now_utc

DELIVERY_TIMEOUT_SEC = 10
MAX_ATTEMPTS = 4
RETRY_BACKOFF_SEC = [2, 10, 30]  # ardışık denemelerin arasındaki bekleme
LEASE_SEC = 120  # bir delivery task'ının tek başına çalışacağı maksimum süre
RECOVERY_STALE_SEC = 60  # yetim sayılan event yaşı (created_at + bu süre)


def _utc_iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _sign(secret: str, body: bytes) -> str:
    mac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={mac}"


def _serialize_value(v: Any) -> Any:
    if isinstance(v, datetime):
        return _utc_iso(v)
    if isinstance(v, dict):
        return {k: _serialize_value(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_serialize_value(x) for x in v]
    return v


# AWS/GCP metadata service IP'leri
_METADATA_HOSTS = {"169.254.169.254", "fd00:ec2::254", "metadata.google.internal", "metadata.goog"}


def validate_callback_url(url: str) -> Tuple[bool, str]:
    """SSRF guard: scheme, host, IP aralığı, metadata endpoint'i kontrol eder.

    Dev/test için `PMS_ALLOW_LOOPBACK_CALLBACK=1` env değişkeni loopback ve
    private IP'lere izin verir; ancak metadata endpoint'leri her zaman bloklanır.
    """
    if not url:
        return True, ""
    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"URL ayrıştırılamadı: {e}"

    if parsed.scheme not in ("http", "https"):
        return False, "callback_url http(s) ile başlamalı"
    host = (parsed.hostname or "").lower()
    if not host:
        return False, "host eksik"
    if host in _METADATA_HOSTS:
        return False, "metadata endpoint izni yok"

    allow_private = os.environ.get("PMS_ALLOW_LOOPBACK_CALLBACK") == "1"

    # Hostname IP olabilir; değilse DNS çöz.
    candidates: List[str] = []
    try:
        ipaddress.ip_address(host)
        candidates = [host]
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, None)
            candidates = list({info[4][0] for info in infos})
        except socket.gaierror as e:
            return False, f"DNS çözümlenemedi: {e}"

    for ip_str in candidates:
        if ip_str in _METADATA_HOSTS:
            return False, "metadata endpoint izni yok"
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return False, f"geçersiz IP: {ip_str}"
        # Bunlar her durumda yasak — env override etmez
        if ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
            return False, f"izinsiz IP aralığı: {ip}"
        # Loopback/private — varsayılan yasak, env ile açılabilir
        if (ip.is_loopback or ip.is_private) and not allow_private:
            return False, f"loopback/private IP izinli değil ({ip}); dev için PMS_ALLOW_LOOPBACK_CALLBACK=1"
    return True, ""


async def build_match_event_payload(
    event_type: str,
    match: Dict[str, Any],
    listing: Dict[str, Any],
    target_hotel_id: str,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """match.created / match.cancelled için PMS payload'ı oluştur.

    `target_hotel_id` PMS sahibi otel — payload'daki `direction` ona göre belirlenir
    (`incoming`: misafir bu otele geliyor, `outgoing`: bu otel misafirini gönderiyor).
    Bu sayede PMS handler kendi context'ine göre kayıt açabilir/iptal edebilir.
    """
    counterparty_id = match["hotel_b_id"] if target_hotel_id == match["hotel_a_id"] else match["hotel_a_id"]
    counterparty = await db.hotels.find_one(
        {"_id": counterparty_id},
        {"name": 1, "region": 1, "micro_location": 1, "phone": 1, "contact_person": 1},
    ) or {}

    # Yön: hotel_a = ilan sahibi (misafir kabul eden); hotel_b = misafiri gönderen
    if target_hotel_id == match["hotel_a_id"]:
        direction = "incoming"  # misafir bu otele geliyor
    else:
        direction = "outgoing"  # bu otel misafirini gönderiyor

    payload = {
        "event_type": event_type,
        "occurred_at": _utc_iso(now_utc()),
        "match": {
            "id": match["_id"],
            "reference_code": match.get("reference_code"),
            "status": match.get("status"),
            "direction": direction,
            "fee_amount": match.get("fee_amount", 0),
            "currency": "TRY",
            "accepted_at": _utc_iso(match.get("accepted_at")),
            "cancelled_at": _utc_iso(match.get("cancelled_at")),
            "cancel_reason": match.get("cancel_reason"),
            "counterparty_hotel": {
                "id": counterparty.get("_id"),
                "name": counterparty.get("name"),
                "region": counterparty.get("region"),
                "micro_location": counterparty.get("micro_location"),
                "phone": counterparty.get("phone"),
                "contact_person": counterparty.get("contact_person"),
            },
            "listing": {
                "id": listing.get("_id"),
                "concept": listing.get("concept"),
                "region": listing.get("region"),
                "micro_location": listing.get("micro_location"),
                "date_start": _utc_iso(listing.get("date_start")),
                "date_end": _utc_iso(listing.get("date_end")),
                "nights": listing.get("nights"),
                "pax": listing.get("pax"),
                "capacity_label": listing.get("capacity_label"),
                "price_min": listing.get("price_min"),
                "price_max": listing.get("price_max"),
                "pms_external_ref": listing.get("pms_external_ref"),
            },
        },
    }
    if extra:
        payload["match"].update(extra)
    return _serialize_value(payload)


async def enqueue_pms_event(
    hotel_id: str,
    event_type: str,
    payload: Dict[str, Any],
) -> Optional[str]:
    """Olayı outbox'a yaz ve teslimat task'ını başlat.

    Otelin PMS bağlantısı yoksa veya callback_url tanımlı değilse sessizce
    geçer (None döner) — bu, PMS kullanmayan oteller için CapX akışını
    bozmamak içindir. Aksi halde event_id döner.
    """
    integ = await db.pms_integrations.find_one({"hotel_id": hotel_id, "status": "active"})
    if not integ:
        return None
    callback_url = integ.get("callback_url")
    if not callback_url:
        return None

    event_id = str(uuid.uuid4())
    dispatch_id = str(uuid.uuid4())
    now = now_utc()
    doc = {
        "_id": event_id,
        "hotel_id": hotel_id,
        "event_type": event_type,
        "callback_url": callback_url,
        "payload": payload,
        "payload_id": payload.get("match", {}).get("id") or payload.get("event_id"),
        "status": "pending",
        "dispatch_id": dispatch_id,
        "attempts": 0,
        "last_error": None,
        "last_attempt_at": None,
        "delivered_at": None,
        "created_at": now,
        "updated_at": now,
    }
    try:
        await db.pms_outbound_events.insert_one(doc)
    except Exception as e:
        # CRITICAL: outbox INSERT başarısız → olay kayıp. Logla ama CapX akışını kırma.
        logger.error("pms_outbound enqueue FAILED hotel=%s event=%s: %s", hotel_id, event_type, e)
        return None

    asyncio.create_task(_deliver_with_retry(event_id, integ["webhook_secret"], dispatch_id))
    return event_id


async def _post_once(callback_url: str, headers: Dict[str, str], body: bytes) -> tuple[int, str]:
    timeout = aiohttp.ClientTimeout(total=DELIVERY_TIMEOUT_SEC)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        # allow_redirects=False: redirect ile farklı host'a (özellikle internal) saptırma engellenir
        async with session.post(callback_url, data=body, headers=headers, allow_redirects=False) as resp:
            text = await resp.text()
            return resp.status, text[:500]


async def _claim_lease(event_id: str, dispatch_id: str) -> Optional[Dict[str, Any]]:
    """Bu task'ın dispatch_id'sinin hâlâ geçerli olduğunu doğrula ve lease yenile.

    Eğer event başka bir dispatch_id'ye ait olmuşsa (manuel retry, recovery veya
    duplicate task) None döner → çağıran abort eder.
    """
    res = await db.pms_outbound_events.find_one_and_update(
        {"_id": event_id, "dispatch_id": dispatch_id, "status": {"$in": ["pending", "in_flight"]}},
        {"$set": {"status": "in_flight", "lease_until": now_utc() + timedelta(seconds=LEASE_SEC), "updated_at": now_utc()}},
    )
    return res


async def _deliver_with_retry(event_id: str, webhook_secret: str, dispatch_id: str) -> None:
    """Lease'i tut, MAX_ATTEMPTS deneme + backoff; sonunda delivered/failed yaz."""
    for attempt_idx in range(MAX_ATTEMPTS):
        ev = await _claim_lease(event_id, dispatch_id)
        if not ev:
            # Başka bir task / retry üstlendi, biz çekiliyoruz.
            return

        body = json.dumps(ev["payload"], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "X-CapX-Event-Id": event_id,
            "X-CapX-Event-Type": ev["event_type"],
            "X-CapX-Signature": _sign(webhook_secret, body),
            "User-Agent": "CapX-Webhook/1.0",
        }

        attempt_no = (ev.get("attempts") or 0) + 1
        status_code: Optional[int] = None
        error: Optional[str] = None
        try:
            status_code, body_preview = await _post_once(ev["callback_url"], headers, body)
            if 200 <= status_code < 300:
                # CAS: yalnızca dispatch hâlâ bizimse delivered işle.
                upd = await db.pms_outbound_events.update_one(
                    {"_id": event_id, "dispatch_id": dispatch_id},
                    {"$set": {
                        "status": "delivered",
                        "attempts": attempt_no,
                        "delivered_at": now_utc(),
                        "last_attempt_at": now_utc(),
                        "last_error": None,
                        "last_response_status": status_code,
                        "updated_at": now_utc(),
                    }},
                )
                if upd.modified_count == 1:
                    return
                return  # dispatch_id değişmiş — yeni task ilgilenir
            error = f"HTTP {status_code}: {body_preview}"
        except asyncio.TimeoutError:
            error = "timeout"
        except Exception as e:
            error = f"{type(e).__name__}: {e}"

        terminal = attempt_no >= MAX_ATTEMPTS
        upd = await db.pms_outbound_events.update_one(
            {"_id": event_id, "dispatch_id": dispatch_id},
            {"$set": {
                "status": "failed" if terminal else "pending",
                "attempts": attempt_no,
                "last_attempt_at": now_utc(),
                "last_error": error,
                "last_response_status": status_code,
                "updated_at": now_utc(),
            }},
        )
        if upd.modified_count == 0:
            # Dispatch değişmiş → yeni sahip ilgilenir
            return
        if terminal:
            logger.warning("pms_outbound delivery FAILED event=%s attempts=%d err=%s", event_id, attempt_no, error)
            return
        await asyncio.sleep(RETRY_BACKOFF_SEC[min(attempt_idx, len(RETRY_BACKOFF_SEC) - 1)])


async def retry_event(event_id: str, hotel_id: str) -> Dict[str, Any]:
    """Manuel yeniden deneme — yalnızca olayın sahibi otel tetikleyebilir.

    Yeni bir `dispatch_id` üretir → varsa eski task ilk fırsatta abort eder.
    """
    ev = await db.pms_outbound_events.find_one({"_id": event_id, "hotel_id": hotel_id})
    if not ev:
        raise LookupError("event_not_found")
    if ev["status"] == "delivered":
        return {"status": "already_delivered"}

    integ = await db.pms_integrations.find_one({"hotel_id": hotel_id, "status": "active"})
    if not integ or not integ.get("callback_url"):
        raise LookupError("pms_disconnected")

    new_dispatch = str(uuid.uuid4())
    await db.pms_outbound_events.update_one(
        {"_id": event_id},
        {"$set": {
            "status": "pending",
            "dispatch_id": new_dispatch,
            "attempts": 0,
            "last_error": None,
            "callback_url": integ["callback_url"],
            "updated_at": now_utc(),
        }},
    )
    asyncio.create_task(_deliver_with_retry(event_id, integ["webhook_secret"], new_dispatch))
    return {"status": "retrying"}


async def recover_pending_events() -> int:
    """Startup'ta çağrılır: yetim kalmış pending/in_flight event'leri yeniden başlatır.

    Yeni `dispatch_id` üretir → eğer eski task hâlâ asılıysa (unlikely after restart)
    CAS ile devre dışı kalır. Stale lease (in_flight + lease_until geçmiş) da toplanır.
    Returns: spawn edilen task sayısı.
    """
    cutoff = now_utc() - timedelta(seconds=RECOVERY_STALE_SEC)
    query = {
        "$or": [
            {"status": "pending", "updated_at": {"$lt": cutoff}},
            {"status": "in_flight", "lease_until": {"$lt": now_utc()}},
        ],
    }
    spawned = 0
    async for ev in db.pms_outbound_events.find(query):
        integ = await db.pms_integrations.find_one({"hotel_id": ev["hotel_id"], "status": "active"})
        if not integ or not integ.get("callback_url"):
            continue
        new_dispatch = str(uuid.uuid4())
        await db.pms_outbound_events.update_one(
            {"_id": ev["_id"]},
            {"$set": {
                "status": "pending",
                "dispatch_id": new_dispatch,
                "callback_url": integ["callback_url"],
                "updated_at": now_utc(),
            }},
        )
        asyncio.create_task(_deliver_with_retry(ev["_id"], integ["webhook_secret"], new_dispatch))
        spawned += 1
    if spawned:
        logger.info("pms_outbound: recovered %d pending event(s) on startup", spawned)
    return spawned


async def list_events(hotel_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    cursor = db.pms_outbound_events.find(
        {"hotel_id": hotel_id},
    ).sort("created_at", -1).limit(limit)
    out = []
    async for ev in cursor:
        out.append({
            "id": ev["_id"],
            "event_type": ev.get("event_type"),
            "status": ev.get("status"),
            "attempts": ev.get("attempts", 0),
            "callback_url": ev.get("callback_url"),
            "last_error": ev.get("last_error"),
            "last_response_status": ev.get("last_response_status"),
            "created_at": _utc_iso(ev.get("created_at")),
            "delivered_at": _utc_iso(ev.get("delivered_at")),
            "last_attempt_at": _utc_iso(ev.get("last_attempt_at")),
            "match_id": (ev.get("payload") or {}).get("match", {}).get("id"),
            "reference_code": (ev.get("payload") or {}).get("match", {}).get("reference_code"),
        })
    return out
