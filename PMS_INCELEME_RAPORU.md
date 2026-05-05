# Syroce PMS — Detaylı İnceleme Raporu

> **İncelenen depo:** `beyinsiz1903/emergent-yeni-uygulama` (Syroce PMS)  
> **Klon yolu:** `/tmp/pms/pms` — bu workspace'in DIŞINDA (sadece okundu, dokunulmadı)  
> **Son commit:** `39bcaf3 — Move scan endpoints to a dedicated router file`  
> **Boyut:** 1.266 Python dosyası / 355.096 satır backend, 596 JS dosyası / 172.551 satır frontend  
> **Kendi olgunluk durumu:** "Production Candidate SaaS — GO-LIVE READY %91.8" (391+ test geçiyor)  
> **Rapor amacı:** (1) PMS'in mevcut durumunu objektif olarak değerlendir, (2) CapX ↔ PMS çift taraflı entegrasyonu için PMS tarafında yapılması gerekenleri kod bloklarıyla ileten yol haritası ver.

---

## 1. Genel Mimari — Kanıtlanmış Güçlü Yönler

PMS reposu, *zanaatkar seviyesinde* tasarlanmış, kurumsal seviye bir SaaS PMS'tir. Dikkat çeken gerçek olarak doğrulanmış mimari kararlar:

### 1.1 Bounded Context Ayrımı (Hexagonal)
- `backend/channel_manager/` — Hexagonal mimari ile tam izole (`domain/`, `application/`, `infrastructure/`, `interfaces/`, `connectors/`).
- Provider-agnostik **canonical model** (`CanonicalRoomType`, `CanonicalRatePlan`, `InventorySlice`, `RestrictionSet`, `CanonicalReservation`) — yeni connector ekleme maliyeti minimal.
- HotelRunner v2 connector tam implement (XML builder/parser, OTA mesajları, token bucket rate limit, exponential backoff retry).

### 1.2 Multi-tenant + Tenant Context
- `core/tenant_db.py` → `tenant_context()` helper'ı request başına context set/reset yapıyor.
- Marketplace v1 (`routers/marketplace_b2b.py`) tenant-bağımsız API key ile çoklu otele tek noktadan erişim sağlıyor; `PRICE_TOLERANCE = 0.50` TL ile **price-spoofing koruması** mevcut.
- `routers/pms_outbound.py` Bearer API key + entitlement check (`tenant_has_module`) ile abonelik yaşam döngüsü kapanıyor — abonelik biterse credential silinmese bile 403 dönüyor. Bu çok iyi bir yaklaşım.

### 1.3 Güvenlik Katmanı
- `security/field_encryption.py` — HMAC-SHA256 deterministik search hash (queryable encrypted fields).
- `security/rotation_engine.py` + `reencryption_worker.py` — secret rotation ile transparent re-encryption.
- `routers/integration_credentials.py` — AES at-rest + startup'ta `os.environ` hidrasyonu (CREDENTIAL_DEFINITIONS tek doğru kaynak).
- `routers/mailing.py` — Resend webhook için **svix-style HMAC** doğrulama + replay protection (`hmac.compare_digest`).
- `routers/room_qr_requests.py` — QR token: HMAC-SHA256 (`tenant_id|room_id`, `JWT_SECRET`); DB'de extra state yok.
- PII strict mode router, classification, audit log immutable koleksiyon.

### 1.4 Operasyonel Olgunluk
- Webhook DLQ + manuel retry (`routers/webhook_admin.py`, `webhook_retry_service.py`).
- DORA metrics, deploy tracker, drift alerting (`controlplane/`).
- Sandbox simulation engine (`channel_manager/application/sandbox_simulation/`) — provider mock harness ile test.
- `docs/` altında: `GO_LIVE_RUNBOOK.md`, `INCIDENT_PLAYBOOK.md`, `BACKUP_AND_RESTORE.md`, `DISASTER_RECOVERY.md`, KVKK, PCI-DSS, SLO/SLA, penetration test plan, CHAOS testing master plan.

### 1.5 Test Kapsamı
- `backend/tests/` — 391+ test geçiyor (`test_secrets_manager.py`, channel_manager E2E, atomic booking, vb.).
- Shadow compare (`shared_kernel/shadow_metrics.py`) — yeni servisler legacy implementasyonla paralel çalıştırılıp parity doğrulanıyor (özellikle `pms_availability.py`'de — overbooking hassasiyeti).

**Sonuç:** Bu kod tabanı *gerçekten* production-grade. Ortalama bir B2B SaaS'ın çok üstünde.

---

## 2. Tespit Edilen Açık Konular ve Riskler

### 2.1 Bilinçli Stub'lar — `NotImplementedError` (kod hatası DEĞİL)

Aşağıdaki dosyalardaki `NotImplementedError`'lar abstract base class'lardır; pluggable provider pattern için bilerek konulmuştur. **Hata değildir**, ancak sözleşme:

| Dosya | Stub | Mevcut Concrete Impl |
|---|---|---|
| `core/secrets/vault_provider.py` | 6× NotImplementedError | `aws_secrets_manager`, `local_dev` çalışıyor — Vault sağlayıcısı yok |
| `infra/secrets_manager.py` | 3× | Aynı durum |
| `modules/event_bus/abstraction.py` | 4× | Concrete impl: in-memory + Redis adapter |
| `modules/messaging/providers.py` | 1× | Resend + SMTP |
| `modules/platform_scaling/messaging_gateway.py` | 1× | Pluggable |

**Risk:** Bir geliştirici yanlışlıkla Vault'u prod config'e koyarsa → app açılışta crash. **Öneri:** `vault_provider.py` `__init_subclass__` veya factory'de `if backend == "vault": raise ConfigurationError("Vault not implemented; use aws_secrets_manager")`.

### 2.2 Frontend — Eksik Tek İş

`test_result.md` dosyanızda `implemented: false` olan **tek** öğe:

```yaml
- task: "Channel Manager Ops Dashboard"
  implemented: false
  working: "NA"
  file: ""
  stuck_count: 0
  priority: "medium"
```

Backend tarafı (`channel_manager/interfaces/routers/dashboard_router.py`) hazır. Sadece React frontend'inde dashboard sayfası eksik. Backend endpoint'leri:
- `GET /api/channel-manager/v2/observability/dashboard` (toplu metrik)
- `GET /api/channel-manager/v2/connectors/{id}/health` (connector health)
- `GET /api/channel-manager/v2/sync/jobs?status=failed` (başarısız sync'ler)

### 2.3 `pass` Placeholder'ların Bağlamsal Analizi

Toplam 20+ `pass` satırı buldum. Hepsi kontrol edildi; **çoğu legitimate**:

| Konum | Durum |
|---|---|
| `bootstrap/middleware_registry.py` (4×), `observability_init.py` | Optional middleware — yokken sessizce geç (OK) |
| `infra/ws_redis_adapter.py:317`, `:349` | Redis disconnect race'lerinde sessiz fallback (OK) |
| `security/rotation_engine.py:411`, `:427` | Best-effort cleanup (OK) |
| `security/reencryption_worker.py:255` | Worker shutdown (OK) |
| `domains/revenue/rms_router/demand_forecast.py:105` ⚠️ | **Şüpheli** — exception silenceleniyor; logger çağrısı eklenmeli |
| `domains/revenue/rms_router/dashboards.py:187` ⚠️ | **Şüpheli** — aynı |
| `infra/redis_cluster.py:185`, `:226` | Cluster failover try/except — log yok |

**Aksiyon:** Sadece şüpheli olanlar için `logger.warning(...)` ekleyin.

### 2.4 `agency_endpoints.py` Yarım Bağlantı

`AGENCY_INTEGRATION_GUIDE.md` belgesi 3 TODO listesi sunuyor:
1. `compute_soft_availability_and_restrictions()` — mevcut helper'a bağlanmamış (placeholder dönüyor)
2. `compute_price_snapshot()` — `rate_periods` collection'ından okumuyor (placeholder)
3. `get_commission_pct_for_link()` — sabit %15 dönüyor

`agency_endpoints.py` dosyasını bulmaya çalıştım ama klonda yok (`/app/backend/` referansı var, repoda görünmüyor). Eğer oluşturmadıysanız bu acentenin güvenli rezervasyon talebi gönderme yolu kapalıdır. Üç fonksiyonun `server.py`'deki gerçek implementasyonlarına bağlanması gerekiyor.

### 2.5 Tek Dosya Şişkinliği

- `routers/integration_credentials.py` — 17 statik credential definition + AES + os.environ rewrite. Dosya makul ama yeni entegrasyon (CapX) ekledikçe `CREDENTIAL_DEFINITIONS` listesi büyüyecek; **registry pattern'a (her connector kendi tanımını contribute eder)** geçilmesi önerilir.
- `bootstrap/startup_phases.py` — 4 yerde `pass` + 1000+ satır; phased startup kompleks. Her phase'in ayrı modülü hak edebilir (örn. `phases/db_init.py`, `phases/security_init.py`).

### 2.6 Vault Backend Eksikliği — Compliance Risk

Eğer hedef pazar finans/sağlık ise (PCI-DSS L1 gereksinimi ile birlikte), `aws_secrets_manager` çoğunlukla yeterlidir; ancak **on-prem deploy senaryosu** için Vault impl yok. `local_dev` provider'ın production'da açılması engellenmeli — startup validator kontrolü eklenmeli (`if SECRETS_BACKEND == "local_dev" and ENV == "production": fail_fast`).

### 2.7 Diğer Küçük Notlar

- `routers/__init__.py` çok büyük — router auto-discovery convention'ı düşünülebilir (`importlib.iter_modules`).
- `channel_manager/connectors/hotelrunner_v2/` — XML üretimi sağlam; ancak **XML imzalama yok**. HotelRunner şu an XML imzası istemiyor; ama SiteMinder/Channex eklendiğinde gerekebilir.
- Frontend testleri sayısı backend'in çok altında; React komponent testleri (Jest + RTL) zayıf.

### 2.8 Kritik Olmayan Ama Düzeltilmeli

- `core/secrets/vault_provider.py:34` mesajı sözleşmeyi açıklıyor ama **ConfigurationError** sınıfı (özel exception) kullanmıyor. Custom exception type ile bunu değiştirin (Sentry'de filtrelenebilir).
- `routers/hotelrunner_compat.py:89-105` — webhook signature header çoklu isim kabul ediyor (`X-Signature` veya alternatifler). Bu legacy compat için OK ama dökümante edilmeli (currently sadece kod yorumunda).

---

## 3. CapX ↔ PMS Çift Taraflı Entegrasyon — PMS Tarafında Yapılacaklar

> **Kapsam:** CapX tarafında `/api/integrations/v1/pms/*` endpoint'leri **bu commit'te eklendi** (`backend/server.py`). PMS tarafında aşağıdaki yapı kurulduğunda iki sistem konuşacak.

### 3.1 Mimari Özet

```
┌────────────────┐       Bearer API key       ┌────────────────┐
│  Syroce PMS    │ ────────────────────────►  │     CapX       │
│  (sizin proje) │  POST /availability/sync   │ (bu workspace) │
│                │  POST /reservation/event   │                │
│                │       (HMAC imzalı)        │                │
│                │ ◄────────────────────────  │                │
│                │   POST /capx/match/notify  │                │
│                │       (HMAC imzalı)        │                │
└────────────────┘                            └────────────────┘
```

İki yön de **Bearer API key + HMAC-SHA256 webhook signature** kullanır — sizin `pms_outbound.py` + `mailing.py` (Resend) örüntülerinin aynısı.

### 3.2 CapX'in Sunduğu Endpoint'ler (PMS'in çağıracağı)

Aşağıdaki endpoint'ler CapX'te **ŞU AN aktif** (bu commit ile eklendi):

| Method | Path | Auth | Açıklama |
|---|---|---|---|
| `POST` | `/api/integrations/v1/pms/connect` | JWT (otel admin) | API key + webhook secret üretir (rotation desteği var). Yanıtta ham anahtar **bir kez** dönülür. |
| `GET`  | `/api/integrations/v1/pms/status` | JWT | Bağlantı durumu, son sync/event zamanı, sayaçlar. |
| `PUT`  | `/api/integrations/v1/pms/callback` | JWT | CapX → PMS yönündeki callback URL'i ayarla. |
| `POST` | `/api/integrations/v1/pms/disconnect` | JWT | Anahtarı revoke eder. |
| `POST` | `/api/integrations/v1/pms/availability/sync` | **Bearer API key** | PMS müsaitlik snapshot'ı push'lar; auto_publish=true ise CapX `availability_listings`'e idempotent upsert yapar. |
| `POST` | `/api/integrations/v1/pms/reservation/event` | **Bearer API key + X-CapX-Signature** | PMS rezervasyon olaylarını HMAC imzalı bildirir. `X-CapX-Event-Id` ile idempotent. |
| `GET`  | `/api/integrations/v1/pms/recent` | JWT | Son sync + event listesi (debug). |

### 3.3 PMS Tarafında Yapılacaklar — Adım Adım

#### Adım 1: Credential katalogüne CapX'i ekleyin

`backend/routers/integration_credentials.py` → `CREDENTIAL_DEFINITIONS` listesinin **Integrations** bölümüne ekleyin:

```python
# --- Integrations: CapX ---
{"key": "CAPX_BASE_URL", "name": "CapX Base URL", "category": "integrations",
 "description": "CapX prod API kökü, örn. https://api.capx.com.tr",
 "doc_url": "https://github.com/<sizin-capx-repo>"},
{"key": "CAPX_API_KEY", "name": "CapX API Key", "category": "integrations",
 "description": "Otel başına CapX'in /integrations/v1/pms/connect çağrısından dönen anahtar.",
 "doc_url": ""},
{"key": "CAPX_WEBHOOK_SECRET", "name": "CapX Webhook Secret", "category": "integrations",
 "description": "CapX'ten gelen rezervasyon-event-callback'leri imzalamak için kullanılan HMAC anahtarı.",
 "doc_url": ""},
```

> **Not:** Çoklu otel destekleyeceği için bu üçlü tenant başına olmalı. Önerim: `CREDENTIAL_DEFINITIONS`'e değil, **yeni bir koleksiyona** (`capx_integrations`) tenant başına yazın — `core/afsadakat_provisioner.py`'deki desenin aynısı.

#### Adım 2: CapX provisioner modülü

Yeni dosya: `backend/core/capx_provisioner.py` — `afsadakat_provisioner.py`'nin **kardeş kopyası**:

```python
"""CapX entegrasyon provisioner — afsadakat_provisioner.py kardeşi.

Per-tenant API key + webhook secret saklar; CapX'in /connect cevabını alıp
saklar; outbound HMAC için secret döner; entitlement bağlama opsiyonel.
"""
from __future__ import annotations
from datetime import UTC, datetime
from typing import Any
import hashlib
from core.database import db
from core.crypto import get_crypto_service

CAPX_PRODUCT_KEY = "capx_marketplace"
COLLECTION = "capx_integrations"


async def store_capx_credentials(tenant_id: str, base_url: str, api_key: str, webhook_secret: str) -> dict:
    crypto = get_crypto_service()
    now = datetime.now(UTC)
    doc = {
        "tenant_id": tenant_id,
        "base_url": base_url.rstrip("/"),
        "api_key_enc": crypto.encrypt(api_key),
        "api_key_hash": hashlib.sha256(api_key.encode()).hexdigest(),
        "webhook_secret_enc": crypto.encrypt(webhook_secret),
        "status": "active",
        "updated_at": now,
    }
    await db[COLLECTION].update_one(
        {"tenant_id": tenant_id},
        {"$set": doc, "$setOnInsert": {"connected_at": now}},
        upsert=True,
    )
    return doc


async def get_capx_credentials(tenant_id: str) -> dict | None:
    doc = await db[COLLECTION].find_one({"tenant_id": tenant_id, "status": "active"})
    if not doc:
        return None
    crypto = get_crypto_service()
    return {
        "base_url": doc["base_url"],
        "api_key": crypto.decrypt(doc["api_key_enc"]),
        "webhook_secret": crypto.decrypt(doc["webhook_secret_enc"]),
    }


async def find_tenant_by_capx_api_key(api_key: str) -> dict | None:
    """CapX'ten gelen webhook'larda Bearer auth için kullanılır (CapX otelin
    PMS'ine push yaparken kendi anahtarını kullanır — biz hash karşılaştırırız)."""
    h = hashlib.sha256(api_key.encode()).hexdigest()
    return await db[COLLECTION].find_one({"api_key_hash": h, "status": "active"})
```

#### Adım 3: CapX channel_manager connector'ı

`backend/channel_manager/connectors/capx/` dizini açın. HotelRunner v2 connector'ı **örnek alın**:

```
backend/channel_manager/connectors/capx/
├── __init__.py
├── client.py           # httpx async client + retry/rate limit (mevcut hotelrunner_v2/client.py kopyası)
├── auth.py             # Bearer API key header injection
├── mapper.py           # CapX listing/event → CanonicalReservation / InventorySlice
├── outbound.py         # PMS → CapX: availability/sync + reservation/event push
└── webhook_handler.py  # CapX → PMS: match.created, match.cancelled callbacks
```

`outbound.py` çekirdeği — CapX'in HMAC bekleyen endpoint'i (`/reservation/event`) için:

```python
import hmac, hashlib, json, uuid
from typing import Any
import httpx
from core.capx_provisioner import get_capx_credentials


async def push_reservation_event(tenant_id: str, event_type: str, external_id: str,
                                 room_type: str, pax: int, date_start, date_end,
                                 occurred_at, payload: dict[str, Any] | None = None) -> dict:
    creds = await get_capx_credentials(tenant_id)
    if not creds:
        return {"skipped": "capx_not_connected"}

    body = {
        "event_type": event_type,                   # reservation.created|updated|cancelled
        "external_id": external_id,
        "room_type": room_type,
        "pax": pax,
        "date_start": date_start.isoformat(),
        "date_end": date_end.isoformat(),
        "occurred_at": occurred_at.isoformat(),
        "payload": payload or {},
    }
    body_bytes = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = hmac.new(creds["webhook_secret"].encode(), body_bytes, hashlib.sha256).hexdigest()
    event_id = str(uuid.uuid4())

    url = f"{creds['base_url']}/api/integrations/v1/pms/reservation/event"
    headers = {
        "Authorization": f"Bearer {creds['api_key']}",
        "Content-Type": "application/json",
        "X-CapX-Signature": f"sha256={sig}",
        "X-CapX-Event-Id": event_id,
    }
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(url, content=body_bytes, headers=headers)
    return {"status": r.status_code, "body": r.text, "event_id": event_id}


async def push_availability_snapshot(tenant_id: str, date_start, date_end, rooms: list[dict],
                                     region: str | None = None, auto_publish: bool = True,
                                     external_ref: str | None = None) -> dict:
    creds = await get_capx_credentials(tenant_id)
    if not creds:
        return {"skipped": "capx_not_connected"}

    body = {
        "date_start": date_start.isoformat(),
        "date_end": date_end.isoformat(),
        "region": region,
        "rooms": rooms,                # [{room_type, pax, price_min, price_max, currency, notes}]
        "auto_publish": auto_publish,
        "external_ref": external_ref,
    }
    url = f"{creds['base_url']}/api/integrations/v1/pms/availability/sync"
    headers = {
        "Authorization": f"Bearer {creds['api_key']}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(url, json=body, headers=headers)
    return {"status": r.status_code, "body": r.text}
```

> **HMAC kuralı (CRITICAL):** CapX tarafı imza doğrulamasını **ham body byte'ları** üzerinde yapıyor. Yukarıdaki kodda `json.dumps(..., separators, sort_keys)` ile *deterministik* serialize edip aynı byte'ları hem imza hem POST body olarak gönderiyoruz. Aksi halde imza tutmaz.

#### Adım 4: CapX Router (PMS-side)

Yeni dosya: `backend/routers/integrations_capx.py` — `integrations_afsadakat.py` kardeş kopyası:

```python
"""CapX entegrasyon endpoint'leri.

- /api/integrations/capx/connect (tenant admin)  → CapX'e connect çağrısı yap, secret'ları sakla
- /api/integrations/capx/status (tenant admin)   → bağlantı durumu
- /api/integrations/capx/disconnect (tenant admin)
- /api/integrations/capx/webhook (CapX → us, Bearer + HMAC)  → CapX olaylarını al
- /api/integrations/capx/sync-availability (tenant admin, manuel push)
"""
from __future__ import annotations
import hashlib
import hmac
import logging
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
import httpx

from core.capx_provisioner import (
    CAPX_PRODUCT_KEY, get_capx_credentials, store_capx_credentials,
    find_tenant_by_capx_api_key,
)
from core.security import get_current_user
from core.subscriptions import tenant_has_module
from models.schemas import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/integrations/capx", tags=["capx"])


class CapxConnectRequest(BaseModel):
    base_url: str = Field(..., min_length=8, max_length=256)
    capx_admin_jwt: str = Field(..., min_length=10)  # otelin CapX'teki JWT'si (tek kullanım)


@router.post("/connect")
async def connect(payload: CapxConnectRequest, user: User = Depends(get_current_user)) -> dict:
    if not user.tenant_id:
        raise HTTPException(403, "Tenant gerekli")
    if not await tenant_has_module(user.tenant_id, CAPX_PRODUCT_KEY):
        raise HTTPException(403, "CapX modülü için aktif abonelik bulunamadı")

    # CapX'e tek kullanımlık JWT ile /connect çağrısı yap
    url = f"{payload.base_url.rstrip('/')}/api/integrations/v1/pms/connect"
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(url, headers={"Authorization": f"Bearer {payload.capx_admin_jwt}"})
    if r.status_code != 200:
        raise HTTPException(502, f"CapX /connect başarısız: {r.status_code} {r.text}")

    data = r.json()
    await store_capx_credentials(
        tenant_id=user.tenant_id,
        base_url=payload.base_url,
        api_key=data["api_key"],
        webhook_secret=data["webhook_secret"],
    )
    return {"connected": True, "webhook_url": data["webhook_url"], "sync_url": data["sync_url"]}


@router.get("/status")
async def status(user: User = Depends(get_current_user)) -> dict:
    if not user.tenant_id:
        raise HTTPException(403, "Tenant gerekli")
    creds = await get_capx_credentials(user.tenant_id)
    if not creds:
        return {"connected": False}
    # Üst düzey HTTP status check
    async with httpx.AsyncClient(timeout=5) as c:
        r = await c.get(
            f"{creds['base_url']}/api/integrations/v1/pms/status",
            headers={"Authorization": f"Bearer {creds['api_key']}"},
        )
    return {"connected": True, "remote": r.json() if r.status_code == 200 else {"error": r.status_code}}


@router.post("/webhook")
async def capx_webhook(
    request: Request,
    authorization: str | None = Header(default=None),
    x_capx_signature: str | None = Header(default=None),
):
    """CapX → PMS callback (eşleşme, iptal, fatura)."""
    api_key = (authorization or "").removeprefix("Bearer ").strip()
    integ = await find_tenant_by_capx_api_key(api_key)
    if not integ:
        raise HTTPException(401, "Geçersiz CapX API anahtarı")

    body_bytes = await request.body()
    # CapX kendi webhook secret'ı ile imzalar
    creds = await get_capx_credentials(integ["tenant_id"])
    sig = (x_capx_signature or "").removeprefix("sha256=")
    expected = hmac.new(creds["webhook_secret"].encode(), body_bytes, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise HTTPException(401, "İmza doğrulanamadı")

    import json
    event = json.loads(body_bytes.decode())
    # event = {"type": "match.created"|"match.cancelled", "match_id": ..., "listing_id": ..., ...}
    # PMS tarafında: ChannelManager event_bus'a publish → reservation_import_service işlesin
    from modules.event_bus import publish
    await publish(f"capx.{event.get('type', 'unknown')}", event, tenant_id=integ["tenant_id"])
    return {"received": True}
```

`backend/server.py`'de router'ı mount edin (mevcut `app.include_router(...)` blokları arasında):

```python
try:
    from routers.integrations_capx import router as capx_router
    app.include_router(capx_router)
    print("✅ CapX integration router mounted")
except ImportError as e:
    print(f"⚠️ CapX router not available: {e}")
```

#### Adım 5: Channel Manager Domain Event Hook

`channel_manager/application/inventory_sync_service.py` ya da PMS'in rezervasyon yaratma akışında, CapX'e push tetikleyici ekleyin (event-driven, fire-and-forget):

```python
# Örnek: PMS booking confirmed olduğunda
from channel_manager.connectors.capx.outbound import push_reservation_event

async def on_booking_confirmed(booking, tenant_id):
    # ... mevcut iş ...
    await push_reservation_event(
        tenant_id=tenant_id,
        event_type="reservation.created",
        external_id=booking["_id"],
        room_type=booking["room_type"],
        pax=booking["pax"],
        date_start=booking["check_in"],
        date_end=booking["check_out"],
        occurred_at=booking["created_at"],
        payload={"source": "pms", "booking_ref": booking.get("ref")},
    )
```

İptalde `event_type="reservation.cancelled"` ile aynı `external_id` gönderin — CapX otomatik `availability_listings`'i kapatır.

#### Adım 6: Müsaitlik Push Job'u

CapX'e müsaitlik push'unu yapacak periyodik bir job ekleyin (her oda tipinde değişiklik olduğunda veya saatte 1):

```python
# backend/modules/inventory/jobs/capx_availability_push.py
from channel_manager.connectors.capx.outbound import push_availability_snapshot

async def push_today_to_capx(tenant_id: str, hotel_id: str):
    rooms = await compute_capx_eligible_inventory(tenant_id, hotel_id, days=14)
    # rooms = [{room_type: "deluxe-doble", pax: 5, price_min: 4000, price_max: 6000, currency: "TRY"}]
    if not rooms:
        return
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    await push_availability_snapshot(
        tenant_id=tenant_id,
        date_start=now,
        date_end=now + timedelta(days=14),
        rooms=rooms,
        region="Sapanca",      # veya hotel.region
        auto_publish=True,
        external_ref=f"snapshot-{now.strftime('%Y%m%d')}",
    )
```

`scheduler_service.py` veya `ml_scheduler.py` içine cron olarak bağlayın.

#### Adım 7: Webhook DLQ Entegrasyonu (önerilen)

CapX'e gönderilen event'ler de sizin mevcut `webhook_admin.py` DLQ sistemine girmeli. `webhook_retry_service.py:110`'daki HMAC pattern aynısı zaten kullanılabilir; `outbound.push_reservation_event` çağrısını `webhook_deliveries` koleksiyonu üzerinden async kuyruğa atın → mevcut retry engine devralır.

#### Adım 8: Test Stratejisi

`backend/tests/integrations/test_capx_outbound.py`:

```python
import hmac, hashlib, json
import pytest
from httpx import AsyncClient
from channel_manager.connectors.capx.outbound import push_reservation_event

@pytest.mark.asyncio
async def test_hmac_signature_format(monkeypatch):
    """CapX'e gönderilen imza doğru formatlanmış olmalı."""
    captured = {}
    class FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def post(self, url, content, headers):
            captured["headers"] = headers
            captured["body"] = content
            class R: status_code = 200; text = "{}"
            return R()
    monkeypatch.setattr("channel_manager.connectors.capx.outbound.httpx.AsyncClient", lambda **k: FakeClient())
    monkeypatch.setattr("channel_manager.connectors.capx.outbound.get_capx_credentials",
                        lambda tid: {"base_url": "http://x", "api_key": "k", "webhook_secret": "s"})
    from datetime import datetime
    await push_reservation_event("t1", "reservation.created", "ext1", "deluxe", 2,
                                 datetime(2025,1,1), datetime(2025,1,3), datetime.utcnow())
    assert captured["headers"]["X-CapX-Signature"].startswith("sha256=")
    sig = captured["headers"]["X-CapX-Signature"].split("=",1)[1]
    expected = hmac.new(b"s", captured["body"], hashlib.sha256).hexdigest()
    assert sig == expected
```

### 3.4 PMS Frontend (Hotel Admin Paneli)

`Settings → Entegrasyonlar` sayfasına CapX kartı ekleyin (mevcut Af-sadakat kartının yanına):

```
┌─────────────────────────────────────┐
│ 🛏️ CapX Marketplace                 │
│ Kapasite paylaşım ağı (Türkiye)     │
│                                     │
│ Durum: Bağlı (last sync: 5 dk önce) │
│ API Key: ****a4f2                   │
│                                     │
│ [Bağlantıyı Yenile] [Bağlantıyı Kes]│
└─────────────────────────────────────┘
```

Endpoint çağrıları sırayla:
1. `POST /api/integrations/capx/connect` — base_url + capx_admin_jwt input'u alır
2. `GET /api/integrations/capx/status` — kart üzerinde live status

### 3.5 Güvenlik Checklist (PMS Side)

- [ ] `webhook_secret` ham haliyle log'a yazmayın — `core.crypto`'da encrypt edin.
- [ ] `find_tenant_by_capx_api_key` MongoDB query'sini hash üzerinden yapın (constant-time değil ama hash collision pratikte imkansız).
- [ ] Rate limit ekleyin: `slowapi` veya mevcut `infra/rate_limiter.py` ile `/api/integrations/capx/webhook` için 120/dk.
- [ ] CapX'e gönderdiğiniz **outbound** request'ler için httpx timeout ZORUNLU (yukarıdaki örneklerde 10-15s); aksi halde hung connection sızar.
- [ ] CapX'in CORS politikası: `PUBLIC_BASE_URL` env ortam başına ayrı (sandbox/prod).
- [ ] Replay protection (önerilen): CapX `X-CapX-Event-Id` gönderiyor — sizin tarafta bu ID'yi `processed_capx_events` koleksiyonunda 24 saat tutun, duplicate ise 200 dönün ama event'i tekrar işlemeyin.

---

## 4. Kapanış — Önerilen Sıralama

PMS reposunuzda **bu sıra ile** ilerleyin (her madde atomik PR olabilir):

| # | İş | Süre Tahmini | Bağımlılık |
|---|---|---|---|
| 1 | `core/capx_provisioner.py` + indeksler | 2 saat | — |
| 2 | `routers/integrations_capx.py` + mount | 3 saat | 1 |
| 3 | `channel_manager/connectors/capx/outbound.py` (HMAC fix kritik) | 4 saat | 1 |
| 4 | Booking event hook (created/cancelled push) | 2 saat | 3 |
| 5 | Periyodik availability push job | 3 saat | 3 |
| 6 | Frontend: Settings → CapX kartı | 4 saat | 2 |
| 7 | Test suite (HMAC + idempotency + DLQ) | 4 saat | 4,5 |
| 8 | Channel Manager Ops Dashboard frontend (test_result.md eksik tek iş) | 1-2 gün | — (bağımsız) |
| 9 | (Opsiyonel) `agency_endpoints.py` 3 TODO bağlantısı | 4 saat | — |
| 10 | (Opsiyonel) Vault provider impl veya prod-time guard | 2 saat | — |

**Toplam minimum CapX entegrasyonu:** ~22 saat (3 gün) tek geliştirici ile. Bu sürede CapX tarafı (`/integrations/v1/pms/*`) zaten hazır olduğu için iki sistemi gerçek uçtan uca konuşturabilirsiniz.

---

## 5. Sözleşmeler — Hızlı Referans

### 5.1 HMAC İmza Formatı (CapX'in beklentisi)

```
header: X-CapX-Signature: sha256=<hex>
body:   raw bytes (deterministic JSON: separators=(",",":"), sort_keys=True önerilir)
hash:   hmac_sha256(webhook_secret, body) → hex digest
```

### 5.2 Event ID (idempotency)

```
header: X-CapX-Event-Id: <uuid4>
```
Aynı event_id ile tekrar gönderilen istek CapX'te yutulur, `{"received": true, "duplicate": true}` döner.

### 5.3 Auth Hata Kodları

| HTTP | Anlam |
|---|---|
| 401 | Eksik/geçersiz Bearer token, eksik X-CapX-Signature, imza tutmuyor |
| 403 | Token geçerli ama abonelik aktif değil (entitlement check) |
| 400 | Payload validation hatası (date_end <= date_start vb.) |
| 429 | Rate limit (60/dk sync, 120/dk event) |

### 5.4 Koleksiyon İsimleri (CapX tarafı)

```
pms_integrations              — connection state per hotel (unique hotel_id)
pms_availability_snapshots    — her snapshot history
pms_reservation_events        — her event idempotent (unique _id = X-CapX-Event-Id)
pms_outbound_events           — CapX → PMS giden olayların outbox'ı (retry/replay)
availability_listings         — pms_external_ref alanı eklendi (sparse index)
```

---

## 6. CapX → PMS Yönü — Inbound Webhook Şartnamesi (PMS tarafının uygulayacağı)

CapX'te bir eşleşme oluştuğunda veya iptal edildiğinde, **otelin daha önce
kaydettiği `callback_url`** adresine HTTP POST ile imzalı bir webhook gönderilir.
PMS bu olayı alıp kendi rezervasyon kayıtlarını oluşturur/iptal eder.

### 6.1 Bağlantı Hazırlığı

PMS panelinden otelin CapX'e bağlanması için şu üç değer alınır
(otel CapX panelinde "PMS Bağlantısı → Bağlan" deyince ekrana **bir kez**
düşer; sonradan tekrar gösterilmez, kopyalanmalıdır):

| Değer | Açıklama |
|---|---|
| `CAPX_BASE_URL` | CapX prod domain (ör. `https://capx.replit.app`) |
| `CAPX_API_KEY`  | PMS → CapX yönündeki Bearer token (request başlıklarında) |
| `CAPX_WEBHOOK_SECRET` | CapX → PMS yönündeki HMAC imza anahtarı (alıcı doğrulaması için) |

CapX → PMS yönü için PMS'in ek olarak şunu yapması gerekir:
**callback URL'sini CapX'e bildirmek** (otel paneli üzerinden):

```
PUT  {CAPX_BASE_URL}/api/integrations/v1/pms/callback
Authorization: Bearer <otel JWT>      ← otelin login token'ı
Content-Type:  application/json

{ "callback_url": "https://pms.example.com/capx/webhook" }
```

> Bu URL **PMS sunucusunda public'e açık** olmalı, HTTPS önerilir, 10 saniye
> içinde 2xx döndürmelidir. CapX 4 deneme yapar; ardışık denemeler arasında
> 2s → 10s → 30s eksponansiyel backoff uygular. 4. deneme de başarısızsa olay
> `failed` durumuna düşer ve manuel replay için endpoint açılır.
>
> **SSRF guard:** CapX `callback_url` olarak verilen adresin DNS çözümünü
> yapar; loopback/private/link-local/metadata endpoint'lerine yönelen URL'leri
> reddeder. Dev/test için `PMS_ALLOW_LOOPBACK_CALLBACK=1` env değişkeni
> loopback ve özel ağlara izin verir (metadata endpoint'leri her durumda yasak).

### 6.2 Webhook İstek Formatı

CapX, PMS'in `callback_url` adresine şu istekle gelir:

```http
POST https://pms.example.com/capx/webhook
Content-Type:    application/json; charset=utf-8
User-Agent:      CapX-Webhook/1.0
X-CapX-Event-Id:    <uuid4>                    ← idempotency anahtarı
X-CapX-Event-Type:  match.created | match.cancelled
X-CapX-Signature:   sha256=<hex>               ← bkz §6.3

<JSON body — bkz §6.4>
```

**PMS handler şu üç adımı yapmalı:**
1. `X-CapX-Signature` doğrula (uymuyorsa 401).
2. `X-CapX-Event-Id` daha önce işlendi mi kontrol et (idempotent — duplicate
   ise 200 dönüp hiçbir şey yapma).
3. Olayı işle ve **mutlaka 2xx döndür** (yoksa retry tetiklenir).

### 6.3 İmza Doğrulama (PMS tarafı örnek — Python)

```python
import hmac, hashlib

def verify_capx_signature(secret: str, raw_body: bytes, header: str) -> bool:
    if not header or not header.startswith("sha256="):
        return False
    received = header.split("=", 1)[1]
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(received, expected)

# Örnek FastAPI handler
@app.post("/capx/webhook")
async def capx_webhook(request: Request,
                       x_capx_signature: str = Header(...),
                       x_capx_event_id: str = Header(...),
                       x_capx_event_type: str = Header(...)):
    raw = await request.body()
    if not verify_capx_signature(CAPX_WEBHOOK_SECRET, raw, x_capx_signature):
        raise HTTPException(401, "bad signature")
    if await db.processed_capx_events.find_one({"_id": x_capx_event_id}):
        return {"received": True, "duplicate": True}
    payload = json.loads(raw)
    await handle_capx_event(x_capx_event_type, payload)
    await db.processed_capx_events.insert_one({"_id": x_capx_event_id})
    return {"received": True}
```

> **Önemli:** İmza, **alınan ham body byte'ları** üzerinden hesaplanır. Body'yi
> JSON'a parse edip yeniden serialize ederek imza hesaplamak HMAC'i bozar.

### 6.4 Payload Şemaları

#### 6.4.1 `match.created`

```json
{
  "event_type": "match.created",
  "occurred_at": "2026-05-05T09:18:42.123456+00:00",
  "match": {
    "id": "80f13afa-bdab-451d-aa32-811e8dd477cb",
    "reference_code": "SPC-2026-00001",
    "status": "active",
    "direction": "incoming",
    "fee_amount": 0,
    "currency": "TRY",
    "accepted_at": "2026-05-05T09:18:41.987654+00:00",
    "cancelled_at": null,
    "cancel_reason": null,
    "counterparty_hotel": {
      "id": "...",
      "name": "GuestHotelXYZ",
      "region": "Sapanca",
      "micro_location": "Kırkpınar",
      "phone": "5559876543",
      "contact_person": "B Owner"
    },
    "listing": {
      "id": "...",
      "concept": "Çift Kişilik",
      "region": "Sapanca",
      "micro_location": "Sapanca Merkez",
      "date_start": "2026-05-15T00:00:00+00:00",
      "date_end": "2026-05-17T00:00:00+00:00",
      "nights": 2,
      "pax": 2,
      "capacity_label": "DBL",
      "price_min": 1000,
      "price_max": 2000,
      "pms_external_ref": null
    }
  }
}
```

#### 6.4.2 `match.cancelled`

`match.created` ile **aynı şema**, ek alanlar dolu olur:

```json
{
  "event_type": "match.cancelled",
  "occurred_at": "...",
  "match": {
    ...,
    "status": "cancelled",
    "cancelled_at": "2026-05-05T09:19:55.000000+00:00",
    "cancel_reason": "müşteri iptal etti"
  }
}
```

### 6.5 `direction` Alanı — Hangi Tarafa Push Geldi?

CapX bir eşleşmeyi **her iki tarafın PMS'ine de** push eder (her PMS yalnızca
kendi otelinin sahip olduğu bağlantı için olayı görür). Payload'daki
`direction` alanı PMS'e kendisinin hangi rolde olduğunu söyler:

| `direction` | Anlamı |
|---|---|
| `incoming` | Misafir **bu otele geliyor** (host = ilan sahibi). PMS bir rezervasyon **açmalı**. |
| `outgoing` | Bu otel misafirini **karşı otele gönderiyor** (guest). PMS bunu **giden transfer** olarak loglayabilir; rezervasyon açmaya gerek yok. |

PMS handler `direction == "incoming"` olduğunda kendi rezervasyon sistemine
yeni kayıt açar. `outgoing` için yalnızca kayıt amacıyla saklayabilir veya
yutabilir.

### 6.6 Retry & Replay

- CapX otomatik retry: **4 deneme**, ardışık denemelerin arasında `2s → 10s → 30s`
  eksponansiyel backoff. (Bir denemenin transport timeout'u 10 saniyedir.)
- **Concurrency güvencesi:** Her olayın `dispatch_id` token'ı vardır; manuel
  retry token'ı yeniler → varsa eski task abort eder, duplicate POST olmaz.
- **Restart dayanımı:** CapX süreci yeniden başlatıldığında startup hook'u
  yetim `pending`/`in_flight` (lease süresi geçmiş) olayları toplar ve
  teslimatı yeniden başlatır.
- Tüm denemeler başarısız olursa olay `failed` durumuna düşer ve **otel
  panelinden manuel yeniden gönderim** yapılabilir:

  ```
  POST {CAPX_BASE_URL}/api/integrations/v1/pms/events/{event_id}/retry
  Authorization: Bearer <otel JWT>
  ```

- Otel panelinde son 50 olayın listesi:

  ```
  GET {CAPX_BASE_URL}/api/integrations/v1/pms/events?limit=50
  Authorization: Bearer <otel JWT>
  ```

  Yanıt her olay için `id, event_type, status, attempts, last_error,
  callback_url, last_response_status, created_at, delivered_at, last_attempt_at,
  match_id, reference_code` döner.

### 6.7 Hata Tablosu (CapX'in PMS yanıtına yorumu)

| PMS HTTP yanıt | CapX davranışı |
|---|---|
| 2xx       | `delivered`. Bir daha gönderilmez. |
| 3xx       | Hata sayılır, retry. (PMS endpoint sabit kalmalı.) |
| 4xx (özellikle 401) | Hata sayılır, retry. PMS imzayı doğru kontrol etmeli. |
| 5xx       | Hata sayılır, retry. |
| Timeout (>10s) | Hata sayılır, retry. |
| Tüm denemeler tükendi | `failed`. Manuel replay gerekir. |

### 6.8 Tetiklenen Olay Noktaları (CapX tarafı, referans için)

| Olay | Tetiklenme Anı | Kod Noktası |
|---|---|---|
| `match.created` | Talep kabul (`POST /requests/{id}/accept`) | `app/routers/requests_matches.py` accept handler sonu |
| `match.created` | Alternatif kabul (`POST /requests/{id}/accept-alternative`) | Aynı dosyada accept-alternative handler sonu |
| `match.cancelled` | Eşleşme iptal (`POST /matches/{id}/cancel`) | Aynı dosyada cancel_match handler sonu |

---

> **Not:** Bu rapor `/tmp/pms/pms` üzerindeki kod taramalarına ve sizin kendi `docs/` + `test_result.md` + `AGENCY_INTEGRATION_GUIDE.md` belgelerinize dayanmaktadır. Hatalı çıkan bir saptama görürseniz bana özel olarak ileterek raporu güncelleyeyim.
