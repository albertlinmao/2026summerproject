# Implementation Summary: Artistic Swimming Analytics Platform

Authoritative sources live with the specs; this file is the operational entry point.

| Concern | Source of truth |
| --- | --- |
| Identity and authorization | `specs/001-analytics-dashboard/identity-contract.md` |
| Entity/field reference | `specs/001-analytics-dashboard/data-model.md` |
| API surface | `specs/001-analytics-dashboard/contracts/openapi.yaml` |
| Schema | `backend/supabase/migrations/` (apply in timestamp order) |
| Ad-hoc migration + probe scripts | `scripts/tmp/AdhocDataMigration/`, `scripts/tmp/AdhocTesting/` |

---

## 1. What was built

### 1.1 Identity model: Person / Club / Membership

A person is a human, a club is the tenant, and membership is the edge between them.

- `as_person` has **no `club_id`**. Belonging to a club is a row in `as_club_membership`.
- `as_person_identity` is an optional 1:1 link from a person to the auth subject (`sub`).
  Minors, alumni and dormant swimmers exist as people with no account at all.
- `as_athlete` and `as_coach` are **views** over `as_person + as_club_membership`; neither is
  ever written to, and neither carries a `club_id`.
- Roles are club-scoped: `admin | coach | swimmer | parent | official`, with statuses
  `invited | active | dormant | left`. `title` is free text for display and never authorizes.
- Only the JWT `sub` is trusted. `person_id`, `club_ids` and `roles_by_club` are a **cache**;
  `core/auth.py` re-reads membership from the database before granting anything.
- Imported result rows are immutable. Identity is resolved through `as_result_person_link`,
  unique on `(result_table, result_id, athlete_name)`. A name is not an identity, so an
  unresolvable printed name is left unlinked and counted, never guessed.

### 1.2 Ingestion

| Concern | Detail |
| --- | --- |
| Figure results | `scripts/ingest_figures.py` — parses judge panels and per-figure scores |
| Routine results | `scripts/ingest_routines.py` — parses routines, team assignments, judge panels |
| Table | `as_meet_figure_result` / `as_meet_routine_result` |
| Panels | `as_meet_judge_panel` (keyed by meet and figure) |
| Dimensions | `as_event`, `as_meet`, `as_figure` |
| Lineage | `athlete_name` / `athlete_birth_year` on the result tables are **deliberately not renamed** |
| Analytics | `as_daily_aggregations` materialized view, refreshed via `refresh_as_daily_aggregations()` |

> The aggregation view resolves results **through** `as_result_person_link` and drops anything it
> cannot resolve. Seeding data without populating that bridge yields a silently empty dashboard.

---

## 2. Developer session: local smoke test

Steps are ordered by dependency; do not skip ahead. Paths are given relative to the **repository
root** unless a step says otherwise.

### 0. Prerequisites

- **Docker Desktop** running. That is the whole database story — **there is no Supabase CLI in
  this setup.** The stack is the official self-hosted Docker Compose project in `supabase/`,
  started with `docker compose`. Do not run `supabase start` / `supabase db reset`; the CLI is not
  installed and the compose project is the supported path.
- **Node** — the installed `v24.12.0` is **below Angular 22's floor of `>= v24.15.0`**, so
  `npm start` in the frontend will refuse to run. Upgrade Node, or use the container path in
  step 4, which pins Node 22.
- **Python 3.11+** with `pip install -r requirements.txt` (`pdfplumber`, `psycopg2-binary`,
  `python-dotenv`, `supabase`, `requests`).

Copy the environment template and fill it in:

```bash
cp .env.example .env
```

| Variable | Purpose |
| --- | --- |
| `SUPABASE_URL` | `http://localhost:8000` — Kong, the only HTTP entry point to the stack |
| `SUPABASE_SERVICE_ROLE_KEY` | Required by the loaders — service-role **bypasses RLS**, so an anon key cannot insert into the RLS-protected identity tables |
| `DATABASE_URL` | `postgresql://postgres:<password>@localhost:5432/postgres` |
| `PGHOST` / `PGPORT` / … | Alternative to `DATABASE_URL`; the ad-hoc scripts assemble a DSN from these. **`DATABASE_URL` wins** if both are set, so the two must not disagree. |
| `USER_SERVICE_JWT_SECRET` | Required to sign a demo token; without it login returns **503** |

> The key fallback order is `SUPABASE_SERVICE_ROLE_KEY → SUPABASE_SERVICE_KEY →
> SUPABASE_ANON_KEY → SUPABASE_KEY`, identical to `backend/src/core/database.py`. This repo's
> existing `.env` carries the legacy `SUPABASE_KEY`; prefer the explicit name so it is obvious
> which credential is in play. **Rotate** every credential that was ever committed — the Postgres
> password and the service-role JWT that used to be hardcoded in the root scripts are in git history.

> **`host.docker.internal` vs `localhost` — the existing `.env` is set up for containers.** The
> committed `.env` currently holds `SUPABASE_URL=http://host.docker.internal:8000`, which is correct
> *inside* a container and **does not resolve from a host process** on Docker Desktop. So:
>
> | How you run the backend | `SUPABASE_URL` | `DATABASE_URL` host |
> | --- | --- | --- |
> | `docker compose up backend` (step 3) | `http://host.docker.internal:8000` | `host.docker.internal` |
> | `uvicorn` on the host (step 3) | `http://localhost:8000` | `localhost` |
>
> The current `.env` has no `DATABASE_URL` and no `PG*` at all. The backend therefore falls back to
> the corrected `5432` default, but the **ad-hoc scripts will raise `MissingConfig`** — they read
> `os.environ` directly and do not go through `Settings`, so they need `DATABASE_URL` or `PGHOST`
> set explicitly. Add them from `.env.example` before running anything under `scripts/`.

### 1. Start Supabase (Docker Compose)

Run from the **`supabase/` directory** — the compose file resolves `.env` and `./volumes/**`
relative to the project directory, and `supabase/.env` is what supplies every port and secret.

```bash
cd supabase
docker compose up -d
docker compose ps          # wait until db and kong report healthy
```

Do **not** add `-f ./dev/docker-compose.dev.yml`. That overlay **rebuilds Studio from source** —
`build.context: ..` with `dockerfile: apps/studio/Dockerfile` — and there is no `apps/` directory
anywhere in this repository, nor a root `package.json` for that build to use. Compose resolves `..`
against the project directory, so it looks for `<repo root>/apps/studio/Dockerfile`; run from
`supabase/dev/` it would look for `supabase/apps/studio/Dockerfile`. Neither exists, so `up` fails
at build time and takes the whole start down with it. The base `docker-compose.yml` is the working
configuration.

| Service | Host port | Notes |
| --- | --- | --- |
| Kong (REST / auth / storage / realtime) | **8000** | also 8443 for TLS; `SUPABASE_URL` points here |
| Postgres | **5432** | `POSTGRES_PORT=5432` in `supabase/.env` |
| Supavisor pooler | 6543 | transaction mode |
| Studio | *not published* | no `ports:` in the base compose file, and the overlay that adds `8082` is the broken one |
| Inbucket (mail) | *absent* | only in the dev overlay; see the auth-email note below |

Verify Kong is serving:

```bash
curl http://localhost:8000/rest/v1/ -H "apikey: <ANON_KEY from supabase/.env>"
```

> **Port collision.** Kong takes host port **8000**, which is also the backend's default. Either run
> the backend in Docker (the root `docker-compose.yml` publishes it on **18081**), or move the
> backend to another port. `SUPABASE_PUBLIC_URL` and `API_EXTERNAL_URL` in `supabase/.env` both
> assume 8000, so changing Kong's port means changing those too.
>
> **Auth email.** `ENABLE_EMAIL_AUTOCONFIRM=false` and `SMTP_HOST=supabase-mail`, but the base
> compose file has no `mail` service, so confirmation mail cannot be delivered. This does not block
> the smoke test, which authenticates against the demo stub in `backend/src/api/auth.py` rather than
> Supabase Auth.
>
> `FUNCTIONS_VERIFY_JWT=false`, so the edge functions do not require a bearer token.

### 2. Apply the migrations

The `db` service mounts only Supabase's own init scripts — **the project migrations are not applied
automatically**. Apply the one schema script:

1. `20260827_all_schema_from_scratch.sql` — every table, view, materialized view, function, trigger,
   index, RLS policy and grant, in one file, applicable to an empty database.

`20260826_person_identity_migration.sql` also remains, but it is **not** a schema file. It is the
one-way *data* transform for databases still holding the legacy `as_athlete` / `as_coach` tables, and
the only way to convert them; a fresh database never needs it. A database in the legacy state below
applies it **after** the schema script.

The schema script is standalone and idempotent; re-running it is not a substitute for step 2 of the
legacy transform.

#### The live database is on the LEGACY schema — read this before you run anything

Postgres **is** running on `5432` and holds real ingested data. As of this writing it is
**pre-identity-migration**:

| | Present in the live DB | Absent (created by the chain) |
| --- | --- | --- |
| Legacy | `as_athlete` (469 rows), `as_coach`, `as_team`, `as_team_member`, `as_video_uploads`, `as_video_markers`, `as_routine_timers`, `as_predictive_insights`, `as_coaching_recommendations` | |
| Imported results | `as_event` (3), `as_meet` (4), `as_figure`, `as_meet_judge_panel`, `as_meet_figure_result` (681), `as_meet_routine_result` (0) | |
| `as_club` | 58 rows, columns `(id, name)` **only** | |
| Identity | | `as_person`, `as_person_identity`, `as_club_membership`, `as_person_link`, `as_result_person_link`, `as_competition_result` |

**Good news: the schema script is fully idempotent, so applying it on top of this database is the
intended path, not a mistake.** Every `CREATE TABLE` is `IF NOT EXISTS`, every `ADD COLUMN` is
guarded, and constraints go through `DO $$ … IF NOT EXISTS` blocks. So the seven already-present
tables are *skipped* rather than clobbered, and the identity tables are created alongside them.
`20260826` then, in order:

1. Adds `code` / `city` / `created_by` to the existing 2-column `as_club` and backfills `code`.
2. Backfills `as_person` from `as_athlete` / `as_coach`, splitting `name` on the last space.
3. Backfills `as_club_membership` (`role='swimmer'` / `'coach'`, `status='active'`) from their
   `club_id`.
4. **Then** `drop table if exists public.as_athlete, public.as_coach` and recreates both as *views*
   over `as_person` + `as_club_membership`.

The backfill is guarded by `to_regclass('public.as_athlete') is not null` and runs **before** the
drop, and the live data supports it: all 469 athletes have a non-null `club_id` spanning all 58
clubs, and none has a blank `name`. Expect roughly 469 `as_person` and 469 `as_club_membership` rows
afterwards. The name split is heuristic ("last token = family name") and is expected to need
hand-correcting.

> **Do not run this against a database you have not backed up.** Step 4 above is destructive to the
> legacy tables by design. `pg_dump` first, or use the reset path below on a scratch volume.
>
> **Name splitting is lossy in one specific way:** a single-token name (`"Madonna"`) yields
> `given_name='Madonna'` and `family_name=NULL`, and a blank name is skipped entirely. Neither is
> fatal, but both mean `as_person` row count can be lower than the legacy count.

#### Apply them

`psql` is not needed on the host — use the one inside the container:

```bash
cd supabase
docker compose exec db psql -U postgres -d postgres -c '\dt public.*'
```

From PowerShell, pipe the file in (PowerShell has no `<` redirection):

```powershell
cd supabase
Get-Content ..\backend\supabase\migrations\20260827_all_schema_from_scratch.sql -Raw |
  docker compose exec -T db psql -v ON_ERROR_STOP=1 -U postgres -d postgres
```

That is the whole schema. Apply `20260826_person_identity_migration.sql` afterwards only if the
database still holds the legacy `as_athlete` / `as_coach` tables.

> **The `postgres` password is not `postgres`.** `supabase/.env` sets a different
> `POSTGRES_PASSWORD`, and `docker compose exec db psql` authenticates as the `postgres` superuser
> over the container's local socket, so it works without one — but the **host-side** `DATABASE_URL`
> in your root `.env` must carry the real password, or every query fails with
> `password authentication failed for user "postgres"`. That is the current state: the root `.env`
> has no `DATABASE_URL` at all and the backend falls back to the `postgres:postgres` default, which
> is wrong. Copy the password out of `supabase/.env` into `DATABASE_URL` before step 3.
>
> Beware: a failed database connection currently surfaces as **`409 Demo club not found`**, not a
> 500, from `POST /api/auth/login`, so a wrong password looks like missing seed data. That is a
> defect in the login path's error handling, not a sign you did step 2 wrong.

`-v ON_ERROR_STOP=1` matters: without it `psql` carries on after an error and you get a
half-applied schema that looks fine.

> The database image is `supabase/postgres:15.8.1.085` — **PostgreSQL 15**. `supabase/config.toml`
> in the same directory claims `major_version = 16`; that file is a leftover from the CLI
> workflow and is not what the running container uses.
>
> `supabase/reset.sh` looks like the obvious teardown, but it is broken: it invokes the broken dev
> overlay, and it can only restore `.env` from a `supabase/.env.example` that does not exist. A
> `supabase/.env.old` in the tree suggests it was run once. To reset by hand:
> `docker compose down -v` from `supabase/`, then recreate `supabase/.env` before starting again.

Confirm the identity core exists:

```sql
select table_name from information_schema.tables
 where table_name in ('as_person','as_club','as_club_membership','as_person_identity',
                      'as_result_person_link')
 order by table_name;
```

### 3. Start the backend

FastAPI (`uvicorn src.main:app`). **Use port 8080, not 8000** — Kong already owns host port 8000
for the Supabase stack, and the two cannot bind the same port. 8080 is also clear of `8001`, which
`frontend/src/environments/environment.ts` reserves for `userServiceUrl`. The container path
avoids the question entirely by publishing on 18081.

```bash
# local, on 8080 to stay clear of Kong (8000) and of userServiceUrl (8001)
cd backend
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8080
```

```bash
# containerised (adds Redis; publishes 18081 -> 8000)
docker compose up --build backend
```

Either way the backend reads the stack from `.env` — point `SUPABASE_URL` at `http://localhost:8000`
(Kong) and `DATABASE_URL` at port `5432`. `backend/src/core/config.py` now defaults to exactly
those, so the defaults are safe; set the variables explicitly anyway, because the containerised run
needs `host.docker.internal` in place of `localhost` (see the note in step 0). The container's
listens on `8000` internally, so `--port 8080` above is only for the host run.

Verify — `/health` is unauthenticated and needs no database:

```bash
curl http://127.0.0.1:8080/api/health          # local run
curl http://127.0.0.1:18081/api/health         # containerised
curl http://127.0.0.1:8080/openapi.json        # 29 paths
```

### 4. Start the frontend

```bash
cd frontend
npm install
npm start                 # ng serve --host 0.0.0.0 --port 4200
```

Open `http://localhost:4200`. Or run the nginx image on `8081`:

```bash
docker compose up --build frontend
```

The frontend calls the backend at `http://127.0.0.1:8080/api` (`environment.ts`), so run the
backend on the port from step 3. `environment.ts` also carries `supabaseUrl`, which must point at
Kong — `http://localhost:8000`, **not** the CLI default `54321`.

The API gateway is an Edge Function at `supabase/functions/api-gateway/`. It forwards `X-Person-Id`
and comma-separated `X-Club-Ids` (it does **not** use the old `X-User-Id` / `X-Tenant-Id`) and
authenticates with `GATEWAY_PSK`. It is not required for local UI work, which talks to the backend
directly.

> It will **not** run in the Docker stack as configured. The `functions` service mounts
> `./volumes/functions` and starts `--main-service /home/deno/functions/main`, and that `main`
> directory holds Supabase's stock hello-world function, not this gateway. The gateway has to be
> copied into `supabase/volumes/functions/` (or the mount changed) to be served.

### 5. Load scores

**Fastest path — demo seed.** Creates people, memberships, six meets of figure *and* routine
results, and populates `as_result_person_link`, then calls the refresh:

```bash
python scripts/tmp/AdhocDataMigration/generate_demo_data.py
```

**Real PDFs:**

```bash
python scripts/ingest_figures.py  "swim-meets/2026/.../Detailed_-_Age_Group_12_and_Under_Figures.pdf" --dry-run
python scripts/ingest_figures.py  "swim-meets/2026/.../Detailed_-_Age_Group_12_and_Under_Figures.pdf"
python scripts/ingest_routines.py "swim-meets/2026/.../routines.pdf"
```

Always `--dry-run` first. Then link results to people and refresh the aggregation:

```bash
python scripts/tmp/AdhocDataMigration/load_athletes_clubs.py
```

```sql
SELECT refresh_as_daily_aggregations();
```

The materialized view is **not** auto-refreshed; skip this and the dashboard stays empty.

### 6. Register / activate a club as a tenant

There is **no `POST /api/auth/register-club` endpoint yet** — the `auth` router implements only
`/auth/login` and `/auth/me`. Provision the tenant directly, and note the ordering constraint:
`as_club.created_by` references `as_person`, so the administrator is created first.

```sql
-- 1. the administrator (a person is not a login)
INSERT INTO as_person (id, given_name, family_name)
VALUES ('11111111-1111-4111-8111-111111111111', 'Ada', 'Admin') RETURNING id;

-- 2. the tenant
INSERT INTO as_club (id, name, code, city, created_by)
VALUES ('22222222-2222-4222-8222-222222222222', 'Seattle Synchro', 'SST', 'Seattle',
        '11111111-1111-4111-8111-111111111111') RETURNING id;

-- 3. activate them: the membership edge is what grants access
INSERT INTO as_club_membership (person_id, club_id, role, status)
VALUES ('11111111-1111-4111-8111-111111111111',
        '22222222-2222-4222-8222-222222222222', 'admin', 'active');
```

`code` is the stable short handle the app keys on — `results_browser` selects it and demo login
resolves a club by it before falling back to `name`. It is `NOT NULL UNIQUE`.

To create the clubs that the ingest scripts expect instead of by hand:

```bash
python scripts/tmp/AdhocDataMigration/create_club.py
```

### 7. Register a coach, an athlete, or a parent

A membership needs three rows, and the three roles differ **only** in `as_club_membership.role`.
Note the role vocabulary: a swimmer's role is `'swimmer'`, not `'athlete'`.

```sql
-- a person
INSERT INTO as_person (id, given_name, family_name, birth_date)
VALUES ('33333333-3333-4333-8333-333333333333', 'Ava', 'Athlete', '2013-05-04') RETURNING id;

-- their edge to the club: role is 'swimmer' | 'coach' | 'parent'
INSERT INTO as_club_membership (person_id, club_id, role, status)
VALUES ('33333333-3333-4333-8333-333333333333',
        '22222222-2222-4222-8222-222222222222', 'swimmer', 'active');

-- optional: link them to an auth subject so they can log in
INSERT INTO as_person_identity (person_id, subject_id)
VALUES ('33333333-3333-4333-8333-333333333333', '<subject uuid>');
```

Reuse the same shape for a coach (`role = 'coach'`) or a parent (`role = 'parent'`). `title` may
be set for display only — it never authorizes.

`scripts/user_mgmt_sync.py` is the intended integration point for real registration, because the
auth subject is owned by the external user service. It calls that service over HTTP, so it is not
usable against the local stack.

### 8. Log in as coach, athlete, or parent

`POST /api/auth/login` is a **local demo stub** in `backend/src/api/auth.py`: it authenticates
against a hardcoded `_DEMO_USERS` dictionary, and it returns **404** entirely when
`APP_ENV=production`. It mints an HS256 token that `core/auth.py` really does verify — it is a
stub, not a second identity system.

Exactly one account ships out of the box:

| Email | Password | Role | Club |
| --- | --- | --- | --- |
| `sophie.lin@sst.example.com` | `demo123` | `coach` | `SST` |

```bash
curl -X POST http://127.0.0.1:8080/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"sophie.lin@sst.example.com","password":"demo123"}'
```

The response `user` is **snake_case** — `person_id`, `club_ids`, `roles_by_club` — matching the
contract. `person_id` is `null` and `club_ids` is `[]` until that subject has an
`as_person_identity` row; the UI is expected to show an unprovisioned state rather than a club.

**To smoke-test an athlete or a parent you must add them to `_DEMO_USERS`** in
`backend/src/api/auth.py`:

```python
"ava.athlete@sst.example.com": {
    "password": "demo123",
    "name": "Ava Athlete",
    "club_code": "SST",
    "club_name": "Seattle Synchro",
    "roles": ["swimmer"],          # 'admin' | 'coach' | 'swimmer' | 'parent' | 'official'
    "permissions": ["read:dashboard", "read:analytics"],
},
```

Then link the row. The stub derives the subject deterministically as
`uuid5(NAMESPACE_URL, "sst-demo-subject:<email>")`, and login only resolves a person when
`as_person_identity.subject_id` equals it:

```bash
python -c "import uuid; print(uuid.uuid5(uuid.NAMESPACE_URL, 'sst-demo-subject:ava.athlete@sst.example.com'))"
# c2872095-c8ce-5367-af2d-239c65be565d
```

```sql
INSERT INTO as_person_identity (person_id, subject_id)
VALUES ('33333333-3333-4333-8333-333333333333', 'c2872095-c8ce-5367-af2d-239c65be565d');
```

Also give the person a membership in the club `code = 'SST'` — **claims are a cache, so a token
with `club_ids` and no `as_club_membership` row still authorizes nothing.** Verify with:

```bash
curl http://127.0.0.1:8080/api/auth/me -H "Authorization: Bearer $TOKEN"
```

### 9. Run the smoke test

`scripts/tmp/AdhocTesting/` holds 14 read-only probes. Start with the offline ones, then work
outward — the folder README has the full triage order for "the dashboard is empty".

The three `check_client_*` scripts use FastAPI's `TestClient`, so they need the backend
*importable* but **not** running.

```bash
# offline - no database, no network, no backend
python scripts/tmp/AdhocTesting/check_judge_panel_regex.py     # panel name regex vs sample text
python scripts/tmp/AdhocTesting/check_routine_pdf_parse.py     # real routine parser -> JSON
python scripts/tmp/AdhocTesting/check_client_auth_override.py  # faked caller; set FAKE_CLUB_ID

# database
python scripts/tmp/AdhocTesting/check_tables.py                # as_* objects; spot old unprefixed names
python scripts/tmp/AdhocTesting/check_table_columns.py         # column-level drift; did the migration land?
python scripts/tmp/AdhocTesting/check_data.py                  # as_athlete / as_coach project correctly?
python scripts/tmp/AdhocTesting/check_athletes.py              # printed names in the imported results
python scripts/tmp/AdhocTesting/check_schema.py                # one row per result table + the link bridge
python scripts/tmp/AdhocTesting/check_db_uuid_query.py         # what a non-uuid filter really does
python scripts/tmp/AdhocTesting/check_db_meets_teams.py        # event -> meet -> team via Supabase

# backend via TestClient - no server needed
python scripts/tmp/AdhocTesting/check_client_login_flow.py     # real login, exercises the auth path
python scripts/tmp/AdhocTesting/check_client_results_browser.py  # unauthenticated: expects 401

# backend over HTTP - server must be running (step 3)
python scripts/tmp/AdhocTesting/check_api_http.py              # login + /auth/me + dashboard payload
python scripts/tmp/AdhocTesting/check_dashboard_team_overview.py  # drills into team_overview.athletes
```

The HTTP and login probes read the password from `DEMO_PASSWORD` rather than embedding it:

```bash
DEMO_PASSWORD=demo123 python scripts/tmp/AdhocTesting/check_api_http.py
```

A coach only sees swimmers in clubs they hold a membership in — `check_dashboard_team_overview.py`
expects **403** for a club the caller is not a member of, not a silent fallback.

---

## 3. Known gaps

Blocking the runbook above:

- The Supabase stack is **Docker Compose in `supabase/`**, not the CLI. Nothing here depends on the
  Supabase CLI, and `supabase/reset.sh` should not be used: it invokes `dev/docker-compose.dev.yml`,
  which rebuilds Studio from `apps/studio/Dockerfile` — a path that does not exist in this repository
  (there is no `apps/` directory at all), so the build fails — and it can only restore `.env` from a
  `supabase/.env.example` that is also
  missing. A `supabase/.env.old` in the tree suggests it was run once, before those files went away.
- **The Supabase stack is up, and the database is on the legacy schema.** Postgres answers on `5432`
  as `15.8`, holding 58 clubs / 469 athletes / 681 figure results across 4 meets. None of the five
  migrations has been applied to it, so no `as_person` / `as_club_membership` /
  `as_result_person_link` exists yet and `as_club` is still `(id, name)`. Step 2 is the first real
  test of the chain. The chain is idempotent and its `as_athlete` → `as_person` backfill fits this
  data, so applying it in place should work — but step 4 of that migration drops the legacy tables,
  so back up first. Full inventory in step 2.
- **The root `.env` cannot currently reach the database.** It has no `DATABASE_URL`, and the
  `postgres:postgres` default in `config.py` is not the password `supabase/.env` sets — the result
  is `password authentication failed`, which the login path reports as a misleading
  `409 Demo club not found`. Fix `.env` before step 3.
- `20260820_full_schema.sql` contained an unterminated `$$` that made the whole file unapplicable;
  it is fixed (see the 2026-09-27 session in `Prompts to build a dashboard.md`), but applying the
  chain in step 2 is the first real test of it.
- **Config defaults still assume the CLI.** `backend/src/core/config.py` defaulted `SUPABASE_URL` to
  `http://localhost:54321` and `DATABASE_URL` to port `54322`;
  `frontend/src/environments/environment.ts` set `apiUrl` to `http://127.0.0.1:8000/api` — which is
  Kong's port, not the backend's — and `supabaseUrl` to `http://localhost:54321`; `.env.example` set
  `PGPORT=5432` beside a `DATABASE_URL` on `54322`. All four have been corrected to the Docker stack's
  `8000` / `5432`. `scripts/tmp/_ad_hoc_common.py` was already correct: it holds no port default at
  all, deferring to `DATABASE_URL` or the `PG*` variables.
- **Port collision:** Kong (`8000`) versus the backend's default (`8000`). Step 3 resolves it with
  `8080`; the container path publishes `18081`.
- **Studio has no published port** in the base compose file, so there is no UI for running the
  migrations by hand — use `psql` in the container, as step 2 shows. The overlay that would publish
  `8082` is the broken one.
- **No mail service in the base compose file** while `SMTP_HOST=supabase-mail` and
  `ENABLE_EMAIL_AUTOCONFIRM=false`, so Supabase Auth cannot deliver a confirmation email. Harmless
  for this smoke test, which does not use Supabase Auth, but it will bite anyone who tries to sign
  up through Kong's `/auth/v1` endpoints.
- **Node `v24.12.0` < Angular 22's `>= v24.15.0`** blocks `npm start`. Node 22 is pinned in
  `frontend/Dockerfile`, which satisfies the floor, so the container path works today.
- **The edge gateway does not run in the Docker stack** — the `functions` service serves
  `supabase/volumes/functions/main`, which is Supabase's stock hello-world, not
  `supabase/functions/api-gateway/`.
- **No registration endpoints.** Club and person provisioning is SQL; only `/auth/login` and
  `/auth/me` exist. `design.md` still describes `POST /api/auth/register-club` and `/auth/clubs`
  as planned.
- **Login is a hardcoded demo stub** with one account, so an athlete or parent smoke test
  requires a code edit plus a matching `as_person_identity` row.
- `20260820_full_schema.sql` creates an RLS policy for `as_competition_result` but does not define
  the table — it only works as part of the ordered chain.
- The upload path authorizes an eligible guardian to upload, while the insert policy shown appears
  staff-only; upload as a parent will fail until the policies are reconciled.
- The external user service still enforces `UNIQUE (tenant_id, user_id)`, which blocks true
  multi-club membership issuance.
- `api/user-management/` is a broken, unregistered submodule path that still contains a
  historical credential. It is out of scope for edits but the credential must be rotated.

Housekeeping:

- `scripts/test_j5.py`, `scripts/test_j5_positions.py` and `scripts/test_parse.py` are still named
  `test_*.py`, so a bare `pytest` at the repo root collects them.
- `backend/fix_analytics.py` is a second copy of the dead codemod deleted from the root, and
  `backend/enhance_matching.py` is an abandoned one-shot codemod still referencing `athlete_id`.
- `.merge_file_F8223D` is a 37 KB tracked merge-conflict artifact in the repo root.
- `backend/tests/` contains no `test_*.py`; there is no meaningful automated backend suite.
