#!/usr/bin/env python3
"""End-to-end results-browser probe with a real login, via TestClient.

Renamed from ``test_client_3.py``. The password used to be hardcoded; it now
comes from ``DEMO_PASSWORD``.

This is the only one of the three TestClient scripts that exercises the actual
authentication path, so it is the one that would catch a broken JWKS config or a
person whose ``sub`` resolves to no ``as_person_identity`` row.

Run:  DEMO_PASSWORD=... python scripts/tmp/AdhocTesting/check_client_login_flow.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _ad_hoc_common import add_backend_to_path  # noqa: E402

add_backend_to_path()

from fastapi.testclient import TestClient  # noqa: E402

from src.main import app  # noqa: E402

EMAIL = os.environ.get("DEMO_EMAIL", "sophie.lin@sst.example.com")
PASSWORD = os.environ.get("DEMO_PASSWORD")


def main() -> int:
    if not PASSWORD:
        print("DEMO_PASSWORD is not set (it used to be hardcoded here).")
        return 1

    client = TestClient(app)

    login = client.post(
        "/api/auth/login", json={"email": EMAIL, "password": PASSWORD}
    )
    print("POST /api/auth/login ->", login.status_code)
    if login.status_code != 200:
        print(login.text[:500])
        return 1

    body = login.json()
    user = body.get("user", {})
    print("personId:", user.get("person_id"))
    print("clubIds:", user.get("club_ids"))
    print("rolesByClub:", user.get("roles_by_club"))

    headers = {"Authorization": f"Bearer {body['access_token']}"}

    events_res = client.get("/api/results/events", headers=headers)
    print("\nGET /api/results/events ->", events_res.status_code)
    if events_res.status_code != 200:
        print(events_res.text[:500])
        return 1

    events = events_res.json().get("data", [])
    print(f"{len(events)} event(s)")
    if not events:
        return 0

    event_id = events[0]["id"]
    res2 = client.get(f"/api/results/events/{event_id}/meets", headers=headers)
    print(f"GET meets ->", res2.status_code)
    if res2.status_code != 200:
        print(res2.text[:400])
        return 1

    meets = res2.json().get("data", [])
    print(f"{len(meets)} meet(s)")
    if not meets:
        return 0

    meet_id = meets[0]["id"]
    res3 = client.get(f"/api/results/meets/{meet_id}/teams", headers=headers)
    print(f"GET teams ->", res3.status_code)
    if res3.status_code == 200:
        print(json.dumps(res3.json(), indent=2)[:1500])
    else:
        print(res3.text[:400])
    return 0 if res3.status_code == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
