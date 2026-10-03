#!/usr/bin/env python3
"""Seed demo people, memberships and competition results.

Creates the SST club, six swimmers and one coach as ``as_person`` rows with
``as_club_membership`` edges, then generates six meets of figure and routine
results so the analytics engine has enough history to fit a trend.

Identity model: ``specs/001-analytics-dashboard/identity-contract.md``.
A person carries no ``club_id``; the club edge is ``as_club_membership``. The
``as_athlete`` / ``as_coach`` views project over those two tables and are never
written to.

Fixed in this revision:
  * ``as_result_person_link`` is now populated. The previous version created
    people, memberships and result rows but left the bridge empty, so under the
    person/membership model ``as_daily_aggregations`` resolved nothing and
    dropped every row - the dashboard rendered empty for a database this script
    had just seeded. Result rows stay immutable; identity is attached only in
    the link table.
  * The name split now matches the authoritative PDF convention
    (``FAMILY Given``) used by ``load_athletes_clubs.py`` and
    ``user_mgmt_sync.py``. The demo names below are written in ``Given Family``
    order and are converted explicitly, rather than relying on the old helper
    happening to invert correctly.
  * ``_ensure_person`` no longer fails to match single-token names: comparing
    ``lower(NULL) = lower(NULL)`` yields NULL, so a one-word printed name created
    a duplicate person on every run.
  * The hardcoded Postgres password is gone; the DSN comes from the environment.

Run:  python scripts/tmp/AdhocDataMigration/generate_demo_data.py
"""

from __future__ import annotations

import json
import random
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _ad_hoc_common import connect  # noqa: E402

CLUB_CODE = "SST"
CLUB_NAME = "Seattle Synchro"
CLUB_CITY = "Seattle"
COACH_NAME = "Sophie Lin"

# Given Family order, because that is what a human reads. Converted to the
# PDF's "FAMILY Given" before hitting the database.
SWIMMER_NAMES_GIVEN_FAMILY = [
    "Emma Johnson",
    "Olivia Davis",
    "Sophia Martinez",
    "Isabella Rodriguez",
    "Mia Smith",
    "Charlotte Lee",
]

FIGURES = ["Ballet Leg", "Barracuda", "Kip", "Swordfish"]
MEET_COUNT = 6
# A deliberately weak figure per swimmer, so coaching recommendations have
# something to say.
WEAK_FIGURE = {
    "Mia Smith": "Kip",
    "Emma Johnson": "Swordfish",
    "Olivia Davis": "Ballet Leg",
}

FIGURE_TABLE = "as_meet_figure_result"
ROUTINE_TABLE = "as_meet_routine_result"


def split_printed_name(name: str) -> tuple[str | None, str | None]:
    """Split an official result PDF name into (family_name, given_name).

    Result sheets print "FAMILY Given" (e.g. "HE Sunny", "MOLCHANOVA Kate");
    some use "Family, Given". A middle name is not distinguishable from the
    printed form, so everything after the first token becomes given_name.
    """
    name = (name or "").strip()
    if not name:
        return None, None
    if "," in name:
        family, _, given = name.partition(",")
        return family.strip() or None, given.strip() or None
    parts = name.split()
    if len(parts) == 1:
        return parts[0], None
    return parts[0], " ".join(parts[1:])


def to_printed_form(given_family: str) -> str:
    """Convert "Emma Johnson" to the PDF's "Johnson Emma"."""
    family, given = split_printed_name(given_family)
    if family and given:
        return f"{family} {given}"
    return (family or given or given_family).strip()


def _ensure_person(cur, printed_name: str) -> tuple[str, bool]:
    """Return ``as_person.id`` for a printed name, creating it if needed.

    Matches with ``IS NOT DISTINCT FROM`` so a NULL given/family name still
    compares equal instead of silently missing and duplicating the person.
    """
    family_name, given_name = split_printed_name(printed_name)
    cur.execute(
        """
        SELECT id FROM as_person
        WHERE lower(family_name) IS NOT DISTINCT FROM lower(%s)
          AND lower(given_name)  IS NOT DISTINCT FROM lower(%s)
        LIMIT 1;
        """,
        (family_name, given_name),
    )
    row = cur.fetchone()
    if row:
        return row[0], False
    person_id = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO as_person (id, given_name, family_name) VALUES (%s, %s, %s);",
        (person_id, given_name, family_name),
    )
    return person_id, True


def _ensure_membership(cur, person_id: str, club_id: str, role: str) -> bool:
    """Create the person->club edge if absent. Returns True when inserted.

    ``ON CONFLICT DO NOTHING`` without a conflict target covers the partial
    unique index ``uq_as_club_membership_active``, which only constrains
    invited/active rows.
    """
    cur.execute(
        """
        SELECT 1 FROM as_club_membership
        WHERE person_id = %s AND club_id = %s AND role = %s
          AND status IN ('invited', 'active');
        """,
        (person_id, club_id, role),
    )
    if cur.fetchone():
        return False
    cur.execute(
        """
        INSERT INTO as_club_membership (person_id, club_id, role, status)
        VALUES (%s, %s, %s, 'active');
        """,
        (person_id, club_id, role),
    )
    return True


def _ensure_club(cur) -> str:
    cur.execute("SELECT id FROM as_club WHERE code = %s;", (CLUB_CODE,))
    row = cur.fetchone()
    if row:
        return row[0]
    club_id = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO as_club (id, name, code, city) VALUES (%s, %s, %s, %s);",
        (club_id, CLUB_NAME, CLUB_CODE, CLUB_CITY),
    )
    return club_id


def _ensure_event(cur, event_date) -> str:
    cur.execute("SELECT id FROM as_event LIMIT 1;")
    row = cur.fetchone()
    if row:
        return row[0]
    event_id = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO as_event (id, event_name, host_city, event_date) "
        "VALUES (%s, 'Demo Event', %s, %s);",
        (event_id, CLUB_CITY, event_date),
    )
    return event_id


def _clear_previous_results(cur) -> int:
    """Remove prior demo results so repeated runs do not stack scores forever.

    The link rows go with them: they reference the result ids being deleted.
    """
    cur.execute(
        f"""
        DELETE FROM as_result_person_link
        WHERE result_table = %s
          AND result_id IN (SELECT id FROM {FIGURE_TABLE} WHERE team_code = %s);
        """,
        (FIGURE_TABLE, CLUB_CODE),
    )
    cur.execute(
        f"""
        DELETE FROM as_result_person_link
        WHERE result_table = %s
          AND result_id IN (SELECT id FROM {ROUTINE_TABLE} WHERE team_code = %s);
        """,
        (ROUTINE_TABLE, CLUB_CODE),
    )
    cur.execute(f"DELETE FROM {FIGURE_TABLE} WHERE team_code = %s;", (CLUB_CODE,))
    cur.execute(f"DELETE FROM {ROUTINE_TABLE} WHERE team_code = %s;", (CLUB_CODE,))
    return cur.rowcount


def _link(cur, result_table: str, result_id: str, person_id: str,
          athlete_name: str) -> None:
    """Attach one printed name on one result row to a canonical person.

    Keyed on (result_table, result_id, athlete_name) to match
    ``uq_as_result_person_link``. For a routine, every athlete shares one
    result_id, so the printed name is the only intra-row discriminator.
    """
    cur.execute(
        """
        INSERT INTO as_result_person_link
            (result_table, result_id, person_id, athlete_name, confidence)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (result_table, result_id, athlete_name) DO NOTHING;
        """,
        (result_table, result_id, person_id, athlete_name, 1.0),
    )


def main() -> int:
    conn = connect()
    conn.autocommit = True
    cur = conn.cursor()

    try:
        club_id = _ensure_club(cur)
        print(f"Club: {CLUB_NAME} ({CLUB_CODE}) {club_id}")

        # People and the club edge. No as_person_identity row: a login is
        # optional, and these swimmers never sign in.
        person_by_printed: dict[str, str] = {}
        for given_family in SWIMMER_NAMES_GIVEN_FAMILY:
            printed = to_printed_form(given_family)
            person_id, created = _ensure_person(cur, printed)
            _ensure_membership(cur, person_id, club_id, "swimmer")
            person_by_printed[printed] = person_id
            print(f"  {'created' if created else 'existing'} swimmer {printed} {person_id}")

        coach_printed = to_printed_form(COACH_NAME)
        coach_id, coach_created = _ensure_person(cur, coach_printed)
        _ensure_membership(cur, coach_id, club_id, "coach")
        print(f"  {'created' if coach_created else 'existing'} coach    {coach_printed} {coach_id}")

        base_date = datetime.now() - timedelta(days=180)
        event_id = _ensure_event(cur, base_date.date())

        meets = []
        for i in range(MEET_COUNT):
            meet_id = str(uuid.uuid4())
            meet_date = base_date + timedelta(days=30 * i)
            meet_name = f"Demo Meet {i + 1}"
            cur.execute(
                """
                INSERT INTO as_meet (id, event_id, name, meet_date)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING;
                """,
                (meet_id, event_id, meet_name, meet_date.date()),
            )
            meets.append({"id": meet_id, "index": i, "date": meet_date})

        removed = _clear_previous_results(cur)
        print(f"\nCleared {removed} previous demo result rows (and their links).")

        print("Generating competition results...")
        figure_links = routine_links = 0

        for meet in meets:
            idx = meet["index"]
            for swimmer_idx, given_family in enumerate(SWIMMER_NAMES_GIVEN_FAMILY):
                printed = to_printed_form(given_family)
                # A gentle upward trend, plus noise.
                base_score = 55.0 + (swimmer_idx * 2) + (idx * 1.5)
                actual_score = round(base_score + random.uniform(-2, 2), 2)

                figure_scores = {
                    fig: round(actual_score + random.uniform(-3, 3), 2)
                    for fig in FIGURES
                }
                weak = WEAK_FIGURE.get(given_family)
                if weak:
                    figure_scores[weak] = round(figure_scores[weak] - 5.0, 2)

                result_id = str(uuid.uuid4())
                cur.execute(
                    f"""
                    INSERT INTO {FIGURE_TABLE}
                        (id, meet_id, team_code, team_name, athlete_name,
                         figure_score, figure_scores, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        result_id,
                        meet["id"],
                        CLUB_CODE,
                        CLUB_NAME,
                        printed,
                        actual_score,
                        json.dumps(figure_scores),
                        meet["date"],
                    ),
                )
                _link(
                    cur,
                    FIGURE_TABLE,
                    result_id,
                    person_by_printed[printed],
                    printed,
                )
                figure_links += 1

            # One routine per meet, printed names only. The link rows below are
            # what make these attributable.
            routine_id = str(uuid.uuid4())
            routine_score = round(65.0 + (idx * 2) + random.uniform(-1, 2), 2)
            cur.execute(
                f"""
                INSERT INTO {ROUTINE_TABLE}
                    (id, meet_id, team_code, team_name, team_athletes,
                     routine_score, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s);
                """,
                (
                    routine_id,
                    meet["id"],
                    CLUB_CODE,
                    CLUB_NAME,
                    json.dumps([{"name": n} for n in person_by_printed]),
                    routine_score,
                    meet["date"],
                ),
            )
            for printed, person_id in person_by_printed.items():
                _link(cur, ROUTINE_TABLE, routine_id, person_id, printed)
                routine_links += 1

        print(f"  figure results: {figure_links}  (each linked to 1 person)")
        print(f"  routine results: {MEET_COUNT}  ({routine_links} links)")

        # Prove the bridge is what the dashboard reads.
        cur.execute(
            """
            SELECT count(*) FROM as_daily_aggregations
            WHERE person_id IN %s;
            """,
            (tuple(person_by_printed.values()),),
        )
        agg = cur.fetchone()
        print(
            "\nas_daily_aggregations rows for these swimmers: "
            f"{agg[0] if agg else 0}"
        )
        if not agg or agg[0] == 0:
            print(
                "  WARNING: the materialized view has no rows. It is built from "
                "as_result_person_link, so refresh it:\n"
                "    SELECT refresh_as_daily_aggregations();"
            )

        print(f"\nClub ID:        {club_id}")
        print(f"Coach person:   {coach_id} ({coach_printed})")
        print("Swimmer persons: " + ", ".join(
            f"{n}={p}" for n, p in person_by_printed.items()
        ))
        print("Login is optional: no as_person_identity rows were created.")
        return 0
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
