"""FastAPI app composition for CapX.

Routes are defined in `app/routers/*` modules. Importing them is enough to
register handlers on the shared `api` APIRouter (prefix=/api). The websocket
endpoints are mounted on a separate router that already includes /api in its
paths, so it is included on the app directly.

Decorator side-effect imports are fragile: if a router module is removed from
`ROUTER_MODULES` (or fails to import), its routes silently vanish. To catch
this early, we assert the expected unique route count at startup. Bump
`EXPECTED_API_ROUTES` / `EXPECTED_WS_ROUTES` deliberately when adding endpoints.
"""
import importlib
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute, APIWebSocketRoute
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api_router import api
from app.config import limiter, logger
from app.db import client
from app.indexes import ensure_indexes

# Single source of truth for all router modules. Adding a module here is the
# only step required to mount its routes (decorators register on shared `api`).
ROUTER_MODULES = [
    "admin",
    "admin_logs",
    "admin_revenue",
    "auth",
    "cross_region",
    "files",
    "inventory",
    "kvkk",
    "listings",
    "market_trends",
    "notifications",
    "payments",
    "performance",
    "performance_scores",
    "pms",
    "pricing",
    "regions",
    "reports",
    "request_stats",
    "requests_matches",
    "sheets",
    "stats",
    "subscriptions",
    "templates",
]

# Expected route counts — bump deliberately when adding endpoints. These guard
# against silent drift if a router module is removed or renamed.
EXPECTED_API_ROUTES = 98  # unique /api/* HTTP paths (incl. /api/ws/status)
EXPECTED_WS_ROUTES = 1    # /api/ws/notifications (websocket)
# Total unique paths exposed = EXPECTED_API_ROUTES + EXPECTED_WS_ROUTES = 97

# Trigger router-module imports (decorator side effects register on `api`).
for _name in ROUTER_MODULES:
    importlib.import_module(f"app.routers.{_name}")

from app.routers import websocket as websocket_routes  # noqa: E402

app = FastAPI(title="Hotel-to-Hotel Capacity Exchange Platform")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# /api/* routes (incl. /api/integrations/v1/pms/*)
app.include_router(api)
# WebSocket router declares its own /api/ws/* paths
app.include_router(websocket_routes._ws_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


def _verify_route_contract() -> None:
    """Assert that the live app exposes the expected number of routes.

    Catches regressions where a router module is silently dropped or a route
    decorator is misspelled (e.g., `@app.` instead of `@api.`).
    """
    api_paths = {r.path for r in app.routes if isinstance(r, APIRoute) and r.path.startswith("/api")}
    ws_paths = {r.path for r in app.routes if isinstance(r, APIWebSocketRoute)}
    if len(api_paths) != EXPECTED_API_ROUTES:
        raise RuntimeError(
            f"Route contract drift: expected {EXPECTED_API_ROUTES} unique /api paths, "
            f"got {len(api_paths)}. Update EXPECTED_API_ROUTES in app/main.py if intentional."
        )
    if len(ws_paths) != EXPECTED_WS_ROUTES:
        raise RuntimeError(
            f"WebSocket contract drift: expected {EXPECTED_WS_ROUTES} ws routes, "
            f"got {len(ws_paths)}: {sorted(ws_paths)}"
        )
    logger.info("Route contract OK: %d /api paths, %d ws routes", len(api_paths), len(ws_paths))


_verify_route_contract()


@app.on_event("startup")
async def startup_event():
    """Uygulama başlangıcında indeksleri oluştur ve yetim PMS olaylarını topla."""
    await ensure_indexes()
    try:
        from app.services.pms_outbound import recover_pending_events
        await recover_pending_events()
    except Exception as e:  # pragma: no cover — recovery hatası boot'u engellememeli
        import logging
        logging.getLogger(__name__).warning("pms_outbound recovery failed: %s", e)


@app.on_event("shutdown")
async def shutdown_db_client() -> None:
    client.close()
