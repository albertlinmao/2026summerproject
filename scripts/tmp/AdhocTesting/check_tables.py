#!/usr/bin/env python3
"""List the ``as_*`` tables in the public schema.

Read-only. Renamed from ``test_tables.py``; the old ``test_*.py`` name made
pytest attempt to collect it, and connecting at import time made that fail.

The ``as_`` prefix is the project's naming convention for schema objects, so
this is also the quickest way to spot objects that survived a rename under the
old unprefixed names (``club``, ``athlete``).

Run:  python scripts/tmp/AdhocTesting/check_tables.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _ad_hoc_common import MissingConfig, connect  # noqa: E402


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
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' ORDER BY table_name;
            """
        )
        names = [r[0] for r in cur.fetchall()]

        cur.execute(
            """
            SELECT table_name, table_type FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name LIKE 'as_%%'
            ORDER BY table_name;
            """
        )
        typed = cur.fetchall()

        print(f"public schema: {len(names)} objects")
        print("\nas_* objects (name, type):")
        for name, kind in typed:
            print(f"  {name:44} {kind}")

        legacy = [n for n in names if not n.startswith("as_")]
        if legacy:
            print("\nObjects NOT using the as_ prefix (check for leftovers):")
            for name in legacy:
                print(f"  {name}")
        return 0
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
