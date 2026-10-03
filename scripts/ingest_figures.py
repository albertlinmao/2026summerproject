#!/usr/bin/env python3
"""Parse figure PDFs and load results into separate Supabase tables.

Usage:
  python scripts/ingest_figures.py /path/to/Detailed_-_Age_Group_12_and_Under_Figures.pdf [--dry-run]

Writes as_event -> as_meet -> as_figure -> as_meet_judge_panel -> as_meet_figure_result,
then calls synchronized_meet() to reconcile people, clubs and memberships.

Re-importing a PDF that is already loaded is refused rather than duplicated. See
scripts/ingest_common.py for the write path and why it is shared with ingest_routines.py.
"""
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
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


def parse_float(val: str, warnings: List[str]) -> Optional[float]:
    """Read a score, or return None. Never invent a 0.0.

    The old version returned 0.0 for anything it could not read, including '-.-'
    which is a placeholder for a figure that was not performed. That wrote a
    fabricated zero into an official result, indistinguishable from a real zero,
    and because totals are summed from these it also dragged the athlete's total
    down. None says "not read", which is what actually happened.
    """
    text = (val or "").strip()
    if text in ("", "-", ".-", "-.-", "N/A"):
        warnings.append(f"unreadable score {val!r} stored as NULL")
        return None
    try:
        return float(text)
    except ValueError:
        warnings.append(f"unreadable score {val!r} stored as NULL")
        return None


def parse_figure_pdf_text(text: str) -> Dict[str, Any]:
    lines = [ln.rstrip() for ln in text.splitlines()]
    warnings: List[str] = []

    # Filter out common page header lines that might be parsed first
    header_lines = []
    for ln in lines:
        stripped = ln.strip()
        if not stripped:
            continue
        if stripped.startswith("Code Rank") or stripped.startswith("Code Pos"):
            continue
        if stripped.startswith("Created using") or "Report Created" in stripped or stripped.startswith("Signature") or stripped.startswith("Page:"):
            continue
        header_lines.append(stripped)
        if len(header_lines) >= 3:
            break

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
        
    # If city ends up with trailing comma/spaces, strip it
    if host_city:
        host_city = host_city.strip(", ")
        if not host_city:
            host_city = None
    
    # Supabase expects valid date or null
    if not event_date:
        event_date = None
    
    figures_dict = {}
    judges_panels = {}
    figure_shorts = []
    referee_name = None

    i = 0
    while i < len(lines):
        line = lines[i]
        
        if "Referee:" in line:
            rm = re.search(r"Referee:\s*(.+)", line)
            if rm:
                referee_name = rm.group(1).split("  ")[0].strip()

        if re.search(r"F\d+:\s", line.lstrip()):
            # We found the F1 F2 F3 headers
            columns = []
            for m in re.finditer(r"(F\d+):\s*(.*?)(?=\s+F\d+:|$)", line):
                f_short = m.group(1)
                f_name = m.group(2).strip()
                start_idx = m.start(1)
                columns.append((start_idx, f_short))
                figure_shorts.append(f_short)
                f_num = f_short[1:]
                figures_dict[f_short] = {
                    "figure_code": f"Figure {f_num}",
                    "figure_code_short": f_short,
                    "name": f_name,
                }
                judges_panels[f_short] = {}
                
            # next line is DD
            i += 1
            if i < len(lines):
                dd_line = lines[i]
                dds = re.findall(r"DD:\s*([0-9.]+)", dd_line)
                for idx, dd in enumerate(dds):
                    if idx < len(figure_shorts):
                        figures_dict[figure_shorts[idx]]["degree_difficulty"] = float(dd)

            # next lines are J1 to J5+
            i += 1
            while i < len(lines) and lines[i].strip().startswith("J"):
                j_line = lines[i]
                j_num = j_line.strip()[:2]
                for m in re.finditer(r"[^\s](?:[^\s]|\s(?!\s))*[^\s]|[^\s]", j_line[2:]):
                    val = m.group(0).strip()
                    if val:
                        pos = m.start(0) + 2
                        best_diff = 999
                        closest_col = None
                        for c_start, f_short in columns:
                            diff = abs(c_start - pos)
                            if diff < best_diff:
                                best_diff = diff
                                closest_col = f_short
                        if closest_col:
                            judges_panels[closest_col][j_num] = val
                i += 1
            i -= 1 # adjust back since outer loop will increment
            break
        i += 1

    # find the full figure names
    while i < len(lines):
        line = lines[i].strip()
        fm = re.match(r"^Figure\s+(\d+)\s+(.+?)\s+([0-9.]+)$", line)
        if fm:
            f_num = fm.group(1)
            f_short = f"F{f_num}"
            if f_short in figures_dict:
                figures_dict[f_short]["name"] = fm.group(2).strip()
                figures_dict[f_short]["degree_difficulty"] = float(fm.group(3))
        if "Total:" in line or "Code Rank Draw" in line:
            break
        i += 1

    figures = list(figures_dict.values())
    judges = []
    for f_short, panel in judges_panels.items():
        judges.append({
            "figure_code_short": f_short,
            "panel_name": figures_dict[f_short]["name"],
            "panel": panel
        })
        
    if referee_name:
        judges.append({
            "figure_code_short": None,
            "panel_name": "Referee",
            "panel": {"Referee": referee_name}
        })

    num_scores = max((len(panel) for panel in judges_panels.values()), default=4)
    athletes = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        athlete_header = re.match(r"^\s*(?P<rank>\d+)\.\s*\((?P<draw>\d+)\)\s*(?P<team_code>[A-Z0-9]+)\s*-\s*(?P<team_name>.+)$", line)
        if athlete_header:
            athlete = {
                "rank": athlete_header.group("rank"),
                "draw": athlete_header.group("draw"),
                "team_code": athlete_header.group("team_code"),
                "team_name": athlete_header.group("team_name").strip(),
                "athlete_name": None,
                "athlete_birth_year": None,
                "penalty": None,
                "total_score": None,
                "figure_score": None,
                "figure_results": [],
            }

            i += 1
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i < len(lines):
                swimmer_line = lines[i].strip()
                swimmer_match = re.match(r"^(?P<name>.+?)\s*\[(?P<year>\d{4})\]$", swimmer_line)
                if swimmer_match:
                    athlete["athlete_name"] = swimmer_match.group("name").strip()
                    athlete["athlete_birth_year"] = int(swimmer_match.group("year"))
                    i += 1
                elif swimmer_line: # fallback for lines without birth year
                    athlete["athlete_name"] = swimmer_line.strip()
                    i += 1

            while i < len(lines):
                current = lines[i].strip()
                if not current:
                    i += 1
                    continue
                if re.match(r"^\d+\.\s*\(\d+\)\s+", current):
                    break
                if current.startswith("Created using") or current.startswith("Signature") or current.startswith("Page:"):
                    i += 1
                    continue
                if current.startswith("Fig"):
                    tokens = current.split()
                    if len(tokens) >= 2 + num_scores and tokens[0].lower() == "fig":
                        figure_number = int(tokens[1].lstrip("#"))
                        judge_scores = [parse_float(token, warnings) for token in tokens[2:2+num_scores]]
                        fig_total = parse_float(tokens[2+num_scores], warnings) if len(tokens) > 2+num_scores else None
                        overall_total = parse_float(tokens[3+num_scores], warnings) if len(tokens) > 3+num_scores else None
                        figure_item = {
                            "figure_number": figure_number,
                            "judge_scores": judge_scores,
                            "total_score": fig_total,
                            "figure_score": overall_total
                        }
                        
                        if overall_total is not None:
                            athlete["figure_score"] = overall_total
                            
                        athlete["figure_results"].append(figure_item)
                i += 1

            figure_totals = [f["total_score"] for f in athlete["figure_results"] if f["total_score"] is not None]
            athlete["total_score"] = sum(figure_totals) if figure_totals else None

            athletes.append(athlete)
            continue
        i += 1

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
        "figures": figures,
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

    # Refuses a re-ingest before anything is written. Duplicate result rows cannot
    # be corrected afterwards: forbid_result_updates() blocks the UPDATE that would
    # otherwise fix them.
    replaced = prepare_meet_for_write(
        client, "as_meet_figure_result", meet_id, source_file, replace_source
    )

    if payload["figures"]:
        figure_rows = [{**row, "meet_id": meet_id} for row in payload["figures"]]
        fig_out = client.insert("as_figure", figure_rows)
        fig_map = {f["figure_code_short"]: f["id"] for f in fig_out}

        missing = [f for f in fig_map if not f]
        if missing:
            raise IngestError(f"figure insert returned rows without figure_code_short: {missing}")
        if len(fig_map) != len(payload["figures"]):
            raise IngestError(
                f"inserted {len(fig_map)} figure(s) but the PDF described {len(payload['figures'])}; "
                "refusing to attach judge panels to a guess"
            )

        if payload["judges"]:
            judge_rows = []
            for j in payload["judges"]:
                f_short = j.get("figure_code_short")
                if f_short is not None and f_short not in fig_map:
                    # The old code used fig_map.get() here, so a missing figure left
                    # the panel row with a NULL figure_id and no complaint.
                    raise IngestError(
                        f"judge panel for {f_short!r} has no matching figure row; refusing to "
                        "write a panel that cannot be attached to its figure"
                    )
                row = dict(j)
                row["meet_id"] = meet_id
                row["figure_id"] = fig_map.get(f_short)
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
                "athlete_name": athlete.get("athlete_name"),
                "athlete_birth_year": athlete.get("athlete_birth_year"),
                "penalty": athlete.get("penalty"),
                "total_score": athlete.get("total_score"),
                "figure_score": athlete.get("figure_score"),
                "figure_scores": athlete.get("figure_results", []),
                "source_file": source_file
            })
        client.insert("as_meet_figure_result", athlete_rows)

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
        print("Usage: python scripts/ingest_figures.py <pdf1> [pdf2 ...] "
              "[--dry-run] [--replace-source] [--allow-empty] [--no-provision]")
        return 2
    if not args:
        print("Usage: python scripts/ingest_figures.py <pdf1> [pdf2 ...] "
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
            # Extraction and parse sit inside the try on purpose. They used to sit
            # outside it, so one malformed PDF raised out of the loop and abandoned
            # every file after it while the files before it were already committed.
            parsed = parse_figure_pdf_text(extract_text_from_pdf(path))
            summary = insert_rows_to_supabase(
                parsed, path, dry_run=dry_run,
                replace_source=replace_source, allow_empty=allow_empty,
            )
            print(describe(parsed))
            if not dry_run:
                print(f"  {summary}")
                if provision:
                    try:
                        # Runs after the results are written, so a failure here leaves the
                        # results in place. That ordering is not changed here; it is
                        # reported as a failure so the run does not look clean.
                        synchronized_meet(parsed, dry_run=False, routine=False)
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
    # The old main() returned 0 no matter what, so a scheduled run could not tell
    # a clean import from one where every PDF failed.
    return 1 if report.failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
