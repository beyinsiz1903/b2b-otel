# Hotel-to-Hotel Capacity Exchange Platform — Implementation Plan

1) Objectives
- Build a regional B2B hotel-to-hotel capacity exchange for Sapanca & Kartepe.
- Enforce progressive disclosure: hotel identity/contact remains hidden until a match is accepted.
- Single user type (HOTEL) with email/password auth (JWT). No consumer bookings, no payments collected.
- Provide working FastAPI + MongoDB backend, React frontend, and clean B2B UI with clear match states.
- Log all actions with timestamps for traceability.

2) Implementation Steps

A. Architecture & Tech
- Stack: FastAPI (REST, /api prefix), MongoDB (MONGO_URL), React + shadcn/ui (REACT_APP_BACKEND_URL), JWT auth.
- Services bind to 0.0.0.0:8001 (backend) and 3000 (frontend). No hardcoded URLs.
- Serialization helpers to convert ObjectId/datetime for JSON responses.

B. Data Model (Collections)
- hotels: {name, region, micro_location, concept, address, phone, whatsapp, website, contact_person, email (unique), password_hash, created_at, updated_at}
- availability_listings: {hotel_id, region, micro_location, concept, capacity_label, pax, date_start, date_end, nights, price_min, price_max, availability_status(available|limited|alternative), is_locked, lock_request_id, created_at, updated_at}
- requests: {from_hotel_id, to_listing_id, to_hotel_id, guest_type(family|couple|group), notes, confirm_window_minutes, status(pending|accepted|rejected|alternative_offered|cancelled|expired), alternative_payload(optional), created_at, updated_at}
- matches: {request_id, listing_id, hotel_a_id, hotel_b_id, status(accepted), reference_code, fee_amount, fee_status(due|recorded|waived), accepted_at, created_at}
- activity_logs: {actor_hotel_id, action, entity, entity_id, metadata, created_at}
- counters (for reference codes): {key:"SPC-2026" -> seq: 481}

C. Business Rules
- Pre-match visibility: listings API returns ONLY {region, micro_location, concept, capacity_label/pax, date range, night count, price_range, availability_status, is_locked}. Hotel identity fields are removed unless viewer is owner or match accepted with viewer as a party.
- Request creation: creates request, sets listing.is_locked=true and lock_request_id=request_id; subsequent request attempts are blocked until decision.
- Decision flow (receiving hotel): accept → creates match + reference code; reject → unlocks listing; offer_alternative → request.status=alternative_offered (with proposed terms); requester may accept alternative → creates match.
- Progressive disclosure trigger: after match acceptance, both hotels may view each other’s identity/contact for that match; never shown to unrelated hotels.
- Monetization: on match acceptance, set matches.fee_amount (fixed from env MATCH_FEE_TL) and fee_status=due. No payment processing.
- Logging: every create/update/decision action writes activity_logs with timestamps.

D. API Surface (all prefixed with /api)
- Auth: POST /auth/register, POST /auth/login, GET /auth/me
- Hotels: GET /hotels/me, PUT /hotels/me
- Listings:
  - POST /listings (create)
  - GET /listings (anonymous feed; supports filters: region, concept, pax, date range; mine=true returns owner’s full details)
  - GET /listings/{id} (anonymous unless owner or accepted match party)
  - PUT /listings/{id}, DELETE /listings/{id} (owner only)
- Requests:
  - POST /requests (create to a listing)
  - GET /requests/outgoing, GET /requests/incoming
  - GET /requests/{id}
  - POST /requests/{id}/accept
  - POST /requests/{id}/reject
  - POST /requests/{id}/offer-alternative
  - POST /requests/{id}/accept-alternative
  - POST /requests/{id}/cancel
- Matches: GET /matches, GET /matches/{id}

E. Reference Code Generation
- Prefix by region: Sapanca → "SPC", Kartepe → "KTP"; format: {PREFIX}-{YYYY}-{NNNNN}. Maintain atomic counters per prefix-year in counters collection (findOneAndUpdate with $inc, upsert).

F. Frontend (React)
- Pages: Login, Register, Listings Feed (anonymous cards), Availability Management (create/edit/list), Requests (Incoming/Outgoing), Dashboard (KPIs: active/incoming/completed/rejected), Match Detail (reveals identity post-acceptance). Mobile responsive.
- UI: Status chips (available/limited/alternative/locked), region & concept filters, date pickers, request modal (guest type, notes, confirm window), alternative offer modal.
- Data flow: axios instance using REACT_APP_BACKEND_URL, store JWT in memory + localStorage; route guards; data-testid attributes on interactive elements.
- Progressive UI: never show hotel identity in listing card; after accepted match, show contact info on Match Detail and related request rows.

G. Indexes & Constraints
- listings: index(region, concept, availability_status, is_locked), TTL not required; enforce owner-only writes.
- requests: index(to_hotel_id, from_hotel_id, status), index(to_listing_id, status).
- matches: index(hotel_a_id), index(hotel_b_id), unique(request_id).

H. Phase 1 — Core POC (Decision)
- POC Status: SKIPPED (Level 2: CRUD + JWT; no external integrations). Proceed directly to full app, then do end-to-end testing.
- User Stories to validate core rules (for later E2E):
  1. As a hotel, I can browse listings and never see hotel identity pre-match.
  2. As a hotel, sending a request locks the listing for others.
  3. As receiving hotel, I can accept/reject/offer alternative on an incoming request.
  4. Upon acceptance, both hotels see identity details and a reference code.
  5. A fixed match fee entry is recorded; no invoice/payment is attempted.

I. Phase 2 — App Development (Full MVP)
- Backend Implementation
  - Auth (register/login/me) with bcrypt hashing and JWT; middleware to inject hotel into requests.
  - Models + CRUD for listings with anonymity/sanitization layer and lock enforcement.
  - Request lifecycle endpoints (accept/reject/offer-alt/accept-alt/cancel) with state checks.
  - Match creation with reference code and fee recording.
  - Activity logging util for all mutations.
- Frontend Implementation
  - Routing: /login, /register, /listings, /availability, /requests, /dashboard, /matches/:id.
  - Components: ListingCard (anonymous), Filters, ListingForm, RequestModal, AlternativeModal, StatusChips, MatchDetail, DashboardCards.
  - State: auth context, axios interceptor for auth header; loading/error states.
  - Visual: modern B2B tone; no consumer booking language.
- Testing & QA
  - Use testing_agent_v3 to run E2E flows covering user stories; skip camera/voice/drag-drop.
  - Fix all issues, re-run until green.
- Phase 2 User Stories
  1. As a hotel, I can register and log in securely.
  2. As a hotel, I can create/edit my availability with region, concept, capacity, dates, and price range.
  3. As a hotel, I can filter listings by region/concept/date and see only anonymous data.
  4. As a hotel, I can send a request with guest type, notes, and confirm window; locked state appears.
  5. As receiving hotel, I can accept a request and see generated reference code immediately.
  6. As receiving hotel, I can reject a request which unlocks the listing.
  7. As receiving hotel, I can offer an alternative (notes + price/date suggestion); requester can accept alternative to confirm.
  8. As a hotel, I can view outgoing/incoming requests and their statuses.
  9. As a hotel, I can open a match detail page and see counterpart identity only after acceptance.
  10. As a hotel, I can view dashboard KPIs for active, incoming, completed, rejected.
  11. As a hotel, I can sign out and sessions clear.

3) Next Actions
- Implement backend (auth, models, listings, requests, matches, logging, reference code generator) with /api prefix and serializers.
- Implement frontend pages, forms, and flows with progressive disclosure enforced in UI and by backend.
- Seed two test hotels and listings for E2E.
- Run testing_agent_v3 against Phase 2 user stories; iterate fixes.
- Apply design_agent guidelines for styling polish.

4) Success Criteria
- Anonymous listings never leak hotel identity before acceptance.
- Request lock prevents concurrent matches; unlocking on reject works.
- Accept or accept-alternative creates match, reveals identities, generates reference code, records fixed fee.
- All Phase 2 user stories pass via testing agent; no red screen errors; all API routes under /api; env vars used; interactive elements have data-testid.
- Backend/Frontend integrated at provided preview URL and responsive on mobile/desktop.
