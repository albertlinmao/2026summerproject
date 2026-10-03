# Load Artistic-Swim Meet Results (Figures / Routines) into Supabase

Step-by-step guide for loading meet result PDFs into the local Supabase stack
using the existing ingest scripts.

## 1. What the scripts do

| Script | Purpose | Tables written |
|---|---|---|
| `scripts/ingest_figures.py` | Parse figure result PDFs (e.g. `Detailed_-_..._Figures.pdf`) | `as_meet`, `as_event`, `as_meet_figure_result`, `as_meet_judge_panel` |
| `scripts/ingest_routines.py` | Parse routine result PDFs (team/duet/solo finals) | `as_meet`, `as_event`, `as_meet_routine_result`, `as_meet_judge_panel` |

`as_meet_figure_result.athlete_name` / `athlete_birth_year` and
`as_meet_routine_result.team_athletes` are verbatim fields from the PDF and keep
their names as data lineage. They are not identity references. The canonical
person behind a result row is recorded in `as_result_person_link`.

Both also provision **user-management records** via `scripts/user_mgmt_sync.py`:

- New club found in the PDF → new `tenant` + default roles/permissions
  (`PLATFORM_ENGINEER`, `ORG_ADMIN`, `ORG_USER`) + dashboard mirror `as_club`.
- Every printed swimmer name → an `as_person` row, an `as_person_identity` row
  (`subject_id` = the Supabase Auth user id), a Supabase Auth user (default
  password `Defaul$Pa66word`), `user_profile` (PII encrypted), `membership`, and
  an `as_club_membership` row with role `swimmer`, status `active`.
- Routines only → swimmers added to the team in `as_team` / `as_team_member`
  per the routine's team assignment.
- New tenant → mints a tenant API key into `tenant_api_keys` (printed once,
  e.g. `ssk_live_xxxxxx.<secret>`; only the bcrypt hash is stored). This key is
  how the dashboard will later identify a user's club/tenant.

A person has no `club_id` and a login is optional — see
`specs/001-analytics-dashboard/identity-contract.md`. `as_athlete` and
`as_coach` are **views** over `as_person` + `as_club_membership` and are never
written to.

> **Blocking dependency (identity service).** `public.membership` in
> `api/user-management/supabase/migrations/01_initial_schema.sql` is declared
> `unique (tenant_id, user_id)`, which makes multi-club membership impossible.
> It must become `unique (tenant_id, user_id, role_id)` (or be replaced by a
> membership-per-role structure). Until that lands, provisioning works
> single-club in practice. See identity-contract.md section 4.

All user-mgmt writes are **idempotent** (safe to re-run). Result rows are
inserted freshly each run (existing behavior).

## 2. Prerequisites

- Local Supabase stack is **running** (Docker Desktop + `docker compose up`).
- Python 3.10+ with a virtual environment at the project root (`.venv`).
- The repository's env/config files are present as checked in.

## 3. One-time setup

The identity model must be in place first — apply
`backend/src/supabase/migrations/20260826_person_identity_migration.sql` (creates
`as_person`, `as_person_identity`, `as_club_membership`, `as_person_link`,
`as_result_person_link`, and the `as_athlete` / `as_coach` views). The sync script
expects those tables and will not create them.

```powershell
# 1. From the project root
cd C:\Users\linma\workspace\02-learning-AI\2026summerproject

# 2. Create & activate the virtual environment (first time only)
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # activate for this shell

# 3. Install dependencies
python -m pip install -r requirements.txt
```

Verify deps: `pdfplumber`, `requests`, `python-dotenv`, `psycopg2-binary`,
`bcrypt`.

## 4. Prepare the configuration

The scripts read configuration from two env files (already committed; verify
they exist):

- **`.env`** (project root, used for the REST/Auth API)
  - `SUPABASE_URL` → `http://host.docker.internal:8000` (must resolve;
    the script rewrites `host.docker.internal` → `localhost`)
  - `SUPABASE_KEY` → the service-role key (survives `email_confirm`, mints
    auth users). Falls back to `SUPABASE_SERVICE_ROLE_KEY` / `SERVICE_ROLE_KEY`.
- **`supabase/.env`** (used for direct Postgres writes)
  - `POSTGRES_PASSWORD` → the local DB password
  - `POSTGRES_HOST` → `db` (script rewrites to `localhost`), `POSTGRES_PORT`,
    `POSTGRES_DB` (default `postgres`)

No changes needed if you use the checked-in values. If you change them, keep the
two files in sync with the values the Supabase stack was started with.

## 5. Put the PDFs in place

Engine results PDFs live under `swim-meets\<yyyy>\<meet_name>`.

```text
swim-meets/
  2026/
    20260321_Classic_Snohomish_WA/
      Age Group 12 and Under Figures.pdf          <- figures (ingest_figures.py)
      Age Group 12 and Under Team Free Final.pdf  <- routines (ingest_routines.py)
```

Recommended filename conventions:
- Figures: `*Figures.pdf` (or any "Detailed" figure sheet)
- Routines: `*Final.pdf` / `*Prelims.pdf` (team/duet/solo/combination sheets)

## 6. Load a FIGURE results PDF

```powershell
# Dry run first — prints the parse, writes nothing
python scripts\ingest_figures.py "swim-meets\2026\20260321_Classic_Snohomish_WA\Age Group 12 and Under Figures.pdf" --dry-run

# Real load
python scripts\ingest_figures.py "swim-meets\2026\20260321_Classic_Snohomish_WA\Age Group 12 and Under Figures.pdf"

# Re-import the same PDF after a parser fix — required, otherwise the load is refused
python scripts\ingest_figures.py "swim-meets\2026\20260321_Classic_Snohomish_WA\Age Group 12 and Under Figures.pdf" --replace-source
```

Expected output:

```text
Processing: <path>
  event : <EVENT>
  date  : <D> <MON> <YYYY>   city: <CITY>
  meet  : <MEET>
  figures: <N>
  judges : <N>
  results: <N>
  created event, created meet          <- or "reused event, reused meet"
  [user-mgmt] provisioned tenant + default roles for club '<CLUB>'      (only for new clubs)
  [user-mgmt] API key for <CLUB> (tenant <id>): ssk_live_xxxxxx.<secret>  (only for new clubs)
  [user-mgmt]   store it now --- only the bcrypt hash is saved.
  [user-mgmt] ensured person '<NAME>' (<name>@<club>.swim, person <person_id>) in club '<CLUB>'

[OK] <path>

1 ok, 0 skipped, 0 failed or refused (1 file(s))
```

If a club already exists, you will **not** see `provisioned tenant` or a new
API key — the users are reused/memberships ensured.

### Flags

| Flag | Effect |
|---|---|
| `--dry-run` | Print the parse (event, meet, figure/judge/result counts, warnings). Writes nothing and touches no table. |
| `--replace-source` | Delete this PDF's existing result rows for the meet, then re-import. Without it a re-ingest is **refused**. |
| `--allow-empty` | Permit a PDF that parses to zero results. Without it the load is refused, because that normally means the PDF layout drifted. |

The exit code is `0` only when every file succeeded. `REFUSED` and `FAILED`
both mean a non-zero exit, so a scheduled run can tell a clean import from a
failed one.

### Two refusals worth knowing

- **Already ingested.** Results for this PDF are already on the meet. Nothing is
  written. Duplicate result rows cannot be corrected afterwards, because
  `forbid_result_updates()` blocks the `UPDATE` that would fix them — they have to
  be deleted. Use `--replace-source`, or clear the whole event with
  `sql/03_clear_event_data_by_eventid.sql`.
- **The meet is ambiguous or shared.** The same meet name already has two rows in
  the event, or the meet already holds results from a *different* PDF. The load
  stops rather than adding a third meet or destroying the other file's rows.

Warnings printed during a load are data problems, not noise. `unreadable score
'-.-' stored as NULL` means the sheet marked that figure as not performed; the old
parser wrote a fabricated `0.0` there instead.

## 7. Load a ROUTINE results PDF

```powershell
# Dry run
python scripts\ingest_routines.py "swim-meets\2026\20260321_Classic_Snohomish_WA\Age Group 12 and Under Team Free Final.pdf" --dry-run

# Real load
python scripts\ingest_routines.py "swim-meets\2026\20260321_Classic_Snohomish_WA\Age Group 12 and Under Team Free Final.pdf"
```

Same output shape as figures, plus:
- team assignment is provisioned (`as_team` + `as_team_member`, role `ATHLETE`);
- a routine team's swimmers come from the `team_athletes` list in the PDF.

### The routine score arithmetic is not finished

`as_meet_routine_result` is still empty on the live database — this path has never
completed an import, which is why the problems below went unnoticed.

- **`synchronization_total` is NULL on every row.** The parser used to write the
  STC deduction into this column, which put `-15.9667` in a column that means a
  total, with three STC lines racing for the same field. The deduction is still
  recorded, in `routine_scores`, where it belongs.
- **Some sheets lose their score lines.** The `ACRO` / `Choreo and Music` /
  `STC` patterns only match a line carrying either zero or two trailing numbers,
  and the detailed sheets carry one. Those lines are dropped, so
  `element_total`, `artisticimpression_total` and `routine_score` come out too
  low. The load prints a warning naming how many lines were dropped, because the
  failure is otherwise invisible — the row looks complete.
- The figure path has a related open question: the trailing value on the first
  `Fig #1` row (e.g. `63.9867`) is stored as that figure's `figure_score` **and**
  as the athlete's, while figures 2-4 get `NULL`. What that column represents has
  not been established, so it has not been "fixed" by guessing.

Neither has been changed by inventing a number. Confirming the intended column
semantics is a domain question, not a regex tweak.

## 8. Load multiple PDFs at once

Pass several paths in one command:

```powershell
python scripts\ingest_figures.py `
  "swim-meets\2026\20260321_Classic_Snohomish_WA\Age Group 12 and Under Figures.pdf" `
  "swim-meets\2026\20260321_Classic_Snohomish_WA\Novice 10 and Under Figures.pdf" `
  --dry-run
```

Or load **all figure sheets for one meet** via the existing helper:

```powershell
# Loads every matching PDF in a meet folder
.\swim-meets\Load_PDF_competition_results_2_DB.ps1            # real load
.\swim-meets\Load_PDF_competition_results_2_DB.ps1 -DryRun    # preview
```

(That helper currently targets a hard-coded 2025 meet folder — edit line 21 for
the meet you want.)

## 9. Verify the data

Check the loaded rows and provisioned records:

```powershell
docker exec -it supabase-db psql -U postgres -d postgres -c "SELECT name, team_code FROM as_club ORDER BY created_at;"
docker exec -it supabase-db psql -U postgres -d postgres -c "SELECT count(*) FROM as_meet_figure_result;"
docker exec -it supabase-db psql -U postgres -d postgres -c "SELECT count(*) FROM as_meet_routine_result;"
docker exec -it supabase-db psql -U postgres -d postgres -c "SELECT person_id, role, status FROM as_club_membership LIMIT 20;"
```

Or browse locally: **Supabase Studio** → http://localhost:8000 (Table Editor /
SQL Editor).

User-management records to check (same DB):
- `tenant`, `role`, `role_permission`, `membership`, `user_profile`
- `as_person`, `as_person_identity`, `as_club_membership` (the dashboard identity core)
- `as_team`, `as_team_member` (routines)
- `tenant_api_keys` (one active row per new club, hashed)

## 10. Use the tenant API key later

The printed `ssk_live_<prefix>.<secret>` is the value a dashboard caller will
present as `Authorization: Bearer <key>`. `resolve_tenant_api_key()` in
`scripts/user_mgmt_sync.py` looks it up by prefix, verifies the bcrypt hash,
checks `status='active'`/expiry, and returns the `tenant_id` — the club the key
belongs to, i.e. the tenant being provisioned. It is *not* the set of clubs a
logged-in user may act in: that is resolved from `as_club_membership` via the
`club_ids` / `roles_by_club` claims and a membership lookup
(identity-contract.md section 4). Only the hash is stored, so save the plaintext
key somewhere safe when it is printed.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: pdfplumber` / `bcrypt` / `psycopg2` | Re-run `python -m pip install -r requirements.txt` (active venv) |
| `Failed to insert to Supabase` / connection refused | Supabase stack not running → `docker compose up -d` in `supabase\`; wait for health |
| Auth create-user failed on first club load | `SUPABASE_KEY` in `.env` is not the service-role key; update it from `supabase/.env: SERVICE_ROLE_KEY` |
| `File not found:` | Path is relative to your current directory — use a full or repo-root-relative path (see step 6 examples) |
| Nothing inserted for a PDF | Some results sheets are event *summaries*; use the "Detailed" figure sheet or the Final/Prelims routine sheet |
| Wrong date/city parsed | The parser reads header lines 1-3 of the PDF text; use sheets that start with event name / meet name / city + date |
| Missing `pii_encryption_key` vault secret | User-profile inserts require the Supabase vault key present in the local DB (from the user-management migrations) |