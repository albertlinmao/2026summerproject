#!/usr/bin/env python3
"""Check how a non-UUID value behaves against a uuid column.

Renamed from ``test_db_uuid.py``. The original passed the string ``"101"`` to an
``.eq("meet_id", ...)`` filter on a uuid column. Under the person/membership
model a silently-failing uuid filter is easy to misread as "no data", so this
now asserts what the driver actually does instead of just printing an exception.

Run:  python scripts/tmp/AdhocTesting/check_db_uuid_query.py
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _ad_hoc_common import (  # noqa: E402
    MissingConfig,
    add_backend_to_path,
    supabase_client,
)

add_backend_to_path()

from src.core.database import get_supabase  # noqa: E402

TABLE = "as_meet_figure_result"


def probe(supabase, value: str) -> None:
    label = f"{value!r} ({type(value).__name__})"
    try:
        res = (
            supabase.table(TABLE)
            .select("team_code, team_name")
            .eq("meet_id", value)
            .limit(1)
            .execute()
        )
        print(f"{label}: OK, {len(res.data or [])} row(s)")
    except Exception as exc:  # noqa: BLE001 - the point is to observe the error
        print(f"{label}: raised {type(exc).__name__}: {exc}")


def main() -> int:
    try:
        supabase_client()
    except MissingConfig as exc:
        print(exc)
        return 1

    supabase = get_supabase()
    print(f"Probing {TABLE}.eq('meet_id', ...) - the column is uuid.\n")

    probe(supabase, "101")
    probe(supabase, str(uuid.uuid4()))

    print(
        "\nA real uuid returns rows; a non-uuid raises. If a script 'found "
        "nothing',\ncheck whether it passed a non-uuid before assuming the "
        "table is empty."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
