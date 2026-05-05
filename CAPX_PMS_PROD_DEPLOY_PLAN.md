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

## 4) PMS Ekibine İletilecek 3 Soru

> CapX prod deploy planı hazır (`CAPX_PMS_PROD_DEPLOY_PLAN.md`). Aşağıdaki üç noktayı netleştirmeden prod'a geçmek istemiyorum, çünkü her biri prod konfigürasyonunu doğrudan etkiliyor.

### 1. Prod callback URL formatı ve geçiş süreci
UAT'de bize verdiğiniz callback URL Replit dev domain'i (`cd790339-...kirk.replit.dev`). Prod'da bu URL ne olacak — `*.replit.app` mı, custom domain mı? Ve değişim sırasında nasıl koordine edeceğiz: önce siz prod'a alıp yeni URL'i yazılı bildirin → biz CapX prod admin panelinden tek tıkla güncelleyelim, ardından siz UAT URL'ini decommission edin? Ya da paralel açık dursun belirli bir süre?

### 2. Prod credential paketi — yeni mi, aynı mı?
UAT için size verdiğimiz `api_key=capx_pk_lLmp…D1VM` ve webhook_secret prod'da aynı mı kalacak, yoksa prod onboarding ile **yeni bir set** üreteceğiz? CapX tarafındaki best-practice **ayrı set** (UAT/prod credential izolasyonu); ama sizin tarafınızda secret store yönetimi nasıl?  
Eğer ayrı set istiyorsanız: prod'da yeni hotel kaydı + `POST /api/integrations/v1/pms/connect` ile yeni anahtarlar üretilir, ham anahtar bir kez döner ve sizin vault'unuza işlenir.

### 3. Production rate limit / kota beklentisi
Prod'da iki kalemde planlama bilgisi gerekiyor:
- **`availability/sync`**: Tipik bir tenant için günde / saatte kaç snapshot push'lanır? OTA-tetikli mi, periyodik (cron) mi? CapX'te tenant başına dakikalık quota (örn. 30/dk) tanımlamamız gerekiyor.
- **`reservation/event`**: Pik anda (örn. peak season Cuma akşamı) tahmini event/sn nedir? CapX outbound retry mekanizması 4 deneme x 30s'lik tail'de 100k+ event tutar, ama erken alarm eşikleri kalibre etmek için sayı lazım.
- **Toplam tenant sayısı (ilk 30 / 90 gün)**: 1 mi, 10 mu, 100 mü? DB indeks stratejisi (`pms_integrations.api_key_hash` zaten unique index'li) ve Mongo cluster sizing buna bağlı.

Cevaplar gelir gelmez prod publish'i tetikleyebiliriz; teknik tarafta blocker yok.

---

## Notlar
- Bu plan **sıralı** — Faz 0 cevapları gelmeden Faz 1 başlamaz.
- Her faz sonu kullanıcı onayı alınır (özellikle Faz 1 ve Faz 3).
- Plan `CAPX_PMS_INBOUND_WEBHOOK_SPEC.md` ile uyumlu; spec'te değişiklik gerektirmiyor.
