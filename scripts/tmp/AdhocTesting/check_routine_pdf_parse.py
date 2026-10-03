#!/usr/bin/env python3
"""Run the routine PDF text parser over a dumped text file and print JSON.

Offline: no database, no network. The parser itself is imported from
``scripts/ingest_routines.py`` so this exercises the real ingest code path
rather than a copy.

Renamed from ``test_parse.py``, which collided with the unrelated
``scripts/test_parse.py`` and was likewise collected by pytest.

Usage:
    python scripts/tmp/AdhocTesting/check_routine_pdf_parse.py [path-to-text]

The input defaults to ``<repo-root>/temp_pdf_text.txt``. Dump one with
``scripts/inspect_pdf.py`` first.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts"
DEFAULT_INPUT = REPO_ROOT / "temp_pdf_text.txt"


def main() -> int:
    # Two entries are needed: the repo root for `scripts.ingest_routines`, and
    # scripts/ itself because ingest_routines.py does a flat
    # `from user_mgmt_sync import synchronized_meet`.
    for entry in (REPO_ROOT, SCRIPTS_DIR):
        if str(entry) not in sys.path:
            sys.path.insert(0, str(entry))

    # Import the real parser, not a copy of it.
    from scripts.ingest_routines import parse_routine_pdf_text

    if len(sys.argv) > 1:
        source = Path(sys.argv[1])
    else:
        source = DEFAULT_INPUT

    if not source.is_file():
        print(f"Input not found: {source}")
        print("Dump PDF text first, e.g.:  python scripts/inspect_pdf.py <pdf>")
        return 1

    text = source.read_text(encoding="utf-8", errors="replace")
    print(f"Parsed {len(text):,} characters from {source}")
    result = parse_routine_pdf_text(text)
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
