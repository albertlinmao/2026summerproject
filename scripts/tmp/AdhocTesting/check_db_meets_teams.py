#!/usr/bin/env python3
"""Walk event -> meet -> team through the Supabase client.

Read-only. Renamed from ``test_db.py``.

Import path is now derived from ``__file__`` rather than ``os.getcwd()``, so the
script runs from any working directory.

Run:  python scripts/tmp/AdhocTesting/check_db_meets_teams.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _ad_hoc_common import (  # noqa: E402
    MissingConfig,
    add_backend_to_path,
    supabase_client,
)

add_backend_to_path()

from src.core.database import get_supabase  # noqa: E402


def show_meets(supabase, event_id: str) -> None:
    result = (
        supabase.table("as_meet")
        .select("id, name, meet_date")
        .eq("event_id", event_id)
        .execute()
    )
    print(f"Meets for event {event_id}: {len(result.data or [])}")
    for row in result.data or []:
        print(f"  {row['id']}  {row.get('name')}  {row.get('meet_date')}")


def show_teams(supabase, meet_id: str) -> None:
    for table in ("as_meet_figure_result", "as_meet_routine_result"):
        res = (
            supabase.table(table)
            .select("team_code, team_name")
            .eq("meet_id", meet_id)
            .execute()
        )
        teams = {r.get("team_code") for r in (res.data or [])}
        print(f"  {table}: {len(res.data or [])} rows, {len(teams)} distinct team(s)")


def main() -> int:
    try:
        supabase_client()  # fail fast on missing config
    except MissingConfig as exc:
        print(exc)
        return 1

    supabase = get_supabase()
    events = supabase.table("as_event").select("id, event_name").limit(5).execute()
    rows = events.data or []
    if not rows:
        print("No events. Run the ingest scripts first.")
        return 1

    for event in rows:
        print(f"\nEvent: {event.get('event_name')} ({event['id']})")
        show_meets(supabase, event["id"])
        meets = (
            supabase.table("as_meet")
            .select("id")
            .eq("event_id", event["id"])
            .limit(1)
            .execute()
        )
        if meets.data:
            show_teams(supabase, meets.data[0]["id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
