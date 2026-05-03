"""FastAPI app composition for CapX.

Routes are defined in `app/routers/*` modules. Importing them is enough to
register handlers on the shared `api` APIRouter (prefix=/api). The websocket
endpoints are mounted on a separate router that already includes /api in its
paths, so it is included on the app directly.
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api_router import api
from app.config import limiter
from app.db import client
from app.indexes import ensure_indexes

# Importing the router modules registers their @api.* routes (decorator side
# effects). Order does not matter for correctness — keep alphabetical.
from app.routers import (  # noqa: F401
    admin,
    admin_logs,
    admin_revenue,
    auth,
    cross_region,
    files,
    inventory,
    kvkk,
    listings,
    market_trends,
    notifications,
    payments,
    performance,
    performance_scores,
    pms,
    pricing,
    regions,
    reports,
    request_stats,
    requests_matches,
    sheets,
    stats,
    subscriptions,
    templates,
    websocket as websocket_routes,
)

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


@app.on_event("startup")
async def startup_event():
    """Uygulama başlangıcında indeksleri oluştur."""
    await ensure_indexes()


@app.on_event("shutdown")
async def shutdown_db_client() -> None:
    client.close()
