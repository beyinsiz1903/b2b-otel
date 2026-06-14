# CapX

CapX is a B2B hotel-to-hotel capacity sharing platform for Türkiye, enabling hotels to share and utilize excess capacity.

## Run & Operate

*   **Backend:** `cd backend && uvicorn server:app --host 0.0.0.0 --port 8000 --reload`
*   **Frontend:** `cd frontend && npx craco start`
*   **Install Python Dependencies:** `uv add ...` (as per `backend/pyproject.toml`)
*   **Install Frontend Dependencies:** `npm install --legacy-peer-deps`
*   **Environment Variables:**
    *   `MONGO_URL` (for MongoDB Atlas connection)
    *   `REACT_APP_BACKEND_URL` (Frontend; empty for relative URL, full origin for cross-origin production)
    *   `PORT=5000` (Frontend)
    *   `HOST=0.0.0.0` (Frontend)
    *   `DANGEROUSLY_DISABLE_HOST_CHECK=true` (Frontend)
    *   `WDS_SOCKET_PORT=0` (Frontend)
    *   `BROWSER=none` (Frontend)
    *   `PMS_ALLOW_LOOPBACK_CALLBACK=1` (Backend; for dev, allows loopback IPs for PMS callbacks)
*   **DB Migrations/Setup:** `backend/scripts/bootstrap_pms_uat_tenant.py` (idempotent, `--rotate`, `--callback-url`)

## Stack

*   **Backend:** FastAPI (0.110.1), Motor (3.3.1), PyMongo (4.5.0), bcrypt (4.1.3), slowapi, aiohttp, Google Auth libraries, ReportLab
*   **Frontend:** React (CRA + Craco), react-router-dom v6, Tailwind CSS
*   **Database:** MongoDB
*   **Build Tool:** Craco (Frontend)
*   **Runtime:** Python, Node.js

## Where things live

*   **Backend Source:** `backend/app/`
    *   `app/main.py`: Main FastAPI application entry point.
    *   `app/api_router.py`: Aggregates all API routes.
    *   `app/models.py`: Database models.
    *   `app/db.py`: Database connection and utilities.
    *   `app/services/`: Business logic modules (e.g., `billing`, `inventory`, `pricing_engine`).
    *   `app/routers/`: API endpoint definitions (e.g., `auth`, `listings`, `payments`).
    *   `app/indexes.py`: MongoDB index definitions.
    *   `app/security.py`: Authentication and authorization logic.
    *   `server.py`: Legacy shim pointing to `app.main`.
*   **Frontend Source:** `frontend/src/`
    *   `frontend/src/setupProxy.js`: Proxy configuration for API and WebSocket.
    *   `frontend/.env`: Frontend environment variables.
*   **DB Schema:** Defined implicitly by `app/models.py` and `app/indexes.py` (for collections like `pms_integrations`, `pms_availability_snapshots`, `pms_reservation_events`, `password_reset_tokens`).
*   **API Contracts:** Implicitly defined by FastAPI routers in `backend/app/routers/` and `backend/app/api_router.py`.
*   **PMS Integration Spec:** `CAPX_PMS_INBOUND_WEBHOOK_SPEC.md`
*   **PMS Prod Deploy Plan:** `CAPX_PMS_PROD_DEPLOY_PLAN.md` (5 faz + rollback + risk matrisi + PMS cevapları)
*   **PMS Smoke Script:** `scripts/prod_smoke_pms.sh` (4-adım: availability/sync, reservation/event x2 idempotent, fake HMAC 401, fake api key 401)
*   **PMS UAT Bootstrap:** `backend/scripts/bootstrap_pms_uat_tenant.py` (UAT-only; `ENV=production` set ise sys.exit ile bloklar)

## Mimari

*   **Modular Backend:** The backend, initially a monolithic `server.py`, has been refactored into a modular `app/` package structure for better organization and maintainability, preserving original API routes.
*   **Atomic State Transitions:** Critical operations like match acceptance and cancellation use atomic database operations (`$inc`, `update_one` with filters, unique indexes) to prevent race conditions and ensure data consistency.
*   **Idempotent PMS Integration:** PMS integration endpoints (e.g., `reservation/event`, `availability/sync`) are designed to be idempotent using `X-CapX-Event-Id` and unique indexes to handle duplicate requests gracefully.
*   **Compensating Transactions:** Match acceptance flow includes compensation blocks to refund quotas and rollback request statuses if any step fails, ensuring data integrity.
*   **Parallelized Data Fetching:** Performance-critical API endpoints (e.g., `/stats/market-trends`, `/stats/cross-region`) heavily utilize `asyncio.gather` and bulk fetching to reduce database round-trips and improve response times.
*   **Secure Password Reset:** Password reset mechanism uses SHA-256 hashed tokens with TTL, single-use, and an atomic consumption process (`find_one_and_update`) to prevent TOCTOU vulnerabilities and user enumeration.
*   **Per-Tenant Rate Limiting (PMS):** PMS endpoints use a custom `slowapi` `key_func` (`_pms_tenant_rate_key` in `app/routers/pms.py`) that derives the tenant identity from the SHA-256 hash of the Bearer api_key, ensuring quotas are enforced per tenant rather than per IP. Limits: `availability/sync` 10/min, `reservation/event` 50/sec; auth fails (401) are still counted to prevent brute-force probing of the rate limiter.

## Product

*   **Hotel Capacity Sharing:** Core functionality for hotels to list and request excess room capacity.
*   **Admin Approval Workflow:** Hotel registrations require admin approval.
*   **Matchmaking System:** Facilitates matching listings with requests.
*   **Payment & Invoicing:** Handles payment processing and generates PDF invoices.
*   **PMS Integration:** Provides robust inbound and outbound integration with Property Management Systems for real-time availability sync and reservation event handling (creation/cancellation).
*   **Real-time Notifications:** WebSocket-based notifications for system events.
*   **Reporting & Analytics:** Provides market trends, cross-region statistics, and performance scores.
*   **Authentication & Authorization:** Secure user and admin authentication with JWT and rate limiting.

## User preferences

*   Communication language: **Turkish**
*   This repo is currently not being run; the scope is static code review + Turkish report + targeted fixes.

## Son Yapılan Değişiklikler

*   **Per-tenant PMS rate limit** (`backend/app/routers/pms.py`): `_pms_tenant_rate_key` ile IP yerine api_key SHA-256 hash'i bazlı sayım. `availability/sync` → 10/dk, `reservation/event` → 50/sn. Smoke kanıtlandı (attempt 11 → HTTP 429).
*   **Bootstrap prod-guard** (`backend/scripts/bootstrap_pms_uat_tenant.py`): `ENV=production/prod` ise `sys.exit` — UAT script prod'da çalışamaz.
*   **Prod smoke script** (`scripts/prod_smoke_pms.sh`): 4-adım tek komut smoke; `set +x` ile `bash -x` debug modunda bile secret leak yok; `PMS_SMOKE_DEBUG=1` opt-in.
*   **CapX ↔ PMS UAT entegrasyonu — uçtan uca yeşil**: availability/sync (200 + snapshot+listing upsert), reservation/event (200 + idempotent), CapX→PMS match.created webhook (delivered 2s, HMAC iki yönlü).
*   **CI/CD 10 paralel job** (`.github/workflows/main.yml`): api-contract, architecture-guards, docs-freshness, backend-tests, frontend-build, lint, security-scan, deploy-staging, deploy-production, quality-gate.

## Gotchas

*   If deploying cross-origin in production, `REACT_APP_BACKEND_URL` must be set to the full backend origin. For same-origin deployment, it can be left empty.
*   PMS callback URLs from CapX have an SSRF guard; private/loopback/link-local/metadata IPs are rejected unless `PMS_ALLOW_LOOPBACK_CALLBACK=1` is set in development.
*   Password reset in development mode returns a `debug_token`; in production, an email integration (e.g., Resend) is required for actual email delivery.
*   `backend/scripts/bootstrap_pms_uat_tenant.py` is **UAT-only** and refuses to run when `ENV=production` (or `prod`). For prod tenant onboarding, use the admin UI flow that calls `POST /api/integrations/v1/pms/connect` (JWT-protected; raw api_key+webhook_secret returned exactly once).
*   PMS rate limit returns HTTP 429 + `Retry-After` header on quota exceed. Failed-auth (401) attempts are also counted against the per-tenant quota — a misconfigured PMS client hammering with a wrong api_key will hit 429 after 10 attempts/min on `availability/sync`.
*   `scripts/prod_smoke_pms.sh` enforces `set +x` internally so that `bash -x` debugging cannot leak `PMS_API_KEY` / `PMS_WEBHOOK_SECRET`. Use `PMS_SMOKE_DEBUG=1` to opt-in to xtrace when needed.

## Pointers

*   **FastAPI Documentation:** [https://fastapi.tiangolo.com/](https://fastapi.tiangolo.com/)
*   **React Documentation:** [https://react.dev/](https://react.dev/)
*   **MongoDB Documentation:** [https://www.mongodb.com/docs/](https://www.mongodb.com/docs/)
*   **Tailwind CSS Documentation:** [https://tailwindcss.com/docs](https://tailwindcss.com/docs)
*   **Craco Documentation:** [https://craco.js.org/](https://craco.js.org/)
*   **Replit Guides:** [https://docs.replit.com/](https://docs.replit.com/)
*   **Full Review Report:** `CAPX_INCELEME_RAPORU.md`
*   **PMS Integration Report:** `PMS_INCELEME_RAPORU.md`