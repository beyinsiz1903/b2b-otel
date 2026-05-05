# CapX ↔ PMS Production Deploy Planı

> Durum: UAT üç kanalda yeşil (bkz. `replit.md` → "CapX ↔ PMS UAT entegrasyonu" milestone, 2026-05-05). Bu döküman, UAT'den production'a geçiş için ortak checklist'tir. **Deploy değil — onaya hazır plan.**

---

## 1) Production Deploy Sırası (her adım blocker)

### Faz 0 — Hazırlık (deploy öncesi)
- [ ] **PMS ekibinden 3 sorunun cevabı** (bkz. §4) yazılı alınır.
- [ ] Prod deployment hedefi netleştirilir: Replit Reserved VM (önerilen, persistent + custom domain destekler) vs Autoscale.
- [ ] `MONGO_URL` prod cluster'ı UAT'den ayrı mı? Eğer aynıysa namespace ayrımı için `DB_NAME` env override (örn. `hotel_match_prod`) gerekir — şu an default `hotel_match_db`.
- [ ] Prod için ayrı Resend domain doğrulaması (UAT mail'lerinin prod tenant'lara gitmemesi için).
- [ ] `FRONTEND_URL` prod env'e eklenir (reset link doğru domain'e işaret etmeli).

### Faz 1 — Backend prod publish
- [ ] Replit "Publish" → Reserved VM, region: en yakın Avrupa (Frankfurt/Amsterdam).
- [ ] Health check path: `GET /api/` (mevcut endpoint döner).
- [ ] Env secrets prod'a kopyalanır: `MONGO_URL`, `JWT_SECRET`, `RESEND_API_KEY` (connector), Google Sheets OAuth credentials, `FRONTEND_URL`.
- [ ] **`PMS_ALLOW_LOOPBACK_CALLBACK` prod'da SET EDİLMEZ** (UAT'ye özel SSRF guard bypass'ı).
- [ ] Smoke: prod URL'inden `GET /api/` 200, `POST /api/auth/login` test hesabıyla 401/200.

### Faz 2 — PMS tenant prod onboarding (UAT'den taşıma DEĞİL — sıfırdan)
- [ ] Prod'da gerçek otel admin kayıt + admin onay akışı (UAT bypass yok, gerçek prosedür).
- [ ] **`backend/scripts/bootstrap_pms_uat_tenant.py` PROD'DA KOŞULMAZ** — yalnız UAT için. Prod onboarding admin UI üzerinden olur (`POST /api/integrations/v1/pms/connect`, JWT ile).
- [ ] PMS ekibi prod credentials'ı (api_key + webhook_secret) bir kez alır → kendi prod vault'larına yazar.
- [ ] PMS ekibi prod callback URL'ini bildirir → CapX admin paneli "Inbound Callback URL" kartından girer (frontend zaten hazır, bkz. CapX Integration sayfası).

### Faz 3 — Prod smoke (UAT senaryosunun aynısı)
- [ ] `availability/sync` tek snapshot → 200 OK + listing upsert.
- [ ] `reservation/event` tek event → 200 OK, idempotent (aynı `X-CapX-Event-Id` ikinci kez 200 + duplicate yutar).
- [ ] CapX'te bir test eşleşme yarat → PMS callback `match.created` delivered (HMAC OK).
- [ ] CapX'te match cancel → PMS callback `match.cancelled` delivered.
- [ ] `pms_outbound_events` tablosunda `failed` veya 1+ saatten eski `pending` kalmadığı doğrulanır.

### Faz 4 — Gözlem (ilk 7 gün)
- [ ] Replit deployment logs günde bir kez kontrol — `pms_outbound` timeout/retry oranı, 5xx oranı.
- [ ] `pms_outbound_events` koleksiyonunda `failed` durumdaki event'ler için manuel inceleme.
- [ ] PMS tarafıyla haftalık 15 dk sync — duplicate, missing event, mismatch raporu.

---

## 2) Rollback Planı

| Senaryo | Aksiyon |
|---|---|
| Prod webhook'lar PMS'e ulaşmıyor (>10 dk) | CapX admin panelden tenant `callback_url` boşaltılır → outbound publisher sessizce skip eder, eşleşme akışı bozulmaz. PMS düzelttiğinde URL geri set. |
| PMS'ten gelen event'ler 5xx üretiyor | PMS api_key disable: `pms_integrations.status = "disabled"` → tüm inbound 401, ama prod CapX UI çalışmaya devam eder. |
| MongoDB prod cluster sorunu | Replit checkpoint rollback (replit.md → diagnostics skill). Veri kaybı riski yok — outbox idempotent. |
| Tüm entegrasyonu kapatmak | Tek SQL eşdeğeri: `db.pms_integrations.updateMany({}, {$set: {status: "disabled"}})`. CapX core fonksiyonları etkilenmez. |

---

## 3) Risk Matrisi (kalan)

| Risk | Olasılık | Etki | Azaltma |
|---|---|---|---|
| Prod callback URL değişimi (Replit dev → replit.app → custom domain) | Yüksek (3 değişim olabilir) | Orta — yanlış URL → outbound timeout | Her değişimde tek admin UI alanı (frontend hazır), retry mekanizması zaten kurtarır. |
| Webhook secret rotation (PMS isterse) | Düşük | Yüksek — eski secret'la imzalı in-flight event'ler 401 alır | Rotation öncesi `pms_outbound_events` queue'su drain edilir (tüm `pending` delivered olana kadar bekle, sonra rotate). |
| Otel `auto_publish=true` ile yanlış fiyatla canlıya açılırsa | Orta | Yüksek — gerçek satış kaybı | İlk 24 saat `auto_publish=false` ile snapshot toplanır, otel admin manuel publish eder; sonra opt-in olarak true'ya alınır. |
| OTA-tetikli yüksek frekans availability/sync | Bilinmiyor (PMS soru #3) | DB write yükü | Rate limit `pms_integrations` başına dakikalık quota; soru #3 cevabıyla kalibre edilir. |

---

## 4) PMS Ekibinden Alınan Cevaplar (2026-05-05) — ✅ TAM

### 1. Prod callback URL formatı + geçiş — ✅
- **Format:** İlk lansman `*.replit.app` (Replit Deployments default). Custom domain (örn. `pms.syroce.com`) Faz 2'de tenant başına eklenecek; prod kanalı bu beklenmeden açılabilir.
- **Geçiş:** Paralel açık model. PMS prod publish + smoke → yeni base URL gelir → CapX prod admin panelinden tenant `5bad4a34-…` callback URL güncellenir → UAT 7 gün paralel açık (her iki ortam dinler, idempotency_key sayesinde duplicate yok) → Faz 5 yeşilse UAT credential CapX panelinden disable.

### 2. Prod credential paketi — ✅ ayrı set onaylandı
- UAT/prod izolasyonu: prod'da yeni hotel + `POST /api/integrations/v1/pms/connect` ile yeni `api_key`+`webhook_secret` üretilir, ham anahtar bir kez döner.
- PMS tarafında AES-256-GCM şifreli olarak `capx_tenant_credentials` koleksiyonuna yazılır (`PUT /api/capx/tenant-credentials/{tenant_id}`).
- UAT credential prod'a hiç taşınmaz.

### 3. Prod rate limit / hacim — ✅ sayılar net
| Metrik | İlk 30 gün | 90 gün hedefi |
|---|---|---|
| `availability/sync` | tenant başına ~96/gün (15 dk cron) + manuel UI burst | aynı + OTA push |
| `reservation/event` | peak ~5 event/sn, ortalama <0.5/sn | peak ~20/sn |
| Tenant sayısı | 1 (Syroce pilot) | 5–10 |

**PMS önerisi (CapX tarafında uygulanacak):**
- `availability/sync` → tenant başına **10/dk** (manuel snapshot burst için tampon)
- `reservation/event` → tenant başına **50/sn** (peak × 2.5 güvenlik payı)
- Aşımda HTTP **429 + Retry-After**; PMS adapter exponential backoff retry yapar.

---

## 5) CapX Prod Kalan İş Kalemleri (cevaplar sonrası)

Faz 1 (prod publish) öncesi tamamlanacak somut işler:

### Kod değişiklikleri (küçük)
- [ ] **Tenant-bazlı rate limit** — `backend/app/routers/pms.py`'a `slowapi` ile per-tenant limit:
  - `POST /availability/sync`: `10/minute` per `api_key_hash`
  - `POST /reservation/event`: `50/second` per `api_key_hash`
  - 429 yanıtında `Retry-After` header zorunlu (slowapi default veriyor).
- [ ] **`PUBLIC_BASE_URL` env desteği** — şu an reset link `FRONTEND_URL` veya `REPLIT_DEV_DOMAIN`'den türüyor; prod için aynı pattern OK ama kontrol edilmeli (`backend/app/email_service.py` veya çağrı noktası).
- [ ] **Bootstrap script prod-guard** — `backend/scripts/bootstrap_pms_uat_tenant.py` başına `if os.getenv("ENV") == "production": sys.exit("UAT script — prod'da koşulmaz")`.

### Konfigürasyon
- [ ] Replit Reserved VM + custom region (Frankfurt) seçimi.
- [ ] Prod secrets envanteri (CapX tarafı): `MONGO_URL` (prod cluster), `JWT_SECRET`, `RESEND_API_KEY`, Google Sheets OAuth, `FRONTEND_URL` (prod), `DB_NAME=hotel_match_prod`.
- [ ] `PMS_ALLOW_LOOPBACK_CALLBACK` prod'da **SET EDİLMEZ**.
- [ ] Prod cluster'da `ensure_indexes` startup'ta otomatik koşar (kod hazır), ama deploy sonrası ilk istek öncesi `python -c "import asyncio; from app.indexes import ensure_indexes; asyncio.run(ensure_indexes())"` ile pre-warm önerilir.

### Smoke senaryosu (Faz 3'te kullanılacak)
- [ ] PMS UAT'deki snapshot payload + reservation/event payload dosyaya yazılıp `scripts/prod_smoke_pms.sh` olarak bir kerede koşulur (4 adım: availability/sync → reservation/event → match-trigger → cancel-trigger).

---

## Notlar
- Bu plan **sıralı** — Faz 0 cevapları geldi (✅), Faz 1 publish'e hazırız.
- Her faz sonu kullanıcı onayı alınır (özellikle Faz 1 ve Faz 3).
- Plan `CAPX_PMS_INBOUND_WEBHOOK_SPEC.md` ile uyumlu; spec'te değişiklik gerektirmiyor.
- PMS tarafı kendi paralel hazırlığını ilerletiyor (capx_tenant_credentials AES-256-GCM, prod Mongo Atlas M10→M20, idempotency koleksiyonları). CapX tarafından beklenen ek koordinasyon yok.
