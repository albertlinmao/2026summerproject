#!/usr/bin/env python3
"""Print the columns of the core identity and analytics tables.

Read-only. Renamed from ``test_cols.py``; the old ``test_*.py`` name made
pytest attempt to collect it.

This is the quickest way to confirm a migration actually applied - a table that
exists but is missing a column is exactly the failure mode that produced the
``updated_at`` and ``model_version`` drift bugs.

Run:  python scripts/tmp/AdhocTesting/check_table_columns.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _ad_hoc_common import MissingConfig, connect  # noqa: E402

TABLES = [
    "as_person",
    "as_person_identity",
    "as_club",
    "as_club_membership",
    "as_person_link",
    "as_result_person_link",
    "as_video_uploads",
    "as_routine_timers",
    "as_predictive_insights",
    "as_coaching_recommendations",
]

# Columns added by a specific fix. A miss here is a real drift signal.
EXPECTED = {
    "as_predictive_insights": {"model_version"},
    "as_coaching_recommendations": {"model_version"},
    "as_video_uploads": {"updated_at"},
    "as_routine_timers": {"updated_at"},
}


def main() -> int:
    try:
        conn = connect()
    except MissingConfig as exc:
        print(exc)
        return 1

    cur = conn.cursor()
    problems = 0
    try:
        for table in TABLES:
            cur.execute(
                """
                SELECT column_name, data_type FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                ORDER BY ordinal_position;
                """,
                (table,),
            )
            rows = cur.fetchall()
            if not rows:
                print(f"--- {table} --- NOT FOUND")
                problems += 1
                continue

            present = {r[0] for r in rows}
            print(f"--- {table} ---")
            for name, kind in rows:
                print(f"  {name}: {kind}")

            missing = EXPECTED.get(table, set()) - present
            if missing:
                print(f"  !! MISSING expected column(s): {', '.join(sorted(missing))}")
                problems += 1

        print(f"\n{len(TABLES)} tables checked, {problems} problem(s).")
        return 1 if problems else 0
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
