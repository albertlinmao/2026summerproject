#!/usr/bin/env python3
"""
Load non-duplicated person and club data from as_meet_figure_result and
as_meet_routine_result tables.

Logic:
1. Get all unique team_codes from both figure and routine result tables
2. For each team_code, check if it exists in as_club.code
3. If team_code exists in as_club, use the existing as_club.id
4. If team_code does not exist in as_club, create a new club with the team_code
   and team_name from figure or routine result tables
5. Insert each printed name into as_person (a person has no club_id) and record
   the club edge as an as_club_membership row with role 'swimmer', status 'active'
6. Deduplicate people by printed name, memberships by name + club_id combination
7. Populate as_result_person_link for every result row whose printed name maps to
   a person, so the dashboard can attribute scores. Unresolved names are left
   unlinked rather than guessed.

Identity model: specs/001-analytics-dashboard/identity-contract.md
`as_athlete` is a view over as_person + as_club_membership, so nothing is
inserted into it. A login is optional: these swimmers get no as_person_identity
row. The printed name stays on the result rows (as_meet_figure_result.athlete_name,
as_meet_routine_result.team_athletes) as data lineage; canonical resolution lives
in as_result_person_link.

Run:  python scripts/tmp/AdhocDataMigration/load_athletes_clubs.py
Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (see .env.example). The
service-role key is required because these writes target tables that RLS
protects; a read-only anon key cannot insert them.
"""

import json
import sys
import uuid
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _ad_hoc_common import supabase_client  # noqa: E402


def split_printed_name(name):
    """Split an official result PDF name into (family_name, given_name).

    The result sheets print "FAMILY Given" (e.g. "HE Sunny", "MOLCHANOVA Kate");
    some sheets use "Family, Given". Middle names are not distinguishable from
    the printed form, so everything after the first token becomes given_name.
    """
    name = (name or "").strip()
    if not name:
        return None, None
    if "," in name:
        family, _, given = name.partition(",")
        return family.strip() or None, given.strip() or None
    parts = name.split()
    if len(parts) == 1:
        return parts[0], None
    return parts[0], " ".join(parts[1:])


def normalize_name(name):
    return " ".join((name or "").strip().lower().split())


def person_keys(family_name, given_name):
    """Lookup keys for a person, tolerant of the order the parts arrive in.

    The printed PDF form is "FAMILY Given"; the person columns are stored in
    columns, and a person may have been created elsewhere with a middle name.
    Both orderings are registered so either printed form resolves to the person.
    """
    family = (family_name or "").strip()
    given = (given_name or "").strip()
    if not family and not given:
        return ()
    keys = [normalize_name(" ".join(p for p in (family, given) if p))]
    reversed_key = normalize_name(" ".join(p for p in (given, family) if p))
    if reversed_key != keys[0]:
        keys.append(reversed_key)
    return keys


def birth_date_from_year(birth_year):
    """as_person.birth_date is a date; the PDF only carries a 4-digit year."""
    if not birth_year:
        return None
    try:
        return f"{int(birth_year):04d}-01-01"
    except (TypeError, ValueError):
        return None


def main():
    supabase = supabase_client()

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

    # Step 7: Deduplicate swimmers by (name, club_id) -- one membership per pair
    print("\n[Step 7] Deduplicating swimmers...")

    seen = set()
    unique_athletes = []
    for name, cid, by in athletes_raw:
        key = (name, cid)
        if key not in seen:
            seen.add(key)
            unique_athletes.append({"name": name, "club_id": cid, "birth_year": by})

    print(f"  {len(unique_athletes)} unique swimmers")

    # Step 8: Write people to as_person and the club edge to as_club_membership.
    # as_athlete is a view over exactly these two tables and must not be written to.
    print("\n[Step 8] Inserting people into as_person + as_club_membership...")

    persons_result = supabase.table("as_person").select(
        "id, given_name, family_name, middle_name, birth_date"
    ).execute()
    person_ids_by_name = {}  # normalized name key -> as_person.id
    for p in persons_result.data or []:
        for key in person_keys(p.get("family_name"), p.get("given_name")):
            person_ids_by_name.setdefault(key, p["id"])

    memberships_result = supabase.table("as_club_membership").select(
        "person_id, club_id, role, status"
    ).eq("role", "swimmer").execute()
    swimmer_memberships = {
        (m.get("person_id"), m.get("club_id"))
        for m in memberships_result.data or []
        if m.get("status") in ("invited", "active")
    }

    people_created = 0
    inserted = 0
    skipped = 0
    errors = 0
    person_by_printed = {}  # printed PDF name -> as_person.id

    for athlete in unique_athletes:
        name = athlete["name"]
        cid = athlete["club_id"]
        family_name, given_name = split_printed_name(name)
        keys = person_keys(family_name, given_name) or (normalize_name(name),)
        try:
            person_id = person_ids_by_name.get(keys[0])
            if not person_id:
                person_id = str(uuid.uuid4())
                supabase.table("as_person").insert({
                    "id": person_id,
                    "given_name": given_name or family_name or name,
                    "family_name": family_name if given_name else None,
                    "birth_date": birth_date_from_year(athlete["birth_year"])
                }).execute()
                for key in keys:
                    person_ids_by_name.setdefault(key, person_id)
                people_created += 1

            person_by_printed.setdefault(name.strip(), person_id)

            if (person_id, cid) in swimmer_memberships:
                skipped += 1
                continue

            supabase.table("as_club_membership").insert({
                "id": str(uuid.uuid4()),
                "person_id": person_id,
                "club_id": cid,
                "role": "swimmer",
                "status": "active"
            }).execute()
            swimmer_memberships.add((person_id, cid))
            inserted += 1
        except Exception as e:
            errors += 1
            print(f"  ERROR inserting '{athlete['name']}': {e}")

    # Step 9: Populate as_result_person_link.
    #
    # Without this the person/membership model has people but no attributable
    # results: as_daily_aggregations joins through this bridge and drops any
    # result row it cannot resolve, so the dashboard renders empty. Result rows
    # stay immutable - identity is attached here and nowhere else.
    #
    # Keyed on (result_table, result_id, athlete_name) to match
    # uq_as_result_person_link. A routine's team_athletes array shares one
    # result_id, so the printed name is the only intra-row discriminator.
    print("\n[Step 9] Populating as_result_person_link...")

    links_added = 0
    links_unresolved = 0

    for row in fig_data:
        printed = (row.get("athlete_name") or "").strip()
        if not printed:
            continue
        person_id = person_by_printed.get(printed)
        if not person_id:
            links_unresolved += 1
            continue
        supabase.table("as_result_person_link").upsert(
            {
                "result_table": "as_meet_figure_result",
                "result_id": row["id"],
                "person_id": person_id,
                "athlete_name": printed,
                "confidence": 1.0,
            },
            on_conflict="result_table,result_id,athlete_name",
        ).execute()
        links_added += 1

    for row in rout_data:
        team_athletes = row.get("team_athletes") or []
        if isinstance(team_athletes, str):
            try:
                team_athletes = json.loads(team_athletes)
            except (json.JSONDecodeError, TypeError):
                team_athletes = []
        for entry in team_athletes if isinstance(team_athletes, list) else []:
            printed = entry.get("name") if isinstance(entry, dict) else entry
            printed = (printed or "").strip()
            if not printed:
                continue
            person_id = person_by_printed.get(printed)
            if not person_id:
                links_unresolved += 1
                continue
            supabase.table("as_result_person_link").upsert(
                {
                    "result_table": "as_meet_routine_result",
                    "result_id": row["id"],
                    "person_id": person_id,
                    "athlete_name": printed,
                    "confidence": 1.0,
                },
                on_conflict="result_table,result_id,athlete_name",
            ).execute()
            links_added += 1

    print(f"  Links written:              {links_added}")
    print(f"  Left unresolved (no person): {links_unresolved}")

    # Step 10: Summary
    print("\n[Step 10] Summary")
    print(f"  Clubs matched (existing):  {len(club_map)}")
    print(f"  Clubs created (new):       {new_clubs_created}")
    print(f"  People created:            {people_created}")
    print(f"  Swimmer memberships added: {inserted}")
    print(f"  Swimmer memberships exist: {skipped}")
    print(f"  Result-person links:       {links_added}")
    print(f"  Errors:                    {errors}")

    # Per-club breakdown
    clubs_with_athletes = defaultdict(int)
    for a in unique_athletes:
        clubs_with_athletes[a["club_id"]] += 1

    print(f"\n  Swimmers per club:")
    for cid, count in sorted(clubs_with_athletes.items(), key=lambda x: -x[1]):
        cname = next(
            (c["name"] for c in existing_clubs if c["id"] == cid),
            next(
                (cn for cn, ci in club_id_map.items() if ci == cid),
                "Unknown"
            )
        )
        print(f"    {cname}: {count} swimmers")

    if links_unresolved:
        print(f"\n  {links_unresolved} printed name(s) had no as_person row and were")
        print("  left unlinked on purpose: a name is not an identity, and guessing")
        print("  would merge two swimmers who share one. Add the person, then re-run.")

    print("\n  Reminder: as_daily_aggregations is a materialized view. After linking,")
    print("  refresh it:  SELECT refresh_as_daily_aggregations();")

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
