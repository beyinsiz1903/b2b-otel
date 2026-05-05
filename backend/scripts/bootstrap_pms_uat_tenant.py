"""
PMS UAT tenant'ını CapX tarafında bir kerede oluşturur ve PMS ekibine
verilecek 4 credential'ı yazdırır.

Kullanım:
    python backend/scripts/bootstrap_pms_uat_tenant.py \
        [--callback-url https://<PMS-DOMAIN>/api/webhooks/capx/by-tenant/<UUID>] \
        [--hotel-id pms-uat-tenant-5bad4a34] \
        [--rotate]   # mevcut kayıt varsa anahtarı yeniden üret

İki yön de aynı webhook_secret'ı kullanır (PMS→CapX ingestion HMAC + CapX→PMS
outbound HMAC). Bu repo'daki /integrations/v1/pms/connect endpoint'inin
mantığını birebir mirror eder; sadece JWT auth yerine doğrudan DB'ye yazar.
"""
import argparse
import asyncio
import hashlib
import os
import secrets
import sys
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hotel-id", default="pms-uat-tenant-5bad4a34",
                    help="CapX tarafında bu PMS tenant'ı için kullanılacak hotel_id")
    ap.add_argument("--callback-url", default=None,
                    help="PMS'in CapX→PMS push'larını alacağı URL (opsiyonel; sonra da set edilebilir)")
    ap.add_argument("--rotate", action="store_true",
                    help="Var olan kaydı override et (yeni api_key + webhook_secret üret)")
    args = ap.parse_args()

    mongo_url = os.environ.get("MONGO_URL")
    if not mongo_url:
        print("FATAL: MONGO_URL env değişkeni yok.", file=sys.stderr)
        return 2

    db_name = os.environ.get("DB_NAME", "hotel_match_db")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    existing = await db.pms_integrations.find_one({"hotel_id": args.hotel_id})
    if existing and existing.get("status") == "active" and not args.rotate:
        print("=" * 64)
        print(f"UYARI: '{args.hotel_id}' için zaten aktif kayıt var.")
        print(f"  api_key_last4: {existing.get('api_key_last4')}")
        print(f"  callback_url:  {existing.get('callback_url')}")
        print(f"  connected_at:  {existing.get('connected_at')}")
        print(f"  rotated_at:    {existing.get('rotated_at')}")
        print()
        print("Yeni anahtar üretmek için --rotate ile tekrar çalıştır.")
        print("Sadece callback_url set etmek için --callback-url ile çalıştır.")
        print("=" * 64)
        # callback URL update'i rotation olmadan da yap
        if args.callback_url:
            await db.pms_integrations.update_one(
                {"hotel_id": args.hotel_id},
                {"$set": {"callback_url": args.callback_url, "updated_at": datetime.now(timezone.utc)}},
            )
            print(f"\n✓ callback_url güncellendi: {args.callback_url}")
        client.close()
        return 0

    api_key = "capx_pk_" + secrets.token_urlsafe(32)
    webhook_secret = "capx_ws_" + secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)

    set_doc = {
        "hotel_id": args.hotel_id,
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
        {"hotel_id": args.hotel_id},
        {
            "$set": set_doc,
            "$setOnInsert": {
                "connected_at": now,
                "sync_count": 0,
                "event_count": 0,
                "callback_url": args.callback_url,  # ilk insert'te None olabilir
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
    print(f"  hotel_id      : {args.hotel_id}")
    print(f"  callback_url  : {args.callback_url or '(henüz set edilmedi — sonra --callback-url ile ekle)'}")
    print(f"  status        : active")
    print(f"  rotated_at    : {now.isoformat()}")
    print("=" * 64)
    print()
    print("ÖNEMLİ: api_key bir daha gösterilmez — şimdi güvenli bir yere kaydet.")
    print("Anahtarı kaybedersen --rotate ile yenisini üretmek zorunda kalırsın.")
    print()

    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
