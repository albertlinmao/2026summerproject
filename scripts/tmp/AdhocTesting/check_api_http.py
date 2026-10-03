#!/usr/bin/env python3
"""Log in over HTTP and dump the dashboard payload.

Requires the backend running (``uvicorn src.main:app`` from ``backend/``).
Renamed from ``check_api.py`` to keep the whole folder on one ``check_*``
convention. The password is no longer embedded - pass it via
``DEMO_PASSWORD`` or you will get a 401.

The login response is snake_case, matching the contract: ``person_id`` identifies the
human and ``club_ids`` the clubs holding an invited/active membership. Both are a
cache - the backend re-reads membership before authorizing. See identity-contract.md.

Run:  python scripts/tmp/AdhocTesting/check_api_http.py
      DEMO_PASSWORD=... python scripts/tmp/AdhocTesting/check_api_http.py
"""

from __future__ import annotations

import json
import os
import sys

import requests

BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")
EMAIL = os.environ.get("DEMO_EMAIL", "sophie.lin@sst.example.com")
PASSWORD = os.environ.get("DEMO_PASSWORD")


def main() -> int:
    if not PASSWORD:
        print("DEMO_PASSWORD is not set (it used to be hardcoded here).")
        print("Set it in your shell or .env, e.g.:")
        print("  DEMO_PASSWORD=... python scripts/tmp/AdhocTesting/check_api_http.py")
        return 1

    sess = requests.Session()

    resp = sess.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
    )
    print("Login status:", resp.status_code)
    if resp.status_code != 200:
        print("Login error:", resp.text[:500])
        return 1

    data = resp.json()
    token = data.get("access_token", "")
    user = data.get("user", {})
    print("Token:", (token[:20] + "...") if token else "None")
    print("Person ID:", user.get("person_id"))
    print("Club IDs:", user.get("club_ids"))
    print("Roles by club:", user.get("roles_by_club"))

    headers = {"Authorization": f"Bearer {token}"}
    dash = sess.get(f"{BASE_URL}/api/analytics/dashboard", headers=headers)
    print("\nDashboard status:", dash.status_code)
    if dash.status_code == 200:
        print(json.dumps(dash.json(), indent=2)[:4000])
    else:
        print("Dashboard error:", dash.status_code, dash.text[:500])
    return 0 if dash.status_code == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
