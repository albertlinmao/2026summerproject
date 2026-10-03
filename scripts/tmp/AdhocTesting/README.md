# Ad-hoc testing / diagnostic scripts

Throwaway probes used while developing. They are **not** a test suite and are
deliberately **not** named `test_*.py`: pytest collects that pattern, and these
scripts connect to a database or run requests at import time, so collection
failed. The uniform `check_*` prefix keeps them out of pytest's way and makes
"this is an ad-hoc probe, not a test" obvious from the filename.

Writers live in [`../AdhocDataMigration/`](../AdhocDataMigration/).

## Prerequisites

Copy the repository `.env.example` to `.env` and fill in what you need. Every
script fails with a clear message rather than defaulting to a host, because a
defaulted connection string is how a scratch script ends up pointed at
production. Scripts needing the backend also expect it to be running:

```bash
cd backend && uvicorn src.main:app --reload
```

## Offline (no database, no backend)

| Script | What it checks |
| --- | --- |
| `check_judge_panel_regex.py` | The judge-panel name regex against a known PDF text block. |
| `check_routine_pdf_parse.py` | The real `parse_routine_pdf_text` from `scripts/ingest_routines.py` against a dumped text file. |

## Database

| Script | What it checks |
| --- | --- |
| `check_tables.py` | Lists `as_*` objects, and flags anything still using an unprefixed legacy name. |
| `check_table_columns.py` | Columns of the core tables, with an explicit list of columns that a past fix added - a miss here is real migration drift. |
| `check_data.py` | One club's swimmers (via the `as_athlete` view), results, coach, and bridge-row counts. |
| `check_athletes.py` | Distinct printed names for a team, and how many resolved to a person. |
| `check_schema.py` | One row from each result table via the Supabase client. |
| `check_db_meets_teams.py` | Walks event -> meet -> team. |
| `check_db_uuid_query.py` | What a non-uuid value does against a `uuid` column (a silent no-op filter is easy to misread as "no data"). |

## Backend

| Script | What it checks |
| --- | --- |
| `check_api_http.py` | Login + full dashboard payload over real HTTP. |
| `check_dashboard_team_overview.py` | Drills into `widgets.team_overview.athletes`. |
| `check_client_results_browser.py` | Results browser via `TestClient`, unauthenticated. |
| `check_client_auth_override.py` | Results browser with a **faked** caller, to test the authorization branch. Set `FAKE_CLUB_ID`. |
| `check_client_login_flow.py` | Results browser after a **real** login - the only one that exercises authentication. |

## What "empty" usually means

An empty dashboard is far more often a data problem than an authorization one.
The aggregation path is
`as_meet_*_result -> as_result_person_link -> as_daily_aggregations`, and any
result row without a link row is **dropped**, not guessed at. In order:

1. `check_table_columns.py` - did the migrations apply?
2. `check_athletes.py` - do printed names have link rows?
3. `check_data.py` - are there `as_club_membership` rows with status
   `invited`/`active`? A `dormant` or `left` membership grants no access.
4. Only then suspect the auth layer, and use `check_client_auth_override.py`.
