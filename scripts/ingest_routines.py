#!/usr/bin/env python3
"""Parse routine PDFs and load results into separate Supabase tables.

Usage:
  python scripts/ingest_routines.py /path/to/Routine_Results.pdf [--dry-run]
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


def parse_routine_pdf_text(text: str) -> Dict[str, Any]:
    lines = [ln.rstrip() for ln in text.splitlines()]

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
                "synchronization_total": 0.0,
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
                        score["penalty"] = float(sy_match.group("pen"))
                        athlete["synchronization_total"] = score["penalty"]
                    athlete["routine_scores"]["synchronization_scores"].append(score)
                    i += 1
                    continue
                
                i += 1

            # Store athletes json string
            athlete["team_athletes"] = json.dumps(athlete["team_athletes"])
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
        "judges": judges,
        "athletes": athletes,
    }


def insert_rows_to_supabase(payload: Dict[str, Any], source_file: str, dry_run: bool = False) -> None:
    if dry_run:
        print(f"Dry run for {source_file}: would insert events/meets/judges/athletes.")
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

    # Event
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
    
    # Meet
    meet_name = payload["meet"]["name"]
    meet_query_endpoint = f"{supabase_url.rstrip('/')}/rest/v1/as_meet"
    res_meet = requests.get(
        meet_query_endpoint, 
        headers=query_headers, 
        params={"name": f"eq.{meet_name}", "event_id": f"eq.{event_id}", "select": "id"},
        timeout=20
    )
    
    if res_meet.status_code == 200 and res_meet.json():
        meet_id = res_meet.json()[0]["id"]
    else:
        meet = payload["meet"]
        meet["event_id"] = event_id
        meet_rows = insert_rows("as_meet", [meet])
        meet_id = meet_rows[0]["id"]

    # Judges Panel
    if payload["judges"]:
        judge_rows = []
        for j in payload["judges"]:
            j["meet_id"] = meet_id
            judge_rows.append(j)
        # Using as_meet_judge_panel per user prompt
        insert_rows("as_meet_judge_panel", judge_rows)

    # Athlete Results
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
            
        insert_rows("as_meet_routine_result", athlete_rows)

    print(f"Inserted event, meet, judges, and athlete results for {source_file}")


def main(argv: List[str]) -> int:
    if len(argv) < 2:
        print("Usage: python scripts/ingest_routines.py <pdf1> [pdf2 ...] [--dry-run]")
        return 1

    dry_run = "--dry-run" in argv
    paths = [arg for arg in argv[1:] if arg != "--dry-run"]

    for path in paths:
        if not os.path.exists(path):
            print("File not found:", path)
            continue
        print("Processing:", path)
        text = extract_text_from_pdf(path)
        parsed = parse_routine_pdf_text(text)
        try:
            insert_rows_to_supabase(parsed, path, dry_run=dry_run)
        except Exception as exc:
            print("Failed to insert to Supabase:", exc)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
