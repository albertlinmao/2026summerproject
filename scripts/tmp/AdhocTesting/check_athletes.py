#!/usr/bin/env python3
"""List distinct SST swimmer names in the imported figure results.

Read-only. The hardcoded Postgres password was removed in favour of the
environment. Note the query selects ``athlete_name`` - the *printed* name,
which is deliberately not an identity. To see canonical people, join through
``as_result_person_link`` (see ``check_data.py``).

Run: python scripts/tmp/AdhocTesting/check_athletes.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _ad_hoc_common import MissingConfig, connect, print_rows  # noqa: E402

TEAM = "SST"


def main() -> int:
    try:
        conn = connect()
    except MissingConfig as exc:
        print(exc)
        return 1

    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT DISTINCT team_code, athlete_name
            FROM as_meet_figure_result
            WHERE team_code ILIKE %s
            ORDER BY athlete_name;
            """,
            (f"%{TEAM}%",),
        )
        rows = cur.fetchall()
        print(f"{len(rows)} distinct printed name(s) for {TEAM}:")
        print_rows(rows, limit=10)

        # Same names, but resolved to canonical people.
        cur.execute(
            """
            SELECT l.athlete_name, l.person_id, l.confidence
            FROM as_result_person_link l
            WHERE l.result_table = 'as_meet_figure_result'
              AND l.athlete_name IN (
                SELECT DISTINCT athlete_name FROM as_meet_figure_result
                WHERE team_code ILIKE %s
              )
            ORDER BY l.athlete_name;
            """,
            (f"%{TEAM}%",),
        )
        linked = cur.fetchall()
        print(f"\n{len(linked)} of those resolved to a person via as_result_person_link:")
        print_rows(linked, limit=10)
        if not linked:
            print("  (none - run scripts/tmp/AdhocDataMigration/load_athletes_clubs.py)")
        return 0
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
