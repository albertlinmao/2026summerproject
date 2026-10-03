# Ad-hoc data migration scripts

One-off scripts that **write** to the database: provisioning the identity core,
loading people and memberships from imported PDF results, and seeding demo data.

Read-only diagnostics live in [`../AdhocTesting/`](../AdhocTesting/).

## Before running anything

1. Copy the repository `.env.example` to `.env` and fill it in. These scripts
   read credentials from the environment; there are no credentials in the source.
2. Apply the migrations first. The canonical chain is
   `backend/supabase/migrations/`, in timestamp order. These scripts assume the
   schema exists - `create_club.py` mirrors a little DDL so it can bootstrap a
   bare database, but that is a convenience, not a replacement.
3. Point `DATABASE_URL` / `PG*` at a **scratch** database. Two of these scripts
   delete rows.

## Scripts

| Script | What it does |
| --- | --- |
| `create_club.py` | Creates `as_person`, `as_club` and the identity core if absent, then inserts one `as_club` row per SST team code found in the imported results. |
| `load_athletes_clubs.py` | Reads `as_meet_figure_result` / `as_meet_routine_result`, creates an `as_person` per distinct printed name, adds a `swimmer` membership per club, then populates `as_result_person_link`. |
| `generate_demo_data.py` | Seeds the SST club, six swimmers, one coach and six meets of results, then links every result row to its person. |

## Identity model

`specs/001-analytics-dashboard/identity-contract.md` is authoritative. The three
rules these scripts exist to respect:

- **A person has no `club_id`.** The person-to-club edge is
  `as_club_membership`, and it is the authorization source of truth.
- **`as_athlete` and `as_coach` are views.** Never insert into them; they
  project over `as_person` + `as_club_membership`.
- **Imported results are immutable.** A result row keeps the printed name
  (`athlete_name`, `team_athletes`) exactly as the PDF printed it. Attaching a
  result to a canonical human happens *only* in `as_result_person_link`, keyed on
  `(result_table, result_id, athlete_name)` - all three columns, because every
  athlete in a routine's array shares one `result_id`.

## After loading

`as_daily_aggregations` is a materialized view built from the bridge table, so it
will be stale (or empty) until refreshed:

```sql
SELECT refresh_as_daily_aggregations();
```

`check_data.py` in the sibling folder prints the bridge row counts and will tell
you whether anything resolved.
