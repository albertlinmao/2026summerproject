#!/usr/bin/env python3
"""
Load non-duplicated athlete and club data from as_meet_figure_result and
as_meet_routine_result tables.

Logic:
1. Get all unique team_codes from both figure and routine result tables
2. For each team_code, check if it exists in as_club.code
3. If team_code exists in as_club, use the existing as_club.id
4. If team_code does not exist in as_club, create a new club with the team_code
   and team_name from figure or routine result tables
5. Insert athletes to as_athlete table using the club_id from as_club
6. Deduplicate athletes by name + club_id combination
"""

import json
import os
import sys
import uuid
from collections import defaultdict

os.environ['SUPABASE_URL'] = 'http://host.docker.internal:8000'
os.environ['SUPABASE_ANON_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoic2VydmljZV9yb2xlIiwiaXNzIjoic3VwYWJhc2UtZGVtbyIsImlhdCI6MTc3NDU4NTYxNiwiZXhwIjoyMDg5OTQ1NjE2fQ.b1O_-2rmLwVLVrW3Deunk3HAXnRpGgmXhcfOM1b6zCs'

from supabase import create_client


def main():
    supabase = create_client(
        os.environ['SUPABASE_URL'],
        os.environ['SUPABASE_ANON_KEY']
    )

    print("=" * 60)
    print("Athlete & Club Loading Script")
    print("=" * 60)

    # Step 1: Fetch all unique team_codes from both tables
    print("\n[Step 1] Fetching team_codes from result tables...")

    fig_result = supabase.table("as_meet_figure_result") \
        .select("team_code, team_name, athlete_name, athlete_birth_year").execute()
    rout_result = supabase.table("as_meet_routine_result") \
        .select("team_code, team_name, team_athletes").execute()

    fig_data = fig_result.data or []
    rout_data = rout_result.data or []

    print(f"  as_meet_figure_result: {len(fig_data)} rows")
    print(f"  as_meet_routine_result: {len(rout_data)} rows")

    # Step 2: Build unique team_code -> team_name mapping
    print("\n[Step 2] Building unique team_code -> team_name mapping...")

    team_name_map = {}  # team_code -> team_name (first non-null wins)
    for r in fig_data:
        tc = r.get("team_code")
        tn = r.get("team_name")
        if tc and tc not in team_name_map:
            team_name_map[tc] = tn
        elif tc and tc in team_name_map and not team_name_map[tc] and tn:
            team_name_map[tc] = tn

    for r in rout_data:
        tc = r.get("team_code")
        tn = r.get("team_name")
        if tc and tc not in team_name_map:
            team_name_map[tc] = tn
        elif tc and tc in team_name_map and not team_name_map[tc] and tn:
            team_name_map[tc] = tn

    print(f"  Found {len(team_name_map)} unique team_codes")

    # Step 3: Load existing clubs from as_club
    print("\n[Step 3] Checking team_codes against as_club table...")

    clubs_result = supabase.table("as_club").select("id, code, name").execute()
    existing_clubs = clubs_result.data or []
    club_map = {}  # code -> {id, name}
    for club in existing_clubs:
        club_map[club.get("code", "")] = {
            "id": club["id"],
            "name": club["name"]
        }

    print(f"  Found {len(existing_clubs)} existing clubs in as_club")

    # Step 4: Match or create clubs
    print("\n[Step 4] Matching team_codes to clubs (creating new clubs if needed)...")

    new_clubs_created = 0
    club_id_map = {}  # team_code -> club_id

    for team_code, team_name in sorted(team_name_map.items()):
        if team_code in club_map:
            club_id_map[team_code] = club_map[team_code]["id"]
            print(f"  MATCH  '{team_code}' -> existing club '{club_map[team_code]['name']}'")
        else:
            # Create new club
            new_club_id = str(uuid.uuid4())
            new_club_name = team_name or team_code
            try:
                supabase.table("as_club").insert({
                    "id": new_club_id,
                    "name": new_club_name,
                    "code": team_code
                }).execute()
                club_id_map[team_code] = new_club_id
                new_clubs_created += 1
                print(f"  NEW    '{team_code}' -> created club '{new_club_name}'")
            except Exception as e:
                print(f"  ERROR  Failed to create club '{team_code}': {e}")

    print(f"\n  Clubs matched: {len(club_map)}")
    print(f"  Clubs created: {new_clubs_created}")

    # Step 5: Collect athletes from figure results
    print("\n[Step 5] Collecting athletes from figure results...")

    athletes_raw = []  # (name, club_id, birth_year)
    for r in fig_data:
        tc = r.get("team_code")
        name = r.get("athlete_name")
        by = r.get("athlete_birth_year")
        if name and tc and tc in club_id_map:
            athletes_raw.append((name, club_id_map[tc], by))

    print(f"  {len(athletes_raw)} athlete entries from figure results")

    # Step 6: Collect athletes from routine results
    print("\n[Step 6] Collecting athletes from routine results...")

    for r in rout_data:
        tc = r.get("team_code")
        if not tc or tc not in club_id_map:
            continue
        cid = club_id_map[tc]
        team_athletes = r.get("team_athletes", [])
        if isinstance(team_athletes, str):
            try:
                team_athletes = json.loads(team_athletes)
            except (json.JSONDecodeError, TypeError):
                team_athletes = []
        if not isinstance(team_athletes, list):
            continue
        for entry in team_athletes:
            name = None
            if isinstance(entry, dict):
                name = entry.get("name")
            elif isinstance(entry, str):
                name = entry
            if name:
                athletes_raw.append((name, cid, None))

    print(f"  Total athlete entries after routine: {len(athletes_raw)}")

    # Step 7: Deduplicate athletes by (name, club_id)
    print("\n[Step 7] Deduplicating athletes...")

    seen = set()
    unique_athletes = []
    for name, cid, by in athletes_raw:
        key = (name, cid)
        if key not in seen:
            seen.add(key)
            unique_athletes.append({"name": name, "club_id": cid, "birth_year": by})

    print(f"  {len(unique_athletes)} unique athletes")

    # Step 8: Insert athletes into as_athlete
    print("\n[Step 8] Inserting athletes into as_athlete table...")

    inserted = 0
    skipped = 0
    errors = 0

    for athlete in unique_athletes:
        try:
            existing = supabase.table("as_athlete") \
                .select("id") \
                .eq("name", athlete["name"]) \
                .eq("club_id", athlete["club_id"]) \
                .execute()
            if existing.data:
                skipped += 1
                continue

            supabase.table("as_athlete").insert({
                "id": str(uuid.uuid4()),
                "name": athlete["name"],
                "club_id": athlete["club_id"]
            }).execute()
            inserted += 1
        except Exception as e:
            errors += 1
            print(f"  ERROR inserting '{athlete['name']}': {e}")

    # Step 9: Summary
    print("\n[Step 9] Summary")
    print(f"  Clubs matched (existing):  {len(club_map)}")
    print(f"  Clubs created (new):       {new_clubs_created}")
    print(f"  Athletes inserted:         {inserted}")
    print(f"  Athletes already existed:  {skipped}")
    print(f"  Errors:                    {errors}")

    # Per-club breakdown
    clubs_with_athletes = defaultdict(int)
    for a in unique_athletes:
        clubs_with_athletes[a["club_id"]] += 1

    print(f"\n  Athletes per club:")
    for cid, count in sorted(clubs_with_athletes.items(), key=lambda x: -x[1]):
        cname = next(
            (c["name"] for c in existing_clubs if c["id"] == cid),
            next(
                (cn for cn, ci in club_id_map.items() if ci == cid),
                "Unknown"
            )
        )
        print(f"    {cname}: {count} athletes")

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
