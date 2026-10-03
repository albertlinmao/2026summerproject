#!/usr/bin/env python3
"""Probe the judge-panel name regex against a sample PDF text block.

Offline: no database, no network, no backend. Useful when tuning the pattern in
``scripts/ingest_figures.py`` / ``ingest_routines.py`` against known text.

Renamed from ``test_officials.py``. The old ``test_*.py`` name meant pytest
tried to collect it as a test module and failed on the module-level code.
"""

import re

SAMPLE = """ J1 Karen ROSOLOWSKI Svetlana MALINOVSKAYA Rachael NAESSENS
 J2 Olivia ZHANG Denise SHIVELY Dana BRADLEY
 J3 Heidi LURENZ Shannon KORPELA Laura GANZEL
 J4 Debbie LATCHFORD Ginny JASONTEK """

# Family names are upper-case; given names are Capitalised. That contrast is the
# only reliable signal, since the printed form runs "FAMILY Given".
NAME_RE = re.compile(
    r"[A-Z][A-Za-z\.\-']+\s+[A-Z\-']{2,}(?:\s+[A-Z\-']{2,})*"
)


def main() -> int:
    for line in SAMPLE.splitlines():
        if not line.strip():
            continue
        # Drop the "J1" / "J2" panel prefix.
        rest = line.strip()[2:].strip()
        names = NAME_RE.findall(rest)
        print(line.strip()[:2], names)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
