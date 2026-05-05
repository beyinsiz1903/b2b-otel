#!/usr/bin/env bash
# CapX prod smoke test — PMS entegrasyonu
#
# Kullanım:
#   PMS_API_KEY=capx_pk_... \
#   PMS_WEBHOOK_SECRET=capx_ws_... \
#   CAPX_BASE_URL=https://capx.replit.app \
#   bash scripts/prod_smoke_pms.sh
#
# Senaryo:
#   1. /availability/sync  → 200 OK + snapshot_id
#   2. /reservation/event  → 200 OK + idempotent (aynı event-id ile 2. kez de 200, duplicate yutar)
#   3. /reservation/event  → 401 (fake imza)
#   4. /availability/sync  → 401 (fake api key)
#
# Çıktı: her adım için HTTP code + süre. 4/4 yeşilse exit 0.

set -uo pipefail
# Güvenlik: bu script secret env'leri (PMS_API_KEY, PMS_WEBHOOK_SECRET) kullanır.
# `bash -x prod_smoke_pms.sh` ile çağrılsa bile xtrace'i zorla kapatıyoruz ki
# anahtarlar stdout'a sızmasın. Debug için PMS_SMOKE_DEBUG=1 set edilirse açılır.
if [ "${PMS_SMOKE_DEBUG:-0}" = "1" ]; then
  set -x
else
  set +x
fi

: "${PMS_API_KEY:?PMS_API_KEY env zorunlu (capx_pk_...)}"
: "${PMS_WEBHOOK_SECRET:?PMS_WEBHOOK_SECRET env zorunlu (capx_ws_...)}"
: "${CAPX_BASE_URL:?CAPX_BASE_URL env zorunlu (örn. https://capx.replit.app)}"

CAPX_BASE_URL="${CAPX_BASE_URL%/}"
EVENT_ID="prod-smoke-$(date +%s)"
PASS=0
FAIL=0

log() { printf "%s\n" "$*"; }
ok()   { log "  ✅ $*"; PASS=$((PASS+1)); }
fail() { log "  ❌ $*"; FAIL=$((FAIL+1)); }

# ---------- 1) availability/sync ----------
log "[1/4] POST /api/integrations/v1/pms/availability/sync"
AVAIL_PAYLOAD='{
  "date_start": "2026-06-01",
  "date_end":   "2026-06-08",
  "rooms": [
    {"room_type": "Standart", "available_count": 5, "price_min": 2500, "price_max": 3200, "currency": "TRY", "external_ref": "smoke-room-std"}
  ],
  "auto_publish": false
}'
HTTP=$(curl -sS -o /tmp/smoke_avail.json -w "%{http_code} %{time_total}" -X POST \
  "$CAPX_BASE_URL/api/integrations/v1/pms/availability/sync" \
  -H "Authorization: Bearer $PMS_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$AVAIL_PAYLOAD" --max-time 15)
CODE=${HTTP%% *}; TIME=${HTTP##* }
log "  → HTTP $CODE in ${TIME}s"
[ "$CODE" = "200" ] && ok "snapshot kaydedildi: $(grep -oE 'snapshot_id[^,}]*' /tmp/smoke_avail.json | head -1)" || fail "beklenen 200, gelen $CODE — payload: $(cat /tmp/smoke_avail.json | head -c 200)"

# ---------- 2) reservation/event (HMAC + idempotent) ----------
log "[2/4] POST /api/integrations/v1/pms/reservation/event (HMAC)"
RES_PAYLOAD='{"event_type":"created","reservation_id":"smoke-res-001","hotel_external_ref":"hotel-x","occurred_at":"2026-05-05T22:00:00Z"}'
SIG=$(printf '%s' "$RES_PAYLOAD" | openssl dgst -sha256 -hmac "$PMS_WEBHOOK_SECRET" -hex | awk '{print $NF}')
for ATTEMPT in 1 2; do
  HTTP=$(curl -sS -o /tmp/smoke_res.json -w "%{http_code} %{time_total}" -X POST \
    "$CAPX_BASE_URL/api/integrations/v1/pms/reservation/event" \
    -H "Authorization: Bearer $PMS_API_KEY" \
    -H "Content-Type: application/json" \
    -H "X-CapX-Signature: sha256=$SIG" \
    -H "X-CapX-Event-Id: $EVENT_ID" \
    -d "$RES_PAYLOAD" --max-time 15)
  CODE=${HTTP%% *}; TIME=${HTTP##* }
  log "  attempt $ATTEMPT → HTTP $CODE in ${TIME}s"
  [ "$CODE" = "200" ] && ok "attempt $ATTEMPT 200 OK (idempotent: $EVENT_ID)" || fail "attempt $ATTEMPT beklenen 200, gelen $CODE"
done

# ---------- 3) fake HMAC → 401 ----------
log "[3/4] reservation/event fake imza → 401 bekleniyor"
HTTP=$(curl -sS -o /dev/null -w "%{http_code} %{time_total}" -X POST \
  "$CAPX_BASE_URL/api/integrations/v1/pms/reservation/event" \
  -H "Authorization: Bearer $PMS_API_KEY" \
  -H "Content-Type: application/json" \
  -H "X-CapX-Signature: sha256=deadbeef" \
  -H "X-CapX-Event-Id: $EVENT_ID-fake" \
  -d "$RES_PAYLOAD" --max-time 15)
CODE=${HTTP%% *}; TIME=${HTTP##* }
log "  → HTTP $CODE in ${TIME}s"
[ "$CODE" = "401" ] && ok "401 invalid signature (HMAC verification çalışıyor)" || fail "beklenen 401, gelen $CODE"

# ---------- 4) fake api key → 401 ----------
log "[4/4] availability/sync fake api key → 401 bekleniyor"
HTTP=$(curl -sS -o /dev/null -w "%{http_code} %{time_total}" -X POST \
  "$CAPX_BASE_URL/api/integrations/v1/pms/availability/sync" \
  -H "Authorization: Bearer capx_pk_FAKE_KEY_XXXXXX" \
  -H "Content-Type: application/json" \
  -d "$AVAIL_PAYLOAD" --max-time 15)
CODE=${HTTP%% *}; TIME=${HTTP##* }
log "  → HTTP $CODE in ${TIME}s"
[ "$CODE" = "401" ] && ok "401 invalid api key" || fail "beklenen 401, gelen $CODE"

# ---------- özet ----------
log ""
log "================== SONUÇ =================="
log "  PASS: $PASS   FAIL: $FAIL"
[ "$FAIL" -eq 0 ] && { log "  🟢 Tüm smoke kontrolleri YEŞİL — CapX prod PMS entegrasyonu hazır."; exit 0; }
log "  🔴 Smoke FAILED — production publish'i ilerletmeyin."
exit 1
