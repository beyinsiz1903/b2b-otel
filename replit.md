# CapX

Türkiye geneli B2B otelden-otele kapasite paylaşım platformu. FastAPI + MongoDB backend, React (CRA + Craco) frontend.

## Kullanıcı Tercihleri
- İletişim dili: **Türkçe**
- Bu repo şu an çalıştırılmıyor; iş kapsamı statik kod incelemesi + Türkçe rapor + hedeflenmiş düzeltmeler.

## Mimari
- **Backend:** `backend/app/` paketi (refactor sonrası) — FastAPI, Motor (async MongoDB), JWT auth, slowapi rate limiter, reportlab PDF, Google Sheets OAuth, WebSocket bildirim (`/api/ws/notifications`). `backend/server.py` artık 8 satırlık geriye dönük uyumlu shim (`from app.main import app`).
  - `app/config.py`, `app/db.py`, `app/utils.py`, `app/models.py`, `app/security.py`, `app/ws.py`, `app/indexes.py`, `app/api_router.py`, `app/main.py`
  - `app/services/` — billing, inventory, pms_helpers, sheets_helpers, pricing_engine
  - `app/routers/` — 25 modül: auth, listings, requests_matches, stats, admin, sheets, templates, files, inventory, pricing, performance, payments, admin_logs, subscriptions, notifications, websocket, reports, market_trends, performance_scores, kvkk, regions, admin_revenue, request_stats, cross_region, pms
  - Tüm router'lar tek bir paylaşımlı `api = APIRouter(prefix="/api")` üzerinde decorator ile kayıt olur; davranış birebir korundu, 97 unique URL yolu orijinalle eşleşiyor.
- **Frontend:** `frontend/src/` — React + react-router-dom v6, Tailwind, Craco. 19 sayfa + Layout + AuthContext + WSContext.
- **Veri akışı:** otel kayıt → admin onay → ilan/talep/eşleşme → ödeme + fatura PDF.

## Son Yapılan Değişiklikler

### CapX ↔ PMS inbound rezervasyon entegrasyonu — UÇTAN UCA TAMAM (2026-05-05)
İki taraf da hazır ve şartnameye uyumlu. CapX tarafında eşleşme oluştuğunda/iptal edildiğinde, otelin PMS'i HMAC imzalı bir webhook alır ve kendi rezervasyonunu açar/iptal eder.

**CapX tarafı (publisher):**
- `app/services/pms_outbound.py` — outbox + 4-deneme retry (2s/10s/30s) + manuel replay + SSRF guard (private/loopback/link-local/metadata IP'leri reddedilir; dev için `PMS_ALLOW_LOOPBACK_CALLBACK=1`) + dispatch_id concurrency token + startup recovery (lease_until geçmiş yetim event'ler toplanır).
- Koleksiyon: `pms_outbound_events` (3 indeks).
- Hook noktaları: `/requests/{id}/accept`, `/requests/{id}/accept-alternative`, `/matches/{id}/cancel` — her biri her iki tarafa `match.created` / `match.cancelled` push. PMS bağlantısı/callback URL olmayan tarafta sessizce geçer.
- Endpoint: `PUT /api/integrations/v1/pms/callback` (callback URL set + SSRF doğrulama), `GET /api/integrations/v1/pms/events` (otelin kendi son 50 olayı), `POST /api/integrations/v1/pms/events/{id}/retry` (manuel replay; yeni dispatch_id üreterek duplicate riski yok).

**PMS tarafı (consumer — PMS ekibi tamamladı):**
- Handler: `integrations/capx/inbound_match.py` — `direction=incoming` → bookings, `outgoing` → transfer log, terminal status'larda iptal noop.
- Endpoint: `/api/webhooks/capx/by-tenant/{tenant_id}` — tenant secret path'ten resolve, HMAC-SHA256 timing-safe karşılaştırma, atomic idempotency (`capx_events` unique index + DuplicateKey fallback), ack-with-error semantiği.
- Frontend: CapX Integration sayfasına "Inbound Callback URL" kartı (URL/JWT input + kopyala + Aktive Et).
- 19 unit test PASS, architect review PASS (Critical/High yok).

**Şartname dosyası:** `CAPX_PMS_INBOUND_WEBHOOK_SPEC.md` — 322 satır, sadece PMS tarafı için temizlenmiş, tek başına paylaşılabilir.

**E2E smoke (CapX tarafı):** otel kayıt → PMS bağla → callback set → ilan → talep → kabul → webhook geldi (HMAC OK) → iptal → cancel webhook geldi → `/events` `delivered` görüyor. SSRF negatif testleri (metadata IP, link-local, ftp scheme): hepsi 400. EXPECTED_API_ROUTES 96 → 98.

### PMS entegrasyonu — `/api/integrations/v1/pms/*` (7 endpoint)
CapX'in dış PMS sistemleriyle (Syroce vb.) konuşmasını sağlayan tam paket eklendi (`backend/server.py` sonu).
- `POST /connect` (JWT) → API key + webhook secret üretir; rotation destekli, ham anahtar bir kez döner.
- `GET /status`, `PUT /callback`, `POST /disconnect` (JWT) → bağlantı yönetimi.
- `POST /availability/sync` (Bearer API key) → PMS müsaitlik snapshot'ı push'lar; `auto_publish=True` ise `availability_listings`'e idempotent upsert (`pms_external_ref` ile).
- `POST /reservation/event` (Bearer + HMAC-SHA256 `X-CapX-Signature`) → rezervasyon olayları; `X-CapX-Event-Id` ile idempotent (DuplicateKeyError ile yutulur). İptal olayında PMS dış referansına bağlı ilanlar `closed_by_pms` olur.
- `GET /recent` (JWT) → debug listesi.

Yeni koleksiyonlar (indeksler `ensure_indexes`'e eklendi):
- `pms_integrations` (unique `hotel_id`, `api_key_hash` lookup)
- `pms_availability_snapshots` (`hotel_id`, `received_at` desc)
- `pms_reservation_events` (`_id` = X-CapX-Event-Id, idempotent)
- `availability_listings.pms_external_ref` sparse index

PMS tarafı (kullanıcının ayrı Replit sekmesinde yapılacak iş) için detaylı yol haritası: **`PMS_INCELEME_RAPORU.md`** (625 satır, kod blokları + adım adım).

### Frontend — kritik import düzeltmeleri (8 sayfa)
ListingsPage, MatchesPage, MatchDetailPage, ListingDetailPage, ProfilePage, RequestsPage, PaymentsPage, ReportsPage — eksik `useNavigate` / `useLocation` / `Link` / `statusLabel` import'ları eklendi.

### Backend — Hafta 1 paketi
- `POST /matches/{id}/cancel` endpoint'i eklendi; iptal **atomik durum geçişi** ile yapılır (paralel iptal yarışı önlenir), envanter idempotent geri yüklenir (`inventory_decremented` flag çift iade önler), kota yalnızca **kabul eden tarafın aboneliğinden** geri verilir.
- Eşleşme kabul akışı (`/requests/{id}/accept`, `/requests/{id}/accept-alternative`) tamamen yarış-koşulu güvenli:
  - `_consume_match_quota` atomik conditional `$inc` (`matches_used < max_matches`) ile kota tüketir; tüketilen `subscription_id` döndürülür ve match dokümanına `accepted_by_subscription_id` olarak yazılır.
  - Talep durumu geçişi atomik `update_one` filtresi ile yapılır (`status ∈ {pending, alternative_offered}`); paralel kabul-iptal yarışında yalnızca tek istek kazanır.
  - `matches.request_id` üzerinde **unique index** (fail-fast `ensure_indexes`) ile bir talep en fazla bir match'e bağlanır; `DuplicateKeyError` yakalanıp kota iadesi + talep durumu rollback yapılır.
  - Tüm yan etkiler (kota, durum geçişi, listing unlock, match insert) için kompenzasyon blokları; herhangi bir hata sonrası kota geri verilir ve talep önceki durumuna döndürülür.
- `_refund_match_quota` artık `subscription_id` ile çalışır (plan değişimi sonrası yanlış aboneliği etkilemez); legacy iptal akışı için `_refund_match_quota_by_hotel` fallback.
- `POST /auth/forgot-password` + `POST /auth/reset-password`: SHA-256 hash'lenmiş token, 1 saat TTL (Mongo TTL index), tek kullanımlık, kullanıcı sayım sızdırmaz. Reset endpoint'i `find_one_and_update` ile **atomik tüketim** yapar (TOCTOU yok). Dev modunda `debug_token` döner; prod'da e-posta entegrasyonu gerekli.
- `password_reset_tokens` koleksiyonu için unique + TTL index eklendi (fail-fast).
- Rate limit kapsamı genişletildi: `change-password` 10/dk, `forgot/reset-password` 5/dk, `register-upload` 10/dk, `upload-image` 30/dk.

## Son Yapılan Düzeltmeler (Hafta 2)
- **`/matches/{match_id}` null guard:** `hotel_a`/`hotel_b` silinmişse `_hotel_stub` ile `{id, name: "Silinmiş otel", deleted: true}` döner; eski `hotel_a["_id"]` AttributeError fix.
- **`/admin/matches` payment join:** N+1 yerine **toplu join** (otel adları + ödeme bilgileri tek sorguda); response'a `amount_paid`, `payment_count`, `last_payment_status`, `last_payment_at` eklendi.
- **`/inventory/check-availability` body+query desteği:** Pydantic `CheckAvailabilityRequest` body modeli + legacy query params; body öncelik kazanır, ikisi de yoksa 422.
- **`/pricing/market-comparison` median düzeltmesi:** Median artık `(price_min+price_max)/2` midpoint üzerinden hesaplanır; `median_price_min` ve `median_price_max` ek alanları döner; öneri benchmark olarak `median_price`'ı kullanır (avg_min'e göre daha temsili).
- **WS reconnect sonsuz backoff:** `maxReconnectAttempts=5` kaldırıldı; backoff 2s→60s exponential cap, token varken sonsuz dener, logout/intentionalClose ile temiz kapanır.

## E-posta Entegrasyonu (Resend, Hafta 2)
- **Replit Resend connector** bağlandı — API anahtarı + from_email connector proxy üzerinden çekilir, cache'lenmez.
- `backend/email_service.py`: `send_email()`, `build_password_reset_email()`, `EmailNotConfiguredError`.
- `forgot-password` endpoint artık gerçek e-posta gönderir. Hata durumlarında 200 dönmeye devam eder (kullanıcı sayımı sızdırmaz). `FRONTEND_URL` veya `REPLIT_DEV_DOMAIN`'den reset URL'i türetilir, son çare `localhost:3000`.
- Yeni frontend sayfaları: `/forgot-password` (e-posta gir → bağlantı gönder), `/reset-password?token=...` (yeni şifre belirle). Login sayfasına "Şifremi Unuttum" linki eklendi.
- `logger = logging.getLogger("capx")` — server.py'ye standart logging eklendi.

## Replit Workflow Kurulumu (Hafta 2)
- **Backend** workflow: `cd backend && uvicorn server:app --host 0.0.0.0 --port 8000 --reload` (console, port 8000). MongoDB Atlas Syroce cluster `MONGO_URL` secret üzerinden.
- **Frontend** workflow: `cd frontend && npx craco start` (webview, port 5000).
- `frontend/.env`: `REACT_APP_BACKEND_URL=` (boş → relative URL), `PORT=5000`, `HOST=0.0.0.0`, `DANGEROUSLY_DISABLE_HOST_CHECK=true`, `WDS_SOCKET_PORT=0`, `BROWSER=none`.
- `frontend/src/setupProxy.js`: `/api` → `http://localhost:8000`, `ws:true` (HTTP + WS proxy birlikte).
- `WSContext.js` URL fallback: `REACT_APP_BACKEND_URL` boşsa `window.location.host` + protocol (wss/ws) kullanılır — same-origin deploy + dev preview için çalışır.
- Python deps: fastapi 0.110.1, motor 3.3.1, pymongo 4.5.0, bcrypt 4.1.3, slowapi, aiohttp, google-auth(-oauthlib/-httplib2), google-api-python-client vb. (`uv add` ile yüklendi).
- Frontend deps: `npm install --legacy-peer-deps` + `ajv@^8` (CRA `ajv-keywords` modul-not-found düzeltmesi).

## Backend Modülerleştirme (Hafta 3)
- 5056 satırlık `server.py` modüler `app/` paketine bölündü. Toplam 7800+ satır 33 dosyaya dağıtıldı (foundation 8, services 5, router 25, main + shim 2).
- Davranış birebir korundu: 97 unique route path'i orijinalle EXACT MATCH. Tek shared `api` APIRouter üzerinden mount → URL'ler `/api/...` aynen.
- WebSocket için ayrı `_ws_router` (`/api/ws/notifications`, `/api/ws/status`) — yolları kendi içinde `/api`'lı tanımlı, app'e doğrudan include.
- Startup (`ensure_indexes`) + shutdown (`client.close()`) main.py'a taşındı; PMS startup/shutdown event'leri kaldırıldı.
- Workflow değişmedi: `uvicorn server:app` shim üzerinden `app.main:app`'e ulaşır.

## Hafta 4 — Uçtan Uca Test + Performans Düzeltmeleri
- **PricingPage:** Eksik `ConfirmDialog` import düzeltildi (silme onay diyaloğu çalışır hale geldi).
- **`/stats/market-trends` 7.8s → 1.3s (6×):** 6 bölge × 5 ardışık DB sorgusu (~30 round-trip) `asyncio.gather` ile paralelleştirildi; region-agnostic talep sayısı tek seferde alınır.
- **`/stats/cross-region` 0.8s → 0.35s:** Klasik N+1 (her match için 3 ayrı `find_one`) toplu `$in` fetch + bellekte sözlük lookup'a çevrildi (worst-case 15.000 round-trip → 4 sorgu).
- **`/stats/performance-scores` 0.8s → 0.45s:** İki bağımsız sorgu paralel.
- **`/stats` 1.3s → 0.5s:** 4 ardışık `to_list` paralelleştirildi.
- E2E sonuç: 27 protected GET endpoint'in tümü 200 döner; kırık modül/endpoint yok.

## Bilinen Açık Konular (kalan)
- Cross-origin production deploy yapılırsa `REACT_APP_BACKEND_URL` mutlaka tam backend origin'e set edilmeli (same-origin deploy ise boş bırakılabilir).

## Detaylı Rapor
`CAPX_INCELEME_RAPORU.md` dosyası uçtan uca incelemeyi, syroce PMS entegrasyon önerisini ve öncelikli aksiyon planını içerir.
