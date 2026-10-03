#!/usr/bin/env python3
"""Exercise the results browser through FastAPI's TestClient (no server needed).

Renamed from ``test_client.py``. Import path is now derived from ``__file__``
instead of ``os.getcwd() + 'backend'``.

This script does NOT authenticate, so it will 401 unless the endpoint under test
is public. For an authenticated probe use
``check_client_auth_override.py`` (dependency override) or
``check_client_login_flow.py`` (real login).

Run:  python scripts/tmp/AdhocTesting/check_client_results_browser.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _ad_hoc_common import add_backend_to_path  # noqa: E402

add_backend_to_path()

from fastapi.testclient import TestClient  # noqa: E402

from src.main import app  # noqa: E402


def main() -> int:
    client = TestClient(app)

    response = client.get("/api/results/events")
    print("GET /api/results/events ->", response.status_code)
    if response.status_code != 200:
        print("Expected an unauthenticated 401/403 here, not a data leak.")
        print(response.text[:400])
        return 1
    print(json.dumps(response.json(), indent=2)[:1500])

    events = response.json().get("data", [])
    if not events:
        print("\nNo events. Run the ingest scripts first.")
        return 1

    event_id = events[0]["id"]
    res2 = client.get(f"/api/results/events/{event_id}/meets")
    print(f"\nGET /api/results/events/{event_id}/meets ->", res2.status_code)
    print(res2.text[:800])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
