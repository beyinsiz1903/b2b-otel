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

## Architecture decisions

*   **Modular Backend:** The backend, initially a monolithic `server.py`, has been refactored into a modular `app/` package structure for better organization and maintainability, preserving original API routes.
*   **Atomic State Transitions:** Critical operations like match acceptance and cancellation use atomic database operations (`$inc`, `update_one` with filters, unique indexes) to prevent race conditions and ensure data consistency.
*   **Idempotent PMS Integration:** PMS integration endpoints (e.g., `reservation/event`, `availability/sync`) are designed to be idempotent using `X-CapX-Event-Id` and unique indexes to handle duplicate requests gracefully.
*   **Compensating Transactions:** Match acceptance flow includes compensation blocks to refund quotas and rollback request statuses if any step fails, ensuring data integrity.
*   **Parallelized Data Fetching:** Performance-critical API endpoints (e.g., `/stats/market-trends`, `/stats/cross-region`) heavily utilize `asyncio.gather` and bulk fetching to reduce database round-trips and improve response times.
*   **Secure Password Reset:** Password reset mechanism uses SHA-256 hashed tokens with TTL, single-use, and an atomic consumption process (`find_one_and_update`) to prevent TOCTOU vulnerabilities and user enumeration.

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

## Gotchas

*   If deploying cross-origin in production, `REACT_APP_BACKEND_URL` must be set to the full backend origin. For same-origin deployment, it can be left empty.
*   PMS callback URLs from CapX have an SSRF guard; private/loopback/link-local/metadata IPs are rejected unless `PMS_ALLOW_LOOPBACK_CALLBACK=1` is set in development.
*   Password reset in development mode returns a `debug_token`; in production, an email integration (e.g., Resend) is required for actual email delivery.

## Pointers

*   **FastAPI Documentation:** [https://fastapi.tiangolo.com/](https://fastapi.tiangolo.com/)
*   **React Documentation:** [https://react.dev/](https://react.dev/)
*   **MongoDB Documentation:** [https://www.mongodb.com/docs/](https://www.mongodb.com/docs/)
*   **Tailwind CSS Documentation:** [https://tailwindcss.com/docs](https://tailwindcss.com/docs)
*   **Craco Documentation:** [https://craco.js.org/](https://craco.js.org/)
*   **Replit Guides:** [https://docs.replit.com/](https://docs.replit.com/)
*   **Full Review Report:** `CAPX_INCELEME_RAPORU.md`
*   **PMS Integration Report:** `PMS_INCELEME_RAPORU.md`