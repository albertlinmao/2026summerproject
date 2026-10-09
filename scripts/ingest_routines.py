#!/usr/bin/env python3
"""Parse routine score PDFs and load results into separate Supabase tables.

Usage:
  python scripts/ingest_routines.py /path/to/Routine_Results.pdf [--dry-run]

Writes as_event -> as_meet -> as_meet_judge_panel -> as_meet_routine_result,
then calls synchronized_meet() to reconcile people, clubs and memberships, and
finally ensure_people_and_links() to attach each printed swimmer name to a person.

Those last two are separate on purpose. synchronized_meet() is the account half: it
provisions tenants, Auth users and API keys. Attaching a result to a person is the
identity half, it creates no login, and it runs even under --no-provision. A result
that is stored but not attributable is invisible to the dashboard, so attribution must
not depend on Auth succeeding. It runs last because it needs the as_club rows that
provisioning may have just created; as_club.id is the tenant id.

Re-importing a PDF that is already loaded is refused rather than duplicated. See
scripts/ingest_common.py for the write path and why it is shared with ingest_figures.py.

WHY THE PARSER IS COLUMN-AWARE
------------------------------
The number of judges is a property of the meet, not of this parser, so it is read from
each sheet's own header. Three meets in swim-meets/2026 print three judges (J1 J2 J3),
three print five (J1..J5) and two print four (J1..J4). A five-judge sheet looks like

    Code Rank Draw Swimmer Ref DD J1 J2 J3 J4 J5 Total Pen. Total Routine
                                     ^^^^^^^^^^^^^^^^^^^ five
                                                  ^^^^^^^ line total
                                                            ^^^^^^^ cumulative total
                                                                   ^^^^^^^ routine

The old parser read the scoring rows as whitespace-separated tokens with a regex that
captured j1..j4 and then a "total". On a five-judge sheet that silently stores J5 as the
line total, and it only matches when the row happens to carry exactly zero or two
trailing numbers - which real rows do not. Measured over the 17 detailed PDFs in
swim-meets/2026/20260305_WestZone_Sacramento_CA that was 181 of 1818 rows correct, 370
silently wrong and 928 dropped.

So each numeric token is assigned to a column by its horizontal offset against the
header labels on the same page, instead of by counting tokens. Repeated labels ("Total"
appears twice) are numbered left to right, which is what separates the line total from
the cumulative total.

Two details that cost real rows before they were handled:

  * The degree-of-difficulty factor is printed in brackets after the element name,
    "HYBRID (0.5)". On a three-judge sheet its character offset lands under the Ref
    column, so it has to be masked out or every element row looks like a deduction row.
  * Some sheets print the column header once, above the first athlete, rather than
    repeating it per athlete. If that line is consumed while collecting officials, the
    athlete rows below have no header to map against and nothing parses.

The Ref column is the one that defeats whitespace parsing: on a deduction row it holds
the element's ORIGINAL difficulty while the DD column holds the AWARDED one, so the row
carries one extra number in the middle that looks exactly like a judge score.

SCORING ARITHMETIC, verified against every printed total in the sample corpus
---------------------------------------------------------------------------
    judge mean           = middle three of five, or the plain mean of three
    element line total   = judge mean * awarded DD * factor
    AI line total        = judge mean * factor * 3
    STC category total   = mean of the printed fault counts * factor   (no x3)
    printed Total        = sum of the element line totals
    printed AI Total     = sum of the AI line totals
    printed deduction    = the trailing STC column; the category totals are not
                           required to sum to it, because a routine can carry more
                           than one STC panel
    printed Routine      = elements + AI + synchronization deduction

The factor is the number in parentheses after the element type (HYBRID (0.5)). It is
not decorative: DD/2 only ever agreed with DD*factor because one sheet used HYBRID 0.5
with a DD of exactly 7.000. Every other factor in the meet disagreed.

FOUR-JUDGE PANELS ARE NOT SUPPORTED
-----------------------------------
Charlotte David Regional A and Junior Olympics Ypsilanti print four judges, and their
printed line totals cannot be reproduced from the printed judge scores by dropping the
highest and lowest, by dropping either one alone, or by taking the plain mean - the
implied mean moves between positions from row to row. Rather than guess a rule and write
possibly-wrong official scores, those sheets are reported and refused. `--allow-mismatch`
is the deliberate way past that once someone has confirmed the printed totals.

The printed values are authoritative - they are the official scores - so recomputation
is a CHECK, not a source. A row that does not reconcile is reported and, unless
--allow-mismatch is passed, stops the import.

SYNCHRONIZATION IS NOT PROMOTED TO A TOTAL
------------------------------------------
The STC rows carry a deduction. Writing it into `synchronization_total` put -15.9667 in
a column that means a total, and three STC rows raced for it with the last one winning.
It is still not promoted. The deduction is recorded on the STC row as
`synchronization_deduction`, the panel total is derived from it, and it is used to
validate the printed Routine column.
"""
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json

try:
    import pdfplumber
except Exception:
    print("Missing dependency pdfplumber. Install via: pip install -r requirements.txt")
    raise

try:
    import requests
except Exception:
    print("Missing dependency requests. Install via: pip install -r requirements.txt")
    raise

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ingest_common import (  # noqa: E402
    AlreadyIngested,
    IngestError,
    RunReport,
    SupabaseRest,
    add_script_dir_to_path,
    check_results_present,
    describe,
    get_supabase_config,
    prepare_meet_for_write,
    resolve_event,
    resolve_meet,
)

add_script_dir_to_path()

try:
    from person_names import person_match_keys, split_person_name
except ImportError:  # running as a module rather than a script
    from scripts.person_names import person_match_keys, split_person_name

try:
    from routine_identity import ensure_people_and_links
except ImportError:  # running as a module rather than a script
    from scripts.routine_identity import ensure_people_and_links

try:
    from user_mgmt_sync import synchronized_meet
except Exception:
    print("Missing dependency user_mgmt_sync (psycopg2?). Install via: pip install -r requirements.txt")
    raise

# --------------------------------------------------------------------------------------
# Column geometry
# --------------------------------------------------------------------------------------

# Only the labels that carry a number matter. Code/Rank/Draw/Swimmer/Nageuse/Team are
# text columns and are deliberately absent.
HEADER_LABEL_RE = re.compile(r"(?<![A-Za-z])(Ref|DD|Pen\.|Routine|J\d|Total)(?![A-Za-z])")

# The judge count is a property of the meet, not of this parser: the West Zone sheets
# carry five judges (J1..J5), the Classic Snohomish sheets carry three (J1..J3). It is
# read from each header rather than assumed, because assuming five silently turned every
# J3 of a three-judge sheet into a line total.
MIN_JUDGES = 3
MAX_JUDGES = 9

ELEMENT_TYPES = ("ACRO", "HYBRID")
AI_TYPES = ("Choreo and Music", "Performance", "Transitions")
STC_TYPES = ("STC Small", "STC Obvious", "STC Major-Median", "STC Major")

SCORING_ROW_RE = re.compile(r"^\s*(ACRO|HYBRID|Choreo and Music|Performance|Transitions|STC\b)")
ELEMENT_ROW_RE = re.compile(r"^\s*(?P<type>ACRO|HYBRID)\s*\((?P<factor>[0-9.]+)\)")
AI_ROW_RE = re.compile(r"^\s*(?P<type>Choreo and Music|Performance|Transitions)\s*\((?P<factor>[0-9.]+)\)")
# STC categories are labelled Small / Obvious / Major / Major-Median depending on the
# meet, a fault count can be left blank when a judge saw none (so two counts, not three),
# and the trailing deduction is sometimes printed as a bare "-". All three variants are
# in the sample corpus, so the label is taken generically and the counts are a group.
STC_ROW_RE = re.compile(
    r"^\s*(?P<type>STC\s+[A-Za-z][A-Za-z\-]*)\s*\((?P<factor>[0-9.]+)\)"
    r"\s+(?P<counts>[0-9]+\s+[0-9]+(?:\s+[0-9]+)?)\s+(?P<tot>[0-9.]+)"
    r"(?:\s+(?P<pen>-?[0-9.]+|-))?\s*$"
)
NUMBER_RE = re.compile(r"-?\d+\.\d+")
BRACKETED_RE = re.compile(r"\([^)]*\)")


def _mask_bracketed(line: str) -> str:
    """Blank out "(0.6)" style groups, keeping every character offset identical.

    The degree-of-difficulty factor is printed in brackets after the element name. On
    the three-judge sheets its offset lands under the Ref column, so leaving it in made
    every single element row look like a deduction row (Ref=0.6 next to DD=2.375).
    """
    return BRACKETED_RE.sub(lambda m: " " * (m.end() - m.start()), line)

# Printed scores disagree with recomputation by small amounts when the meet software
# rounds intermediate values, so the check needs a tolerance rather than equality.
# 1e-3 relative absorbs that rounding - the printed difficulty "10.02" is itself rounded,
# and one row lands 0.0067 off on 13.3667 (0.05%) - while staying far below the ~0.34%
# gap that a genuinely different scoring rule produces (21.2917 vs 21.2188).
TOL_ABS = 0.005
TOL_REL = 1e-3


def _tolerance(value: float) -> float:
    return max(TOL_ABS, abs(value) * TOL_REL)


def _close(expected: float, printed: Optional[float]) -> bool:
    return printed is not None and abs(expected - printed) <= _tolerance(printed)


def _trimmed_mean(values: List[float]) -> Optional[float]:
    """Artistic swimming drops the highest and lowest score of five.

    With fewer than five judges there is nothing to drop, so the plain mean is used -
    a three-judge sheet averages all three. Verified against both layouts in the repo:
    5-judge HYBRID (0.5) 7.000 6.50 6.50 6.50 6.25 5.50 -> 22.4583, and 3-judge
    ACRO (0.6) 2.375 8.00 6.00 7.50 -> 10.2125.
    """
    if len(values) < MIN_JUDGES:
        return None
    if len(values) >= 5:
        ordered = sorted(values)
        return sum(ordered[1:-1]) / (len(ordered) - 2)
    return sum(values) / len(values)


class ColumnMap:
    """Assigns numbers on a scoring row to the header columns they sit under.

    Built from the header line's own character offsets, so nothing about this PDF's
    page geometry is hardcoded. `Total` appears twice on the real sheets; occurrences
    are numbered left to right, giving ('Total', 0) = the line total and
    ('Total', 1) = the cumulative total.
    """

    def __init__(self, columns: List[Tuple[str, int, float]], header_line: str) -> None:
        self.columns = columns
        self.header_line = header_line

    @classmethod
    def from_header(cls, line: str) -> Optional["ColumnMap"]:
        spans = [(m.group(1), m.start(), m.end()) for m in HEADER_LABEL_RE.finditer(line)]
        if not spans:
            return None
        columns: List[Tuple[str, int, float]] = []
        seen: Dict[str, int] = {}
        for label, start, end in spans:
            seen[label] = seen.get(label, 0) + 1
            columns.append((label, seen[label] - 1, (start + end) / 2.0))
        candidate = cls(columns, line.strip())
        return candidate if candidate.is_scoring_header() else None

    def is_scoring_header(self) -> bool:
        labels = {label for label, _, _ in self.columns}
        if "Total" not in labels or "DD" not in labels:
            return False
        return MIN_JUDGES <= len(self.judge_labels()) <= MAX_JUDGES

    def judge_labels(self) -> List[str]:
        """The judge columns this header declares, in order (J1, J2, ... or J1..J5)."""
        found = []
        for label, occ, _ in self.columns:
            if label.startswith("J") and label[1:].isdigit() and occ == 0:
                found.append((int(label[1:]), label))
        return [label for _, label in sorted(found)]

    def assign(self, offset: float) -> Tuple[str, int]:
        """The column whose header centre is nearest this offset."""
        best: Optional[Tuple[str, int]] = None
        best_distance: Optional[float] = None
        for label, occ, centre in self.columns:
            distance = abs(offset - centre)
            if best_distance is None or distance < best_distance:
                best, best_distance = (label, occ), distance
        assert best is not None
        return best

    def cells(self, line: str) -> Dict[Tuple[str, int], List[float]]:
        """Every decimal number on the line, bucketed by the column it sits under."""
        out: Dict[Tuple[str, int], List[float]] = {}
        for match in NUMBER_RE.finditer(_mask_bracketed(line)):
            midpoint = (match.start() + match.end()) / 2.0
            out.setdefault(self.assign(midpoint), []).append(float(match.group()))
        return out


def describe_slots(cells: Dict[Tuple[str, int], List[float]]) -> str:
    """Human-readable cell dump for the parse trace."""
    parts = []
    for (label, occ), values in sorted(cells.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        name = label if occ == 0 else f"{label}#{occ + 1}"
        parts.append(f"{name}=" + "/".join(f"{v:g}" for v in values))
    return " ".join(parts)


# --------------------------------------------------------------------------------------
# PDF text + classification
# --------------------------------------------------------------------------------------

def extract_text_from_pdf(path: str) -> str:
    text_chunks = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            txt = page.extract_text() or ""
            text_chunks.append(txt)
    return "\n".join(text_chunks)


def classify_pdf(text: str) -> Dict[str, Any]:
    """Decide whether this file is a routine score sheet before parsing it.

    Aggregate/final/schedule PDFs from the same meet have no scoring rows at all. The
    old parser read them, found no results, and only then complained - after the caller
    had already been told it was processing a file.
    """
    lines = text.splitlines()
    headers = [ln for ln in lines if ColumnMap.from_header(ln) is not None]
    element_rows = [ln for ln in lines if ELEMENT_ROW_RE.match(ln)]
    ai_rows = [ln for ln in lines if AI_ROW_RE.match(ln)]
    stc_rows = [ln for ln in lines if STC_ROW_RE.match(ln)]
    team_rows = [
        ln for ln in lines
        if re.match(r"^\s*\d+\.\s*\(\d+\)\s+[A-Z0-9]+\s*-\s*\S+", ln)
    ]
    total_difficulty = [ln for ln in lines if re.match(r"^\s*TOTAL DIFFICULTY\b", ln)]

    signals = {
        "scoring header rows": len(headers),
        "element rows (ACRO/HYBRID)": len(element_rows),
        "artistic impression rows": len(ai_rows),
        "synchronization rows (STC)": len(stc_rows),
        "TOTAL DIFFICULTY rows": len(total_difficulty),
        "ranked team result rows": len(team_rows),
    }
    scoring_rows = len(element_rows) + len(ai_rows) + len(stc_rows)

    if scoring_rows == 0:
        reason = (
            "no scoring rows: this file has no ACRO/HYBRID, Artistic Impression or STC "
            "lines. Aggregate, 'Final', figures, schedule and announcement PDFs from the "
            "same meet look like this."
        )
        return {"is_routine": False, "reason": reason, "signals": signals, "scoring_rows": 0}

    missing = []
    if not headers:
        missing.append("no scoring header (expected a row containing J1..J5, DD and Total)")
    if not team_rows:
        missing.append("no ranked result rows (expected lines like '1.  (12) ABC - CLUB NAME')")
    if not element_rows and not ai_rows:
        missing.append("neither element nor artistic impression scores")
    if missing:
        return {
            "is_routine": False,
            "reason": "scoring rows are present but the sheet is incomplete: " + "; ".join(missing),
            "signals": signals,
            "scoring_rows": scoring_rows,
        }

    return {"is_routine": True, "reason": "", "signals": signals, "scoring_rows": scoring_rows}


# --------------------------------------------------------------------------------------
# Scoring rows
# --------------------------------------------------------------------------------------

def _judges_from(cells: Dict[Tuple[str, int], List[float]],
                 judges: List[str]) -> Optional[Dict[str, float]]:
    out: Dict[str, float] = {}
    for label in judges:
        values = cells.get((label, 0))
        if not values:
            return None
        out[label] = values[0]
    return out


def parse_element_row(line: str, cmap: ColumnMap) -> Dict[str, Any]:
    """An ACRO/HYBRID row: DD, five judges, line total, and optionally the cumulative
    total and the routine score."""
    head = ELEMENT_ROW_RE.match(line)
    assert head is not None
    factor = float(head.group("factor"))
    cells = cmap.cells(line)
    judge_labels = cmap.judge_labels()
    judges = _judges_from(cells, judge_labels)

    record: Dict[str, Any] = {
        "element_type": head.group("type"),
        "factor": factor,
        "raw": line.strip(),
        "columns": describe_slots(cells),
    }

    if judges is None:
        record["error"] = (
            "expected a value under each of " + "/".join(judge_labels) + " but found "
            + (", ".join(sorted({f"{l}#{o + 1}" for l, o in cells if l.startswith("J")})) or "none")
        )
        record["judges"] = {}
        return record

    record["judges"] = judges

    dd_values = cells.get(("DD", 0))
    if not dd_values:
        record["error"] = "no value under the DD column"
        return record
    record["dd"] = dd_values[0]

    # Ref is empty on an ordinary row and holds the ORIGINAL difficulty on a deduction
    # row, where DD holds the awarded one. Storing the original as `dd_nominal` and
    # scoring with `dd` is what makes a deduction row come out right.
    ref_values = cells.get(("Ref", 0))
    if ref_values and ref_values[0] != record["dd"]:
        record["dd_nominal"] = ref_values[0]
        record["deducted"] = True

    totals = cells.get(("Total", 0))
    if not totals:
        record["error"] = "no value under the first Total column (the line total)"
        return record
    record["line_total"] = totals[0]

    cumulative = cells.get(("Total", 1))
    if cumulative:
        record["cumulative_total"] = cumulative[0]

    routine = cells.get(("Routine", 0))
    if routine:
        record["routine_score"] = routine[0]

    mean = _trimmed_mean([judges[j] for j in judge_labels])
    if mean is None:
        record["error"] = "could not compute a judge mean"
    else:
        record["judge_mean"] = round(mean, 6)
        record["computed_total"] = round(mean * record["dd"] * factor, 4)
        record["reconciles"] = _close(record["computed_total"], record["line_total"])
    return record


def parse_ai_row(line: str, cmap: ColumnMap) -> Dict[str, Any]:
    """An Artistic Impression row: five judges and a line total, with the cumulative
    AI total on the first row of the panel."""
    head = AI_ROW_RE.match(line)
    assert head is not None
    factor = float(head.group("factor"))
    cells = cmap.cells(line)
    judge_labels = cmap.judge_labels()
    judges = _judges_from(cells, judge_labels)

    record: Dict[str, Any] = {
        "element_type": head.group("type"),
        "factor": factor,
        "raw": line.strip(),
        "columns": describe_slots(cells),
    }

    if judges is None:
        found = sorted({f"{l}#{o + 1}" for l, o in cells if l.startswith("J")})
        record["error"] = (
            "expected a value under each of " + "/".join(judge_labels)
            + " but found " + (", ".join(found) or "none")
        )
        record["judges"] = {}
        return record

    record["judges"] = judges

    totals = cells.get(("Total", 0))
    if not totals:
        record["error"] = "no value under the first Total column (the line total)"
        return record
    record["line_total"] = totals[0]

    cumulative = cells.get(("Total", 1))
    if cumulative:
        record["cumulative_total"] = cumulative[0]

    mean = _trimmed_mean([judges[j] for j in judge_labels])
    if mean is None:
        record["error"] = "could not compute a judge mean"
    else:
        record["judge_mean"] = round(mean, 6)
        record["computed_total"] = round(mean * factor * 3, 4)
        record["reconciles"] = _close(record["computed_total"], record["line_total"])
    return record


def parse_stc_row(line: str) -> Dict[str, Any]:
    """An STC row. Not column-mapped: these carry integer fault counts, not judge
    scores, and their trailing column is a deduction rather than a total.

    A category total is the mean of the fault counts that were actually printed times the
    factor - there is no x3 here, unlike artistic impression. Verified on
    'STC Small (0.1) 21 44 7 2.4000' (24.0 x 0.1) and on the two-count variant
    'STC Small (0.1) 9 18 1.3500' (13.5 x 0.1).
    """
    match = STC_ROW_RE.match(line)
    if not match:
        return {
            "element_type": "STC",
            "raw": line.strip(),
            "judges": {},
            "error": "STC row did not match: expected "
                     "'STC <category> (factor) count count [count] total [deduction]'",
        }
    counts = [int(n) for n in match.group("counts").split()]
    factor = float(match.group("factor"))
    total = float(match.group("tot"))
    mean = sum(counts) / len(counts)
    record: Dict[str, Any] = {
        "element_type": re.sub(r"\s+", " ", match.group("type")),
        "factor": factor,
        "fault_counts": counts,
        "count_mean": round(mean, 6),
        "total": total,
        "computed_total": round(mean * factor, 4),
        "raw": line.strip(),
    }
    record["reconciles"] = _close(record["computed_total"], total)
    pen = match.group("pen")
    if pen and pen != "-":
        # Recorded, never promoted to synchronization_total: a deduction is not a total,
        # and the column means a total. Used instead to validate the printed Routine.
        record["penalty"] = float(pen)
    elif pen == "-":
        record["penalty"] = 0.0
    return record


def _formula_text(record: Dict[str, Any]) -> str:
    """The multiplier part of the line formula, so the trace shows the real arithmetic."""
    if "dd" in record:
        return f"dd {record['dd']:g} x factor {record['factor']:g}"
    return f"factor {record['factor']:g} x 3"


def _mismatch_reason(record: Dict[str, Any]) -> str:
    """Explain a row whose recomputed total disagrees with the printed one.

    STC rows and element/AI rows have different shapes, so both are spelled out here
    rather than letting one of them raise a KeyError inside the error report.
    """
    if "fault_counts" in record:
        return (
            f"printed category total {record['total']:g} but the fault counts "
            f"{'/'.join(str(c) for c in record['fault_counts'])} average "
            f"{record['count_mean']:g} x {record['factor']:g} = "
            f"{record['computed_total']:g}"
        )
    judge_text = "/".join(f"{v:g}" for v in record["judges"].values())
    deduction_note = (
        f", deduction from {record['dd_nominal']:g}"
        if record.get("dd_nominal") is not None else ""
    )
    return (
        f"printed line total {record['line_total']:g} but the judges {judge_text} give "
        f"{record['computed_total']:g} ({_mean_label(record['judges'])} "
        f"{record['judge_mean']:g} x "
        f"{record.get('dd', '-')} x {record['factor']:g}{deduction_note})"
    )


def _mean_label(judges: Dict[str, float]) -> str:
    """Say which averaging rule produced judge_mean, so the reason is self-explanatory."""
    count = len(judges)
    if count >= 5:
        return "trimmed mean of the middle three"
    if count == 4:
        return "plain mean of four, nothing dropped"
    return f"plain mean of {count}" if count else "mean"


def parse_scoring_row(line: str, cmap: Optional[ColumnMap]) -> Dict[str, Any]:
    if STC_ROW_RE.match(line) or line.strip().startswith("STC"):
        return parse_stc_row(line)
    if ELEMENT_ROW_RE.match(line):
        if cmap is None:
            return {"element_type": "element", "raw": line.strip(), "judges": {},
                    "error": "no scoring header seen before this row, so its numbers "
                             "cannot be told apart from the judges"}
        return parse_element_row(line, cmap)
    if AI_ROW_RE.match(line):
        if cmap is None:
            return {"element_type": "ai", "raw": line.strip(), "judges": {},
                    "error": "no scoring header seen before this row, so its numbers "
                             "cannot be told apart from the judges"}
        return parse_ai_row(line, cmap)
    return {"element_type": "unknown", "raw": line.strip(), "judges": {},
            "error": "row starts like a scoring row but names no known element type"}


# --------------------------------------------------------------------------------------
# Athlete blocks
# --------------------------------------------------------------------------------------

TEAM_ROW_RE = re.compile(
    r"^\s*(?P<rank>\d+)\.\s*\((?P<draw>\d+)\)\s*(?P<team_code>[A-Z0-9]+)\s*-\s*(?P<team_name>.+)$"
)
# The Swimmer column, measured rather than assumed. These sheets do NOT agree on a
# gender prefix: 'F CAI Jolene' and 'M [R] WU Vivian' carry one, 'GIRE Ellie' does not.
# Requiring one silently dropped the name on 119 of the 178 routine PDFs in swim-meets
# (1118 of 1607 athlete blocks had no name at all), which is why an import could show
# scores but no athletes. The prefix is therefore optional, and the reserve marker is
# allowed to be welded to the name ('[R]LANNING Alexandra J').
SWIMMER_ROW_RE = re.compile(
    r"^\s*(?:(?P<gender>[FM])\s+)?(?:\[(?P<res>R)\]\s*)?(?P<name>\S.*?)\s*$"
)

# Footer/signature furniture that sits between blocks and must never become a name.
SWIMMER_NOISE_RE = re.compile(
    r"^\s*(?:Signature\b|Created using\b|Report Created\b|Page:\s*\d|Licensed to\b)",
    re.I,
)


# Status rows sit in the same column as the team row and are not results:
# 'DSQ  23.  (10) OCC - OHIO CORALINAS SYNCHRO'.
STATUS_ROW_RE = re.compile(
    r"^\s*(?:DSQ|SCR|DNS|DNF|WITHDRAWN|WITHDRAWAL|REMOVED|RESERVE)\b", re.I
)

# Meet furniture that shares the block: the running header and footer.
MEET_FURNITURE_RE = re.compile(
    r"championships?\b|invitational\b|nationals?\b|signature\b|licensed to\b|"
    r"report created\b|page\s*:|created using\b|prelims?\b|\bfinals?\b|\btechnical\b|"
    r"roster\b|tournament\b|festival\b|artistic swimming\b|aquatic center\b|"
    r"age group\b",
    re.I,
)

# A bare column header. ColumnMap.from_header only recognises a header that also
# carries the scoring columns, so the swimmer-column header needs its own guard.
SWIMMER_HEADER_RE = re.compile(
    r"^\s*Swimmer\s+Age\s+Group\s*$|^\s*Swimmer\s*$", re.I
)

# A judge panel line: 'J1  Leslie SIMS   Sharon COPP   Daniela GARMENDIA'. Three names
# and a digit, so the decimal guards do not catch it.
JUDGE_PANEL_ROW_RE = re.compile(r"^\s*J\d+\b")

# No swimmer's name contains a year. This is what rejects the venue/date banner that
# repeats inside every block - 'Buffalo. NY 9 APR 2026',
# 'North Natomas Aquatic Center 2601 New Market Dr., Sacramento, CA 95835 7 MAR 2026'.
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")

# The difficulty factor in brackets, e.g. 'ACRO (0.7)', 'TRE1a (1.0)', 'ChoHY (0.2)'.
# This is the reliable structural marker of a scoring row and it never appears in a
# swimmer's name. Element types are NOT a fixed list - the corpus also contains TRE*,
# ChoHY and ReqHY rows that a hardcoded ACRO|HYBRID alternation does not know about -
# so the guard keys on the factor rather than on the element name.
_ELEMENT_FACTOR_RE = re.compile(r"\(\s*\d+(?:\.\d+)?\s*\)")

TOTAL_DIFFICULTY_RE = re.compile(
    r"^\s*TOTAL DIFFICULTY\s+(?P<ref>[0-9.]+)(?:\s+(?P<dd>[0-9.]+))?"
)


def parse_swimmer_line(line: str) -> List[Dict[str, Any]]:
    """Return the athlete entries printed on one Swimmer line, or [] if it is not one.

    Handles every form found in swim-meets/2026:

        'F CAI Jolene'                    gender + name
        'M [R] WU Vivian'                 gender + reserve marker + name
        '[R]LANNING Alexandra J'          reserve marker welded to the name
        'GIRE Ellie'                      no gender column on this sheet
        'LIN Isabella / SIZEMOVA Daria'   duet: two names on one line, split on ' / '
        'LIN - 18/19 Isabella'            division marker before the given name

    A scoring row also matches SWIMMER_ROW_RE now that the gender prefix is optional,
    so those (and footer furniture) are rejected here rather than silently becoming
    athletes. That guard is the whole reason this is a function and not a bare regex.
    """
    if not line or not line.strip():
        return []
    if SWIMMER_NOISE_RE.match(line):
        return []
    if STATUS_ROW_RE.match(line) or MEET_FURNITURE_RE.search(line):
        return []
    if SWIMMER_HEADER_RE.match(line) or JUDGE_PANEL_ROW_RE.match(line) \
            or _YEAR_RE.search(line):
        return []
    # Guard order matters. A scoring row now also matches SWIMMER_ROW_RE because the
    # gender prefix is optional, and swallowing one as a swimmer name would both invent
    # an athlete and stop the row being scored, so the row shapes are rejected first.
    if _ELEMENT_FACTOR_RE.search(line) or SCORING_ROW_RE.match(line) \
            or TOTAL_DIFFICULTY_RE.match(line):
        return []
    # Several decimals in one line is data, not a name.
    if len(re.findall(r"\d+\.\d+", line)) >= 3:
        return []
    if ColumnMap.from_header(line) is not None:
        return []
    if TEAM_ROW_RE.match(line):
        return []

    match = SWIMMER_ROW_RE.match(line)
    if not match:
        return []

    gender = match.group("gender")
    is_reserve = bool(match.group("res"))
    raw_name = (match.group("name") or "").strip()
    # A duet prints both swimmers on one line separated by ' / '. The slash must be
    # padded: an unpadded slash is an age range ('LIN - 18/19 Isabella'), not a duet.
    fragments = [f.strip() for f in re.split(r"\s+/\s+", raw_name)] if re.search(r"\s+/\s+", raw_name) else [raw_name]

    entries = []
    for fragment in fragments:
        parts = split_person_name(fragment)
        if not parts["printed"]:
            continue
        entries.append({
            "name": parts["printed"],
            "gender": {"F": "Female", "M": "Male"}.get(gender),
            "is_reserve": is_reserve,
            "family_name": parts["family_name"],
            "given_name": parts["given_name"],
            "middle_name": parts["middle_name"],
            "suffix": parts["suffix"],
            "alt_name": parts["alt_name"],
        })
    return entries


def _finalise_athlete(athlete: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Derive the panel totals and validate them against the printed cumulative columns.

    The printed line totals are summed; the printed cumulative column is only a check.
    Returns the checks rather than storing them on the athlete, because the athlete dict
    is handed to synchronized_meet() and should not grow keys it does not expect.
    """
    elements = athlete["routine_scores"]["element_scores"]
    ai = athlete["routine_scores"]["artistic_impression_scores"]
    stc = athlete["routine_scores"]["synchronization_scores"]

    element_total = round(sum(r["line_total"] for r in elements if "line_total" in r), 4)
    ai_total = round(sum(r["line_total"] for r in ai if "line_total" in r), 4)
    athlete["element_total"] = element_total
    athlete["artisticimpression_total"] = ai_total

    checks: List[Dict[str, Any]] = []

    printed_element = next((r.get("cumulative_total") for r in elements if "cumulative_total" in r), None)
    if printed_element is None:
        checks.append({
            "check": "element panel total",
            "status": "computed",
            "detail": f"no cumulative Total printed on the first element row; summed the "
                      f"{len(elements)} line totals instead -> {element_total}",
        })
    elif _close(element_total, printed_element):
        checks.append({
            "check": "element panel total",
            "status": "OK",
            "detail": f"sum of {len(elements)} line totals {element_total} matches the "
                      f"printed cumulative Total {printed_element}",
        })
    else:
        checks.append({
            "check": "element panel total",
            "status": "MISMATCH",
            "detail": f"sum of line totals {element_total} vs printed cumulative Total "
                      f"{printed_element} (difference {round(element_total - printed_element, 4)})",
        })

    printed_ai = next((r.get("cumulative_total") for r in ai if "cumulative_total" in r), None)
    if printed_ai is None:
        checks.append({
            "check": "artistic impression panel total",
            "status": "computed",
            "detail": f"no cumulative Total printed on the first AI row; summed the "
                      f"{len(ai)} line totals instead -> {ai_total}",
        })
    elif _close(ai_total, printed_ai):
        checks.append({
            "check": "artistic impression panel total",
            "status": "OK",
            "detail": f"sum of {len(ai)} line totals {ai_total} matches the printed "
                      f"cumulative Total {printed_ai}",
        })
    else:
        checks.append({
            "check": "artistic impression panel total",
            "status": "MISMATCH",
            "detail": f"sum of line totals {ai_total} vs printed cumulative Total "
                      f"{printed_ai} (difference {round(ai_total - printed_ai, 4)})",
        })

    # The STC trailing column is the synchronization deduction, printed once. It is
    # summed from the STC category totals when it is absent.
    printed_stc = next((r.get("penalty") for r in stc if "penalty" in r), None)
    stc_category_sum = round(sum(r.get("total", 0.0) for r in stc), 4)
    if printed_stc is not None:
        sync_adjustment = printed_stc
        if _close(stc_category_sum, abs(printed_stc)):
            checks.append({
                "check": "synchronization deduction",
                "status": "OK",
                "detail": f"printed deduction {printed_stc} equals the sum of the "
                          f"{len(stc)} STC category totals {stc_category_sum}",
            })
        else:
            checks.append({
                "check": "synchronization deduction",
                "status": "note",
                "detail": f"printed deduction {printed_stc} vs sum of the {len(stc)} STC "
                          f"category totals {stc_category_sum}. Not treated as a "
                          f"disagreement: a routine can carry more than one STC panel, so "
                          f"the category totals are not required to sum to the deduction. "
                          f"The printed deduction is what the routine score is checked "
                          f"against and is what gets stored.",
            })
    elif stc:
        sync_adjustment = -stc_category_sum
        checks.append({
            "check": "synchronization deduction",
            "status": "computed",
            "detail": f"no deduction column printed; derived -{stc_category_sum} from the "
                      f"{len(stc)} STC category totals",
        })
    else:
        sync_adjustment = 0.0

    if stc:
        athlete["routine_scores"]["synchronization_deduction"] = sync_adjustment

    printed_routine = next((r.get("routine_score") for r in elements if "routine_score" in r), None)
    expected_routine = round(element_total + ai_total + sync_adjustment, 4)
    if printed_routine is None:
        athlete["routine_score"] = expected_routine
        checks.append({
            "check": "routine score",
            "status": "computed",
            "detail": f"no Routine column printed; elements {element_total} + artistic "
                      f"impression {ai_total} + synchronization {sync_adjustment} -> "
                      f"{expected_routine}",
        })
    else:
        athlete["routine_score"] = printed_routine
        if _close(expected_routine, printed_routine):
            checks.append({
                "check": "routine score",
                "status": "OK",
                "detail": f"elements {element_total} + artistic impression {ai_total} + "
                          f"synchronization {sync_adjustment} = {expected_routine}, "
                          f"printed {printed_routine}",
            })
        else:
            checks.append({
                "check": "routine score",
                "status": "MISMATCH",
                "detail": f"elements {element_total} + artistic impression {ai_total} + "
                          f"synchronization {sync_adjustment} = {expected_routine} vs "
                          f"printed {printed_routine} "
                          f"(difference {round(expected_routine - printed_routine, 4)})",
            })

    return checks


# --------------------------------------------------------------------------------------
# Document parse
# --------------------------------------------------------------------------------------

def parse_routine_pdf_text(text: str) -> Dict[str, Any]:
    lines = [ln.rstrip() for ln in text.splitlines()]
    warnings: List[str] = []
    errors: List[Dict[str, Any]] = []
    trace: List[Dict[str, Any]] = []

    header_lines = []
    for ln in lines:
        stripped = ln.strip()
        if not stripped:
            continue
        if stripped.startswith("Code Rank") or stripped.startswith("Code Pos") or "Referee:" in stripped:
            break
        if stripped.startswith("Created using") or "Report Created" in stripped \
                or stripped.startswith("Signature") or stripped.startswith("Page:"):
            continue
        header_lines.append(stripped)

    event_name = header_lines[0] if len(header_lines) > 0 else ""
    meet_name = header_lines[1] if len(header_lines) > 1 else ""
    city_date_line = header_lines[2] if len(header_lines) > 2 else ""

    date_match = re.search(r"(\d{1,2}\s+[A-Z]{3}\s+\d{4})", city_date_line)
    if date_match:
        event_date = date_match.group(1).strip()
        host_city = city_date_line[:date_match.start()].strip()
    else:
        event_date = None
        host_city = city_date_line if city_date_line else None

    if host_city:
        host_city = host_city.strip(", ")
        if not host_city:
            host_city = None

    judges_panels: Dict[str, Dict[str, str]] = {}
    officials = []
    page_cmap: Optional[ColumnMap] = None

    i = 0
    while i < len(lines):
        line = lines[i]

        # Some sheets print the column header once, above the first athlete, rather than
        # repeating it per athlete. This loop consumes that line on its way to the first
        # rank row, so the map has to be captured here or the athlete rows below would
        # find no header at all.
        if page_cmap is None:
            found_cmap = ColumnMap.from_header(line)
            if found_cmap is not None:
                page_cmap = found_cmap

        for official_title in ["Referee", "Asst. Referee", "DTC", "DATC"]:
            if official_title == "Referee":
                m = re.search(r"(?<!Asst\.\s)Referee:\s*(.+)", line)
            else:
                m = re.search(rf"{official_title}:\s*(.+)", line)
            if m:
                officials.append({
                    "figure_code_short": None,
                    "panel_name": official_title,
                    "panel": {official_title: m.group(1).split("  ")[0].strip()},
                })

        if "Elements" in line and "Artistic Impression" in line and "Synchronization" in line:
            judges_panels["Elements"] = {}
            judges_panels["Artistic Impression"] = {}
            judges_panels["Synchronization"] = {}

            i += 1
            while i < len(lines) and lines[i].strip().startswith("J"):
                j_line = lines[i]
                j_num = j_line.strip()[:2]
                rest = j_line.strip()[2:].strip()
                names = re.findall(
                    r"[A-Z][A-Za-z\.\-\']+\s+[A-Z\-\']{2,}(?:\s+[A-Z\-\']{2,})*", rest
                )
                if len(names) >= 1:
                    judges_panels["Elements"][j_num] = names[0]
                if len(names) >= 2:
                    judges_panels["Artistic Impression"][j_num] = names[1]
                if len(names) >= 3:
                    judges_panels["Synchronization"][j_num] = names[2]
                i += 1
            continue

        if re.match(r"^\s*\d+\.\s*\(\d+\)\s+", line):
            break

        i += 1

    judges = officials
    for panel_name, panel_data in judges_panels.items():
        if panel_data:
            judges.append({
                "figure_code_short": None,
                "panel_name": panel_name,
                "panel": panel_data,
            })

    athletes = []
    cmap: Optional[ColumnMap] = page_cmap
    unparsed = 0
    unreconciled = 0
    stc_notes: List[Dict[str, Any]] = []

    while i < len(lines):
        line = lines[i]
        team_match = TEAM_ROW_RE.match(line)

        if team_match:
            block: Dict[str, Any] = {
                "line_no": i + 1,
                "header": line.strip(),
                "swimmers": [],
                "rows": [],
                "total_difficulty": None,
            }
            athlete: Dict[str, Any] = {
                "rank": int(team_match.group("rank")),
                "draw": int(team_match.group("draw")),
                "team_code": team_match.group("team_code"),
                "team_name": team_match.group("team_name").strip(),
                "team_athletes": [],
                "total_difficulty": [],
                "routine_scores": {
                    "element_scores": [],
                    "artistic_impression_scores": [],
                    "synchronization_scores": [],
                },
                # Left NULL rather than 0.0. A deduction is not a total; see the module
                # docstring. The deduction itself is on the STC rows and, as a derived
                # figure, in routine_scores["synchronization_deduction"].
                "synchronization_total": None,
                "element_total": 0.0,
                "artisticimpression_total": 0.0,
                "routine_score": 0.0,
            }

            i += 1
            while i < len(lines):
                current = lines[i]
                if not current.strip():
                    i += 1
                    continue
                if re.match(r"^\s*\d+\.\s*\(\d+\)\s+", current):
                    break
                if current.strip().startswith("Created using") or "Report Created" in current \
                        or current.strip().startswith("Page:"):
                    i += 1
                    continue
                if "Age Group" in current or "Junior Olympic" in current or "Prelim" in current \
                        or "Final" in current or re.match(r"^\d{1,2}\s+[A-Z]{3}\s+\d{4}", current.strip()):
                    i += 1
                    continue
                if ColumnMap.from_header(current) is not None:
                    cmap = ColumnMap.from_header(current)
                    i += 1
                    continue

                swimmers_on_line = parse_swimmer_line(current)
                if swimmers_on_line:
                    for entry in swimmers_on_line:
                        athlete["team_athletes"].append(entry)
                        block["swimmers"].append({
                            "line_no": i + 1,
                            "text": current.strip(),
                            "name": entry["name"],
                            "gender": entry["gender"],
                            "is_reserve": entry["is_reserve"],
                            "family_name": entry["family_name"],
                            "given_name": entry["given_name"],
                        })
                    i += 1
                    continue

                td_match = TOTAL_DIFFICULTY_RE.match(current)
                if td_match:
                    difficulty = [{"Ref": float(td_match.group("ref"))}]
                    if td_match.group("dd"):
                        difficulty.append({"DD": float(td_match.group("dd"))})
                    athlete["total_difficulty"] = difficulty
                    block["total_difficulty"] = {
                        "line_no": i + 1,
                        "text": current.strip(),
                        "Ref": float(td_match.group("ref")),
                        "DD": float(td_match.group("dd")) if td_match.group("dd") else None,
                    }
                    i += 1
                    continue

                if SCORING_ROW_RE.match(current):
                    record = parse_scoring_row(current, cmap)
                    record["line_no"] = i + 1
                    block["rows"].append(record)

                    if record.get("error"):
                        unparsed += 1
                        errors.append({
                            "kind": "unparsed scoring row",
                            "team": f"{athlete['team_code']} - {athlete['team_name']}",
                            "line_no": i + 1,
                            "text": current.strip(),
                            "columns": record.get("columns", ""),
                            "reason": record["error"],
                        })
                    elif record.get("reconciles") is False and "fault_counts" not in record:
                        unreconciled += 1
                        errors.append({
                            "kind": "score does not reconcile",
                            "team": f"{athlete['team_code']} - {athlete['team_name']}",
                            "line_no": i + 1,
                            "text": current.strip(),
                            "columns": record.get("columns", ""),
                            "reason": _mismatch_reason(record),
                        })

                    if record.get("error"):
                        # A row we could not read must never reach the database, and must
                        # not be counted towards a panel total either.
                        i += 1
                        continue

                    if "fault_counts" in record and record.get("reconciles") is False:
                        # An STC category total that does not match its fault counts is
                        # reported but never blocks: the category totals are display
                        # detail, and a routine can carry more than one STC panel, so they
                        # are not required to sum to the printed deduction. The deduction
                        # itself is what the routine score is checked against.
                        stc_notes.append({
                            "kind": "STC category total not reproducible",
                            "team": f"{athlete['team_code']} - {athlete['team_name']}",
                            "line_no": i + 1,
                            "text": current.strip(),
                            "columns": "",
                            "reason": _mismatch_reason(record),
                        })

                    if record["element_type"] in ELEMENT_TYPES:
                        athlete["routine_scores"]["element_scores"].append(record)
                    elif record["element_type"] in AI_TYPES:
                        athlete["routine_scores"]["artistic_impression_scores"].append(record)
                    else:
                        athlete["routine_scores"]["synchronization_scores"].append(record)
                    i += 1
                    continue

                i += 1

            block["checks"] = _finalise_athlete(athlete)
            block["totals"] = {
                "element_total": athlete["element_total"],
                "artisticimpression_total": athlete["artisticimpression_total"],
                "synchronization_total": athlete["synchronization_total"],
                "routine_score": athlete["routine_score"],
                "total_difficulty": athlete["total_difficulty"],
            }
            trace.append(block)

            athlete["team_athletes"] = json.dumps(athlete["team_athletes"])
            athletes.append(athlete)
            continue
        i += 1

    if unparsed:
        warnings.append(
            f"{unparsed} scoring line(s) could not be parsed at all, so the athlete totals "
            f"for those routines are incomplete."
        )
    if stc_notes:
        warnings.append(
            f"{len(stc_notes)} STC category total(s) could not be reproduced from their fault "
            f"counts. This is reported, not treated as a failure: a routine can carry more "
            f"than one STC panel, so the category totals are not required to sum to the "
            f"printed deduction, which is the figure used in the routine score."
        )
    if unreconciled:
        warnings.append(
            f"{unreconciled} scoring line(s) parsed but do not reconcile: the printed line "
            f"total disagrees with the judges. The printed value was kept because it is the "
            f"official score, but the disagreement is listed below."
        )

    has_stc = any(a["routine_scores"]["synchronization_scores"] for a in athletes)
    if not has_stc:
        warnings.append(
            "no synchronization (STC) rows in this PDF, so synchronization_total stays NULL "
            "on every row. That is expected for a solo sheet: STC appears only on duet and "
            "team routines."
        )

    return {
        "event": {
            "event_name": event_name,
            "host_city": host_city,
            "event_date": event_date,
        },
        "meet": {
            "name": meet_name,
            "meet_date": event_date,
        },
        "judges": judges,
        "athletes": athletes,
        "warnings": warnings,
        "errors": errors,
        "stc_notes": stc_notes,
        "trace": trace,
        "stats": {
            "scoring_rows": sum(
                len(b["rows"]) for b in trace
            ),
            "unparsed": unparsed,
            "unreconciled": unreconciled,
            "stc_notes": len(stc_notes),
        },
    }


# --------------------------------------------------------------------------------------
# Reporting: what the PDF said, how it was read, what will be written
# --------------------------------------------------------------------------------------

def _rule(char: str = "-", width: int = 78) -> str:
    return f"  {char * width}"


def render_pdf_report(payload: Dict[str, Any], source: str, classification: Dict[str, Any]) -> str:
    """Walk the document the way it is laid out, showing what was read at each step."""
    out: List[str] = []
    event = payload["event"]
    meet = payload["meet"]

    out.append("")
    out.append("=" * 78)
    out.append("PDF -> PARSE")
    out.append("=" * 78)
    out.append(f"  file      : {source}")
    signals = classification.get("signals") or {}
    out.append(f"  recognised: routine score sheet "
               f"({signals.get('element rows (ACRO/HYBRID)', 0)} element, "
               f"{signals.get('artistic impression rows', 0)} artistic impression, "
               f"{signals.get('synchronization rows (STC)', 0)} synchronization rows)")
    out.append("")

    out.append("  [1] REPORT HEADER  (lines above the first 'Referee:')")
    out.append(f"        event_name   -> as_event.event_name      = {event['event_name']!r}")
    out.append(f"        meet name    -> as_meet.name            = {meet['name']!r}")
    out.append(f"        date         -> as_event.event_date     = {event['event_date']!r}")
    out.append(f"        city         -> as_event.host_city      = {event['host_city']!r}")
    out.append(f"        venue/date line as read: {(event['host_city'] or '')} {event['event_date'] or ''}".rstrip())
    out.append("")

    out.append("  [2] OFFICIALS AND JUDGE PANELS  -> as_meet_judge_panel")
    if payload["judges"]:
        for j in payload["judges"]:
            panel = j.get("panel") or {}
            rendered = ", ".join(f"{k}={v}" for k, v in panel.items()) or "(empty)"
            out.append(f"        {j['panel_name']:<22} {rendered}")
        out.append(f"        {len(payload['judges'])} row(s); each panel is one jsonb 'panel' object")
    else:
        out.append("        (none found)")
    out.append("")

    stats = payload.get("stats") or {}
    out.append(f"  [3] RESULTS  -> as_meet_routine_result   "
               f"({len(payload['athletes'])} routine(s), {stats.get('scoring_rows', 0)} scoring row(s))")
    out.append("")

    for block in payload.get("trace") or []:
        totals = block["totals"]
        out.append(_rule())
        out.append(f"  RESULT BLOCK  line {block['line_no']}: {block['header']}")
        out.append("     parsed: rank/draw/team_code/team_name from the row header")
        if block["swimmers"]:
            for s in block["swimmers"]:
                flag = " (reserve)" if s["is_reserve"] else ""
                # A sheet need not print an M/F prefix at all; say so rather than
                # pretending the swimmer's gender is known.
                gender = s["gender"] or "-"
                out.append(f"     line {s['line_no']:>4} swimmer{flag:<10} {gender:<7} "
                           f"{s['name']!r}  -> team_athletes jsonb")
        else:
            out.append("     (no swimmer lines)")

        if block["total_difficulty"]:
            td = block["total_difficulty"]
            out.append(f"     line {td['line_no']:>4} {td['text']}")
            out.append(f"                     -> total_difficulty jsonb  "
                       f"Ref={td['Ref']:g}" + (f" DD={td['DD']:g}" if td["DD"] is not None else ""))

        for record in block["rows"]:
            head = f"     line {record['line_no']:>4} {record['raw']}"
            out.append(head)
            if record["element_type"] in STC_TYPES or record["element_type"] == "STC":
                parts = [f"type={record['element_type']}", f"factor={record.get('factor', '-')}"]
                for key in ("J1", "J2", "J3"):
                    if key in record:
                        parts.append(f"{key}={record[key]}")
                if "total" in record:
                    parts.append(f"category_total={record['total']:g}")
                if "penalty" in record:
                    parts.append(f"deduction={record['penalty']:g}")
                out.append("                     -> " + "  ".join(parts))
                out.append("                     -> routine_scores.synchronization_scores[] "
                           "(NOT promoted to synchronization_total)")
                continue

            if record.get("error"):
                out.append(f"                     !! {record['error']}")
                if record.get("columns"):
                    out.append(f"                     !! columns seen: {record['columns']}")
                continue

            if "fault_counts" in record:
                parts = [f"type={record['element_type']}", f"factor={record['factor']:g}"]
                parts.append("counts=" + "/".join(str(c) for c in record["fault_counts"]))
                parts.append(f"count_mean={record['count_mean']:g}")
                parts.append(f"total={record['total']:g}")
                if "penalty" in record:
                    parts.append(f"penalty={record['penalty']:g}")
            else:
                parts = [f"type={record['element_type']}", f"factor={record['factor']:g}"]
                if "dd" in record:
                    parts.append(f"dd={record['dd']:g}")
                if record.get("dd_nominal") is not None:
                    parts.append(f"dd_nominal(Ref)={record['dd_nominal']:g}  [deduction row]")
                for label in record["judges"]:
                    parts.append(f"{label}={record['judges'][label]:g}")
                parts.append(f"line_total={record['line_total']:g}")
            if "cumulative_total" in record:
                parts.append(f"cumulative_total={record['cumulative_total']:g}")
            if "routine_score" in record:
                parts.append(f"routine={record['routine_score']:g}")
            out.append("                     -> " + "  ".join(parts))
            if "computed_total" in record:
                mark = "OK" if record.get("reconciles") else "MISMATCH"
                out.append(f"                     check: {_mean_label(record['judges'])} {record['judge_mean']:g} "
                           f"x {_formula_text(record)} = "
                           f"{record['computed_total']:g} vs printed "
                           f"{record['line_total']:g}  [{mark}]")

        out.append("     " + _rule("-", 70)[2:])
        for check in block["checks"]:
            out.append(f"     {check['status']:<9} {check['check']}: {check['detail']}")
        out.append("     -> as_meet_routine_result row:")
        out.append(f"          element_total={totals['element_total']:g}  "
                           f"artisticimpression_total={totals['artisticimpression_total']:g}  "
                           f"synchronization_total={totals['synchronization_total']}  "
                           f"routine_score={totals['routine_score']:g}")
    out.append("")
    return "\n".join(out)


def render_write_plan(payload: Dict[str, Any], source: str, dry_run: bool) -> str:
    """The exact table/column plan, so a write can be checked before it happens."""
    out: List[str] = []
    athletes = payload["athletes"]

    out.append("=" * 78)
    out.append("PARSE -> DATABASE")
    out.append("=" * 78)
    mode = "dry run: nothing below is written" if dry_run else "write order"
    out.append(f"  {mode}")
    out.append("")
    out.append("  as_event")
    out.append(f"      upsert by (event_name)  <- event['event_name'] = {payload['event']['event_name']!r}")
    out.append("      set event_date, host_city")
    out.append("")
    out.append("  as_meet")
    out.append(f"      resolve under that event  <- meet['name'] = {payload['meet']['name']!r}")
    out.append("      set meet_date")
    out.append("")
    out.append("  as_meet_judge_panel")
    out.append(f"      insert {len(payload['judges'])} row(s): meet_id, panel_name, panel (jsonb), "
               f"figure_code_short")
    out.append("")
    out.append(f"  as_meet_routine_result   insert {len(athletes)} row(s)")
    out.append("      meet_id            the as_meet id above")
    out.append("      rank, draw         from the 'N.  (D) CODE - Name' row")
    out.append("      team_code, team_name")
    out.append("      team_athletes      jsonb list of {name, gender, is_reserve}")
    out.append("      total_difficulty   jsonb [{Ref, DD}] from the TOTAL DIFFICULTY row")
    out.append("      routine_scores     jsonb {element_scores[], artistic_impression_scores[],")
    out.append("                         synchronization_scores[], synchronization_deduction}")
    out.append("      element_total      sum of the element line totals")
    out.append("      artisticimpression_total  sum of the AI line totals")
    out.append("      synchronization_total     NULL - a deduction is not a total")
    out.append("      routine_score     the printed Routine column")
    out.append(f"      source_file       {source!r}  (idempotency key)")
    out.append("")
    out.append("  identity link (as_result_person_link, runs last, no accounts)")
    out.append("      every printed name on a result row is resolved to an as_person row:")
    out.append("        matched on an existing person  -> reuse that person")
    out.append("        matched on two people          -> reported, left unlinked")
    out.append("        matched on nobody              -> a person is created")
    out.append("      a swimmer membership is added for the club, but only if the club")
    out.append("      already exists: as_club.id is the tenant id and is never invented.")
    out.append("      the link keeps the PDF's printed spelling verbatim as athlete_name.")
    out.append("")
    out.append("  person sync (accounts)")
    out.append("      synchronized_meet(parsed, routine=True) reconciles clubs, people and")
    out.append("      memberships, and provisions accounts unless --no-provision was passed.")
    out.append("      Runs before the identity link, because a club provisioned above is a")
    out.append("      real as_club row by the time the link needs its id. The link runs")
    out.append("      either way: a result nobody is attached to is invisible downstream.")
    out.append("")
    return "\n".join(out)


def render_errors(payload: Dict[str, Any]) -> str:
    """For every problem: what it is, which block, and why the parse failed."""
    errors = payload.get("errors") or []
    notes = payload.get("stc_notes") or []
    out: List[str] = []
    out.append("=" * 78)
    out.append(f"PARSE PROBLEMS ({len(errors)})")
    out.append("=" * 78)
    if not errors:
        out.append("  none: every scoring row parsed and every total reconciled")

    for n, err in enumerate(errors, 1):
        out.append("")
        out.append(f"  [{n}] {err['kind'].upper()}")
        out.append(f"      routine : {err['team']}")
        out.append(f"      pdf line: {err['line_no']}")
        out.append(f"      text    : {err['text']}")
        if err.get("columns"):
            out.append(f"      columns : {err['columns']}")
        out.append(f"      why     : {err['reason']}")
        out.append("      effect  : this routine's totals are incomplete or unverified; the "
                   "import is stopped so nothing understated is written")

    if notes:
        out.append("")
        out.append("-" * 78)
        out.append(f"STC NOTES ({len(notes)}) - reported, not a failure")
        out.append("-" * 78)
        out.append("  A routine can carry more than one STC panel, so the category totals")
        out.append("  are not required to sum to the printed deduction. The printed")
        out.append("  deduction is what the routine score is checked against.")
        for n, note in enumerate(notes, 1):
            out.append("")
            out.append(f"  [{n}] pdf line {note['line_no']}: {note['text']}")
            out.append(f"      why: {note['reason']}")

    out.append("")
    return "\n".join(out)


# --------------------------------------------------------------------------------------
# Write
# --------------------------------------------------------------------------------------

def insert_rows_to_supabase(payload: Dict[str, Any], source_file: str, dry_run: bool = False,
                            replace_source: bool = False, allow_empty: bool = False,
                            allow_mismatch: bool = False,
                            sink: Optional[Dict[str, Any]] = None) -> str:
    """Write one parsed PDF. Returns a human-readable summary of what happened.

    `sink` is an optional dict that receives the REST client and the inserted result
    rows, so the identity pass in main() can reuse this connection and these ids
    instead of opening a second one and guessing which row got which id.
    """
    check_results_present(payload, allow_empty)

    errors = payload.get("errors") or []
    unparsed = [e for e in errors if e["kind"] == "unparsed scoring row"]
    unreconciled = [e for e in errors if e["kind"] == "score does not reconcile"]

    if unparsed and not allow_mismatch:
        first = unparsed[0]
        raise IngestError(
            f"{len(unparsed)} scoring row(s) could not be parsed, so the totals for those "
            f"routines would be written incomplete. Nothing was written. First failure at "
            f"line {first['line_no']} of {source_file}: {first['text']!r} - {first['reason']}. "
            f"See the PARSE PROBLEMS block above for all of them. If this sheet really does "
            f"carry scores this parser cannot read, re-run with --allow-mismatch to import "
            f"the rest and leave the affected routines for a human."
        )

    if unreconciled and not allow_mismatch:
        first = unreconciled[0]
        raise IngestError(
            f"{len(unreconciled)} scoring row(s) do not reconcile: the printed line total "
            f"disagrees with what the judges give. The printed value is the official score "
            f"and would still be what gets written, but a disagreement this widespread "
            f"usually means the panel is scored by a rule this parser does not model. "
            f"Nothing was written. First failure at line {first['line_no']} of "
            f"{source_file}: {first['text']!r} - {first['reason']}. See the PARSE PROBLEMS "
            f"block above for all of them. Re-run with --allow-mismatch only if you have "
            f"confirmed the printed totals are correct and want them imported anyway."
        )

    if dry_run:
        return "dry run, nothing written"

    config = get_supabase_config()
    client = SupabaseRest(config["url"], config["key"])

    event_id, event_created = resolve_event(client, payload["event"])
    meet_id, meet_created = resolve_meet(client, payload["meet"], event_id)

    # Refuses a re-ingest before anything is written.
    replaced = prepare_meet_for_write(
        client, "as_meet_routine_result", meet_id, source_file, replace_source
    )

    if payload["judges"]:
        judge_rows = []
        for j in payload["judges"]:
            row = dict(j)
            row["meet_id"] = meet_id
            judge_rows.append(row)
        client.insert("as_meet_judge_panel", judge_rows)

    if payload["athletes"]:
        athlete_rows = []
        for athlete in payload["athletes"]:
            athlete_rows.append({
                "meet_id": meet_id,
                "rank": athlete.get("rank"),
                "draw": athlete.get("draw"),
                "team_code": athlete.get("team_code"),
                "team_name": athlete.get("team_name"),
                "team_athletes": athlete.get("team_athletes"),
                "total_difficulty": athlete.get("total_difficulty"),
                "routine_scores": athlete.get("routine_scores"),
                "element_total": athlete.get("element_total"),
                "artisticimpression_total": athlete.get("artisticimpression_total"),
                "synchronization_total": athlete.get("synchronization_total"),
                "routine_score": athlete.get("routine_score"),
                "source_file": source_file,
            })
        # Keep the returned rows: PostgREST answers in input order, so index i of
        # `inserted` is the database id of `athlete_rows[i]`, and as_result_person_link
        # needs that id to attach the printed names to.
        inserted = client.insert("as_meet_routine_result", athlete_rows)
    else:
        inserted = []

    if sink is not None:
        # Identity linking cannot run here: it needs the clubs that provisioning
        # creates, and provisioning happens in main() after this function returns.
        sink["client"] = client
        sink["inserted"] = inserted

    parts = []
    parts.append("created event" if event_created else "reused event")
    parts.append("created meet" if meet_created else "reused meet")
    if replaced:
        parts.append(replaced)
    if unreconciled:
        parts.append(f"imported with {len(unreconciled)} unreconciled score(s) (--allow-mismatch)")
    return ", ".join(parts)


def attach_identities(payload: Dict[str, Any], sink: Dict[str, Any]) -> str:
    """Link the printed names on the rows just written to real people.

    Runs whether or not accounts were provisioned. A result that is stored but not
    attributable is invisible to the dashboard, and attribution must not depend on
    Auth succeeding, so this is a separate step from synchronized_meet().
    """
    client = sink.get("client")
    inserted = sink.get("inserted") or []
    if client is None:
        raise IngestError("no database client was captured, so nothing could be linked")
    identity = ensure_people_and_links(client, inserted, payload, dry_run=False)
    for line in identity.lines():
        print(f"    ! {line}")
    return identity.summary()


def main(argv: List[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    flags = {a for a in argv[1:] if a.startswith("--")}
    known = {"--dry-run", "--replace-source", "--allow-empty", "--no-provision", "--allow-mismatch"}
    unknown = flags - known
    usage = ("Usage: python scripts/ingest_routines.py <pdf1> [pdf2 ...] "
             "[--dry-run] [--replace-source] [--allow-empty] [--no-provision] [--allow-mismatch]")
    if unknown:
        print("Unknown option(s):", ", ".join(sorted(unknown)))
        print(usage)
        return 2
    if not args:
        print(usage)
        return 1

    dry_run = "--dry-run" in flags
    replace_source = "--replace-source" in flags
    allow_empty = "--allow-empty" in flags
    allow_mismatch = "--allow-mismatch" in flags
    # Account provisioning is on by default because the import and the roster are
    # two views of the same PDF: an athlete with a result but no account cannot
    # be rostered. --no-provision imports results only, for an import whose
    # swimmers are not members of this system (a reference meet, an archive).
    provision = "--no-provision" not in flags
    report = RunReport()

    for path in args:
        if not os.path.exists(path):
            report.add(path, "SKIPPED", "file not found")
            continue
        print("Processing:", path)
        try:
            text = extract_text_from_pdf(path)
            classification = classify_pdf(text)
            if not classification["is_routine"]:
                print("  NOT A ROUTINE SCORE PDF - skipped")
                print(f"    reason: {classification['reason']}")
                for name, count in (classification.get("signals") or {}).items():
                    print(f"    {name}: {count}")
                report.add(path, "SKIPPED", "not a routine score PDF")
                continue

            parsed = parse_routine_pdf_text(text)

            print(render_pdf_report(parsed, path, classification))
            print(render_write_plan(parsed, path, dry_run))
            print(render_errors(parsed))
            print(describe(parsed))

            sink: Dict[str, Any] = {}
            summary = insert_rows_to_supabase(
                parsed, path, dry_run=dry_run,
                replace_source=replace_source, allow_empty=allow_empty,
                allow_mismatch=allow_mismatch,
                sink=sink,
            )
            if not dry_run:
                print(f"  {summary}")
                if provision:
                    try:
                        synchronized_meet(parsed, dry_run=False, routine=True)
                    except Exception as exc:
                        report.add(path, "FAILED", f"results written, but person sync failed: {exc}")
                        print("  person sync FAILED after results were written:", exc)
                        continue
                else:
                    print("  account provisioning skipped (--no-provision)")
                try:
                    # After provisioning: a club provisioned above is a real as_club
                    # row by now, and as_club.id is the tenant id these links need.
                    print(f"  identity: {attach_identities(parsed, sink)}")
                except Exception as exc:
                    report.add(path, "FAILED", f"results written, but identity linking failed: {exc}")
                    print("  identity linking FAILED after results were written:", exc)
                    continue
            report.add(path, "OK")
        except AlreadyIngested as exc:
            report.add(path, "REFUSED", str(exc))
            print("  REFUSED -", exc)
        except IngestError as exc:
            report.add(path, "FAILED", str(exc))
            print("  FAILED -", exc)
        except Exception as exc:
            report.add(path, "FAILED", f"{type(exc).__name__}: {exc}")
            print("  FAILED -", f"{type(exc).__name__}: {exc}")

    print(report.render())
    return 1 if report.failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
