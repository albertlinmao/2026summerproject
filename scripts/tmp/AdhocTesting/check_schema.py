#!/usr/bin/env python3
"""Dump one row from each imported result table via the Supabase client.

Kept its name; it moved. Two fixes:

  * The import path was ``os.getcwd() + 'backend'``, which breaks unless the
    script is run from the repo root. It is now derived from ``__file__``.
  * It now also dumps ``as_result_person_link``, because "the result rows look
    right but the dashboard is empty" almost always means the bridge is empty.

Run:  python scripts/tmp/AdhocTesting/check_schema.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _ad_hoc_common import MissingConfig, supabase_client  # noqa: E402

TABLES = [
    "as_meet_figure_result",
    "as_meet_routine_result",
    "as_result_person_link",
]


def main() -> int:
    try:
        supabase = supabase_client()
    except MissingConfig as exc:
        print(exc)
        return 1

    for table in TABLES:
        try:
            res = supabase.table(table).select("*").limit(1).execute()
        except Exception as exc:  # noqa: BLE001 - ad-hoc diagnostic
            print(f"{table}: ERROR {exc}")
            continue
        rows = res.data or []
        print(f"--- {table} ({len(rows)} row(s) shown) ---")
        print(json.dumps(rows, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
