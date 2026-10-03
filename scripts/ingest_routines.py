#!/usr/bin/env python3
"""Parse routine PDFs and load results into separate Supabase tables.

Usage:
  python scripts/ingest_routines.py /path/to/Routine_Results.pdf [--dry-run]

Writes as_event -> as_meet -> as_meet_judge_panel -> as_meet_routine_result,
then calls synchronized_meet() to reconcile people, clubs and memberships.

Re-importing a PDF that is already loaded is refused rather than duplicated. See
scripts/ingest_common.py for the write path and why it is shared with ingest_figures.py.

KNOWN GAP - the score arithmetic is not trustworthy yet. as_meet_routine_result is
still empty on the live database, so this path has never completed an import. The
STC lines carry a deduction that the parser used to write into `synchronization_total`
(a column that means a total, and which received -15.9667), and the ACRO / Artistic
Impression regexes only match when a line has either zero or two trailing numbers,
so most element lines are dropped and element_total / routine_score stay 0.0. Those
values are left NULL rather than filled with a guess - see the warnings the run
prints. Fixing them needs the intended column semantics confirmed, not a regex tweak.
"""
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
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
    from user_mgmt_sync import synchronized_meet
except Exception:
    print("Missing dependency user_mgmt_sync (psycopg2?). Install via: pip install -r requirements.txt")
    raise


def extract_text_from_pdf(path: str) -> str:
    text_chunks = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            txt = page.extract_text() or ""
            text_chunks.append(txt)
    return "\n".join(text_chunks)


def parse_routine_pdf_text(text: str) -> Dict[str, Any]:
    lines = [ln.rstrip() for ln in text.splitlines()]
    warnings: List[str] = []
    dropped_scoring_lines: List[str] = []

    # Extract Header (Event, Meet, City, Date)
    header_lines = []
    for ln in lines:
        stripped = ln.strip()
        if not stripped:
            continue
        if stripped.startswith("Code Rank") or stripped.startswith("Code Pos") or "Referee:" in stripped:
            break
        if stripped.startswith("Created using") or "Report Created" in stripped or stripped.startswith("Signature") or stripped.startswith("Page:"):
            continue
        header_lines.append(stripped)

    # Note: Event and Meet name logic might be specific to the PDF format
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

    judges_panels = {}
    officials = []
    
    i = 0
    # Parse Officials and Panels
    while i < len(lines):
        line = lines[i]
        
        # Officials
        for official_title in ["Referee", "Asst. Referee", "DTC", "DATC"]:
            if official_title == "Referee":
                m = re.search(r"(?<!Asst\.\s)Referee:\s*(.+)", line)
            else:
                m = re.search(rf"{official_title}:\s*(.+)", line)
            if m:
                officials.append({
                    "figure_code_short": None,
                    "panel_name": official_title,
                    "panel": {official_title: m.group(1).split("  ")[0].strip()}
                })

        # Judge Panels Setup
        if "Elements" in line and "Artistic Impression" in line and "Synchronization" in line:
            judges_panels["Elements"] = {}
            judges_panels["Artistic Impression"] = {}
            judges_panels["Synchronization"] = {}
            
            i += 1
            while i < len(lines) and lines[i].strip().startswith("J"):
                j_line = lines[i]
                j_num = j_line.strip()[:2]
                rest = j_line.strip()[2:].strip()
                
                # Split names by Firstname LASTNAME pattern
                names = re.findall(r"[A-Z][A-Za-z\.\-\']+\s+[A-Z\-\']{2,}(?:\s+[A-Z\-\']{2,})*", rest)
                if len(names) >= 1: judges_panels["Elements"][j_num] = names[0]
                if len(names) >= 2: judges_panels["Artistic Impression"][j_num] = names[1]
                if len(names) >= 3: judges_panels["Synchronization"][j_num] = names[2]
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
                "panel": panel_data
            })

    athletes = []
    
    while i < len(lines):
        line = lines[i]
        team_match = re.match(r"^\s*(?P<rank>\d+)\.\s*\((?P<draw>\d+)\)\s*(?P<team_code>[A-Z0-9]+)\s*-\s*(?P<team_name>.+)$", line)
        
        if team_match:
            athlete = {
                "rank": int(team_match.group("rank")),
                "draw": int(team_match.group("draw")),
                "team_code": team_match.group("team_code"),
                "team_name": team_match.group("team_name").strip(),
                "team_athletes": [],
                "total_difficulty": [],
                "routine_scores": {
                    "element_scores": [],
                    "artistic_impression_scores": [],
                    "synchronization_scores": []
                },
                "element_total": 0.0,
                "artisticimpression_total": 0.0,
                # Left NULL rather than 0.0. The old code assigned the STC deduction
                # here, so this column received -15.9667 on a real PDF: a penalty is
                # not a total, and three STC lines raced for the same field with the
                # last one winning. A deduction is still recorded, in the score dict
                # below, where it belongs.
                "synchronization_total": None,
                "routine_score": 0.0
            }

            i += 1
            # Parse routine rows and athletes
            while i < len(lines):
                current = lines[i]
                if not current.strip():
                    i += 1
                    continue
                if re.match(r"^\s*\d+\.\s*\(\d+\)\s+", current):
                    break # Next team
                if current.strip().startswith("Created using") or "Report Created" in current or current.strip().startswith("Page:"):
                    i += 1
                    continue
                if "Age Group" in current or "Junior Olympic" in current or "Prelim" in current or "Final" in current or re.match(r"^\d{1,2}\s+[A-Z]{3}\s+\d{4}", current.strip()):
                    i += 1
                    continue
                if "Code Rank Draw Team" in current:
                    i += 1
                    continue

                # Swimmer parsing
                swimmer_match = re.match(r"^\s*(?P<gender>[FM])\s+(?:\[(?P<res>R)\]\s+)?(?P<name>.+)$", current)
                if swimmer_match:
                    athlete["team_athletes"].append({
                        "name": swimmer_match.group("name").strip(),
                        "gender": "Female" if swimmer_match.group("gender") == "F" else "Male",
                        "is_reserve": bool(swimmer_match.group("res"))
                    })
                    i += 1
                    continue

                # Scores Parsing
                parts = current.strip().split()
                if not parts:
                    i += 1
                    continue
                
                # Element Score (ACRO / HYBRID)
                el_match = re.match(r"^\s*(?P<type>ACRO|HYBRID)\s*\((?P<factor>[0-9.]+)\)\s+(?P<dd>[0-9.]+)\s+(?P<j1>[0-9.]+)\s+(?P<j2>[0-9.]+)\s+(?P<j3>[0-9.]+)\s+(?P<j4>[0-9.]+)\s+(?P<tot>[0-9.]+)(?:\s+(?P<el_tot>[0-9.]+)\s+(?P<routine>[0-9.]+))?$", current)
                if el_match:
                    score = {
                        "element_type": el_match.group("type"),
                        "factor": float(el_match.group("factor")),
                        "dd": float(el_match.group("dd")),
                        "J1": float(el_match.group("j1")),
                        "J2": float(el_match.group("j2")),
                        "J3": float(el_match.group("j3")),
                        "J4": float(el_match.group("j4")),
                        "total": float(el_match.group("tot"))
                    }
                    if el_match.group("el_tot"): athlete["element_total"] = float(el_match.group("el_tot"))
                    if el_match.group("routine"): athlete["routine_score"] = float(el_match.group("routine"))
                    athlete["routine_scores"]["element_scores"].append(score)
                    i += 1
                    continue
                
                # Total Difficulty
                td_match = re.match(r"^\s*TOTAL DIFFICULTY\s+(?P<ref>[0-9.]+)\s+(?P<dd>[0-9.]+)", current)
                if td_match:
                    athlete["total_difficulty"] = [
                        {"Ref": float(td_match.group("ref"))},
                        {"DD": float(td_match.group("dd"))}
                    ]
                    i += 1
                    continue
                
                # Artistic Impression
                ai_match = re.match(r"^\s*(?P<type>Choreo and Music|Performance|Transitions)\s*\((?P<factor>[0-9.]+)\)\s+(?P<j1>[0-9.]+)\s+(?P<j2>[0-9.]+)\s+(?P<j3>[0-9.]+)\s+(?P<j4>[0-9.]+)\s+(?P<tot>[0-9.]+)(?:\s+(?P<ai_tot>[0-9.]+))?$", current)
                if ai_match:
                    score = {
                        "element_type": ai_match.group("type"),
                        "factor": float(ai_match.group("factor")),
                        "J1": float(ai_match.group("j1")),
                        "J2": float(ai_match.group("j2")),
                        "J3": float(ai_match.group("j3")),
                        "J4": float(ai_match.group("j4")),
                        "total": float(ai_match.group("tot"))
                    }
                    if ai_match.group("ai_tot"): athlete["artisticimpression_total"] = float(ai_match.group("ai_tot"))
                    athlete["routine_scores"]["artistic_impression_scores"].append(score)
                    i += 1
                    continue
                
                # Synchronization
                sy_match = re.match(r"^\s*(?P<type>STC Small|STC Obvious|STC Major-Median)\s*\((?P<factor>[0-9.]+)\)\s+(?P<j1>[0-9]+)\s+(?P<j2>[0-9]+)\s+(?P<j3>[0-9]+)\s+(?P<tot>[0-9.]+)(?:\s+(?P<pen>-?[0-9.]+))?$", current)
                if sy_match:
                    score = {
                        "element_type": sy_match.group("type"),
                        "factor": float(sy_match.group("factor")),
                        "J1": int(sy_match.group("j1")),
                        "J2": int(sy_match.group("j2")),
                        "J3": int(sy_match.group("j3")),
                        "total": float(sy_match.group("tot"))
                    }
                    if sy_match.group("pen"):
                        # Recorded, not promoted to synchronization_total. What this
                        # trailing column means is not established, so it is kept with
                        # the STC row instead of being reported as a score total.
                        score["penalty"] = float(sy_match.group("pen"))
                    athlete["routine_scores"]["synchronization_scores"].append(score)
                    i += 1
                    continue

                # A line that starts like a scoring row but matched none of the
                # patterns above is a dropped score, not a stray line. The ACRO and
                # Artistic Impression regexes only match when the line carries either
                # zero or two trailing numbers, and the real sheets carry one, so this
                # is where the totals quietly go to zero. Count them and say so.
                if re.match(r"^\s*(ACRO|HYBRID|Choreo and Music|Performance|Transitions|STC)", current):
                    dropped_scoring_lines.append(current.strip()[:80])
                    i += 1
                    continue

                i += 1

            # Store athletes json string
            athlete["team_athletes"] = json.dumps(athlete["team_athletes"])
            athletes.append(athlete)
            continue
        i += 1

    if dropped_scoring_lines:
        warnings.append(
            f"{len(dropped_scoring_lines)} scoring line(s) did not match any pattern and were "
            "dropped, so element_total / artisticimpression_total / routine_score are "
            f"understated. First: {dropped_scoring_lines[0]!r}"
        )
    warnings.append(
        "synchronization_total is NULL on every row: the STC trailing column is recorded in "
        "routine_scores but is not promoted to a total, because what it represents is not "
        "established."
    )

    return {
        "event": {
            "event_name": event_name,
            "host_city": host_city,
            "event_date": event_date
        },
        "meet": {
            "name": meet_name,
            "meet_date": event_date
        },
        "judges": judges,
        "athletes": athletes,
        "warnings": warnings,
    }



def insert_rows_to_supabase(payload: Dict[str, Any], source_file: str, dry_run: bool = False,
                            replace_source: bool = False, allow_empty: bool = False) -> str:
    """Write one parsed PDF. Returns a human-readable summary of what happened."""
    check_results_present(payload, allow_empty)

    config = get_supabase_config()
    client = SupabaseRest(config["url"], config["key"])

    if dry_run:
        return "dry run, nothing written"

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
                "source_file": source_file
            })
        client.insert("as_meet_routine_result", athlete_rows)

    parts = []
    parts.append("created event" if event_created else "reused event")
    parts.append("created meet" if meet_created else "reused meet")
    if replaced:
        parts.append(replaced)
    return ", ".join(parts)


def main(argv: List[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    flags = {a for a in argv[1:] if a.startswith("--")}
    known = {"--dry-run", "--replace-source", "--allow-empty", "--no-provision"}
    unknown = flags - known
    if unknown:
        print("Unknown option(s):", ", ".join(sorted(unknown)))
        print("Usage: python scripts/ingest_routines.py <pdf1> [pdf2 ...] "
              "[--dry-run] [--replace-source] [--allow-empty] [--no-provision]")
        return 2
    if not args:
        print("Usage: python scripts/ingest_routines.py <pdf1> [pdf2 ...] "
              "[--dry-run] [--replace-source] [--allow-empty] [--no-provision]")
        return 1

    dry_run = "--dry-run" in flags
    replace_source = "--replace-source" in flags
    allow_empty = "--allow-empty" in flags
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
            parsed = parse_routine_pdf_text(extract_text_from_pdf(path))
            summary = insert_rows_to_supabase(
                parsed, path, dry_run=dry_run,
                replace_source=replace_source, allow_empty=allow_empty,
            )
            print(describe(parsed))
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
