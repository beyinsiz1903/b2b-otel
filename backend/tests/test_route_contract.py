"""Route contract smoke test.

Run from `backend/`:
    python3 -m tests.test_route_contract

Verifies:
  1) `app.main` imports without errors (catches missing imports / circulars).
  2) Live app exposes EXPECTED_API_ROUTES + EXPECTED_WS_ROUTES (catches
     decorator misspellings or dropped router modules).
  3) Two specific WebSocket paths are present.

Exits non-zero on failure so it can be wired into CI.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.routing import APIRoute, APIWebSocketRoute  # noqa: E402

from app.main import app, EXPECTED_API_ROUTES, EXPECTED_WS_ROUTES  # noqa: E402


def _collect_failures() -> list[str]:
    api_paths = {r.path for r in app.routes if isinstance(r, APIRoute) and r.path.startswith("/api")}
    ws_paths = {r.path for r in app.routes if isinstance(r, APIWebSocketRoute)}

    failures: list[str] = []
    if len(api_paths) != EXPECTED_API_ROUTES:
        failures.append(
            f"/api path count mismatch: expected {EXPECTED_API_ROUTES}, got {len(api_paths)}"
        )
    if len(ws_paths) != EXPECTED_WS_ROUTES:
        failures.append(
            f"ws route count mismatch: expected {EXPECTED_WS_ROUTES}, got {len(ws_paths)}: {sorted(ws_paths)}"
        )
    if "/api/ws/notifications" not in ws_paths:
        failures.append("missing /api/ws/notifications websocket route")
    if "/api/ws/status" not in api_paths:
        failures.append("missing /api/ws/status http route")
    return failures


def test_route_contract():
    """Pytest entry — assert tüm route kontratları sağlanıyor."""
    failures = _collect_failures()
    assert not failures, "\n".join(failures)


def main() -> int:
    """CLI entry — geriye uyumluluk için korunuyor (`python -m tests.test_route_contract`)."""
    failures = _collect_failures()
    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    api_paths = {r.path for r in app.routes if isinstance(r, APIRoute) and r.path.startswith("/api")}
    ws_paths = {r.path for r in app.routes if isinstance(r, APIWebSocketRoute)}
    print(f"OK  {len(api_paths)} /api paths  {len(ws_paths)} ws routes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
