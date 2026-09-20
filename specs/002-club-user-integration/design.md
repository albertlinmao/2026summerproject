# Design: Club / Coach / Athlete / Parent User Integration

**Feature**: `002-club-user-integration`
**Created**: 2026-09-16
**Status**: Design (not started — this document precedes implementation)
**Applies to**: `001-analytics-dashboard` (dashboard app) + `001-multi-tenant-user-api` (user-management service)

---

## 1. Purpose

Rearchitect how the analytics dashboard identifies people. Today the dashboard is
single-club, demo-authenticated, and has no concept of *teams* or *parents*. This
design makes the existing **user-management service** the single source of truth for
identity and club organization, and makes the dashboard read identity from its JWT.

Decisions locked with the owner (2026-09-16):

| Decision | Choice |
|---|---|
| Deliverable | **Design doc only** (this document) — no code yet |
| Unapproved users login? | **No.** Approval gate: pending users cannot log in |
| Org model ownership | **User-management service owns all org data** (clubs, mapping, teams, family links); dashboard keeps lightweight `as_*` reference mirrors |

---

## 2. Current State (Gap Analysis)

### 2.1 What exists

**Dashboard app** (`backend/`, `frontend/`)
- FastAPI on `:8000`, reads local Supabase (`:54321` PostgREST, `:54322` Postgres).
- Analytics tables `as_event`, `as_meet*`, `as_*video*`, `as_routine_timers`, widgets; reference stubs `as_club(id, name)`, `as_athlete(id, club_id, name)`, `as_coach(id, club_id, name)`.
- Two auth paths:
  - `core/auth.py` — **verified** JWT (`RS256` JWKS or HS256 shared secret), claims `sub, club_id, roles, athlete_ids, permissions`; provides `get_current_user`, `require_role`, `require_club_access`.
  - `api/auth.py` — demo `POST /auth/login` (HS256, hardcoded demo user, `iss="sst-demo-auth"`); and an insecure `verify_jwt` (signature skipped, reads `uid`) used by insights/markers/uploads/timers.
- RLS resolves club scope by looking up `as_coach` / `as_athlete`; family video access uses `auth.jwt() -> 'athlete_ids'`.
- Frontend: Angular 22 standalone, Material M3. Login page, `AuthService` (signals + localStorage), `authGuard` / `roleGuard`, shell with user menu/logout. **No** registration/onboarding pages. **No** Parent role anywhere. Club/team pages exist but are dead routes/placeholders. `environment.ts` already defines `userServiceUrl: http://localhost:8001` (unused).

**User-management service** (`api/user-management/`)
- FastAPI on `:8001`, owns its own Supabase stack.
- Tables: `tenant`, `user_profile` (FK `auth.users`, pgcrypto-PII-encrypted), `role`, `permission`, `role_permission`, `membership`, `audit_log`.
- APIs: `POST/GET /api/v1/tenants`, `GET/POST /api/v1/users`, `GET/POST /api/v1/roles`, `GET /api/v1/audit`, auth webhook.
- Trust model: Supabase Edge Function validates JWT, injects `X-Tenant-Id` / `X-User-Id`; FastAPI requires `X-Internal-Secret`. `POST /tenants` (onboarding) bypasses JWT.
- User lifecycle already models `INVITED → ACTIVE → SUSPENDED / SOFT_DELETED`. Onboarding creates the auth user as `email_confirm: true` and always `email_confirm` on create — there is **no approval gate yet**.
- Feature flags gate onboarding (`tenant-onboarding`) and GDPR.

### 2.2 Gaps vs. target

1. Club ≠ tenant. `as_club` is a local reference, not sourced from `tenant`.
2. No `user_status` (user/role-type mapping + approval state), no teams, no family (parent↔athlete) links, no athlete profile (birth year).
3. No approval workflow — users are created active; no approve/deny.
4. Login is a mock; the dashboard never authenticates against the user-management service.
5. No club/user registration pages; no Parent role or UI.
6. RLS/code resolve club by looking up local `as_coach`/`as_athlete` instead of trusting claims; the `tbl->jwt` contract already exists but is only partially enforced.
7. Insecure legacy `verify_jwt` path (`uid` claim) coexists with the verified path.

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
│  /api/auth/me    → claims → club/team/parent scoping            │
│  /api/analytics/* /results/* ... (existing) reads claims        │
│  SyncService     → mirrors scheduler(users/clubs/teams→ as_*)   │
└──────────────┬──────────────────────────────────────────────────┘
               │ HTTP + X-Internal-Secret (+ X-Tenant-Id/X-User-Id for admin calls)
┌──────────────▼──────────────────────────────────────────────────┐
│ User-Management Service (FastAPI :8001)  =  source of truth     │
│  auth (login/token mint) · tenants(clubs) · users · mapping     │
│  teams · family links · approve/deny · roles · audit            │
│  Supabase Auth (identity) + Postgres (org model)                │
└──────────────┬──────────────────────────────────────────────────┘
               │ auth.users / tenant / membership / as_* org tables
┌──────────────▼──────────────────────────────────────────────────┐
│ Supabase (user-service stack)                                   │
└─────────────────────────────────────────────────────────────────┘
```

Principles:
- **Single source of truth** for identity & org: the user-management service + its DB.
- **The dashboard trusts the JWT claims** minted by the user service. RLS becomes claim-driven (`club_id`, `athlete_ids`) instead of table lookups.
- **The dashboard never stores PII or membership**; `as_*` mirror tables hold display names only for analytics joins.
- **No secrets in the browser**: public registration/login flows go through the dashboard BFF; only the backend holds `X-Internal-Secret`.
- Dashboard legacy tables (`as_meet_*_result`) stay as-is (competition records, immutable). New optional `athlete_id` FK links results to accounts.

---

## 4. Data Model Changes

### 4.1 User-management service DB (new migration `05_org_model.sql`)

All in the user-service Postgres (its Supabase instance). PII stays encrypted in
`user_profile`; org tables hold UUIDs + non-PII (names of teams/clubs are fine, but
keep sign-ups minimal).

```
tenant (exists)                          -- a club == one tenant row
user_profile (exists)                    -- one row per auth.users.id; status drives approval

-- Club record; id is the SAME value as tenant.id (club == tenant).
as_club (
  id   uuid primary key references tenant(id) on delete cascade,
  name text not null
)

-- REQUIRED BY SPEC: user <-> membership-class mapping + approval state.
-- One user == one row (single active club is enforced by membership.unique(tenant_id,user_id)).
user_status (
  user_id       uuid primary key references user_profile(id) on delete cascade,
  role_type     text not null check (role_type in ('COACH','ATHLETE','PARENT')),
  status        text not null default 'PENDING'
                check (status in ('PENDING','APPROVED','REJECTED','SUSPENDED')),
  requested_at  timestamptz not null default now(),
  approved_by   uuid references user_profile(id),
  approved_at   timestamptz,
  created_at    timestamptz not null default now()
)

-- REQUIRED BY SPEC: club member roster (denormalized, one row per member).
-- PK = auth.users id (user_profile.id). Display copies of first/last/email
-- (authoritative source remains user_profile); role = primary member role,
-- status = membership lifecycle. club_id points at as_club(id) == tenant.id.
as_club_member (
  id           uuid primary key references user_profile(id) on delete cascade,
  club_id      uuid not null references as_club(id),
  first_name   text not null,
  last_name    text not null,
  email        text not null,
  role         text not null check (role in ('ATHLETE','COACH','OWNER','PARENT')),
  status       text not null default 'ACTIVE'
               check (status in ('ACTIVE','INACTIVE','SOFT_DELETED')),
  updated_by   uuid references user_profile(id),
  created      timestamptz not null default now(),
  last_updated timestamptz not null default now()
)
create index idx_as_club_member_club on as_club_member(club_id);

-- Club-level staff designations: owners and the club lead coach.
as_club_role (
  id        uuid pk default gen_random_uuid(),
  club_id   uuid not null references tenant(id) on delete cascade,
  user_id   uuid not null references user_profile(id) on delete cascade,
  role      text not null check (role in ('OWNER','LEAD_COACH','ADMIN')),
  created_at timestamptz not null default now(),
  unique (club_id, user_id, role)
)

-- Teams; each team has one designated lead coach.
as_team (
  id           uuid pk default gen_random_uuid(),
  club_id      uuid not null references tenant(id) on delete cascade,
  name         text not null,
  lead_coach_id uuid references user_profile(id),     -- designated lead coach
  created_at   timestamptz not null default now(),
  unique (club_id, name)
)

-- Team membership; athletes can belong to many teams; team captain is a role.
as_team_member (
  id        uuid pk default gen_random_uuid(),
  team_id   uuid not null references as_team(id) on delete cascade,
  user_id   uuid not null references user_profile(id) on delete cascade,
  team_role text not null check (team_role in ('COACH','CAPTAIN','ATHLETE')),
  created_at timestamptz not null default now(),
  unique (team_id, user_id)
)

-- Parent <-> athlete links (family access; parents see linked athletes' data).
as_family_link (
  id          uuid pk default gen_random_uuid(),
  parent_id   uuid not null references user_profile(id) on delete cascade,
  athlete_id  uuid not null references user_profile(id) on delete cascade,
  relationship text not null default 'PARENT' check (relationship in ('PARENT','GUARDIAN','OTHER')),
  created_at  timestamptz not null default now(),
  unique (parent_id, athlete_id)
)

-- Athlete profile (birth year etc.). Athlete row == a user_profile + user_status(ATHLETE).
as_athlete_profile (
  athlete_id uuid pk references user_profile(id) on delete cascade,
  club_id    uuid not null references tenant(id) on delete cascade,
  birth_year integer
)
```

Approval rule: **a user may log in only when `user_profile.status = 'ACTIVE'`
AND `user_status.status = 'APPROVED'`** (for the user's club). Register → status
`INVITED` / mapping `PENDING`. Approve → set both `ACTIVE` / `APPROVED`. Deny →
mapping `REJECTED` (auth user kept suspended).

Reconciliation of the three user tables:

| Table | Role | Purpose |
|---|---|---|
| `user_profile` | identity (auth, encrypted PII) | source of truth for PII + lifecycle `INVITED/ACTIVE/SUSPENDED/SOFT_DELETED` |
| `user_status` | approval + membership class | `PENDING/APPROVED/REJECTED` gate + `role_type COACH/ATHLETE/PARENT` |
| `as_club_member` | club roster (denormalized) | display names/email + `role ATHLETE/COACH/OWNER/PARENT` + `status ACTIVE/INACTIVE/SOFT_DELETED` for club-admin lists |

`as_club_member.role` includes `OWNER`; additional designations
(`LEAD_COACH`, `ADMIN`) remain in `as_club_role`. Write path: registration/approval/
role changes update `user_profile` + `user_status` + `as_club_member` together (single
transaction in the user service), or maintain it via a DB trigger on the others.

### 4.2 Dashboard mirror tables (extend `as_*` reference schema)

`as_club`, `as_athlete`, `as_coach` exist. Add columns/rows and a team mirror; keep
them **read-only sync targets**:

```
as_club    (+ code text null, status text, synced_at timestamptz)   -- id = tenant uuid (same value as user-service as_club.id)
as_athlete (+ birth_year int null, synced_at)                       -- id = user_profile uuid; name = display name
as_coach   (+ synced_at)                                            -- coaches & family staff (id = user_profile uuid)
as_team    (id uuid pk, club_id fk as_club, name text, lead_coach_id uuid, synced_at)   -- new
user_status_mirror (optional per athlete/coach row: role_type + status) -- or infer from as_athlete/as_coach rows
```

Optional (recommended) analytics linkage: add nullable `athlete_id uuid references
as_athlete(id)` to `as_meet_figure_result` and `as_meet_routine_result`; backfill by
name+birth_year+club match at sync time; enables per-account analytics without
fuzzy-name joins.

### 4.3 JWT claims contract (issued by user service, consumed by dashboard)

| Claim | Type | Meaning |
|---|---|---|
| `sub` | uuid string | auth.users id (user identity) |
| `iss` | string | `"sst-user-service"` |
| `aud` | string | `APP_NAME` of the dashboard (currently `app-name` default — align via `USER_SERVICE_JWT_AUDIENCE`) |
| `email`, `name` | string | display only |
| `club_id` | uuid | **active club** (tenant) |
| `club_name` | string | display |
| `tenant_id` | uuid | club_id (same value, user-service native name) |
| `roles` | string[] | dashboard role vocabulary: `Coach`, `Lead Coach`, `Club Admin`, `Club Owner`, `Athlete`, `Team Captain`, `Parent` |
| `role_type` | string | `COACH\|ATHLETE\|PARENT` (primary mapping class) |
| `athlete_ids` | uuid[] | for ATHLETE → `[self]`; for PARENT → linked athletes via `as_family_link`; for COACH → empty (club-scoped) |
| `team_ids` | uuid[] | teams the athlete is a member of (empty for non-athletes) |
| `permissions` | string[] | resolved from `role.permission` + club/team roles (e.g. `members.approve`, `teams.write`) |

`club_id`/`roles`/`athlete_ids`/`permissions` are **backward-compatible** with the
existing `core/auth.py` claims parsing and RLS `auth.jwt()` usage.

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
  (`sign_in_with_password`), then checks approval gate (§4.1). Mints dashboard JWT
  (RS256, audience = dashboard `APP_NAME`). Returns
  `{access_token, expires_in, user{id,email,name,club_id,roles,athlete_ids,team_ids,permissions,status}}`.
  Errors: `401 INVALID_CREDENTIALS`, `403 PENDING_APPROVAL`.
- `POST /auth/register` — public member registration body
  `{email,password,first_name,last_name,club_id,role_type}`. Creates auth user
  (confirmed), `user_profile` INVITED, `user_status` PENDING, optional
  `as_athlete_profile{birth_year}`. Returns `{mapping_id, status:"PENDING"}`.
- `POST /auth/register-club` — **alias of `POST /tenants`** (existing onboarding).
  Creates tenant + owner (ACTIVE, `as_club_role: OWNER`) and returns the same
  `TenantResponse`; the BFF then mints an owner token so the new club admin is logged in.
- `GET /auth/clubs` — public list `{id, name}` for the registration page.
- `GET /auth/me` — claims of the current caller (single source for profile UI).

Org administration (tenant-scoped via `X-Tenant-Id`/`X-User-Id`; owner/admin roles)
- `GET /members?status=PENDING&role_type=` — list club members + mapping + status (approval queue).
- `POST /members/{user_id}/approve` — sets `user_profile.status=ACTIVE`,
  `user_status.status=APPROVED`, `approved_by/at`. Audit-logged.
- `POST /members/{user_id}/reject` — sets mapping `REJECTED`, suspends auth user.
- `POST /members/{user_id}/roles` — grant/revoke `OWNER|LEAD_COACH|ADMIN` (`as_club_role`).
- `GET /teams`, `POST /teams` (create, set `lead_coach_id`), `PATCH /teams/{id}`,
  `POST /teams/{id}/members` (join; `team_role`), `DELETE /teams/{id}/members/{user_id}`.
- `GET /family-links`, `POST /family-links` (parent links athlete),
  `DELETE /family-links/{id}`.

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
`core/auth.get_current_user` + `require_role(["Club Owner","Club Admin"])`):
- forward to user-service with `X-Internal-Secret` + the caller's `X-Tenant-Id`/`X-User-Id`.

`core/auth.py` — unchanged claim model; add optional status check helper
(`require_active` reads a new `user_status`/`approved` claim if present).

Legacy cleanup (design target): migrate `insights/markers/uploads/timers` from the
insecure `verify_jwt` (`uid`) to `get_current_user`; delete the demo login in
production builds (keep behind `APP_ENV != production` for local dev).

### 5.3 RLS updates (dashboard Supabase)

- Replace `current_user_club_id()` table lookups with `(auth.jwt()->>'club_id')::uuid`.
- Keep family video access via `jwt_linked_athlete_ids()` (already claim-based);
  extend to also allow a coach's athlete scope and parent from `as_family_link` via sync mirror.
- Add policies so widget/timer tables scope by `club_id` claim (already `auth.uid()` for user-owned rows).

---

## 6. End-to-End Flows

### 6.1 Club registration (REQ #6)
```
/register-club → BFF POST /api/auth/register-club
  → user-svc POST /tenants (bypass JWT, X-Internal-Secret)
      creates: tenant, owner auth user (ACTIVE), user_profile, membership(Admin),
               user_status(role_type 'COACH') + as_club_role OWNER
  → BFF mint owner token via /auth/login
  → redirect (role Club Owner) → /dashboard/club-admin
```

### 6.2 Member registration (REQ #7)
```
/register (choose club, role coach|athlete|parent) → BFF POST /api/auth/register
  → user-svc creates auth user (confirmed), profile INVITED, mapping PENDING, athlete profile if athlete
  → success page "pending approval"
```

### 6.3 Approval (REQ #4)
```
Owner/Admin → /dashboard/club-admin/members (PENDING list)
  → POST /members/{id}/approve → status ACTIVE/APPROVED
  until then login returns 403 PENDING_APPROVAL ("A club admin must approve you first")
```

### 6.4 Login (REQ #5)
```
/login → BFF POST /api/auth/login → user-svc verifies creds + approval gate
  → mint RS256 JWT (aud=APP_NAME, claims §4.3) → browser stores token + user
  → shell renders role-based nav (§7). RLS uses claims on every Supabase query.
```

### 6.5 Teams (REQ #3)
Club admin creates teams; assigns lead coach (coach user). Athlete joins 1..n teams;
captain set per team. `team_ids` claim drives athlete-team analytics; lead-coach claims
drive team-scoped coach views. Coach with a team-lead role sees only their teams' athletes.

---

## 7. Frontend Design (dashboard SPA)

### 7.1 Pages / routes

| Route | Component | Guard |
|---|---|---|
| `/login` | LoginComponent (rework: call BFF, show "pending approval" error) | public |
| `/register` | New `MemberRegistrationComponent` (club picker + role picker coach/athlete/parent) | public |
| `/register-club` | New `ClubRegistrationComponent` (tenant/club registration) | public |
| `/dashboard` | ShellComponent (role-based redirect) | authGuard |
| `/dashboard/coach` | CoachDashboardComponent | roles `[Coach, Lead Coach, Club Admin, Club Owner]` |
| `/dashboard/athlete-figure` | AthleteFigureDashboardComponent | coach/admin roles |
| `/dashboard/swimmer` | SwimmerDashboardComponent | `[Athlete, Team Captain]` |
| `/dashboard/family` | **New ParentDashboardComponent** (linked athletes' progress + videos) | `[Parent]` |
| `/dashboard/club-admin` | **Enable ClubAdminDashboardComponent** → tabs: Members(approve), Teams, Owners | `[Club Owner, Club Admin]` |
| `/dashboard/club-admin/members`, `/teams` | new admin sub-pages | above |

### 7.2 Roles
Extend role vocabulary & guards to add `Parent` everywhere it matters (see §4.3 claim
table). Shell nav adapts by role: coach/admin see coach dashboard + club admin; athlete
sees swimmer + own figure dashboards; parent sees family dashboard only.

### 7.3 Auth service
`AuthService` keeps its signals/localStorage shape; `login()` now calls the BFF and
parses claims `{ id, clubId, roles, athleteIds, teamIds, permissions, name, email }`;
`register()`, `registerClub()` added; `hasRole/hasAnyRole/hasPermission` unchanged.
`userServiceUrl` env already exists — used by the BFF only (browser never calls `:8001`
directly, avoiding the internal-secret issue).

---

## 8. Data Sync Strategy

- **On-login sync (fast path):** BFF, after successful login with claims, upserts the
  current club's mirrors (`as_club`, `as_athlete`, `as_coach`, `as_team`,
  `user_status_mirror`) from user-service `GET /auth/me` + `GET /teams`.
- **Background sync:** daily pg_cron / edge function on the dashboard stack calls a
  backend `SyncService` endpoint to refresh all clubs (guarded by service role/PSK).
- **Result linkage:** the sync assigns `athlete_id` on `as_meet_*_result` by
  name+birth_year+club to previously name-matched rows (one-time backfill + blocklist
  for ambiguity).

---

## 9. Security Notes

- Passwords only ever handled by Supabase Auth. No password PII in dashboard or logs.
- BFF proxies all public identity calls; `X-Internal-Secret` never reaches the browser.
- JWT: RS256 keypair owned by user service; `USER_SERVICE_JWKS_URL` already in dashboard
  config. Move demo auth behind non-production flags; keep HS256 only for local dev.
- Audit: approval/deny/team/role mutations go through existing `audit_log` (user-service
  trigger) + webhooks.
- RLS: claim-driven; sanitize legacy `verify_jwt` endpoints (§5.2).

## 10. Open Questions (to resolve at implementation kickoff)

1. Multi-club users (member of two clubs) — MVP assumes one **active club** / JWT;
   long-lived design should allow re-issue per club. What is the MVP stance?
2. Coach access scope: club-wide vs. team-scoped (lead coaches see only their team)?
   Proposed MVP: coaches see club-wide; lead coach gets team scoping via `team_ids` claim.
3. Does an unapproved user need to see "pending" state on login, or are generic
   `403` + email fine? (Design assumes login shows pending message.)
4. Where does `as_athlete_profile` birth_year come from at registration (self-declared)?
5. Role ↔ permission seeding: define the seed set for dashboard powers (approve
   members, manage teams, upload/annotate videos, view analytics) as `permission` rows.
6. Are result-table `athlete_id` backfills in-scope for this feature, or follow-up?

## 11. Roadmap / Task Breakdown (implementation phase)

**Phase A — User service org model & auth**
- Migration `05_org_model.sql` (tables §4.1) + RLS/user-service policies.
- Auth mint service (`POST /auth/login`, `POST /auth/register`, RS256 keypair + JWKS), approve/deny endpoints, teams + family-link CRUD.
- Seed permissions + roles (`Coach`, `Lead Coach`, `Club Admin`, `Club Owner`, `Athlete`, `Team Captain`, `Parent`).
- Tests: auth gate (approval), cross-tenant isolation for member/team calls.

**Phase B — Dashboard backend integration**
- `api/auth.py` BFF proxies (login/register/register-club/clubs) + `api/members.py` + `api/teams.py`.
- `SyncService` (mirror upsert, on-login + daily) + result `athlete_id` backfill.
- Replace legacy `verify_jwt` (`uid`) with `get_current_user`; demo login gated to dev.
- RLS rewrite to claims; update `core/auth.py` (`require_rooted` helpers, optional status claim).

**Phase C — Frontend**
- Rework login (pending state), register member page, register-club page.
- Club-admin dashboard: members approval tab + teams management (create team, lead coach, captain, roster).
- Parent role + family dashboard; shell nav by role; dead-route cleanup.

**Phase D — End-to-end hardening**
- Seed/integration data (register club → register athlete → approve → login → analytics).
- Load/obs checks on login, audit coverage for all state mutations, docs/quickstart update.

> Priority ordering per dependency: A → B → C; D is verification across A–C.