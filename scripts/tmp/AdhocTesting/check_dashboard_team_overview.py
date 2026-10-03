#!/usr/bin/env python3
"""Log in over HTTP and print the dashboard's team_overview rows.

Requires the backend running. Renamed from ``test_api.py``; the old
``test_*.py`` name made pytest attempt to collect it, and its module-level
request ran at import time.

Differences from ``check_api_http.py``: this one drills into
``widgets.team_overview.athletes`` instead of dumping the whole payload. The
password used to be hardcoded and is now read from ``DEMO_PASSWORD``.

Note the coach can only see swimmers in clubs they hold a membership in - the
endpoint returns 403 for a club the caller is not a member of, rather than
silently falling back to the caller's first club.

Run:  DEMO_PASSWORD=... python scripts/tmp/AdhocTesting/check_dashboard_team_overview.py
"""

from __future__ import annotations

import json
import os

import requests

BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")
EMAIL = os.environ.get("DEMO_EMAIL", "sophie.lin@sst.example.com")
PASSWORD = os.environ.get("DEMO_PASSWORD")


def main() -> int:
    if not PASSWORD:
        print("DEMO_PASSWORD is not set (it used to be hardcoded here).")
        return 1

    sess = requests.Session()
    resp = sess.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
    )
    print("Login status:", resp.status_code)
    if resp.status_code != 200:
        print("Login error:", resp.status_code, resp.text[:500])
        return 1

    token = resp.json().get("access_token", "")
    headers = {"Authorization": f"Bearer {token}"}

    dash = sess.get(f"{BASE_URL}/api/analytics/dashboard", headers=headers)
    print("Dashboard status:", dash.status_code)
    if dash.status_code != 200:
        print("Dashboard error:", dash.status_code, dash.text[:500])
        return 1

    try:
        athletes = dash.json()["widgets"]["team_overview"]["athletes"]
    except (KeyError, TypeError) as exc:
        print("Unexpected dashboard shape (missing team_overview):", exc)
        print(json.dumps(dash.json(), indent=2)[:2000])
        return 1

    print(f"\nTeam overview athletes ({len(athletes)}):")
    for a in athletes:
        print(
            f"  {a.get('name')}: "
            f"figure={a.get('avg_figure_score')}, "
            f"routine={a.get('avg_routine_score')}, "
            f"trend={a.get('improvement_trend')}"
        )

    if not athletes:
        print(
            "\nEmpty. The team_overview widget aggregates through "
            "as_result_person_link,\nso check the bridge before suspecting the "
            "authorization layer."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
