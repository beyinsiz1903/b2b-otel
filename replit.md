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

## Bilinen Açık Konular (öncelikli)
- `serialize_doc` & `/matches/{id}` counterparty: hotel_a/hotel_b silinmişse null guard yok.
- `/admin/matches` payment join eksik (placeholder "-").
- `/inventory/check-availability` POST + query param uyumsuzluğu.
- `/pricing/market-comparison` median yalnızca `price_min` üzerinden.
- WS reconnect 5 deneme sonrası kalıcı kapanır.
- E-posta gönderimi yok (forgot-password için TODO).
- `backend/server.py` 4280+ satır tek dosya; modülerleştirme önerilmiş.

## Detaylı Rapor
`CAPX_INCELEME_RAPORU.md` dosyası uçtan uca incelemeyi, syroce PMS entegrasyon önerisini ve öncelikli aksiyon planını içerir.
