# CapX

Türkiye geneli B2B otelden-otele kapasite paylaşım platformu. FastAPI + MongoDB backend, React (CRA + Craco) frontend.

## Kullanıcı Tercihleri
- İletişim dili: **Türkçe**
- Bu repo şu an çalıştırılmıyor; iş kapsamı statik kod incelemesi + Türkçe rapor + hedeflenmiş düzeltmeler.

## Mimari
- **Backend:** `backend/server.py` — FastAPI, Motor (async MongoDB), JWT auth, slowapi rate limiter, reportlab PDF, Google Sheets OAuth, WebSocket bildirim (`/api/ws/notifications`).
- **Frontend:** `frontend/src/` — React + react-router-dom v6, Tailwind, Craco. 19 sayfa + Layout + AuthContext + WSContext.
- **Veri akışı:** otel kayıt → admin onay → ilan/talep/eşleşme → ödeme + fatura PDF.

## Son Yapılan Değişiklikler

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

## Bilinen Açık Konular (kalan)
- `backend/server.py` 5050+ satır tek dosya; modülerleştirme önerilmiş (büyük refactor; ayrı karar).

## Detaylı Rapor
`CAPX_INCELEME_RAPORU.md` dosyası uçtan uca incelemeyi, syroce PMS entegrasyon önerisini ve öncelikli aksiyon planını içerir.
