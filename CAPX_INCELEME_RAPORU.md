# CapX Platformu — Detaylı Statik İnceleme Raporu

**Hazırlanma Tarihi:** 03 Mayıs 2026
**İnceleme Türü:** Uçtan uca statik kod incelemesi (uygulama çalıştırılmadı, yalnızca kaynak kod analiz edildi)
**Kapsam:** `backend/server.py` (4193 satır, 98 endpoint) + `frontend/src/` (19 sayfa, Layout, AuthContext, WSContext, api.js, constants.js)
**Stack:** FastAPI + Motor (async MongoDB) + JWT • React (CRA + Craco) + react-router v6 + Tailwind

---

## 1. YÖNETİCİ ÖZETİ

CapX, mimari olarak oldukça olgun bir B2B kapasite paylaşım platformu. 6 bölge desteği, abonelik planları, KVKK akışı, fatura PDF üretimi, oda tipi şablonları, fiyatlandırma kuralları motoru, performans/gelir raporları, gerçek zamanlı bildirim WebSocket'i ve Google Sheets entegrasyonu gibi ileri seviye modülleri içeriyor.

Ancak frontend tarafında **8 sayfa, açıldığı anda beyaz ekran/JS hatası verecek kritik import eksikleri içeriyor**. Bu hatalar tek başına platformun yarısının kullanılamamasına yol açar; aciliyet sırası en başta bunlar olmalı.

Backend tarafında ise mimari sağlam, ancak **abonelik kullanım sayacı, envanter geri iadesi, eşleşme karşı taraf hesabı ve ödeme bilgisi görüntüsü** gibi iş mantığı boşlukları var.

**Genel sağlık skoru:**
| Alan | Durum |
|---|---|
| Mimari & klasör yapısı | İyi |
| Backend endpoint kapsamı | Çok iyi (98 route) |
| Frontend kod kalitesi | **Kritik (import bug'ları)** |
| Test kapsamı | Çok zayıf (yalnızca `tests/backend_test.py` var) |
| İş mantığı tutarlılığı | Orta (5–6 boşluk) |
| Güvenlik (rate limit, CORS, secret yönetimi) | Orta |
| 3rd-party PMS entegrasyonuna hazırlık | Düşük (planlanmamış) |

---

## 2. KRİTİK FRONTEND HATALARI (ACİL — Sayfa Çöker)

Toplam **8 sayfada** kritik import eksikleri var. Hepsi **tek satırlık** düzeltme ile çözülür. Sayfa açıldığında React `useNavigate is not defined` veya `Link is not defined` hatası verir.

### 2.1 `ListingsPage.js` — `/listings` sayfası açılınca çöker
- **Sorun:** Satır 27'de `const navigate = useNavigate()` çağrılıyor ama `react-router-dom`'dan sadece `Link` import edilmiş.
- **Çözüm:** `import { Link, useNavigate } from "react-router-dom";`

### 2.2 `MatchesPage.js` — `/matches` sayfası açılınca çöker
- **Sorun:** Satır 9'da `useNavigate` kullanılıyor; import yok.
- **Çözüm:** `import { Link, useNavigate } from "react-router-dom";`

### 2.3 `MatchDetailPage.js` — `/matches/:id` sayfası açılınca çöker
- **Sorun:** `useNavigate` ve `useLocation` kullanılıyor ama yalnızca `useParams, Link` import edilmiş.
- **Çözüm:** `import { useParams, Link, useNavigate, useLocation } from "react-router-dom";`

### 2.4 `ListingDetailPage.js` — `/listings/:id` çöker
- **Sorun:** Satır 12'de `useLocation` kullanılıyor, import edilmemiş.
- **Çözüm:** Mevcut import satırına `useLocation` eklenmeli.

### 2.5 `ProfilePage.js` — `/profile` çöker
- **Sorun:** Satır 283'te `useLocation()` çağrılıyor, hiç import yok.
- **Çözüm:** `import { useLocation } from "react-router-dom";` eklenmeli.

### 2.6 `RequestsPage.js` — Boş "Giden talepler" sekmesinde çöker
- **Sorun:** Satır 147'de `<Link to="/listings">…` kullanılmış ama `Link` import yok.
- **Çözüm:** `Link` import edilmeli.

### 2.7 `PaymentsPage.js` — Faturası olan satırda çöker
- **Sorun:** Satır 94'te `<Link to={"/invoices/"+...}>` kullanılmış, `Link` import yok.
- **Çözüm:** `Link` import edilmeli.

### 2.8 `ReportsPage.js` — "Talep İstatistikleri" sekmesi çöker
- **Sorun:** Satır 172 ve 190'da `statusLabel(...)` çağrılıyor; `constants.js` içinden import edilmemiş.
- **Çözüm:** `import { statusLabel } from "../constants";` eklenmeli.

### 2.9 (Bilgi) `WSContext` ↔ `AuthContext` provider sırası
- `AuthContext` içinde `useWS()` **çağrılıyor** ve `ws.connect()/disconnect()` kullanılıyor. Bu yüzden `App.js`'te **`WSProvider` mutlaka `AuthProvider`'ın dışında** kalmalı; aksi hâlde uygulama açılışta çöker. Mevcut kod doğru sırada — **dikkat edilmesi gereken bir invariant** olarak not düşülmüştür.

---

## 3. ÖNEMLİ BACKEND BUG'LARI ve İŞ MANTIĞI BOŞLUKLARI

### 3.1 Eşleşme sonrası iptal/iade akışı yok (Orta–Yüksek)
- `_decrement_inventory_on_match` (satır 2609) talep kabul edildiğinde envanteri düşürüyor.
- Backend'de yalnızca **kabul edilmeden önceki** talep iptali (`/requests/{id}/cancel`) ve red (`/requests/{id}/reject`) endpoint'leri var. **Kabul edilmiş eşleşmeyi iptal eden bir endpoint hiç yok.**
- Sonuç: gerçek hayatta misafir gelmediğinde / no-show / mutabık kalınan iptal gibi durumlarda otel sistemden iz silmek için envanter düzeltmesini manuel yapmak zorunda.
- **Çözüm:** `POST /matches/{id}/cancel` endpoint'i eklenmeli; idempotent `_increment_inventory_on_cancel` ile envanter geri yüklenmeli (match dokümanında `inventory_decremented: true` flag'i ile çift iadeyi önle), ardından webhook tetiklenmeli.

### 3.2 Abonelik `matches_used` sayacı hiç artmıyor (Yüksek)
- Satır 3508'de `matches_used: 0` ile başlatılıyor; modelde alan var (satır 569) ama eşleşme kabulünde **artırma kodu yok**.
- Sonuç: ücretsiz plan limitsizmiş gibi davranıyor; "max_matches" kontrolü hiçbir zaman tetiklenmez.
- **Çözüm:** `accept_request`/`accept_match` içinde aboneliğe `$inc: {matches_used: 1}` eklenmeli ve plan limitine ulaşıldığında 402 dönülmeli.

### 3.3 `/inventory/check-availability` POST + query param uyumsuzluğu (Orta)
- Endpoint POST olarak tanımlı ama parametreler query string bekliyor; frontend'den çağrı şekline göre 422 dönebilir. Body modeli ile değiştirilmeli ya da GET yapılmalı.

### 3.4 Eşleşme "karşı taraf" alanı ezbere `hotel_a` varsayıyor (Orta)
- `serialize_doc` benzeri yardımcılarda counterparty hesaplaması bazı yerlerde `hotel_a_id == current` ise `hotel_b` döndürüyor; `hotel_a` veya `hotel_b` veritabanında silinmişse `None` üzerinde alan erişimi 500 hatası verir.
- **Çözüm:** `hotel_a` ya da `hotel_b` `None` ise placeholder bir dict ile fallback verilmeli.

### 3.5 `/admin/matches` ödeme bilgisi placeholder (Düşük–Orta)
- Admin tablosunda her satırda "ödeme: -" gösteriliyor; payment koleksiyonundan join atılmıyor. Operasyonel görünürlük zayıf.
- **Çözüm:** Match ID üzerinden `payments` koleksiyonundan tek seferlik aggregate ile durum çekilmeli.

### 3.6 `market-comparison` median hesabı yalnızca `price_min` üzerinden (Düşük)
- Aralıklı fiyatlandırma yapan oteller için medyan yanıltıcı. `(price_min + price_max) / 2` ile düzeltilebilir.

### 3.7 Google Sheets `redirect_uri` hardcoded (Düşük)
- `REACT_APP_BACKEND_URL` ortam değişkeninden alınıyor; ortamlar arası taşımada (staging/prod) Google Console'da yeniden tanımlama zorunlu. Sabit "well-known" callback path zaten var, sorun değil ama **dokümante edilmeli**.

### 3.8 WebSocket yeniden bağlanma kalıcı kapanıyor (Düşük)
- `WSContext.js` 5 deneme sonrası "failed" durumuna geçip yeniden denemiyor. Geçici ağ kesintilerinde kullanıcı sayfayı yenilemek zorunda kalır.
- **Çözüm:** Exponential backoff ile sınırsız (ya da 30 dk) deneme; `visibilitychange` event'ında forced reconnect.

### 3.9 Rate limiting kapsamı dar (Orta — Güvenlik)
- `slowapi` kurulu ve `register` (5/dk), `login` (10/dk) ve bir ödeme endpoint'inde aktif. **Ancak** `forgot-password`, `verify-email`, `payments/*`, dosya yükleme ve aramaya açık endpoint'ler korumasız.
- **Çözüm:** Tüm yazma endpoint'lerine en az IP başına 60/dk; kimlik doğrulama akışları için 10/dk; `Retry-After` header'ı dön.

### 3.10 Şifre sıfırlama akışı eksik (Orta)
- Backend'de `/auth/forgot-password` ve `/auth/reset-password` endpoint'leri yok; frontend'te de link yok. Kullanıcı şifresini unutursa veritabanına manuel müdahale gerekiyor.

---

## 4. EKSİK / ÖLÜ MODÜLLER

| Modül | Durum | Öneri |
|---|---|---|
| Şifremi unuttum | Yok | Email tabanlı token akışı |
| Email bildirimleri | Yok (sadece in-app) | SendGrid/Postmark + template |
| SMS bildirimleri | Yok | NetGSM/Twilio |
| iCal / channel manager besleme | Yok | `.ics` export endpoint |
| Otel arama (full-text) | Sadece bölge filtresi | Mongo `$text` index veya Atlas Search |
| Çoklu dil (i18n) | Hardcoded TR | `react-i18next` |
| Rol-bazlı yetkilendirme | Sadece `is_admin` | `role: owner/staff/finance` |
| Audit log UI | Backend var, AdminPage'te boş | Tablo + filtre eklenmeli |
| Sözleşme/PDF imzası | Yok | DocuSign/KolayPDF entegrasyonu |
| Müşteri (PAX) bilgisi aktarımı | Yok | Eşleşme kabulünde transferi tetikleyen alan |
| Fatura e-Arşiv/e-Fatura entegrasyonu | Sadece PDF | GIB entegratörü (Logo, Mikro, Nilvera) |
| Mobil uygulama | Yok | React Native / PWA manifesto eklenmeli |

---

## 5. KÜÇÜK UI/UX İYİLEŞTİRMELERİ

- **LoginPage** alt başlığında "Sapanca & Kartepe" hardcoded, sistem 6 bölge destekliyor — "Türkiye geneli" yapılmalı.
- **AvailabilityPage** `price_max = price_min` yapıyor; iki ayrı input olmalı.
- **AdminPage > "logs"** sekmesi if/else dışında render ediliyor; çalışıyor ama yapı tutarsız.
- **PerformancePage**: KPI kartlarında trend (önceki haftaya göre %) yok.
- **Notifications panel**: tarih `toLocaleString` ile değil, `dayjs.fromNow()` ile "5 dk önce" gösterilmeli.
- **Mobil görünüm**: Layout sidebar 768px altında collapse'lanıyor ama tablolar `overflow-x-auto` değil; Listings/Matches tabloları taşıyor.
- **Loading state'leri**: çoğu sayfada `Spinner` yok; boş `[]` gösteriyor — kullanıcıyı yanıltır.
- **Boş durum (empty state)** illüstrasyonu/CTA'sı yok.

---

## 6. GÜVENLİK & UYUM

| Konu | Durum | Aksiyon |
|---|---|---|
| JWT secret | `.env` (iyi) | Rotasyon politikası tanımla |
| Şifre hash | bcrypt (iyi) | — |
| CORS | `*` muhtemelen | Production'da whitelisted domain |
| KVKK aydınlatma | Backend var, UI bağlantılı | Cookie banner eklenmeli |
| KVKK veri silme | Endpoint var | Anonimleştirme tarihçesi tutulsun |
| HTTPS | Replit otomatik | Custom domain'de zorunlu |
| Dosya yükleme | Boyut limiti? | 5 MB üst sınır + MIME whitelist |
| SQL/NoSQL injection | Motor query'leri parametreli | İyi |
| Mass assignment | Pydantic modelleri sıkı mı? | Birkaç endpoint'te `**body` var; gözden geçir |
| Rate limit | Kısmi (yalnızca login/register/bir payment route) | Tüm yazma endpoint'lerine yaymalı |
| 2FA | Yok | TOTP (pyotp) opsiyonel olarak |

---

## 7. PERFORMANS & ÖLÇEKLENEBİLİRLİK

- **Index'ler:** `matches.hotel_a_id`, `hotel_b_id` index'leri var (satır 3164–3166). İyi. Ancak `listings.region`, `listings.start_date`, `requests.status` için bileşik index önerilir.
- **N+1 sorgu:** `/admin/matches` ve `/reports/revenue` döngüde tek tek `find_one` çağırıyor; `aggregate $lookup` ile tek sorguya indirilmeli.
- **WebSocket:** Tek instance varsayımı var. Birden fazla worker/replica'ya çıkıldığında Redis pub/sub broker eklenmeli.
- **PDF üretimi (reportlab) senkron:** Büyük faturalarda event loop'u kilitler; `asyncio.to_thread` ile sarılmalı.
- **MongoDB connection pooling:** Motor varsayılanı 100. Production'da izlenmeli.

---

## 8. KOD KALİTESİ NOTLARI

- `backend/server.py` **4193 satır tek dosya**. Bakım çok zorlaşacak. `routers/auth.py`, `routers/listings.py`, `routers/matches.py`, `routers/admin.py`, `services/inventory.py`, `services/billing.py` şeklinde modülerleştirilmeli.
- Frontend'te `api.js` tek dosyada toplanmış (iyi), ancak fonksiyon isimleri tutarsız (`getListings` vs `listingsList`). Bir kez gözden geçirilip standartlaştırılmalı.
- Yalnızca tek bir geniş `tests/backend_test.py` dosyası var; modül başına test yok, frontend test sıfır. En azından kritik akışlar (auth, eşleşme kabul, ödeme) için pytest + httpx fixture'lı testler ve frontend'de Vitest/RTL smoke test eklenmeli.
- `console.log` ifadeleri production'da kalmış olabilir; `eslint-plugin-no-console` kuralı eklenmeli.
- TypeScript yok; uzun vadede `frontend` TS'e geçirilmeli (özellikle `api.js` tip güvenliği için).

---

## 9. SYROCE PMS İLE 3rd-PARTY MODÜL OLARAK ENTEGRASYON ÖNERİSİ

CapX'i syroce PMS'inizin içine "kapasite paylaşım modülü" olarak yerleştirmek için iki yaklaşım var. **Önerim 2 numaralı hibrit yaklaşım.**

### Yaklaşım A — İframe / Embed (hızlı ama sınırlı)
- CapX'i syroce arayüzünden iframe ile çağırın.
- Avantaj: 1–2 günde ayağa kalkar, ortak SSO için query string token yeterli.
- Dezavantaj: Veri çift girilir, kullanıcı deneyimi kopuk, mobil sorunlu.
- **Sadece pilot / demo için uygun.**

### Yaklaşım B — Hibrit: REST API + Webhook + SSO (önerilen)

CapX backend'ine syroce'nin konuşacağı yeni bir **`/integrations/v1/*` API yüzeyi** ekleyin. Tasarım önerisi:

#### B.1 Kimlik doğrulama
- Her syroce müşteri otelinin CapX panelinde **"Entegrasyon Anahtarı Üret"** butonu olur.
- Üretilen `api_key` + `api_secret` (HMAC için) syroce konfigürasyonuna kaydedilir.
- İstek başlığı: `X-Capx-Key`, `X-Capx-Signature` (body'nin HMAC-SHA256'sı), `X-Capx-Timestamp` (replay koruması ±5 dk).
- Kullanıcı arayüzü için **SSO**: CapX `/integrations/sso/exchange` endpoint'i, kısa ömürlü JWT döner; syroce kullanıcıyı bu token ile CapX'e yönlendirir.

#### B.2 Senkronizasyon endpoint'leri (syroce → CapX)

| Endpoint | Amaç |
|---|---|
| `POST /integrations/v1/rooms/sync` | Syroce'deki oda tipleri → CapX `room_templates` |
| `PUT  /integrations/v1/inventory` | Tarih × oda tipi bazında müsait sayı (idempotent, `Idempotency-Key` zorunlu) |
| `PUT  /integrations/v1/availability` | Açık/kapalı + min stay + fiyat |
| `POST /integrations/v1/listings` | İhtiyaç fazlası kapasiteyi pazara çıkar |
| `DELETE /integrations/v1/listings/{id}` | Geri çek |
| `GET  /integrations/v1/matches?since=...` | Polling fallback |

#### B.3 Webhook'lar (CapX → syroce)
Syroce panelinden bir webhook URL'i tanımlanır, CapX şu olayları **HMAC imzalı** olarak gönderir:

| Olay | Tetik |
|---|---|
| `match.created` | Yeni eşleşme önerisi |
| `match.accepted` | Eşleşme onaylandı → syroce rezervasyon yaratır |
| `match.cancelled` | İptal → syroce rezervasyonu iptal eder |
| `payment.paid` | Tahsilat → muhasebe modülüne |
| `invoice.issued` | e-Fatura entegratörüne |
| `inventory.adjusted` | CapX'te manuel düzeltme yapıldıysa |

Webhook teslimat: 3 retry, exponential backoff (1m, 5m, 30m), DLQ olarak veritabanı tablosu, syroce panelinde "yeniden gönder" butonu.

#### B.4 Veri modelleme önerisi
CapX `hotels` koleksiyonuna iki alan ekleyin:
```python
external_pms: Optional[str]  # "syroce"
external_id: Optional[str]   # syroce'deki hotel id
external_room_map: Dict[str, str]  # capx_room_template_id -> syroce_room_type_code
```
Bu sayede **çift yönlü ID eşlemesi** garanti.

#### B.5 Çakışma çözümü (kim kazanır?)
- **Master of truth:** envanter sayısı için **PMS (syroce)** kazanır.
- CapX'te yapılan envanter değişiklikleri webhook ile syroce'ye gider, syroce onayını döner.
- Eşleşme/listing iş akışları CapX'te master.

#### B.6 İlk ürünleştirme yol haritası (4 sprint, ~6 hafta)

| Sprint | Çıktı |
|---|---|
| 1 | API key/secret + HMAC middleware, SSO token exchange, OpenAPI dokümanı |
| 2 | rooms/sync + inventory PUT + availability PUT + idempotency |
| 3 | match webhook'ları + retry/DLQ + syroce tarafında handler iskeleti |
| 4 | Pilot otel ile canlı test, monitoring (Sentry + Prometheus), runbook |

#### B.7 Ticari paketleme önerisi
- syroce kullanan otele CapX **otomatik discount** (örn. %20).
- Tek faturada gösterim için CapX abonelik ücreti syroce ana faturasına yansıtılabilir (revenue share modeli).
- "Syroce Connected" rozeti CapX listing kartında.

---

## 10. ÖNCELİK SIRALI AKSİYON PLANI

### Hafta 1 — Acil
1. ✅ Bölüm 2'deki **8 frontend import hatası** düzeltilmeli (1 saatlik iş, ama yarısı şu an bozuk).
2. ✅ `matches_used` sayacı + eşleşme iptal endpoint'i & envanter iadesi (Bölüm 3.1, 3.2).
3. ✅ Şifremi unuttum akışı (Bölüm 3.10).
4. ✅ Rate limit kapsamını tüm yazma endpoint'lerine yay (Bölüm 3.9).

### Hafta 2–3 — Önemli
5. `serialize_doc` null guard (3.4), `/admin/matches` payment join (3.5).
6. Email bildirim altyapısı (SendGrid).
7. Mobil tablo overflow + empty state component'leri.
8. `backend/server.py` modüler bölme.

### Ay 1–2 — Stratejik
9. `/integrations/v1/*` API yüzeyi + webhook altyapısı (Bölüm 9).
10. Syroce ile pilot otel canlıya alma.
11. e-Fatura entegratörü (Nilvera/Logo).
12. Test piramidi + CI (GitHub Actions).
13. TypeScript geçişi.

---

## 11. ÖZET METRİKLER

- **Backend endpoint:** 98
- **Frontend sayfa:** 19
- **Çöken sayfa (mevcut hâliyle):** **8**
- **Yüksek öncelikli backend bug:** 4
- **Eksik ana modül:** 7+
- **Tahmini düzeltme süresi (Hafta 1 paketi):** 3 iş günü
- **Syroce entegrasyonu MVP:** 6 hafta

---

**Sonuç:** CapX vizyon ve mimari olarak güçlü; ancak frontend'te bir gözden geçirme dalgasına ve backend'de birkaç iş mantığı düzeltmesine acilen ihtiyacı var. Bu düzeltmeler tamamlandıktan sonra syroce ile entegrasyon, pazarda ciddi bir farklılaştırıcı olur. Yukarıdaki yol haritasını sırayla uyguladığınızda 6–8 hafta içinde hem CapX'i sağlamlaştırıp hem de syroce müşterilerinize tek tıkla açabilirsiniz.
