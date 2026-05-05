"""
PMS UAT tenant'ını CapX tarafında bir kerede kurar:
  1. UAT için bir hotel kaydı upsert eder (approved durumda)
  2. pms_integrations kaydını gerçek hotel _id'sine bağlar
  3. (Verilirse) callback_url'i set eder

Kullanım:
    # İlk kurulum: hotel + credential
    python backend/scripts/bootstrap_pms_uat_tenant.py

    # Mevcut kayda callback URL ekle (api_key değişmez):
    python backend/scripts/bootstrap_pms_uat_tenant.py \
        --callback-url https://<PMS-DOMAIN>/api/webhooks/capx/by-tenant/<UUID>

    # Anahtarı yeniden üret (PMS'e yeni credential paketi göndermek gerekir):
    python backend/scripts/bootstrap_pms_uat_tenant.py --rotate

İki yön de aynı webhook_secret'ı kullanır.
"""
import argparse
import asyncio
import hashlib
import os
import secrets
import sys
import uuid
from datetime import datetime, timezone

import bcrypt
from motor.motor_asyncio import AsyncIOMotorClient


UAT_HOTEL_EMAIL = "pms-uat@capx.local"
UAT_HOTEL_NAME = "PMS UAT Test Hotel"
LEGACY_FAKE_HOTEL_ID = "pms-uat-tenant-5bad4a34"


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _ensure_hotel(db) -> str:
    """UAT hotel kaydını upsert et, _id döndür."""
    existing = await db.hotels.find_one({"email": UAT_HOTEL_EMAIL})
    if existing:
        return existing["_id"]

    hotel_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    random_pw = secrets.token_urlsafe(24)
    pw_hash = bcrypt.hashpw(random_pw.encode(), bcrypt.gensalt()).decode()

    await db.hotels.insert_one({
        "_id": hotel_id,
        "name": UAT_HOTEL_NAME,
        "region": "Sapanca",
        "micro_location": "PMS Sandbox",
        "concept": "PMS UAT integration test tenant — not a real hotel.",
        "address": "—",
        "phone": "+90 000 000 0000",
        "whatsapp": None,
        "website": None,
        "contact_person": "PMS Integration",
        "email": UAT_HOTEL_EMAIL,
        "password_hash": pw_hash,
        "is_admin": False,
        "approval_status": "approved",
        "rejection_reason": None,
        "documents": [],
        "created_at": now,
        "updated_at": now,
    })
    return hotel_id


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--callback-url", default=None,
                    help="PMS'in CapX→PMS push'larını alacağı URL")
    ap.add_argument("--rotate", action="store_true",
                    help="api_key + webhook_secret'ı yeniden üret (PMS'e yeni paket gerekir)")
    args = ap.parse_args()

    mongo_url = os.environ.get("MONGO_URL")
    if not mongo_url:
        print("FATAL: MONGO_URL env değişkeni yok.", file=sys.stderr)
        return 2

    db_name = os.environ.get("DB_NAME", "hotel_match_db")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    # 1) Hotel kaydı (idempotent)
    real_hotel_id = await _ensure_hotel(db)

    # 2) Eski fake hotel_id'li kayıt varsa, gerçek hotel_id'ye taşı
    legacy = await db.pms_integrations.find_one({"hotel_id": LEGACY_FAKE_HOTEL_ID})
    existing = await db.pms_integrations.find_one({"hotel_id": real_hotel_id})

    if legacy and not existing:
        # Migration: eski kaydı gerçek hotel_id'ye relink (api_key/webhook_secret KORU)
        await db.pms_integrations.update_one(
            {"hotel_id": LEGACY_FAKE_HOTEL_ID},
            {"$set": {"hotel_id": real_hotel_id, "updated_at": datetime.now(timezone.utc)}},
        )
        existing = await db.pms_integrations.find_one({"hotel_id": real_hotel_id})
        print(f"✓ Eski fake hotel_id'li kayıt gerçek hotel_id'ye taşındı: {real_hotel_id}")
    elif legacy and existing:
        # Çakışma: ikisi de varsa eskisini sil
        await db.pms_integrations.delete_one({"hotel_id": LEGACY_FAKE_HOTEL_ID})
        print(f"✓ Eski fake kayıt silindi (gerçek kayıt zaten mevcuttu).")

    # 3) Credential kararı
    if existing and not args.rotate:
        print("=" * 64)
        print("✓ Mevcut PMS UAT tenant kaydı bulundu — anahtarlar KORUNDU.")
        print(f"  hotel_id (real)  : {real_hotel_id}")
        print(f"  api_key_last4    : {existing.get('api_key_last4')}")
        print(f"  callback_url     : {existing.get('callback_url')}")
        print(f"  status           : {existing.get('status')}")
        print(f"  connected_at     : {existing.get('connected_at')}")
        print("=" * 64)

        if args.callback_url:
            await db.pms_integrations.update_one(
                {"hotel_id": real_hotel_id},
                {"$set": {"callback_url": args.callback_url,
                          "updated_at": datetime.now(timezone.utc)}},
            )
            print(f"\n✓ callback_url güncellendi: {args.callback_url}")
        else:
            print("\nℹ Yeni anahtar üretmek için --rotate ile çalıştır.")
            print("ℹ callback_url set etmek için --callback-url ile çalıştır.")

        client.close()
        return 0

    # Yeni kayıt veya rotate
    api_key = "capx_pk_" + secrets.token_urlsafe(32)
    webhook_secret = "capx_ws_" + secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)

    set_doc = {
        "hotel_id": real_hotel_id,
        "api_key_hash": _hash_key(api_key),
        "api_key_last4": api_key[-4:],
        "webhook_secret": webhook_secret,
        "status": "active",
        "rotated_at": now,
        "updated_at": now,
    }
    if args.callback_url:
        set_doc["callback_url"] = args.callback_url

    await db.pms_integrations.update_one(
        {"hotel_id": real_hotel_id},
        {
            "$set": set_doc,
            "$setOnInsert": {
                "connected_at": now,
                "sync_count": 0,
                "event_count": 0,
                "callback_url": args.callback_url,
                "last_sync_at": None,
                "last_event_at": None,
            },
        },
        upsert=True,
    )

    base_domain = os.environ.get("REPLIT_DEV_DOMAIN", "<REPLIT_DEV_DOMAIN>")
    base_url = f"https://{base_domain}"

    print("=" * 64)
    print("  PMS UAT CREDENTIALS  —  PMS ekibine ilet")
    print("=" * 64)
    print(f"base_url       : {base_url}")
    print(f"api_key        : {api_key}")
    print(f"webhook_secret : {webhook_secret}")
    print(f"jwt_token      : (kullanılmıyor — Bearer api_key fallback aktif)")
    print()
    print("Endpoint URL'leri (PMS bunları kullanır):")
    print(f"  POST {base_url}/api/integrations/v1/pms/availability/sync")
    print(f"  POST {base_url}/api/integrations/v1/pms/reservation/event")
    print()
    print("CapX tarafı kayıt detayı:")
    print(f"  hotel_id (real) : {real_hotel_id}")
    print(f"  hotel_email     : {UAT_HOTEL_EMAIL}")
    print(f"  callback_url    : {args.callback_url or '(henüz set edilmedi)'}")
    print(f"  status          : active")
    print(f"  rotated_at      : {now.isoformat()}")
    print("=" * 64)
    print()
    print("ÖNEMLİ: api_key bir daha gösterilmez — şimdi güvenli bir yere kaydet.")
    print()

    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
