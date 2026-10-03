#!/usr/bin/env python3
"""Print a snapshot of one club's swimmers, results and coach.

Read-only. Renamed from ``check_data.py`` only in that it moved; behaviour is
unchanged except that the hardcoded Postgres password was replaced by
environment variables and the connection is closed.

The queries deliberately go through ``as_athlete`` / ``as_coach`` - the views
over ``as_person`` + ``as_club_membership`` - rather than querying people
directly, because the views are what the backend actually reads. If those views
return nothing, the membership rows are missing or not invited/active.

Run:  python scripts/tmp/AdhocTesting/check_data.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _ad_hoc_common import MissingConfig, connect, print_rows  # noqa: E402

CLUB_CODE = "SST"


def main() -> int:
    try:
        conn = connect()
    except MissingConfig as exc:
        print(exc)
        return 1

    cur = conn.cursor()
    try:
        cur.execute("SELECT id, name, code FROM as_club WHERE code = %s", (CLUB_CODE,))
        club = cur.fetchone()
        if not club:
            print(f"No club with code {CLUB_CODE!r}.")
            print("Run scripts/tmp/AdhocDataMigration/create_club.py first.")
            return 1
        club_id = club[0]
        print(f"Club: {club}")

        cur.execute(
            """
            SELECT person_id, name, birth_date FROM as_athlete
            WHERE person_id IN (
                SELECT person_id FROM as_club_membership WHERE club_id = %s
            )
            """,
            (club_id,),
        )
        rows = cur.fetchall()
        print(f"\nSwimmers via as_athlete view ({len(rows)}):")
        print_rows(rows)

        cur.execute(
            "SELECT id, athlete_name, team_code FROM as_meet_figure_result "
            "WHERE team_code = %s LIMIT 5",
            (CLUB_CODE,),
        )
        rows = cur.fetchall()
        print(f"\nFigure results, first 5 ({len(rows)}):")
        print_rows(rows)

        cur.execute(
            "SELECT id, team_athletes FROM as_meet_routine_result "
            "WHERE team_code = %s LIMIT 2",
            (CLUB_CODE,),
        )
        rows = cur.fetchall()
        print(f"\nRoutine results, first 2 ({len(rows)}):")
        print_rows(rows)

        cur.execute(
            """
            SELECT person_id, name FROM as_coach
            WHERE person_id IN (
                SELECT person_id FROM as_club_membership WHERE club_id = %s
            )
            """,
            (club_id,),
        )
        rows = cur.fetchall()
        print(f"\nCoach via as_coach view ({len(rows)}):")
        print_rows(rows)

        # The bridge the dashboard aggregates through. Empty here explains an
        # empty dashboard even when the result rows above are populated.
        cur.execute(
            """
            SELECT result_table, count(*)
            FROM as_result_person_link
            GROUP BY result_table ORDER BY result_table;
            """
        )
        print("\nas_result_person_link rows by table:")
        print_rows(cur.fetchall())
        return 0
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
