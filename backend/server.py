"""Backwards-compatible entrypoint.

The original 5056-line monolithic server.py has been refactored into the
`app/` package. This shim preserves the `server:app` import path used by
uvicorn workflows. See `app/main.py` for composition and `app/routers/*`
for individual endpoint modules.
"""
from app.main import app  # noqa: F401
