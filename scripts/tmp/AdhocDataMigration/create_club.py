#!/usr/bin/env python3
"""Provision the club tenant and the identity core it depends on.

Creates, if absent, ``as_person``, ``as_club_membership`` and
``as_person_identity``, then inserts one ``as_club`` row per team code found in
the imported result tables.

Schema authority: ``backend/supabase/migrations/`` — see
``specs/001-analytics-dashboard/identity-contract.md``. The DDL is mirrored here
only so this can bootstrap a bare database; on a real database the migrations
have already created these tables and the ``IF NOT EXISTS`` clauses make this a
no-op apart from the club inserts.

Fixed in this revision:
  * The club INSERT targeted ``public.club`` while the CREATE targeted
    ``public.as_club``. On any database that had actually been renamed, or on a
    fresh one, the insert failed with "relation club does not exist". Both now
    use ``as_club``.
  * The hardcoded Postgres password is gone; the DSN comes from the
    environment. See ``.env.example``.

Run:  python scripts/tmp/AdhocDataMigration/create_club.py
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _ad_hoc_common import connect  # noqa: E402

# as_club.created_by references as_person(id), so the person table has to exist
# before the club table.
PERSON_DDL = """
CREATE TABLE IF NOT EXISTS public.as_person (
    id          UUID PRIMARY KEY,
    given_name  TEXT NOT NULL,
    family_name TEXT,
    middle_name TEXT,
    birth_date  DATE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

CLUB_DDL = """
-- `created_by` is the operator person id, replacing the old `opid` text column.
CREATE TABLE IF NOT EXISTS public.as_club (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    code        TEXT NOT NULL UNIQUE,
    description TEXT,
    city        TEXT,
    website     TEXT,
    email       TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    created_by  UUID REFERENCES public.as_person(id)
);
"""

IDENTITY_DDL = """
-- Optional 1:1 link to an auth subject. A person may have no identity at all.
CREATE TABLE IF NOT EXISTS public.as_person_identity (
    person_id  UUID PRIMARY KEY REFERENCES public.as_person(id) ON DELETE CASCADE,
    subject_id UUID NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- The tenant-scoped edge. Authorization source of truth; a person has no club_id.
CREATE TABLE IF NOT EXISTS public.as_club_membership (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id  UUID NOT NULL REFERENCES public.as_person(id) ON DELETE CASCADE,
    club_id    UUID NOT NULL REFERENCES public.as_club(id) ON DELETE CASCADE,
    role       TEXT NOT NULL CHECK (role IN ('admin', 'coach', 'swimmer', 'parent', 'official')),
    title      TEXT,
    status     TEXT NOT NULL DEFAULT 'active'
               CHECK (status IN ('invited', 'active', 'dormant', 'left')),
    joined_at  DATE,
    left_at    DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_as_club_membership_active
    ON public.as_club_membership (person_id, club_id, role)
    WHERE status IN ('invited', 'active');
CREATE INDEX IF NOT EXISTS idx_as_club_membership_club_status
    ON public.as_club_membership (club_id, status);
CREATE INDEX IF NOT EXISTS idx_as_club_membership_person
    ON public.as_club_membership (person_id);
CREATE INDEX IF NOT EXISTS idx_as_person_name
    ON public.as_person (lower(family_name), lower(given_name));
"""

DEFAULT_CLUB = ("SEATTLE SYNCHRONIZED SWIM TEAM", "SST", "Seattle, WA")


def find_sst_teams(cur) -> set[tuple[str, str]]:
    """Team codes from the imported result tables that look like SST."""
    teams: set[tuple[str, str]] = set()
    for table in ("as_meet_figure_result", "as_meet_routine_result"):
        cur.execute(
            f"SELECT DISTINCT team_name, team_code FROM public.{table} "
            "WHERE team_code ILIKE '%SST%';"
        )
        teams.update(cur.fetchall())
    return teams


def insert_club(cur, name: str, code: str, city: str) -> None:
    """Insert a club if the code is free. Idempotent on the unique code."""
    cur.execute(
        """
        INSERT INTO public.as_club (name, code, city)
        VALUES (%s, %s, %s)
        ON CONFLICT (code) DO NOTHING;
        """,
        (name, code, city),
    )


def main() -> int:
    conn = connect()
    conn.autocommit = True
    cur = conn.cursor()

    try:
        # Order matters: as_club.created_by -> as_person, and
        # as_club_membership.club_id -> as_club.
        cur.execute(PERSON_DDL)
        print("as_person            created (or already exists).")
        cur.execute(CLUB_DDL)
        print("as_club              created (or already exists).")
        cur.execute(IDENTITY_DDL)
        print("identity core        created (or already exists).")

        teams = find_sst_teams(cur)
        print(f"\nSST teams found in imported results: {len(teams)}")

        inserted = 0
        for team_name, team_code in sorted(teams):
            if "SST" not in (team_code or "").upper():
                continue
            try:
                insert_club(cur, team_name, team_code, "Seattle, WA")
                print(f"  verified/inserted club: {team_name} ({team_code})")
                inserted += 1
            except Exception as exc:  # noqa: BLE001 - ad-hoc script
                print(f"  FAILED to insert {team_name}: {exc}")

        if not teams:
            print("No SST teams in the result tables; inserting the default club.")
            insert_club(cur, *DEFAULT_CLUB)
            print(f"  verified/inserted club: {DEFAULT_CLUB[0]} ({DEFAULT_CLUB[1]})")
            inserted += 1

        cur.execute("SELECT id, name, code FROM public.as_club ORDER BY code;")
        print(f"\nas_club now holds {len(cur.fetchall())} rows ({inserted} touched).")
        return 0
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
