#!/usr/bin/env python3
"""Parse figure PDFs and load results into separate Supabase tables.

Usage:
  python scripts/ingest_figures.py /path/to/Detailed_-_Age_Group_12_and_Under_Figures.pdf [--dry-run]
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

def get_supabase_config() -> Dict[str, str]:
    load_dotenv(ROOT_DIR / ".env")
    load_dotenv(ROOT_DIR / "supabase" / ".env", override=False)

    raw_url = (os.getenv("SUPABASE_URL") or os.getenv("SUPABASE_PUBLIC_URL") or "").strip()
    if raw_url.startswith("postgres://") or raw_url.startswith("postgresql://"):
        raw_url = "http://localhost:8000"
    if raw_url.startswith("http://host.docker.internal"):
        raw_url = raw_url.replace("http://host.docker.internal", "http://localhost")
    if not raw_url:
        raw_url = "http://localhost:8000"

    key = (
        os.getenv("SUPABASE_KEY")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_KEY")
        or os.getenv("SERVICE_ROLE_KEY")
        or os.getenv("ANON_KEY")
        or ""
    )

    return {"url": raw_url, "key": key}


def extract_text_from_pdf(path: str) -> str:
    text_chunks = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            txt = page.extract_text() or ""
            text_chunks.append(txt)
    return "\n".join(text_chunks)


def parse_figure_pdf_text(text: str) -> Dict[str, Any]:
    lines = [ln.rstrip() for ln in text.splitlines()]

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
                "routine_score": None,
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
                        def parse_float(val):
                            if val == '-.-':
                                return 0.0
                            try:
                                return float(val)
                            except ValueError:
                                return 0.0

                        figure_number = int(tokens[1].lstrip("#"))
                        judge_scores = [parse_float(token) for token in tokens[2:2+num_scores]]
                        fig_total = parse_float(tokens[2+num_scores]) if len(tokens) > 2+num_scores else None
                        overall_total = parse_float(tokens[3+num_scores]) if len(tokens) > 3+num_scores else None
                        figure_item = {
                            "figure_number": figure_number,
                            "judge_scores": judge_scores,
                            "total_score": fig_total,
                            "routine_score": overall_total if overall_total is not None else 0
                        }
                        
                        if overall_total is not None:
                            athlete["routine_score"] = overall_total
                            
                        athlete["figure_results"].append(figure_item)
                i += 1

            athlete["total_score"] = sum(fig["total_score"] for fig in athlete["figure_results"] if fig["total_score"] is not None)

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
    }


def insert_rows_to_supabase(payload: Dict[str, Any], source_file: str, dry_run: bool = False) -> None:
    if dry_run:
        print(f"Dry run for {source_file}: would insert events/meets/figures/judges/athletes.")
        return

    supabase_config = get_supabase_config()
    supabase_url = supabase_config["url"]
    supabase_key = supabase_config["key"]

    if not supabase_url or not supabase_key:
        raise RuntimeError("Supabase credentials not provided in environment")

    def insert_rows(table: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        endpoint = f"{supabase_url.rstrip('/')}/rest/v1/{table}"
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        response = requests.post(endpoint, headers=headers, json=rows, timeout=20)
        if response.status_code not in (200, 201):
            raise RuntimeError(f"Supabase insert failed for {table}: {response.status_code} {response.text}")
        if not response.text:
            return []
        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError(f"Supabase returned invalid JSON for {table}: {response.text}") from exc

    event_name = payload["event"]["event_name"]
    query_endpoint = f"{supabase_url.rstrip('/')}/rest/v1/as_event"
    query_headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Accept": "application/json",
    }
    
    res = requests.get(
        query_endpoint, 
        headers=query_headers, 
        params={"event_name": f"eq.{event_name}", "select": "id"},
        timeout=20
    )
    
    if res.status_code == 200 and res.json():
        event_id = res.json()[0]["id"]
    else:
        event_rows = insert_rows("as_event", [payload["event"]])
        if not event_rows:
            raise RuntimeError("No event row returned")
        event_id = event_rows[0]["id"]
    
    meet = payload["meet"]
    meet["event_id"] = event_id
    meet_rows = insert_rows("as_meet", [meet])
    meet_id = meet_rows[0]["id"]

    if payload["figures"]:
        figure_rows = [{**row, "meet_id": meet_id} for row in payload["figures"]]
        fig_out = insert_rows("as_figure", figure_rows)
        
        fig_map = {f["figure_code_short"]: f["id"] for f in fig_out}
        
        if payload["judges"]:
            judge_rows = []
            for j in payload["judges"]:
                f_short = j.get("figure_code_short")
                j["meet_id"] = meet_id
                j["figure_id"] = fig_map.get(f_short)
                judge_rows.append(j)
            insert_rows("as_meet_judge_panel", judge_rows)

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
                "routine_score": athlete.get("routine_score"),
                "figure_scores": athlete.get("figure_results", []),
                "source_file": source_file
            })
            
        insert_rows("as_meet_figure_result", athlete_rows)

    print(f"Inserted event, meet, figures, judges, and athlete results for {source_file}")


def main(argv: List[str]) -> int:
    if len(argv) < 2:
        print("Usage: python scripts/ingest_figures.py <pdf1> [pdf2 ...] [--dry-run]")
        return 1

    dry_run = "--dry-run" in argv
    paths = [arg for arg in argv[1:] if arg != "--dry-run"]

    for path in paths:
        if not os.path.exists(path):
            print("File not found:", path)
            continue
        print("Processing:", path)
        text = extract_text_from_pdf(path)
        parsed = parse_figure_pdf_text(text)
        try:
            insert_rows_to_supabase(parsed, path, dry_run=dry_run)
        except Exception as exc:
            print("Failed to insert to Supabase:", exc)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
