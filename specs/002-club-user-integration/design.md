# Design: Club / Coach / Athlete / Parent User Integration

**Feature**: `002-club-user-integration`
**Created**: 2026-09-16
**Corrected**: identity model aligned to
[`specs/001-analytics-dashboard/identity-contract.md`](../../001-analytics-dashboard/identity-contract.md),
which is authoritative. See §1.1 for the audit trail.
**Status**: Design (not started — this document precedes implementation)
**Applies to**: `001-analytics-dashboard` (dashboard app) + `001-multi-tenant-user-api` (user-management service)

---

## 1. Purpose

Rearchitect how the analytics dashboard identifies people. Today the dashboard is
single-club, demo-authenticated, and has no concept of *teams* or *parents*. This
design makes the **user-management service** the issuer of identity and the holder of
the org model, and makes the dashboard resolve **authorization from its own
`as_person` / `as_club_membership` tables** rather than from the token.

The three facts that drive every decision below:

1. **A person has no `club_id`.** Belonging to a club is a row in `as_club_membership`.
   One login does not imply one club.
2. **A login is optional.** `as_person_identity` may be absent. Minors, dormant
   swimmers and alumni are full members of the model with no account and no
   credentials. *This is the central reason the design changes* — a login-centric
   model cannot represent a child at the club without inventing credentials for them.
3. **Roles are scoped per club.** The same `person_id` may be a `swimmer` in club A and
   a `coach` in club B. Authorization is always (person, club, role).

Decisions locked with the owner (2026-09-16):

| Decision | Choice |
|---|---|
| Deliverable | **Design doc only** (this document) — no code yet |
| Unapproved users login? | **No.** Approval gate: pending users cannot log in |
| Org model ownership | **User-management service owns all org data** (clubs, mapping, teams, family links); dashboard keeps lightweight `as_*` reference mirrors |

### 1.1 Correction of the earlier model (audit trail)

The first draft of this document (2026-09-16) described a **single-club, login-centric**
identity: one user == one row, a `club_id` on the person, a flat `role_type`, and
guardianship encoded in a JWT claim. **That model is wrong** and has been corrected to
match `identity-contract.md`. Nothing was implemented against it, so the cost of the
correction is this document; the equivalent SQL work has already landed in the dashboard
schema (§4.2), so the design is written against the corrected schema rather than
proposing the transform.

What changed, and why the earlier choice was wrong:

| Area | Earlier (2026-09-16) | Corrected | Why the earlier choice was wrong |
|---|---|---|---|
| Person ↔ club | `as_athlete.club_id` / `as_coach.club_id`; `unique (tenant_id, user_id)` in the user service | Person carries **no** `club_id`; club membership is a row in `as_club_membership` | One login then implies one club. A parent with children at two clubs, or a swimmer at one club and a coach at another, is unrepresentable. The user-service constraint is a **bug**, not a policy — §4.1.1. |
| Login | Every person is an account | A login is **optional**; `as_person_identity` may be absent | Minors, dormant swimmers and alumni are full members of the club but cannot hold credentials. Forcing an account either blocks them or invents logins for children. |
| Roles | `role_type in ('COACH','ATHLETE','PARENT')`, one per user | `role` ∈ `admin｜coach｜swimmer｜parent｜official` (lowercase), **per club**, plus display-only `title` | Authorization must be (person, club, role). A single flat role cannot express "swimmer here, coach there". `title` is how `Lead Coach` / `Team Captain` / `Club Owner` survive as UI vocabulary without granting any power. |
| Guardian access | `athlete_ids` JWT claim + `jwt_linked_athlete_ids()` | `as_person_link(parent_person_id, child_person_id, club_id, kind)`, resolved by `app_is_guardian_of(parent, child, club)` | A claim is minted at login and goes stale, so a link added or revoked after issuance is not enforced until the token expires. It also cannot express coach-of or self. |
| RLS | Replace `current_user_club_id()` table lookups with `(auth.jwt()->>'club_id')::uuid` | **Membership is authoritative; claims are a cache** | If the token is the authority, a removed coach keeps access until expiry and emergency revocation is impossible. Offboarding and role changes must take effect on the next request. |
| Identity tables | `as_athlete` / `as_coach` with **no RLS**, read directly by policies | `as_person` / `as_person_identity` / `as_club_membership` / `as_person_link` with RLS; every membership read inside a policy goes through a `SECURITY DEFINER` helper | World-readable identity rows let any caller enumerate every swimmer and parent in the database. And a policy that selects from an RLS-protected table recurses into itself, so the reads have to be indirected. |

**Alternatives considered**

- *Keep one active club per login and re-issue the token when the club changes.*
  Rejected: it turns a club switch into a server-side act and leaves a stale,
  over-privileged token valid in the meantime. Multi-club is normal in this domain, so
  the constraint buys nothing and costs a revocation path.
- *Read club scope from `as_club_membership` but keep `athlete_ids` in the token.*
  Rejected: the claim and the table then disagree, and the table is the one that is
  correct. Two sources of truth means one of them is eventually wrong.
- *Keep `as_athlete` as a table with an `id`, mirroring `as_person`.* Rejected — see
  §4.2.1: projecting one `club_id` collapses a multi-club person into several rows.
- *Drop the user service and keep identity entirely in the dashboard.* Rejected: the
  dashboard would then own credentials and PII, which it has no business holding. The
  split is issuance (user service) versus authorization (dashboard), and the correction
  sharpens that split rather than reversing it.

---

## 2. Current State (Gap Analysis)

### 2.1 What exists

**Dashboard app** (`backend/`, `frontend/`)
- FastAPI on `:8080` (Kong owns `:8000`; the container path publishes `:18081`), reading the local Docker Compose Supabase stack (`:8000` Kong/PostgREST, `:5432` Postgres).
- Analytics tables `as_event`, `as_meet*`, `as_*video*`, `as_routine_timers`, widgets.
  Reference stubs were `as_club(id, name)`, `as_athlete(id, club_id, name)`,
  `as_coach(id, club_id, name)` — the login-centric shape, now replaced (§4.2).
- Two divergent auth paths:
  - `core/auth.py` — **verified** JWT (`RS256` JWKS or HS256 shared secret), claims `sub, club_id, roles, athlete_ids, permissions`; provides `get_current_user`, `require_role`, `require_club_access`.
  - `api/auth.py` — demo `POST /auth/login` (HS256, hardcoded demo user, `iss="sst-demo-auth"`); and an insecure `verify_jwt` (signature skipped, reads `uid`) used by insights/markers/uploads/timers.
- RLS resolves club scope by looking up `as_coach` / `as_athlete` — which themselves
  carried **no RLS**, so the lookup itself read world-readable rows; family video
  access uses `auth.jwt() -> 'athlete_ids'` via `jwt_linked_athlete_ids()`.
- Frontend: Angular 22 standalone, Material M3. Login page, `AuthService` (signals + localStorage), `authGuard` / `roleGuard`, shell with user menu/logout. **No** registration/onboarding pages. **No** Parent role anywhere. Club/team pages exist but are dead routes/placeholders. `environment.ts` already defines `userServiceUrl: http://localhost:8001` (unused).
- **Identity transform already landed in the schema** (before this design):
  `backend/supabase/migrations/20260826_person_identity_migration.sql` migrates
  existing databases; `backend/supabase/migrations/20260820_full_schema.sql` is
  rewritten and is what a fresh install gets. This design is written against that
  corrected schema, not against the login-centric one.

**User-management service** (`api/user-management/`)
- FastAPI on `:8001`, owns its own Supabase stack.
- Tables: `tenant`, `user_profile` (FK `auth.users`, pgcrypto-PII-encrypted), `role`, `permission`, `role_permission`, `membership`, `audit_log`.
- APIs: `POST/GET /api/v1/tenants`, `GET/POST /api/v1/users`, `GET/POST /api/v1/roles`, `GET /api/v1/audit`, auth webhook.
- Trust model: Supabase Edge Function validates JWT, injects `X-Tenant-Id` / `X-User-Id`; FastAPI requires `X-Internal-Secret`. `POST /tenants` (onboarding) bypasses JWT.
- User lifecycle already models `INVITED → ACTIVE → SUSPENDED / SOFT_DELETED`. Onboarding creates the auth user as `email_confirm: true` and always `email_confirm` on create — there is **no approval gate yet**.
- Feature flags gate onboarding (`tenant-onboarding`) and GDPR.

### 2.2 Gaps vs. target

1. Club ≠ tenant. `as_club` is a local reference, not sourced from `tenant`; the dashboard has no membership feed from the user service.
2. The user service's `membership` table declares `unique (tenant_id, user_id)`, so a person can hold exactly one club. **Blocking dependency** — §4.1.1.
3. The user service models a person only as a `user_profile` row, i.e. as an account. There is no person-without-login, so minors, dormant swimmers and alumni cannot be represented. §4.1.
4. No approval workflow — users are created active; no approve/deny.
5. Login is a mock; the dashboard never authenticates against the user-management service.
6. No club/user registration pages; no Parent role or UI.
7. The dashboard has `as_club_membership` / `as_person_link` tables but **nothing populates them** — the transform created the schema, not the feed. §8.
8. Insecure legacy `verify_jwt` path (`uid` claim) coexists with the verified path. Two divergent auth paths in one backend is itself a defect — §9.

---

## 3. Target Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ Browser (Angular SPA)                                           │
│  /login  /register  /register-club  /dashboard/*                │
└──────────────┬──────────────────────────────────────────────────┘
               │ HTTPS (JWT Bearer)
┌──────────────▼──────────────────────────────────────────────────┐
│ Dashboard Backend (FastAPI :8000)  =  BFF + Analytics           │
│  /api/auth/*     → proxies public identity flows to user svc    │
│  /api/auth/me    → sub → as_person_identity → memberships       │
│  /api/analytics/* /results/* ... scope by membership, not claims│
│  SyncService     → mirrors scheduler(persons/clubs/membership→  │
│                    as_*); guards resolve via app_*() RLS helpers│
└──────────────┬──────────────────────────────────────────────────┘
               │ HTTP + X-Internal-Secret (+ X-Person-Id/X-Club-Ids for admin calls)
┌──────────────▼──────────────────────────────────────────────────┐
│ User-Management Service (FastAPI :8001)  =  issuer of identity │
│  auth (login/token mint) · tenants(clubs) · users · membership · │
│  teams · person links · approve/deny · roles · audit            │
│  Supabase Auth (identity) + Postgres (org model)                │
└──────────────┬──────────────────────────────────────────────────┘
               │ auth.users / tenant / membership / as_* org tables
┌──────────────▼──────────────────────────────────────────────────┐
│ Supabase (user-service stack)                                   │
└─────────────────────────────────────────────────────────────────┘
```

Principles:
- **Single source of truth for issuance:** the user-management service and its DB own
  the auth subject, the org model, and the RS256 keypair. The dashboard never mints a
  non-dev token and never stores credentials.
- **Single source of truth for authorization:** `as_club_membership` in the dashboard
  DB. Authorization is always evaluated as (person, club, role).
- **Claims are a cache, never the authority.** The dashboard verifies the signature
  and then reads the database. Of the token, RLS trusts exactly one claim — `sub`, to
  find `as_person_identity.person_id`. Everything else is UI convenience. This is what
  makes offboarding and role changes effective on the next request instead of at token
  expiry.
- **A login is optional.** Persons with no `as_person_identity` are full members of the
  model. A minor is reached through a guardian's session, not through a fabricated
  account.
- **The dashboard stores no PII.** `as_person` holds names and `birth_date` for display
  and analytics joins; credentials and encrypted contact details stay in the user
  service. Membership *is* mirrored, because authorization has to be resolvable
  locally.
- **No secrets in the browser**: public registration/login flows go through the
  dashboard BFF; only the backend holds `X-Internal-Secret`.
- Dashboard legacy tables (`as_meet_*_result`) stay as-is (competition records,
  immutable). Their literal `athlete_name` / `athlete_birth_year` fields keep their
  names as lineage; the canonical reference is `as_result_person_link` and a nullable
  `person_id` FK.

---

## 4. Data Model Changes

### 4.1 User-management service DB (new migration `05_org_model.sql`)

All in the user-service Postgres (its Supabase instance). PII stays encrypted in
`user_profile`; org tables hold UUIDs + non-PII (names of teams/clubs are fine, but
keep sign-ups minimal).

The vocabulary is **not** re-invented here — it is fixed by
[`identity-contract.md` §2](../../001-analytics-dashboard/identity-contract.md) and
mirrored into the dashboard:

- `role` ∈ `admin | coach | swimmer | parent | official` — lowercase, coarse, drives RLS.
- `title` — free text, **display only** (`Club Owner`, `Lead Coach`, `Team Captain`).
  Never authorizes anything.
- `status` ∈ `invited | active | dormant | left`. `invited` and `active` grant access;
  `dormant` and `left` do not.

A person may hold **several** memberships. There is no `club_id` on a person anywhere
in this model.

```
tenant (exists)                          -- a club == one tenant row
user_profile (exists)                    -- one row per auth.users.id; status drives approval

-- A person exists independently of an account. This is the user-service counterpart
-- of as_person: minors, dormant swimmers and alumni have no login and no credentials,
-- and must still be representable. birth_date (not birth_year) is a property of the
-- human, not of a club, which is why it cannot live on a club-scoped profile row.
as_person (
  id          uuid primary key default gen_random_uuid(),
  given_name  text not null,
  family_name text,
  middle_name text,
  birth_date  date,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
)
create index idx_as_person_name on as_person (lower(family_name), lower(given_name));

-- The only link to an account. Absent for a person with no login.
-- user_profile.id is the auth.users id, so this is the service-side equivalent of
-- as_person_identity.subject_id -- the sole link to the identity provider, never a
-- business key, never exposed in API payloads.
as_person_identity (
  person_id  uuid primary key references as_person(id) on delete cascade,
  user_id    uuid not null unique references user_profile(id) on delete cascade,
  created_at timestamptz not null default now()
)

-- Club record; id is the SAME value as tenant.id (club == tenant).
as_club (
  id   uuid primary key references tenant(id) on delete cascade,
  name text not null
)

-- The tenant-scoped edge. Authorization source of truth.
-- One person, many rows: swimmer in club A, coach in club B, parent in club C.
as_club_membership (
  id          uuid primary key default gen_random_uuid(),
  person_id   uuid not null references as_person(id) on delete cascade,
  club_id     uuid not null references as_club(id) on delete cascade,
  role        text not null check (role in ('admin','coach','swimmer','parent','official')),
  title       text,   -- display only: 'Club Owner', 'Lead Coach', 'Team Captain'
  status      text not null default 'invited'
              check (status in ('invited','active','dormant','left')),
  approved_by uuid references as_person(id),
  approved_at timestamptz,
  joined_at   date,
  left_at     date,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
)
create unique index uq_as_club_membership_active
  on as_club_membership (person_id, club_id, role) where status in ('invited','active');
create index idx_as_club_membership_club   on as_club_membership (club_id, status);
create index idx_as_club_membership_person on as_club_membership (person_id);

-- Guardian edge, scoped to a club. Replaces the old as_family_link.
-- The child is a *person*, not necessarily an account: a 9-year-old has no login and
-- still has a parent who can see their footage. The link is also club-scoped, because
-- guardianship is a fact about a club community, not a global fact.
as_person_link (
  id               uuid primary key default gen_random_uuid(),
  parent_person_id uuid not null references as_person(id) on delete cascade,
  child_person_id  uuid not null references as_person(id) on delete cascade,
  club_id          uuid not null references as_club(id) on delete cascade,
  kind             text not null default 'parent'
                   check (kind in ('parent','guardian','emergency_contact')),
  created_at       timestamptz not null default now(),
  check (parent_person_id <> child_person_id)
)
create index idx_as_person_link_child on as_person_link (child_person_id, club_id, kind);

-- Teams; each team has one designated lead coach (a person, not necessarily an account).
as_team (
  id            uuid pk default gen_random_uuid(),
  club_id       uuid not null references tenant(id) on delete cascade,
  name          text not null,
  lead_coach_id uuid references as_person(id),
  created_at    timestamptz not null default now(),
  unique (club_id, name)
)

-- Team membership. A swimmer can be on many teams. 'CAPTAIN' is a designation, not a
-- role, so it lives in title -- roles are the closed set that drives RLS.
as_team_member (
  id         uuid pk default gen_random_uuid(),
  team_id    uuid not null references as_team(id) on delete cascade,
  person_id  uuid not null references as_person(id) on delete cascade,
  title      text check (title is null or title = 'Team Captain'),
  created_at timestamptz not null default now(),
  unique (team_id, person_id)
)
```

Approval rule: **a login is served only when `user_profile.status = 'ACTIVE'` and the
caller holds at least one `as_club_membership` with `status in ('invited','active')`**.
Register → person + `as_person_identity` + `as_club_membership(status 'invited')`.
Approve → `status = 'active'`, `approved_by/at`. Deny → `status = 'left'` and the auth
user is suspended. Leaving a club sets `status = 'left'` + `left_at`; pausing sets
`dormant`. None of these wait for a token to expire, because none of them are in the
token (§5.3).

Reconciliation of the user-service tables:

| Table | Role | Purpose |
|---|---|---|
| `user_profile` | account (auth, encrypted PII) | credentials + lifecycle `INVITED/ACTIVE/SUSPENDED/SOFT_DELETED` |
| `as_person` | the human | names, `birth_date`; exists with or without a login |
| `as_person_identity` | account ↔ person | absent when the person has no login |
| `as_club_membership` | club roster + approval + role | `(person, club, role, status)` — the authorization edge |
| `as_person_link` | family | guardian edges inside one club |
| `as_team` / `as_team_member` | teams | club-scoped; captain is a `title` |

Removed tables and why:

| Removed | Replaced by | Reason |
|---|---|---|
| `user_status` | `as_club_membership.status` | Its only content beyond approval was a single `role_type` per user (`user_id` primary key) — that is the one-role-per-user assumption, which is exactly what multi-club per-role authorization replaces. Approval state now lives on the membership it approves. |
| `as_club_member` | `as_club_membership` | Renamed, and dropped `first_name`/`last_name`/`email` display copies (PII stays in `user_profile`) and its `id = user_profile.id`, which structurally permitted one row per user. |
| `as_club_role` | `as_club_membership.role` + `.title` | `OWNER` → `role='admin'` + `title='Club Owner'`; `LEAD_COACH` → `role='coach'` + `title='Lead Coach'`. Roles must stay a closed set because RLS branches on them; designations are display. |
| `as_athlete_profile` | `as_person.birth_date` | It put a person attribute (`birth_year`) next to a `club_id`, i.e. it re-created the person-is-a-club-scoped-row mistake. Swimming status is a `swimmer` membership; the date of birth is on the person. |
| `as_family_link` | `as_person_link` | Re-keyed from `user_profile` to persons, so a child with no account can be linked, and scoped to a club so the link means something inside one community. |

#### 4.1.1 Blocking dependency: `public.membership`

`api/user-management/supabase/migrations/01_initial_schema.sql` declares
`public.membership` with **`unique (tenant_id, user_id)`**.

**That constraint is a bug, not a design choice.** It makes multi-club membership
impossible: a parent with children at two clubs, or a coach in one club and a swimmer
in another, cannot be represented at all. It must become

```
unique (tenant_id, user_id, role_id)
```

or `public.membership` must be replaced by the
`as_person` / `as_person_identity` / `as_club_membership` shape above.

This change lives in **`api/user-management`, a separate repository**, and is therefore
out of scope for the dashboard and for this feature's implementation. It is recorded
here as a **blocking dependency**, not as work: no dashboard estimate should include
it, and no dashboard code should work around it.

Until it lands, the dashboard operates single-club *in practice* (a person can hold only
one membership upstream, so `as_club_membership` will only ever have one `club_id` per
person). The RLS predicates in `20260820_full_schema.sql` are already written for the
multi-club case — `app_current_club_ids()` returns an array and every predicate is
`= any (...)` — so relaxing the upstream constraint requires **no** dashboard change.
That is the reason the schema was written for the multi-club case while the
authoritative source still cannot produce one.

### 4.2 Dashboard tables (person / club / membership)

The login-centric → person/membership transform has already landed in the dashboard
schema, in two places:

- `backend/supabase/migrations/20260826_person_identity_migration.sql` — for
  **existing** databases. One-way and idempotent: a no-op on a database that is already
  at the target schema, so it is safe to re-run.
- `backend/supabase/migrations/20260820_full_schema.sql` — **rewritten** to the
  same target state. This is what a **fresh install** gets; it is the definition, not a
  superset of the migration.

**One canonical chain.** All five dashboard migrations live in
`backend/supabase/migrations/` and apply in timestamp order:

| Migration | Role |
|---|---|
| `20260804_initial_schema.sql` | `as_club`, the identity tables, `as_result_person_link`, the `as_athlete` / `as_coach` views, the `app_*()` authorization helpers, the imported result tables |
| `20260819_dashboard_tables.sql` | `as_daily_aggregations`, predictive insights, coaching recommendations, results-browser widget |
| `20260819_video_and_timer.sql` | `as_video_uploads`, `as_video_markers`, `as_routine_timers` |
| `20260820_full_schema.sql` | Standalone full schema — every table, helper, policy and grant in one file |
| `20260826_person_identity_migration.sql` | Forward transform for databases already on the old schema |

The identity tables, `as_result_person_link`, and the `app_*()` helpers are declared in
`20260804` — the first migration — because `CREATE POLICY` parses and analyses its
expression at creation time, so a policy in a later file cannot call a helper that a later
file has not defined yet. `20260820` re-declares all of them with `CREATE OR REPLACE`, so
applying that file alone still yields a complete schema and a normal ordered apply is a
no-op for those statements.

The chain was previously split across `backend/supabase/migrations/` and
`backend/src/supabase/migrations/`, with the latter's `20260820_full_schema.sql`
duplicating every table in the former. That duplication is resolved; a second
`backend/src/supabase/` tree no longer exists.

A person belongs to no club. Membership is the edge. `as_club` is unchanged.

```
as_club             (id, name, ...)                                    -- the tenant
as_person           (id, given_name, family_name, middle_name,
                     birth_date, created_at, updated_at)               -- no club_id, no credentials
as_person_identity  (person_id pk, subject_id unique, created_at)      -- OPTIONAL
as_club_membership  (id, person_id, club_id, role, title, status,
                     joined_at, left_at, created_at, updated_at)
as_person_link      (id, parent_person_id, child_person_id, club_id, kind, created_at)
as_result_person_link (id, result_table, result_id, person_id, athlete_name,
                       confidence, resolved_by, resolved_at)
as_athlete          -- VIEW (§4.2.1)
as_coach            -- VIEW (§4.2.1)
as_team             (id, club_id, name, lead_coach_id, synced_at)      -- sync mirror
```

`subject_id` is matched against the verified `sub` claim. It is the only link between
the dashboard database and the identity provider, is never a business key, and is never
returned in an API payload.

Every `*.athlete_id` becomes `*.person_id` (insights, recommendations, videos,
aggregations, `as_competition_results_browser_widgets.user_id`), and every
`auth.uid()` in a **data** column (`uploaded_by`, `created_by`, `resolved_by`) becomes
`person_id` referencing `as_person(id)`. `auth.uid()` in **RLS** becomes
`app_current_person_id()`.

Result linkage is `as_result_person_link`, not a fuzzy join: `as_meet_routine_result.team_athletes`
is a JSON array of printed names sharing one `result_id`, so the printed name is the
only intra-row discriminator available and it has to be stored alongside the resolved
`person_id`. `as_meet_figure_result.athlete_name` and `athlete_birth_year` keep their
names — they are lineage fields transcribed from the result PDFs, not identity
references. `birth_date` now lives on `as_person`, not on a club-scoped athlete
profile.

#### 4.2.1 `as_athlete` and `as_coach` are views, with no `club_id` and no `id`

Both become views over `as_person` + `as_club_membership`:

```sql
create view as_athlete as
select p.id as person_id, p.given_name, p.family_name, p.middle_name, p.birth_date,
       btrim(coalesce(p.middle_name || ' ', '') || p.given_name || ' '
             || coalesce(p.family_name, '')) as name
from   as_person p
where  exists (select 1 from as_club_membership m
               where m.person_id = p.id and m.role = 'swimmer'
                 and m.status in ('invited', 'active'));

create view as_coach as
select p.id as person_id, p.given_name, p.family_name, p.middle_name,
       btrim(coalesce(p.middle_name || ' ', '') || p.given_name || ' '
             || coalesce(p.family_name, '')) as name
from   as_person p
where  exists (select 1 from as_club_membership m
               where m.person_id = p.id and m.role in ('coach', 'admin')
                 and m.status in ('invited', 'active'));
```

Exposed columns: `person_id`, `name` (plus the name parts and `birth_date`).
**No `club_id`. No `id`.**

**Why there is no `club_id`.** The view is defined by the *existence* of a membership,
and a membership is per `(person, club, role)`. Projecting one `club_id` out of that
set forces one of two bad outcomes: either a person with a `swimmer` membership in two
clubs appears **twice**, which collapses one human into multiple rows and double-counts
every analytics join that goes through the view; or the view picks one club
arbitrarily, which is simply false for the other club. Neither is acceptable, so club
scope is expressed by joining `as_club_membership` in the query rather than by a column
on the view. Callers that need a club-scoped roster write
`from as_athlete a join as_club_membership m on m.person_id = a.person_id
where m.club_id = ...`. `as_coach` includes `admin` because club admins are staff for
video access (§5.3.2).

**Why there is no `id`.** The old `as_athlete.id` was `auth.users.id`, and
`*.athlete_id` carried that id across the schema — so the same logical entity was called
`user_id` in some places and `athlete_id` in others. `as_person.id` is the person id;
a second name for it invites exactly that conflation. Exposing the column as
`person_id` makes old `athlete_id` call sites fail at the SQL level rather than
silently resolving against the wrong identifier.

#### 4.2.2 The identity tables now have RLS

Previously `as_athlete` / `as_coach` had **no RLS at all** — they were world-readable,
and the club-scope policies read them directly. So any caller who could reach PostgREST
could enumerate every swimmer, every coach and every parent in the database, including
people who have no account. The transform enables RLS on `as_person`,
`as_person_identity`, `as_club_membership`, `as_person_link` and
`as_result_person_link`, with the predicates in §5.3.

The non-obvious constraint this creates: a policy on `as_club_membership` whose
predicate selects directly from `as_club_membership` **recurses into itself**, and
Postgres rejects the policy. Therefore **every membership read inside a policy goes
through a `SECURITY DEFINER` helper function** — never an inline
`exists (select 1 from as_club_membership ...)` against the same table. Writing the
predicate inline is the single easiest way to get this schema wrong, and the failure
mode is a migration that refuses to apply, not a quiet leak.

### 4.3 JWT claims contract (issued by user service, consumed by dashboard)

The dashboard **verifies the signature** and then resolves authorization **from the
database**. Claims are a cache and a convenience, never the authority. The full contract
is `identity-contract.md` §4; this section is the user service's obligation.

#### Required

| Claim | Type | Meaning |
|---|---|---|
| `sub` | uuid string | Opaque tenant-user subject. Must equal some `as_person_identity.subject_id`. **The only claim RLS trusts.** |
| `iss` | string | `"sst-user-service"` |
| `aud` | string | `APP_NAME` of the dashboard (currently `app-name` default — align via `USER_SERVICE_JWT_AUDIENCE`) |
| `exp`, `iat` | number | Standard. |

#### Optional — cache only, never authoritative

| Claim | Type | Meaning |
|---|---|---|
| `person_id` | uuid | Mirror of `as_person_identity.person_id` for the `sub` above. UI use only. |
| `club_ids` | uuid[] | Clubs with an `invited`/`active` membership. Rendered as the club switcher. |
| `roles_by_club` | object | `{ "<club_id>": ["swimmer","coach"] }`. UI route matching only. |
| `permissions` | string[] | Retained for compatibility; the dashboard does not enforce from it. |
| `team_ids` | uuid[] | Teams the person is on. Analytics convenience only. |
| `email`, `name`, `club_name` | string | Display only. |

#### Forbidden / removed

| Claim | Status | Reason |
|---|---|---|
| `athlete_ids` | **forbidden** | Encodes guardianship in the token, so it goes stale and cannot express coach-of or self. Replaced by `as_person_link` + `app_is_guardian_of()`. A new sibling link would not be enforced until the token expired, and revoking one was impossible without a token revocation endpoint. |
| `club_id` (scalar) | **forbidden** | Implies one login equals one club. Replaced by `club_ids` + a membership lookup. |
| `user_id` | renamed | The claim is `sub`; the database column is `person_id`. They are different identifiers and must not be conflated. |
| `tenant_id` | removed | A redundant alias of the old scalar `club_id`. The dashboard does not speak tenant. |
| `roles` (flat array) | removed | A flat role list is the one-role-per-user assumption in claim form; it cannot say which club a role applies to. Replaced by `roles_by_club`. |
| `role_type` | removed | `COACH｜ATHLETE｜PARENT` was a single classification per user. Replaced by per-club `role` + `title` (§4.1). |

A token carrying a forbidden claim is not a valid token for this dashboard. The
conformance test belongs in the user service: mint a token containing `athlete_ids` or a
scalar `club_id` and assert the dashboard rejects or ignores it. A claim that is only
"documented as forbidden" is a claim that will eventually be used.

### 4.4 API keys (tenant-scoped machine access)

New `tenant_api_keys` table (DDL in `api/user-management/supabase/init/tenant_api_keys.sql`):

| Field | Type | Notes |
|---|---|---|
| `id` | uuid pk | |
| `tenant_id` | uuid fk → tenant(id) | key scoped to one tenant, cascade delete |
| `key_prefix` | varchar(16) unique | public lookup portion (e.g. `ssk_live_...`) |
| `secret_hash` | varchar(255) | bcrypt/Argon2id hash of the full secret (never plaintext) |
| `name` | varchar(100) | label, e.g. "Analytics sync worker" |
| `status` | varchar(20) | `active` / `revoked` / `expired` |
| `expires_at` | timestamptz | TTL, NULL = perpetual |
| `last_used_at` | timestamptz | rotation/metrics |
| `created_at` | timestamptz | |

- Partial index `idx_tenant_api_keys_prefix ON tenant_api_keys(key_prefix) WHERE status = 'active'` for fast auth lookups.
- API requests: caller presents `Authorization: Bearer <key_prefix>.<secret>` → service looks up by `key_prefix`, verifies hash, checks status/TTL, updates `last_used_at`, then injects `X-Tenant-Id` for the request.
- RLS enabled; rows only readable/writable by the service role (hashed secrets must not leak).

### 4.5 Default permissions (seeded)

`init/seed_permissions.sql` seeds the `permission` table idempotently
(`ON CONFLICT (resource, action) DO NOTHING`) with system-level defaults:

| Name | `(resource, action)` | Meaning |
|---|---|---|
| `GLOBAL_ADMIN` | `(GLOBAL, ADMIN)` | system admin of the whole system |
| `PLATFORM_ENGINEER` | `(PLATFORM, ENGINEER)` | developer/platform operator of the user-management service |
| `ORG_ADMIN` | `(ORG, ADMIN)` | admin/maintainer of a tenant |
| `ORG_USER` | `(ORG, USER)` | regular tenant user |
| `ORG_GUEST` | `(ORG, GUEST)` | default visitor (no login required) |

---

## 5. API Design

### 5.1 New user-management endpoints (`api/user-management/backend`)

Prefix `/api/v1`. Public endpoints go through the **dashboard BFF** so no secret is
exposed to the browser; the user service still requires `X-Internal-Secret`.

Auth / identity
- `POST /auth/login` — body `{email, password}`. Verifies via Supabase Auth
  (`sign_in_with_password`), then checks the approval gate (§4.1). Mints dashboard JWT
  (RS256, audience = dashboard `APP_NAME`) with claims per §4.3. Returns
  `{access_token, expires_in, person{person_id,name,email}, club_ids, roles_by_club, team_ids, permissions, status}`.
  **No `athlete_ids`, no scalar `club_id`** in the response or the token. Errors:
  `401 INVALID_CREDENTIALS`, `403 PENDING_APPROVAL`, `403 NO_ACTIVE_MEMBERSHIP`
  (valid credentials, but every membership is `dormant`/`left`).
- `POST /auth/register` — public member registration body
  `{email,password,first_name,last_name,club_id,role}` where `role` ∈
  `admin|coach|swimmer|parent|official` (an admin may not self-select `admin`).
  Creates the auth user (confirmed), `as_person`, `as_person_identity`,
  `user_profile` INVITED and one `as_club_membership(status 'invited')`. Optional
  `birth_date` goes on the **person**, not on a club-scoped profile. Returns
  `{person_id, status:"invited"}`.
- `POST /persons` (club admin, Bearer) — **create a person with no login**. This is the
  endpoint that makes minors, dormant swimmers and alumni first-class: body
  `{given_name, family_name, middle_name, birth_date, club_id, role, status}`, returns
  `{person_id}`. No auth user, no credentials, no `as_person_identity` row. Later, if
  the person wants an account, `POST /persons/{person_id}/invite-account` adds the
  identity and the `auth.users` record.
- `POST /auth/register-club` — **alias of `POST /tenants`** (existing onboarding).
  Creates tenant + owner (`as_club_membership` `role='admin'`, `title='Club Owner'`,
  `status='active'`) and returns the same `TenantResponse`; the BFF then mints an owner
  token so the new club admin is logged in.
- `GET /auth/clubs` — public list `{id, name}` for the registration page.
- `GET /auth/me` — the current caller's person, `club_ids`, `roles_by_club` and
  memberships (single source for profile UI and for the sync trigger, §8).

Org administration (tenant-scoped; `admin` membership in that club required — enforced by the
user service's own RLS, not by a claim). The dashboard resolves the target club from
`as_club_membership` and sends the user service a single `X-Tenant-Id`; it does **not** forward
`X-User-Id`, because the gateway no longer mints one (see §9):
- `GET /members?status=&role=&club_id=` — membership list (the approval queue is
  `status=invited`). Keyed on `person_id`, not `user_id`: a member may have no account.
- `POST /members/{person_id}/approve` — sets the membership `status='active'`,
  `approved_by/at`. Audit-logged. Approves a **membership**, not a login.
- `POST /members/{person_id}/reject` — membership `status='left'`; if the person has an
  identity, the auth user is suspended too.
- `DELETE /members/{person_id}` — sets `status='left'` + `left_at`. Effective on the
  caller's next request, because the token does not carry club scope (§5.3).
- `POST /members/{person_id}/roles` — grant/revoke a `role`, and set/clear the display
  `title` (`Club Owner`, `Lead Coach`, `Team Captain`) separately, since the title
  grants nothing.
- `GET /person-links`, `POST /person-links` (link a parent to a child **who may have no
  account**), `DELETE /person-links/{id}`. Body `{parent_person_id, child_person_id,
  club_id, kind}`.
- `GET /teams`, `POST /teams` (create, set `lead_coach_id`), `PATCH /teams/{id}`,
  `POST /teams/{id}/members` (join; optional `title='Team Captain'`),
  `DELETE /teams/{id}/members/{person_id}`.

Existing endpoints reused unchanged: `GET/POST /roles`, `GET /audit`, `GET/POST /users`.

### 5.2 Dashboard BFF (backend `:8000`)

New router `api/auth.py` additions (public, no Bearer required):
- `POST /api/auth/login` → forwards to user-service `POST /auth/login` with
  `X-Internal-Secret`; returns the minted token + user payload verbatim.
- `POST /api/auth/register` → forward member registration.
- `POST /api/auth/register-club` → forward club/tenant registration; on success,
  call `POST /auth/login` with the admin creds and return an owner session token.
- `GET /api/auth/clubs` → forward public club list.

New admin router `api/members.py` + `api/teams.py` (Bearer required; verified via
`core/auth.get_current_user` + `require_club_role(club, ["admin"])`):
- forward to user-service with `X-Internal-Secret` + an `X-Tenant-Id` the dashboard derives
  from the caller's own active membership in the target club. The gateway forwards
  `X-Person-Id` and a comma-separated `X-Club-Ids`; the single tenant header is built here
  because the user service is tenant-scoped while the dashboard is membership-scoped.

`core/auth.py` — claim model changes: parse `person_id` / `club_ids` / `roles_by_club`;
`require_role` gains a **club argument** because a flat role list can no longer express
scope. `require_club_access` becomes "is `club_id` in `club_ids`", and every actual
data query still asks the database, not the claim. The `athlete_ids` branch is deleted
rather than deprecated — no fallback, so no call site keeps quietly using it.

#### 5.2.1 FINDING: two divergent auth paths (defect, must be resolved)

`backend/src/api/auth.py` defines `verify_jwt`, which decodes the bearer token as

```python
jwt.decode(token, "SECRET", algorithms=["HS256"], options={"verify_signature": False})
```

— `verify_signature: False` against a **hard-coded** `"SECRET"`, reading the `uid` claim
and nothing else. It is the dependency for `insights.py`, `markers.py`, `uploads.py`
and `timers.py`. `backend/src/core/auth.py` in the same process verifies properly
(`RS256` via JWKS, or HS256 with a configured secret). A token with **any** well-formed
HS256 body passes `verify_jwt`, so the four routers above are effectively unauthenticated
today, and they are the routers that read analytics and **write video uploads**.

**This is a defect, not a design choice, and it is not resolved by any part of this
document.** Two auth paths in one backend means the security posture is whatever the
weakest dependency says it is, and it differs per route. The required resolution:

- The dashboard must **always verify the signature**. There is no legitimate mode in
  which a data route trusts an unverified token.
- Collapse `api/auth.py:verify_jwt` onto `core/auth.get_current_user` — or delete it and
  re-point the four routers — so there is exactly one verified path. Anything left
  importing `verify_jwt` fails review.
- Demo token minting (`iss="sst-demo-auth"`) stays behind `APP_ENV != production`. That
  is a legitimate dev affordance; skipping verification on a data route is not, because
  it is not gated by anything.
- The unverified path is also a *correctness* problem now: it returns `auth.users.id`,
  whereas RLS resolves `person_id`. Leaving it in place guarantees an endpoint that reads
  rows under a different identity than the browser does.

Recorded as a finding rather than silently dropped, because the same code that is
insecure is also load-bearing for four routers.

### 5.3 RLS (dashboard Supabase)

Authorization is resolved from `as_club_membership`, **never** from a claim. The
`athlete_ids` claim and `jwt_linked_athlete_ids()` are **removed**.
`current_user_club_id()` is replaced by the helper set below — and note the direction of
travel: the earlier draft proposed replacing `current_user_club_id()`'s table lookups with
`(auth.jwt() ->> 'club_id')::uuid`, which is the **opposite** of what is required. Claims
are a cache, so making the token the authority would mean an offboarded coach keeps club
access until the token expires, and a role change takes up to an hour to bite. Membership
is authoritative; only `sub` is read from the token, and only to find
`as_person_identity.person_id`.

#### 5.3.1 Helper functions

| Function | Returns | Purpose |
|---|---|---|
| `app_current_person_id()` | `uuid` | `as_person_identity.person_id` where `subject_id = auth.uid()`. Null when the caller has no identity — the ordinary case for a minor or an alumni record. |
| `app_active_memberships()` | `setof as_club_membership` | The caller's memberships with `status in ('invited','active')`. |
| `app_current_club_ids()` | `uuid[]` | Clubs the caller belongs to. Replaces `current_user_club_id()`, which structurally could only ever return one. |
| `app_has_club_role(club, roles[])` | `boolean` | Membership-authoritative role check. The only way a policy asks "is this person a coach **here**". |
| `app_is_club_staff(club)` | `boolean` | `app_has_club_role(club, array['coach','admin'])`. |
| `app_is_guardian_of(parent, child, club)` | `boolean` | `as_person_link` lookup, kind `parent`/`guardian`. Replaces `jwt_linked_athlete_ids()`. |
| `app_shares_club(person)` | `boolean` | The person and the caller share at least one active membership. The general "may I see this person" predicate. |
| `app_is_active_member(person)` | `boolean` | The person holds an `invited`/`active` membership somewhere. |
| `app_visible_person_ids()` | `uuid[]` | Union of: the caller, everyone in the caller's clubs, and every child linked to the caller within a club. The roster predicate for insights/recommendations. |
| `app_can_view_video(club, person)` | `boolean` | The family-access predicate, composed (§5.3.2). |
| `app_can_edit_video(club, uploaded_by)` | `boolean` | Uploader or club staff. |

Every one of them is declared

```sql
stable security definer set search_path = ''
```

with **fully-qualified** names in the body (`public.as_club_membership`, `auth.uid()`),
owned by a role that bypasses RLS. That is load-bearing, not style, for two separate
reasons:

1. **Recursion.** A policy on `as_club_membership` that reads `as_club_membership`
   re-enters that table's own RLS and Postgres rejects the policy. `security definer`
   executes the read as the owner, so the predicate sees rows without re-entering RLS.
   `security invoker` would hit the same recursion, which is why inlining the `exists`
   is not an optimisation.
2. **Search-path safety.** With `search_path` pinned to empty, an unqualified name cannot
   be resolved out of a schema the caller controls. Fully qualifying every name inside
   the body is what makes the pinning effective.

These functions replace both `current_user_club_id()` and `jwt_linked_athlete_ids()`.

#### 5.3.2 Family video access

`app_can_view_video(club_id, person_id)` is true when **any** of:

1. **coach-of** — `app_is_club_staff(club_id)`.
2. **self** — `person_id = app_current_person_id()` **and**
   `app_has_club_role(club_id, array['swimmer'])`.
3. **guardian-of** — `app_is_guardian_of(app_current_person_id(), person_id, club_id)`,
   i.e. an `as_person_link` of kind `parent`/`guardian` inside that club.

The identical scope is applied to Supabase Storage objects, so a signed URL is bounded
the same way a `select` is. A storage path of `{club_id}/{person_id}/` keeps the object
key consistent with the predicate.

**Why branch 2 requires a membership and not merely an identity.** An identity says
*this browser is this human*; it says nothing about *this club*. Without the membership
test, anyone who has ever held an account at the club — a former swimmer, an alumnus, or
a parent who is herself a `swimmer` on the same team — would gain blanket read access to
every other athlete's footage there. Requiring an active `swimmer` membership in that
same club narrows branch 2 to "my own footage, at a club where I actually swim", which is
the only reading under which a 16-year-old's footage is not visible to a 40-year-old
parent who used to swim at the same club.

**Why a claim could not do this.** `athlete_ids` was computed at login, so a link added
after issuance was not enforced until the token expired, and one that was revoked stayed
live for the remainder of the token's life. It also had no way to express "coach at this
club" or "this is me" — hence a single flat list doing three different jobs. Reading
`as_person_link` on each request makes a link effective immediately, and an emergency
offboarding becomes one `status` update rather than a token revocation.

#### 5.3.3 Policy changes

- `as_person` — `select` when `id = app_current_person_id() or app_shares_club(id)`;
  `update` self only. Note the read scope is club-mates, not everyone: the old
  world-readable table is what let a caller enumerate the whole database.
- `as_person_identity` — readable only by its own person
  (`person_id = app_current_person_id()`). It holds the `auth.users` id, so no policy
  exposes one caller's subject to another.
- `as_club_membership` — `select` for the row's own person or club staff; `insert`,
  `update` and `delete` require `app_has_club_role(club_id, array['admin'])`, and are
  **not** self-service. A caller who could insert their own `admin` membership would have
  a privilege-escalation hole; the write path goes through the user service, which is
  where approval happens.
- `as_person_link` — `select` when the caller is either endpoint or club staff; writes
  `admin` only. Otherwise a parent could attach themselves to any child in the database.
- `as_result_person_link` — `select` when `person_id = any (app_visible_person_ids())`;
  `insert` requires `resolved_by = app_current_person_id()` **and**
  `app_shares_club(person_id)`, so a club member may disambiguate a result for someone
  they share a club with, and may only claim resolutions they made themselves.
- Video tables and storage objects — `app_can_view_video` for `select`,
  `app_can_edit_video` for `update`/`delete`; `uploaded_by` and `created_by` are
  `person_id`.
- Club-scoped tables (widgets, timers) — `club_id = any (app_current_club_ids())` for
  reads, club staff for writes. `auth.uid()` in data columns is now `person_id`.

---

## 6. End-to-End Flows

### 6.1 Club registration (REQ #6)
```
/register-club → BFF POST /api/auth/register-club
  → user-svc POST /tenants (bypass JWT, X-Internal-Secret)
      creates: tenant, owner auth user, user_profile, as_person + as_person_identity,
               as_club_membership(club, role 'admin', title 'Club Owner', status 'active')
  → BFF mint owner token via /auth/login
  → redirect (role admin) → /dashboard/club-admin
```

### 6.2 Member registration (REQ #7)
```
/register (choose club, role coach|swimmer|parent|official) → BFF POST /api/auth/register
  → user-svc creates auth user (confirmed), as_person + as_person_identity,
    user_profile INVITED, one as_club_membership(status 'invited')
  → success page "pending approval"
```
Self-registration cannot create an `admin` membership; that is granted in-club.

### 6.3 Approval (REQ #4)
```
Club admin → /dashboard/club-admin/members (status 'invited' list)
  → POST /members/{person_id}/approve → membership status 'active'
  until then login returns 403 PENDING_APPROVAL ("A club admin must approve you first")
```
Approving acts on a **membership**, so it works identically for a member who registered
themselves and for a person a club admin added without a login.

### 6.4 Login (REQ #5)
```
/login → BFF POST /api/auth/login → user-svc verifies creds + approval gate
  → mint RS256 JWT (aud=APP_NAME, claims §4.3) → browser stores token + person
  → shell renders role-based nav (§7)
  → every Supabase query resolves scope from as_club_membership via app_*() helpers
```
Note the last line: RLS reads the **database**, not the claims. A `club_ids` claim that
has gone stale produces a wrong club switcher option, not over-permission.

### 6.5 Teams (REQ #3)
Club admin creates teams; assigns a lead coach (a person, possibly with no account);
swimmers join 1..n teams; captain is set as `as_team_member.title = 'Team Captain'`.
`team_ids` remains a convenience claim for athlete-team analytics. Lead-coach scoping
is **not** a claim decision — if it is added, it becomes a new
`app_is_team_lead(team)`-style helper reading `as_team`, consistent with §5.3.1.

### 6.6 A person with no login (the reason this design changed)
```
Club admin → /dashboard/club-admin/people → "Add person"
  → POST /persons {given_name:'Mia', family_name:'Novak', birth_date:'2015-04-02',
                   club_id, role:'swimmer', status:'active'}
  → as_person row created. NO auth user. NO as_person_identity. No credentials exist.
  → Mia appears in as_athlete (view), has results, has videos.

Mia's parent → /register → role 'parent' at the same club → approved
  → POST /person-links {parent_person_id: <parent>, child_person_id: Mia,
                        club_id, kind:'parent'}
  → parent's session now passes app_is_guardian_of(parent, Mia, club)
  → parent sees Mia's analytics and Mia's videos at that club, via RLS

Mia is never asked for a password. If she later wants an account, an admin runs
POST /persons/{person_id}/invite-account and an as_person_identity row appears.
```
This is what the earlier `athlete_ids` + `as_athlete.club_id` model could not express:
either Mia has no record, or she has a fabricated account, or her father has to be
modeled as her.

---

## 7. Frontend Design (dashboard SPA)

### 7.1 Pages / routes

| Route | Component | Guard |
|---|---|---|
| `/login` | LoginComponent (rework: call BFF, show "pending approval" error) | public |
| `/register` | New `MemberRegistrationComponent` (club picker + role picker `coach｜swimmer｜parent｜official`) | public |
| `/register-club` | New `ClubRegistrationComponent` (tenant/club registration) | public |
| `/dashboard` | ShellComponent (club switcher + role-based redirect) | authGuard |
| `/dashboard/coach` | CoachDashboardComponent | `admin` in selected club |
| `/dashboard/athlete-figure` | AthleteFigureDashboardComponent | `admin` in selected club |
| `/dashboard/swimmer` | SwimmerDashboardComponent | `swimmer` in selected club |
| `/dashboard/family` | **New ParentDashboardComponent** (linked children's progress + videos) | `parent` in selected club |
| `/dashboard/club-admin` | **Enable ClubAdminDashboardComponent** → tabs: People(members/approve), People-without-account, Teams, Designations | `admin` in selected club |
| `/dashboard/club-admin/members`, `/teams` | new admin sub-pages | above |

`Club Owner`, `Lead Coach` and `Team Captain` are **titles**, not guards. They come from
`membership.title` and are rendered in the UI (badge, list column, sorting); they never
appear in a guard condition. A guard asks `roles_by_club[selectedClubId]`, and a
misconfigured title cannot escalate anything.

### 7.2 Roles
Guards are evaluated **per selected club**, because the same person can be a `swimmer` in
one club and a `coach` in another. The shell therefore owns a `selectedClubId` signal
(initialised from `club_ids`, switchable) and every guard is a function of
`(selectedClubId, rolesByClub)`. Shell nav adapts by role within the selected club: staff
see coach + club-admin, swimmers see swimmer + own figure dashboards, parents see family
only. A user with memberships in two clubs sees two different navs, which is the visible
consequence of dropping the scalar `club_id`.

The parent dashboard's list of children comes from an **API** that reads `as_person_link`
— never from a claim. A child added after the parent logged in appears on refresh, with
no re-login.

### 7.3 Auth service
`AuthService` keeps its signals/localStorage shape; `login()` now calls the BFF and parses
`{personId, clubIds, rolesByClub, teamIds, permissions, name, email}` (no `athleteIds`,
no `clubId`); adds `selectedClubId`; `register()`, `registerClub()` added;
`hasRole/hasAnyRole/hasPermission` become club-scoped
(`hasRole(clubId, role)`). `userServiceUrl` env already exists — used by the BFF only
(browser never calls `:8001` directly, avoiding the internal-secret issue).

---

## 8. Data Sync Strategy

- **On-login sync (fast path):** BFF, after a successful login, upserts the caller's own the
  `as_club_membership` and `as_person_link` rows plus the `as_club` / `as_person` /
  `as_team` mirrors. This is an optimization, not a correctness requirement: a club's
  full roster still arrives via the background sync, so a link created for a *different*
  member is not visible until one of the two paths runs. Decide explicitly whether a
  newly linked child appears immediately or on the next sync, and do not assume the fast
  path covers it — it only covers the caller's own rows.
- **Sync source:** the user service's org API (`GET /auth/me`, `GET /members`,
  `GET /person-links`, `GET /teams`) — **not** the token. A claim set cannot populate
  `as_club_membership`: it carries no `status` history, no `title`, no `joined_at` /
  `left_at`, and it cannot describe a person who has no account at all. The claims are at
  best a hint that something *may* have changed.
- **Background sync:** daily pg_cron / edge function on the dashboard stack calls a
  backend `SyncService` endpoint to refresh all clubs (guarded by service role/PSK). This
  is the path that catches a person added, a link created, or a membership ended while
  nobody was logged in.
- **Result linkage:** the sync resolves `as_result_person_link` rows and sets nullable
  `person_id` on `as_meet_figure_result` / `as_meet_routine_result`. For routines it
  matches the JSON `team_athletes` printed names plus birth year within a club, and
  stores the printed `athlete_name` alongside the resolved `person_id` — that name is
  the only intra-row discriminator, so it is part of the record rather than a lookup
  key. Ambiguous candidates stay unresolved (blocklist) instead of being guessed. This
  replaces the name+birth_year+club fuzzy join the earlier draft proposed for a
  club-scoped `athlete_id`; `athlete_name` / `athlete_birth_year` keep their names as
  lineage fields.
- **Removed from sync:** `user_status_mirror` (folded into `as_club_membership.status`)
  and any mirror that carries identity in its `id`. Mirrors carry `person_id`; they are
  not the identity.

---

## 9. Security Notes

- Passwords only ever handled by Supabase Auth. No password PII in dashboard or logs.
- BFF proxies all public identity calls; `X-Internal-Secret` never reaches the browser.
- JWT: RS256 keypair owned by user service; `USER_SERVICE_JWKS_URL` already in dashboard
  config. Move demo auth behind non-production flags; keep HS256 only for local dev.
- **Signature verification is always on.** No data route may accept an unverified token.
  The two divergent paths in the backend today (`api/auth.py` unverified vs
  `core/auth.py` JWKS-verified) are a defect to be resolved, not a configuration to
  choose between — see the finding in §5.2.1.
- Audit: approval/deny/team/role/link mutations go through existing `audit_log`
  (user-service trigger) + webhooks. Removing a person link is an access-control change
  and is logged as one.
- RLS: membership-driven via the `app_*()` helpers (§5.3). The identity tables are no
  longer world-readable (§4.2.2), and the `athlete_ids` claim is not a fallback — it is
  forbidden, so there is no path by which a stale token widens access.
- Revocation is a data operation, not a token operation: an ended membership or a
  removed `as_person_link` row takes effect on the caller's next request, so an
  emergency offboarding does not wait for a token to expire.
- **Gateway header contract (implemented).** `supabase/functions/api-gateway/index.ts`
  resolves the caller and forwards `X-Person-Id` plus a comma-separated `X-Club-Ids`,
  and no longer forwards `X-User-Id` / `X-Tenant-Id`. Two reasons: a `X-User-Id` would
  invite a downstream handler to treat a login subject as a person, and the dashboard is
  membership-scoped while the user service is tenant-scoped, so collapsing to one
  `X-Tenant-Id` at the edge would silently pick a club for a multi-club caller. The
  single `X-Tenant-Id` that the user service expects is therefore derived per-request by
  the dashboard from the caller's own active membership, after `require_club_role`
  (see the admin router note in §5.4). `X-Internal-Secret` and the `isTenantSuspended`
  check are unchanged. `sub` remains the only claim the gateway trusts.

## 10. Open Questions (to resolve at implementation kickoff)

1. **Blocking dependency:** when does `public.membership`'s `unique (tenant_id, user_id)`
   become `unique (tenant_id, user_id, role_id)` in `api/user-management` (§4.1.1)?
   Until it does, multi-club is untestable end to end, though the dashboard schema
   already supports it. This is an upstream date to confirm, not dashboard work.
2. Coach access scope: club-wide vs. team-scoped. Proposed MVP: `app_is_club_staff` is
   club-wide; lead-coach team scoping is a follow-up and, if built, must be a new
   `app_*` helper reading `as_team` — never a claim.
3. Does an unapproved user need to see "pending" state on login, or are generic
   `403` + email fine? (Design assumes login shows pending message.)
4. Where does `as_person.birth_date` come from for a person added without an account?
   (Design assumes the club-admin person form; a minor has no self-declared value, and an
   empty `birth_date` must not block a membership.)
5. Role ↔ permission seeding: define the seed set for dashboard powers (approve
   memberships, manage teams, upload/annotate videos, view analytics) as `permission`
   rows. Note these remain advisory — the dashboard does not enforce from
   `permissions` (§4.3).
6. Are `as_result_person_link` backfills in scope for this feature, or follow-up?
7. Should a person with no login be given a *managed* sign-in later (invite-account) in
   this feature, or only a parent-mediated view?

## 11. Roadmap / Task Breakdown (implementation phase)

**Phase 0 — Blocking dependency (upstream, separate repo)**
- `api/user-management`: relax `public.membership` to `unique (tenant_id, user_id,
  role_id)`, or replace `membership` with `as_person` / `as_person_identity` /
  `as_club_membership` (§4.1.1). Tracked here because the dashboard's multi-club
  behaviour is untestable until it lands. No dashboard change is required by it.

**Phase A — User service org model & auth**
- Migration `05_org_model.sql` (tables §4.1) + RLS/user-service policies. Includes
  `as_person` and optional `as_person_identity` so a person can exist without an account.
- Auth mint service (`POST /auth/login`, `POST /auth/register`, RS256 keypair + JWKS);
  `POST /persons` (no-login person) and `POST /persons/{person_id}/invite-account`.
- Approve/deny/leave on **memberships**; teams + person-link CRUD.
- Seed roles (`admin｜coach｜swimmer｜parent｜official`) and `title` values (`Club Owner`,
  `Lead Coach`, `Team Captain`) as display data, not as permission grants.
- Tests: auth gate (approval), cross-tenant isolation, **multi-club membership** once
  Phase 0 lands, and "person with no login" end to end.

**Phase B — Dashboard backend integration**
- `api/auth.py` BFF proxies (login/register/register-club/clubs) + `api/members.py` +
  `api/teams.py`.
- **Resolve the auth-path finding (§5.2.1):** collapse `api/auth.py:verify_jwt` onto
  `core/auth.get_current_user` (or delete it and re-point insights/markers/uploads/
  timers); demo minting stays dev-gated. Signature verification is unconditional.
- `SyncService` (membership/link upsert, on-login + daily) + `as_result_person_link`
  resolution and `person_id` backfill.
- RLS verification pass against `20260820_full_schema.sql` + the
  `20260826_person_identity_migration.sql` path: every membership read inside a policy
  goes through a `SECURITY DEFINER` helper; no policy reads a token claim except `sub`.
- `core/auth.py`: `require_club_role(club, roles)`, `person_id` claim, `athlete_ids`
  branch deleted with no fallback.

**Phase C — Frontend**
- Rework login (pending state), register member page, register-club page, club switcher.
- Club-admin dashboard: membership approval tab, **add a person without an account**,
  teams management (create team, lead coach, captain, roster), designations.
- Parent role + family dashboard driven by `as_person_link`; shell nav per selected
  club; dead-route cleanup.

**Phase D — End-to-end hardening**
- Seed/integration data (register club → add a person with no login → link a parent →
  approve → login → analytics → video visible to the parent).
- Claim-conformance test: a token carrying `athlete_ids` or a scalar `club_id` is
  rejected or ignored.
- Immediate-revocation test: end a membership and confirm access is denied on the next
  request without a re-login.
- Load/obs checks on login, audit coverage for all state mutations, docs/quickstart
  update.

> Priority ordering per dependency: Phase 0 (upstream, parallel) → A → B → C; D is
> verification across A–C.
