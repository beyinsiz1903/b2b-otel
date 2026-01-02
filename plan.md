# Hotel-to-Hotel Capacity Exchange Platform — Implementation Plan (Updated for Phase 3 & 3.2)

## 1) Objectives

- Build a regional B2B hotel-to-hotel capacity exchange for Sapanca & Kartepe.
- Enforce progressive disclosure: hotel identity/contact remains hidden until a match is accepted.
- Maintain a single user type (HOTEL) with email/password auth (JWT). No consumer bookings, no payments collected.
- Provide a working FastAPI + MongoDB backend, React frontend, and clean B2B UI with clear match states.
- Log all actions with timestamps for traceability.
- **Post-MVP Phase 3.1 (COMPLETED):** Strengthen perceived value and trust by surfacing a dedicated Match Detail experience and clear fee awareness (per-match fee + monthly summary) without changing legal positioning or adding payment processing.
- **Post-MVP Phase 3.2 (NEW):** Allow hotels to enrich availability listings with non-identifying images (URLs) and structured feature/amenity tags, while keeping listings anonymous and B2B-only.

## 2) Implementation Steps

### A. Architecture & Tech

- Stack: FastAPI (REST, `/api` prefix), MongoDB (`MONGO_URL`), React + shadcn/ui (`REACT_APP_BACKEND_URL`), JWT auth.
- Services bind to `0.0.0.0:8001` (backend) and `3000` (frontend). No hardcoded URLs.
- Serialization helpers to convert ObjectId/datetime for JSON responses.
- **Status:** Implemented in Phase 2; actively used by MVP.

### B. Data Model (Collections)

- `hotels`:
  - `{name, region, micro_location, concept, address, phone, whatsapp, website, contact_person, email (unique), password_hash, created_at, updated_at}`
- `availability_listings`:
  - Core fields (Phase 2):
    - `{hotel_id, region, micro_location, concept, capacity_label, pax, date_start, date_end, nights, price_min, price_max, availability_status(available|limited|alternative), is_locked, lock_request_id, created_at, updated_at}`
  - **Phase 3.2 enrichment (to add):**
    - `image_urls: [str]` — optional list of image URLs provided by the hotel (no upload/storage, just URLs).
    - `features: [str]` — optional list of feature/amenity tags (e.g. `"Şömine"`, `"Göl manzarası"`, `"Jakuzili"`).
- `requests`:
  - `{from_hotel_id, to_listing_id, to_hotel_id, guest_type(family|couple|group), notes, confirm_window_minutes, status(pending|accepted|rejected|alternative_offered|cancelled|expired), alternative_payload(optional), created_at, updated_at}`
- `matches`:
  - `{request_id, listing_id, hotel_a_id, hotel_b_id, status(accepted), reference_code, fee_amount, fee_status(due|recorded|waived), accepted_at, created_at}`
- `activity_logs`:
  - `{actor_hotel_id, action, entity, entity_id, metadata, created_at}`
- `counters` (for reference codes):
  - `{key:"SPC-2026" -> seq: 481}`

**Status:** Base data model implemented in backend; collections are created on first write via Motor/Mongo. Phase 3.2 requires extending `availability_listings` documents (and related Pydantic schemas) to include `image_urls` and `features`.

### C. Business Rules

- **Pre-match visibility:**
  - Listings API returns ONLY anonymous, non-contact fields, including:
    - `region, micro_location, concept, capacity_label/pax, date_start, date_end, nights, price_min, price_max, availability_status, is_locked`.
    - **Phase 3.2 (to add):** `image_urls` and `features` **as long as they do not contain explicit identity/contact information** (e.g., logos or images with hotel name signage are discouraged in pilot guidelines, but not programmatically filtered).
  - Hotel identity fields (name, address, phone, WhatsApp, website) are never included in listing responses.
- **Request creation & locking:**
  - Creating a request sets `listing.is_locked = true` and `lock_request_id = request_id`.
  - Subsequent request attempts to a locked listing are rejected until a decision is made.
- **Decision flow (receiving hotel):**
  - `accept` → sets request status to `accepted`, unlocks listing, creates `match` with reference code and fee record.
  - `reject` → sets request status to `rejected`, unlocks listing.
  - `offer_alternative` → sets status to `alternative_offered` with proposed terms in `alternative_payload` (backend ready; UI to be added in a later phase).
  - `accept_alternative` → requester accepts alternative, match is created.
- **Progressive disclosure trigger:**
  - After match acceptance, both hotels may view each other’s identity/contact for that specific match.
  - Identities are never shown to unrelated hotels; `/api/matches/{id}` enforces authorization.
- **Monetization (logical only):**
  - On match acceptance, `matches.fee_amount` is set (fixed from env `MATCH_FEE_TL`) and `fee_status = due`.
  - No payment processing or invoicing is performed; this is a record for potential future billing.
- **Logging:**
  - Every create/update/decision action writes to `activity_logs` with timestamps for traceability.

**Status:** All above core business rules (anon listings, locking, accept/reject, match creation, fee recording, logging) are implemented and verified via E2E tests. Phase 3.2 extends the *content* of a listing (images + features) but does not change core rules.

### D. API Surface (all prefixed with `/api`)

- **Auth:**
  - `POST /auth/register`
  - `POST /auth/login` (OAuth2 password grant style)
  - `GET /auth/me`
- **Hotels:**
  - `GET /hotels/me`
  - `PUT /hotels/me`
- **Listings:**
  - `POST /listings` (create)
  - `GET /listings` (anonymous feed; supports `region`, `concept`; `mine=true` returns only caller’s listings, still without exposing hotel identity to others)
  - `GET /listings/{id}` (anonymous view of a single listing)
  - `PUT /listings/{id}`, `DELETE /listings/{id}` (owner only; can be added/extended as needed)
  - **Phase 3.2 (to adjust):**
    - `POST /listings` should accept optional `image_urls: List[str]` and `features: List[str]` fields.
    - `GET /listings` and `GET /listings/{id}` should include `image_urls` and `features` in their anonymous payloads.
- **Requests:**
  - `POST /requests` (create to a listing)
  - `GET /requests/outgoing`
  - `GET /requests/incoming`
  - `GET /requests/{id}` (optional/extendable)
  - `POST /requests/{id}/accept`
  - `POST /requests/{id}/reject`
  - `POST /requests/{id}/offer-alternative`
  - `POST /requests/{id}/accept-alternative`
  - `POST /requests/{id}/cancel`
- **Matches:**
  - `GET /matches` (list matches where current hotel is `hotel_a_id` or `hotel_b_id`)
  - `GET /matches/{id}` (returns match + `counterparty.self` + `counterparty.other` with full hotel info, only for authorized parties)

**Status:** Implemented and exercised in tests. Phase 3.2 requires extending listings-related schemas and responses to surface `image_urls` and `features`.

### E. Reference Code Generation

- Prefix by region:
  - Sapanca → `"SPC"`
  - Kartepe → `"KTP"`
- Format: `{PREFIX}-{YYYY}-{NNNNN}`
  - Example: `SPC-2026-00481`.
- Implementation:
  - Maintain atomic counters per `{prefix-year}` in `counters` collection via `find_one_and_update` with `$inc` and `upsert: true`.

**Status:** Implemented and verified by tests (reference codes are generated on match creation).

### F. Frontend (React)

- **Phase 2 MVP pages (implemented):**
  - `/login` — Hotel login (email/password) with B2B copy; redirects to `/dashboard` on success.
  - `/register` — Hotel registration form (region, micro-location, concept, contact details, credentials).
  - `/dashboard` — KPI cards:
    - Gönderilen Talepler (outgoing requests count)
    - Gelen Talepler (incoming requests count)
    - Onaylanmış Eşleşmeler (matches count)
  - `/listings` — Anonymous listings feed:
    - Cards show region/micro-location, concept, capacity_label, pax, date range, nights, price range, availability_status, lock state.
    - “Talep Gönder” button triggers request creation; locked listings disable button and change label.
  - `/availability` — Availability management:
    - Form to create capacity (region, concept, micro-location, capacity, dates, prices, status).
    - List of own active listings with status chips.
  - `/requests` — Requests overview:
    - Incoming requests (Gelen Talepler): listing snippet (ID), guest type, confirmation window, status, action buttons (accept/reject).
    - Outgoing requests (Gönderilen Talepler): similar table without decision actions.
- **Phase 3.1 UI (implemented):**
  - `/matches` — Match list page:
    - Uses `/api/matches` to show each match with `reference_code`, `accepted_at`, `fee_amount`, and `fee_status`.
    - Each row has a “Detay” link to `/matches/:id`.
  - `/matches/:id` — Match detail page:
    - Uses `/api/matches/{id}` to display:
      - Reference code (prominent, card with `data-testid=match-reference`).
      - Fee info (`fee_amount`, `fee_status`) with `data-testid=match-fee`.
      - Counterparty details (`counterparty.other`) including name, region, concept, address, phone, WhatsApp, website, contact_person.
      - B2B-only note (`data-testid=match-note`) reinforcing that this is otel → otel kapasite paylaşımı (no end-customer sales).
  - `/dashboard` enhancements:
    - Additional KPI card (`data-testid=kpi-monthly-fee`) that aggregates current-month matches using `/api/matches` and displays: `"{N} eşleşme / {M} TL"`.
- **UI & state:**
  - Auth context, axios interceptor for Bearer token, `ProtectedRoute` wrapper for protected pages.
  - B2B-focused language (no consumer booking terms), clear state chips and lock states.
  - `data-testid` attributes on key interactive elements for automated E2E testing.
- **Phase 3.2 UI (to add):**
  - `/availability` form:
    - New optional fields:
      - `Resim URL’leri` (image URLs) — free-text with helper text (comma-separated) or dynamic list inputs.
      - `Özellikler / İmkanlar` (features) — tags/checkboxes or comma-separated list.
    - On submit, these map to `image_urls: List[str]` and `features: List[str]` in the `POST /api/listings` payload.
  - `/listings` anonymous cards:
    - Display the **first image** (if any) as a small, non-intrusive thumbnail.
    - Show a compact list of key features/amenities (e.g., up to 3–5 tags) under the main fields.
    - Preserve anonymity: no hotel name/logo text.

**Status:** Phase 2 + Phase 3.1 frontend is fully implemented and tested. Phase 3.2 requires extending the availability form and listing cards.

### G. Indexes & Constraints

- `availability_listings`:
  - Index on `(region, concept, availability_status, is_locked)` for efficient querying.
  - Owner-only writes enforced at application layer.
- `requests`:
  - Index on `(to_hotel_id, status)`, `(from_hotel_id, status)`, and `(to_listing_id, status)` for inbox/outbox performance.
- `matches`:
  - Index on `hotel_a_id`, `hotel_b_id`.
  - Unique index on `request_id` to prevent duplicate matches per request.

**Status:** Logical indexing plan; can be physically added via migrations/scripts as needed when moving toward production.

### H. Phase 1 — Core POC (Decision)

- **POC Status:** SKIPPED (Level 2: CRUD + JWT; no external integrations). Proceeded directly to full app, then end-to-end testing.
- **User Stories (validated via Phase 2 E2E):**
  1. As a hotel, I can browse listings and never see hotel identity pre-match.
  2. As a hotel, sending a request locks the listing for others.
  3. As receiving hotel, I can accept/reject/offer alternative on an incoming request.
  4. Upon acceptance, both hotels see identity details and a reference code.
  5. A fixed match fee entry is recorded; no invoice/payment is attempted.

### I. Phase 2 — App Development (Full MVP)

**Status: Completed (backend + frontend + E2E tests).**

- **Backend Implementation (completed):**
  - Auth (`register/login/me`) with bcrypt hashing and JWT; dependency to inject current hotel into requests.
  - Models + CRUD for listings with anonymity and lock enforcement.
  - Request lifecycle endpoints (`accept/reject/offer-alt/accept-alt/cancel`) with state checks.
  - Match creation with reference code and fee recording.
  - Activity logging utility for all mutations.
- **Frontend Implementation (completed):**
  - Routing: `/login`, `/register`, `/dashboard`, `/listings`, `/availability`, `/requests`.
  - Components/pages: auth forms, anonymous listings cards, availability form, requests tables, dashboard KPI cards, shell layout with navigation.
  - State: auth context + axios interceptor; loading/error states.
  - Visual: modern, clean B2B tone; no consumer booking language; clear indication of lock and status.
- **Testing & QA (completed):**
  - Used `testing_agent_v3` to run E2E flows covering all Phase 2 user stories (backend + frontend).
  - Fixed identified login redirect issue; re-tested until green.
- **Phase 2 User Stories (validated):**
  1. As a hotel, I can register and log in securely.
  2. As a hotel, I can create/edit my availability with region, concept, capacity, dates, and price range.
  3. As a hotel, I can filter listings (basic filters) and see only anonymous data.
  4. As a hotel, I can send a request with guest type, notes, and confirm window; locked state appears.
  5. As receiving hotel, I can accept a request and see generated reference code immediately.
  6. As receiving hotel, I can reject a request which unlocks the listing.
  7. As receiving hotel, I can (backend) offer an alternative (notes + price/date suggestion); requester can accept alternative to confirm (backend-ready, UI pending).
  8. As a hotel, I can view outgoing/incoming requests and their statuses.
  9. As a hotel, I can rely on progressive disclosure: counterpart identity is only revealed once a match is accepted (via `/api/matches/{id}`).
  10. As a hotel, I can view dashboard KPIs for outgoing, incoming, and completed matches.
  11. As a hotel, I can sign out and protected routes are no longer accessible.

### J. Phase 3 — Match Detail & Fee Awareness UX (Completed)

**Goal:**
Turn the existing match and fee recording logic into a clear, trust-building UI experience that:
- Shows counterpart hotel identity and full contact details only after an accepted match.
- Surfaces per-match service fee (fixed fee, status) in the match context.
- Adds a simple monthly revenue/fee exposure summary on the dashboard.
- Does **not** introduce payments, checkout, or change the legal positioning (still a B2B matching & request management system, not an OTA or agency).

#### J.1 Backend (Phase 3.1)

- Reuse existing endpoints:
  - `GET /matches` — list of matches for the current hotel.
  - `GET /matches/{id}` — detailed match info with `counterparty.self` and `counterparty.other` hotel records.
- Optional (not required for 3.1, may be considered later):
  - `GET /dashboard/summary` to return aggregated monthly metrics (match count, total fee_amount). For now, Phase 3.1 computes monthly totals client-side from `/matches`.
- Ensure authorization and progressive disclosure rules remain intact:
  - Only hotels that are part of the match can access `/matches/{id}` and see `counterparty.other` details.

**Status:** Implemented and validated by tests (including an unauthorized access test for a third hotel).

#### J.2 Frontend (Phase 3.1)

- **New routes (implemented):**
  - `/matches` — Match list page.
  - `/matches/:id` — Match Detail page.
- **Match List (`/matches`):**
  - Consumes `GET /api/matches`.
  - Shows for each match:
    - Reference code.
    - Accepted date/time.
    - Per-match service fee: `fee_amount` and `fee_status` (e.g., `due`).
  - Each row has a “Detay” link to `/matches/:id` with `data-testid` hooks.
- **Match Detail (`/matches/:id`):**
  - Consumes `GET /api/matches/{id}`.
  - Shows prominently:
    - Reference code (large, easy to copy).
    - Clear label that this match occurred via the platform.
  - **Counterparty section:**
    - `self` (current hotel) summary.
    - `other` (counterparty hotel) full identity and contact:
      - Name
      - Region / micro-location
      - Concept
      - Address
      - Phone
      - WhatsApp
      - Website
      - Contact person
    - Emphasizes that these details are revealed only after a confirmed match and only to match parties.
  - **Service fee section:**
    - Text like: “Bu eşleşme için hizmet bedeli: {fee_amount} TL ({fee_status}).”
  - Small note reinforcing positioning:
    - E.g., “Bu eşleşme, otel → otel kapasite paylaşımı içindir. Son kullanıcıya satış yapılmaz; platform yalnızca B2B eşleşme ve talep yönetimi sağlar.”
- **Dashboard enhancements (`/dashboard`):**
  - KPI card for monthly service fee exposure, computed from `/api/matches` on the client side:
    - “Bu ayki eşleşmeler / hizmet bedeli” → count of matches with `accepted_at` in current month and sum of corresponding `fee_amount`.

**Status:** Fully implemented and validated by E2E tests (backend + frontend).

#### J.3 Phase 3.1 User Stories (Validated)

1. As a hotel, I can open `/matches` and see a list of my accepted matches, each with a reference code and basic summary.
2. As a hotel, I can click a match from the list and navigate to `/matches/:id` to see full details.
3. As a hotel, on the Match Detail page I can see my counterpart hotel’s full identity and contact details **only** for matches I am part of.
4. As a hotel, on the Match Detail page I can clearly see the service fee for that match (amount and status) without making any payment in the app.
5. As a hotel, on the dashboard I can see how many matches I’ve completed this month and the corresponding total service fee (exposure) for these matches.
6. As a hotel, if I try to access a match I’m not part of, I receive an authorization error and no counterpart data is leaked.

### K. Phase 3.2 — Rich Listing Content (Images & Features) (Planned)

**Goal:**
Let hotels add richer, but still anonymous, content to availability listings to better describe their capacity (e.g., visuals and amenities) without exposing hotel identity or shifting into consumer-facing OTA behavior.

#### K.1 Backend Changes

- Extend `availability_listings` documents to include:
  - `image_urls: List[str]` (optional) — list of image URLs.
  - `features: List[str]` (optional) — list of feature/amenity tags.
- Update Pydantic schemas in `server.py`:
  - `AvailabilityListingCreate` to accept optional `image_urls` and `features`.
  - `AvailabilityListingPublic` / `AvailabilityListingMine` to include `image_urls` and `features` in responses.
- Ensure these fields are included in:
  - `POST /api/listings` requests and validations.
  - `GET /api/listings` and `GET /api/listings/{id}` responses.
- Business rule alignment:
  - Images and features must not contain explicit contact/identity data (enforced at the UX and pilot-guideline level rather than strict backend validation for now).

#### K.2 Frontend Changes

- **Availability form (`/availability`):**
  - Add UI controls for:
    - `Resim URL’leri` (image URLs): 
      - Implementation option: single textarea with comma-separated URLs, parsed into `image_urls: string[]` on submit.
      - Future-friendly option: dynamic list of URL inputs.
    - `Özellikler / İmkanlar` (features): 
      - Implementation option: comma-separated tags; parsed into `features: string[]`.
  - Make these fields optional; keep form simple for pilot.
- **Listings feed (`/listings` anonymous cards):**
  - If `image_urls` exists and non-empty:
    - Show the first image as a small thumbnail at the top or side of the card.
  - If `features` exists:
    - Show up to 3–5 top features as small badges under the main details.
  - Continue to **hide all identity/contact fields**; these enhancements are purely descriptive of the stay, not the brand identity.

#### K.3 Phase 3.2 User Stories

1. As a hotel, while creating an availability listing, I can optionally add one or more image URLs that visually represent the capacity.
2. As a hotel, while creating an availability listing, I can optionally add feature/amenity tags (e.g., şömine, göl manzarası, jakuzili).
3. As a hotel browsing `/listings`, I can see a small preview image (if provided) and a couple of key features on each anonymous listing card, in addition to the existing fields (region, concept, capacity, dates, price range, status, lock state).
4. As a hotel, even after images/features are added, I still do **not** see hotel name, address, phone, WhatsApp, or website in `/listings` — identity is only revealed post-match in `/matches/:id`.
5. As a hotel, if I don’t want to add images/features, I can still create listings exactly as before.

## 3) Next Actions

- **Phase 3.2 implementation:**
  - Backend:
    - Extend `AvailabilityListingCreate`, `AvailabilityListingPublic`, and `AvailabilityListingMine` schemas with `image_urls` and `features`.
    - Adjust `POST /api/listings` to accept and persist these fields.
    - Adjust `GET /api/listings` and `GET /api/listings/{id}` to return them.
  - Frontend:
    - Update `/availability` form to collect image URLs and features (simple comma-separated inputs for pilot).
    - Update `/listings` cards to render the first image and key features where available.
  - Testing:
    - Use `testing_agent_v3` to verify that:
      - Listings with and without images/features can be created.
      - Anonymous cards show images/features correctly without leaking identity.
      - Existing flows (requests, matches, match detail) remain unaffected.

- **Beyond Phase 3.2 (unchanged high-level roadmap):**
  - Alternative / Karşı Teklif UI (Phase 3.2 in earlier naming, now next major UX phase):
    - Bring `offer-alternative` and `accept-alternative` flows into the UI with structured fields (alt dates, alt prices, notes) and a clear revision timeline per request.
  - Reporting & Insights:
    - Visual reports for: requests received/filled/missed by period, capacity types, and counterpart hotels.
  - Controlled Regional Expansion:
    - Rollout to new regions (e.g., Abant/Bolu, Ayder, Kaş, Alaçatı) with separate prefixes and region-specific pilots.
  - Commercial Experiments:
    - Refine pricing models (still avoiding % commission): per-match fee, optional subscriptions, unlimited-match packages, etc.

## 4) Success Criteria

- **Phase 2 (MVP) criteria — already met:**
  - Anonymous listings never leak hotel identity before acceptance.
  - Request lock prevents concurrent matches; unlocking on reject works.
  - Accept (or accept-alternative, where used) creates a match, reveals identities for the two parties only, generates a reference code, and records a fixed fee.
  - All Phase 2 user stories pass via testing agent; no red screen errors; all API routes under `/api`; env vars used; interactive elements have `data-testid`.
  - Backend and frontend integrated at the provided preview URL and responsive on mobile/desktop.

- **Phase 3.1 (Match Detail & Fee Awareness) criteria — met:**
  - `/matches` and `/matches/:id` routes work end-to-end against the live backend.
  - Match Detail page displays counterpart identity and contact details **only** when the current hotel is part of the match.
  - Per-match `fee_amount` and `fee_status` are clearly visible on Match Detail without any payment flow.
  - Dashboard shows correct current-month match count and total service fee exposure, based on `accepted_at` and `fee_amount`.
  - All new Phase 3.1 user stories pass via testing agent; no regressions introduced in existing flows.
  - Legal and product positioning remain intact: the system is a B2B matching & request management platform, not an OTA, travel agency, or payment processor.

- **Phase 3.2 (Rich Listing Content) criteria — to be met:**
  - `availability_listings` supports `image_urls` and `features` fields end-to-end (DB, backend schemas, APIs, frontend forms/cards).
  - Hotels can optionally add images and feature tags when creating listings without friction.
  - Anonymous listings display images/features in a way that enhances understanding of capacity but does not reveal direct identity/contact.
  - All existing flows (request creation, locking, match creation, match detail, KPIs) continue to operate correctly with listings that include or omit these new fields.
  - E2E tests for creation, retrieval, and display of enriched listings pass via testing agent; no regressions.
