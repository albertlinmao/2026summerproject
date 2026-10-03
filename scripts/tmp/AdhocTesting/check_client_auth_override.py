#!/usr/bin/env python3
"""Call the results browser with a faked caller, to test authorization logic
without a real login.

Renamed from ``test_client_2.py``.

Fixed in this revision - the override returned ``{"id": "test_user"}``, which is
the pre-membership shape. ``src.core.auth._build_caller`` now returns::

    {
        **claims,
        "person_id":  <uuid str>,
        "memberships": [ {person_id, club_id, role, status, ...}, ... ],
        "club_ids":    [ <club uuid str>, ... ],
        "roles_by_club": { <club uuid str>: [role, ...], ... },
    }

Anything reading ``person_id`` / ``club_ids`` / ``roles_by_club`` therefore saw
``None`` or ``KeyError`` under the old override. The override below matches the
real shape. Set ``FAKE_CLUB_ID`` to a real club id, otherwise the caller's club
list is empty and authorization correctly denies everything.

NOTE: this bypasses authentication, so it proves the *authorization* branch only.
It is not evidence that a real token works - use check_client_login_flow.py for
that.

Run:  FAKE_CLUB_ID=<uuid> python scripts/tmp/AdhocTesting/check_client_auth_override.py
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _ad_hoc_common import add_backend_to_path  # noqa: E402

add_backend_to_path()

from fastapi.testclient import TestClient  # noqa: E402

from src.core.auth import get_current_user  # noqa: E402
from src.main import app  # noqa: E402

FAKE_CLUB_ID = os.environ.get("FAKE_CLUB_ID", "")


def fake_caller() -> dict:
    """A caller in the shape core.auth actually produces."""
    person_id = str(uuid.uuid4())
    club_ids = [FAKE_CLUB_ID] if FAKE_CLUB_ID else []
    return {
        "person_id": person_id,
        "memberships": [
            {"person_id": person_id, "club_id": c, "role": "admin", "status": "active"}
            for c in club_ids
        ],
        "club_ids": club_ids,
        "roles_by_club": {c: ["admin"] for c in club_ids},
    }


def main() -> int:
    caller = fake_caller()
    if not FAKE_CLUB_ID:
        print("FAKE_CLUB_ID is not set: the caller has no club memberships, so")
        print("every authorization check below is expected to deny. That is the")
        print("correct behaviour, not a failure.\n")

    app.dependency_overrides[get_current_user] = lambda: caller
    try:
        client = TestClient(app)

        response = client.get("/api/results/events")
        print("GET /api/results/events ->", response.status_code)
        if response.status_code != 200:
            print(response.text[:400])
            return 1

        events = response.json().get("data", [])
        if not events:
            print("No events. Run the ingest scripts first.")
            return 1

        event_id = events[0]["id"]
        res2 = client.get(f"/api/results/events/{event_id}/meets")
        print(f"GET meets ->", res2.status_code)

        meets = res2.json().get("data", []) if res2.status_code == 200 else []
        if meets:
            meet_id = meets[0]["id"]
            res3 = client.get(f"/api/results/meets/{meet_id}/teams")
            print(f"GET teams ->", res3.status_code)
            print(json.dumps(res3.json(), indent=2)[:1200]
                  if res3.status_code == 200 else res3.text[:400])
        return 0
    finally:
        app.dependency_overrides.clear()


if __name__ == "__main__":
    raise SystemExit(main())
