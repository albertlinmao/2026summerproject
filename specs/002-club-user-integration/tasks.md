---

description: "Task list for 002-club-user-integration"
---

# Tasks: Club / Coach / Athlete / Parent User Integration

**Input**: Design documents from `/specs/002-club-user-integration/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md — all present.

**Tests**: Included. The constitution requires test-first (principle 3) and plan.md names four
required suites (unit / contract / integration / e2e). Every test task below is written
**before** its implementation and must be observed failing first.

**Organization**: Tasks are grouped by user story so each story can be implemented, tested
and demoed as an independent increment. US1 is the MVP because nothing can leave
`user_profile.status = 'INVITED'` until it lands.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel — different files, no dependency on another task in the same group
- **[Story]**: Which user story this belongs to (US1–US6). Tasks with no story tag are
  Foundational or cross-cutting.
- Every task names an exact file path.

## Blocking preconditions — read before starting

**All six blockers from `/speckit.analyze` were cleared by owner ruling on 2026-10-04.**
They began as decision tasks; they are now implementation tasks with concrete files.

| Blocker | Ruling | Now |
|---|---|---|
| Constitution P16 forbade the local identity mirror (K1) | **Amended** → constitution v2.0.0 permits an RLS-scoped mirror under four conditions | T007 (record) — no longer blocks Phase 9 |
| Constitution P7 required OAuth2, design uses GoTrue (K2) | **Amended** → v2.0.0 sanctions GoTrue credential auth alongside OAuth2 | T007 (record) |
| `membership` had `UNIQUE (tenant_id, user_id)` (T008) | **Relaxed** and **landed in this repo** as `06_membership_multi_role.sql` | T008 — gates US2 scenario 3, US5, S5 |
| OQ #9 ingest credential policy | **Ingest de-credentialed**; `claim-account` retargeted to adoption via admin-issued `claim_token` | T071 — US6 no longer contingent |
| OQ #8 `tenant` ↔ `club` mapping undefined | **First-class `as_club.tenant_id` FK**, backfilled by `code` match | T006 — gates T076 |
| OQ #2 coach scope | **Club-wide.** No `app_is_team_lead()` in this feature | US5 scenario 3 |

> **Ingest no longer creates accounts.** `scripts/user_mgmt_sync.py:84` `DEFAULT_PASSWORD`
> and `:525` `get_or_create_auth_user` are deleted, so nothing mints credentials from a parsed
> PDF. US6's subject population is an existing GoTrue account presented with an admin-issued
> `claim_token` — the 9 pre-existing seeded accounts are migrated once under that flow.

## Path Conventions

Two FastAPI backends, one Angular SPA, Python ingest scripts. Dashboard paths are repo-root
relative (`backend/…`, `frontend/…`); the user service is a git submodule (`api/user-management/…`).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Test tooling, config gates, and the three migrations/ratification tasks that
were previously decision placeholders (T006, T007, T008).

- [X] T001 Pin dashboard backend test dependencies in `backend/requirements.txt` — add `pytest`, `pytest-cov`, `httpx`. The dashboard declares no test runner today, so principle 3 is unverifiable without this.
- [X] T002 [P] Add `DEMO_AUTH_ENABLED` to `backend/src/core/config.py`; set `APP_ENV=development` and `DEMO_AUTH_ENABLED=false` in `.env` so the dev branch is not live by default (spec clarification, session 2026-10-03).
- [X] T003 [P] Add a contract-validation step covering both `specs/002-club-user-integration/contracts/openapi.yaml` and `contracts/dashboard-bff.yaml` — principle 12 is "no API spec → no merge". Validate as two documents; a merged document silently collapses duplicate path keys.
- [X] T004 [P] Define the shared error model in `api/user-management/backend/src/models/errors.py` — codes `INVALID_CREDENTIALS`, `PENDING_APPROVAL`, `ACCOUNT_SUSPENDED`, `NO_ACTIVE_MEMBERSHIP`, `PASSWORD_NOT_CHANGED`, `SEEDED_ACCOUNT_EXISTS`, plus `trace_id`.
- [X] T005 Add the `audit_log` writer at `api/user-management/backend/src/services/audit.py` — every membership / identity / person-link transition writes actor and outcome, never a credential value (FR-012, SC-006).
- [X] T006 Add `tenant_id UUID REFERENCES tenant(id)` to `as_club` in `05_org_model.sql`, backfilled from `tenant.code`, then set `NOT NULL` (REQ-011, OQ #8). Four-step procedure in data-model.md §"Resolved: `tenant` ↔ `club`", including the `count(*) WHERE tenant_id IS NULL` = 0 assertion before the `NOT NULL`. Live backfill is 7 rows. - `api/user-management/supabase/migrations/05_org_model.sql`
- [X] T007 Record the ratified governance amendments in `plan.md` Constitution Check and Complexity Tracking: constitution **v2.0.0** permits an RLS-scoped authorization mirror (P16) and GoTrue credential authentication (P7). Already amended in `.specify/memory/constitution.md`; this task confirms no downstream artifact still describes them as conflicts. - `.specify/memory/constitution.md`
- [X] T008 Create `api/user-management/supabase/migrations/06_membership_multi_role.sql` — drop `UNIQUE (tenant_id, user_id)` on `membership` and add `UNIQUE (tenant_id, user_id, role_id)`. **No longer [EXTERNAL REPO]**: the table is defined in this tree at `01_initial_schema.sql`. Separate from `05_org_model.sql` because it alters a table that file does not create. Unblocks US2 scenario 3 and US5; does NOT make person-without-login representable (`membership.user_id` is `NOT NULL`) — REQ-012 records both halves. - `api/user-management/supabase/migrations/06_membership_multi_role.sql`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema, token issuer, and the bootstrap admin. **No user story can start before this completes.**

**⚠️ CRITICAL**: T010–T019 gate every story. T007 no longer gates Phase 9 — the P16/P7
conflicts were ratified as constitution v2.0.0 amendments on 2026-10-04.

### Tests (write first — must fail before implementation)

- [X] T009 [P] Test `05_org_model.sql` applies cleanly to an empty database and reproduces the live column shapes in `api/user-management/supabase/tests/test_migration_org_model.py`

### Schema

- [X] T010 Create `api/user-management/supabase/migrations/05_org_model.sql` — `as_club`, `as_person`, `as_person_identity`, `as_club_membership`, `as_person_link`, `as_team`, `as_team_member`. Replaces the runtime `ORG_MODEL_DDL` at `scripts/user_mgmt_sync.py:102-145`.
- [X] T011 [P] Add `approved_by` / `approved_at` to `as_club_membership` in `05_org_model.sql` — data-model.md D1: `design.md` §5.1 specifies them and neither column exists, so approval currently has nowhere to record attribution.
- [X] T012 [P] Promote `tenant_api_keys` from `api/user-management/supabase/init/` into a numbered migration (currently init-only, invisible to migration history). - `api/user-management/supabase/migrations/05_org_model.sql`
- [X] T013 [P] Seed `permission` rows in `05_org_model.sql` — approve memberships, manage teams, upload/annotate video, view analytics (OQ #5). Advisory only; the dashboard does not enforce from them.
- [X] T014 Add index on `as_club_membership (person_id, club_id, status)` in `05_org_model.sql` so per-club role resolution stays indexed (REQ-002) — plan.md performance goal; `app_has_club_role` runs inside RLS on every row.

### Token issuer

- [X] T015 Implement the RS256 signer and JWKS publication in `api/user-management/backend/src/core/security.py` — currently 12 lines containing only `verify_gateway_psk`. This is the issuer the whole design names and it does not exist.

### Bootstrap and authorization

- [X] T016 [P] Implement `POST /auth/register-club` in `api/user-management/backend/src/services/club_service.py` - creates tenant + owner with `role='admin'`, `title='Club Owner'`, `status='active'` (REQ-006). Every story's test needs an admin before approval is possible.
- [X] T017 [P] Implement `require_club_role(club_id, roles)` in `api/user-management/backend/src/core/security.py`; delete the `athlete_ids` branch with no fallback (FR-007). `app_has_club_role` already accepts a role array, so per-club checks need no new helper.
- [X] T018 Add RLS policies for the seven org tables in `05_org_model.sql`, driven by `SECURITY DEFINER` helpers; no policy may read a claim other than `sub` (FR-008).
- [X] T019 [P] Confirm the 11 `app_*` helpers exist in the service schema, adding any that the org tables need. - `api/user-management/supabase/migrations/05_org_model.sql`

**Checkpoint**: Schema migrated, RS256 issuer live, first admin bootstrappable, role checks club-scoped. Foundation ready.

---

## Phase 3: User Story 1 - Club admin approves a pending member (Priority: P1) 🎯 MVP

**Goal**: `POST /members/{person_id}/approve` becomes the single audited writer of
`as_club_membership.status = 'active'`.

**Why MVP**: Every account lands `INVITED` and nothing in the repository writes `ACTIVE`.
Until this exists the registration flow has nowhere to land and every other story is
undeliverable.

**Independent Test**: Register a member via `POST /auth/register`, confirm login returns
`403 PENDING_APPROVAL`, approve, confirm login now succeeds and the membership reads
`active`. (quickstart S1)

### Tests for User Story 1 ⚠️

> Write these first and watch them fail.

- [ ] T020 [P] [US1] Contract test for `GET /members`, `POST /members/{id}/approve`, `/reject`, `/roles`, `DELETE /members/{id}` in `api/user-management/backend/tests/contract/test_members_contract.py`
- [ ] T021 [P] [US1] Integration test: approval sets `active`, stamps `approved_by`/`approved_at`, and writes an `audit_log` row in `api/user-management/backend/tests/integration/test_membership_approval.py`
- [ ] T022 [P] [US1] Integration test: approving an already-`active` membership returns `409` - `api/user-management/backend/tests/integration/test_membership_approval.py`
- [ ] T023 [P] [US1] Integration test: a caller without an `admin` membership in the target club receives `403` — enforced by the service's own RLS, not by a claim (FR-005) - `api/user-management/backend/tests/integration/test_membership_approval.py`

### Implementation for User Story 1

- [ ] T024 [US1] Create `MembershipApproval` / `MemberSummary` schemas in `api/user-management/backend/src/models/membership.py`
- [ ] T025 [US1] Implement `approve_membership()` in `api/user-management/backend/src/services/membership.py` — the **only** code path permitted to set `active` (REQ-004, FR-009), transactional with its audit row
- [ ] T026 [US1] Implement `api/user-management/backend/src/api/routers/members.py` — `GET /members` (filter by status, keyed on `person_id`) and `POST /members/{id}/approve|reject`
- [ ] T027 [US1] Add `POST /members/{person_id}/roles` to `members.py` (FR-003) — grants a role within a club; `admin` still cannot be self-selected
- [ ] T028 [US1] Add `DELETE /members/{person_id}` to `members.py` → membership `left`, `left_at` set, sessions denied on the next request without re-login (SC-004)
- [ ] T029 [US1] Reject approval that outruns activation: `active` membership on an `INVITED` profile is a bug — surface the account gate, not the club gate - `api/user-management/backend/src/services/membership.py`

**Checkpoint**: US1 fully functional and independently testable.

---

## Phase 4: User Story 2 - Coach self-registers and logs in (Priority: P1)

**Goal**: The registration and login surface that does not exist today, plus the RS256
session with cache-only role claims.

**Independent Test**: `POST /auth/register` with `role=coach`, approve, log in, confirm the
token carries `roles_by_club` with `coach` for that club and no forbidden claims.

### Tests for User Story 2 ⚠️

- [ ] T030 [P] [US2] Contract test for `POST /auth/register|login`, `GET /auth/clubs|me` in `api/user-management/backend/tests/contract/test_auth_contract.py`
- [ ] T031 [P] [US2] Integration test: registration creates `as_person` + identity + `invited` membership and returns **no** token, with `user_profile` left `INVITED` - `api/user-management/backend/tests/integration/test_registration.py`
- [ ] T032 [P] [US2] Integration test: `role=admin` at registration is rejected (REQ-007) - `api/user-management/backend/tests/integration/test_registration.py`
- [ ] T033 [P] [US2] Integration test: login checks both gates independently — `403 PENDING_APPROVAL` vs `403 NO_ACTIVE_MEMBERSHIP` vs `403 ACCOUNT_SUSPENDED` vs `401 INVALID_CREDENTIALS`, each distinguishable - `api/user-management/backend/tests/integration/test_login_gates.py`
- [ ] T034 [P] [US2] Conformance test: minted token omits `athlete_ids`, scalar `club_id`, flat `roles`, `tenant_id`, `role_type` (SC-005) - `api/user-management/backend/tests/contract/test_token_claims.py`
- [ ] T035 [P] [US2] Integration test: an `ACTIVE` profile whose memberships are all `dormant`/`left` gets `403 NO_ACTIVE_MEMBERSHIP`, not a 401 - `api/user-management/backend/tests/integration/test_login_gates.py`

### Implementation for User Story 2

- [ ] T036 [US2] Implement `register()` in `api/user-management/backend/src/services/auth_service.py` — person + identity + invited membership, keyed on the club resolved from the request
- [ ] T037 [US2] Implement `login()` so a pending user receives no session (REQ-005) in `auth_service.py` — GoTrue password verification, then both status gates, then RS256 mint with `iss` = service, `aud` = dashboard `APP_NAME`, `sub` = auth subject
- [ ] T038 [US2] Implement `api/user-management/backend/src/api/routers/auth.py` covering `POST /auth/register`, `POST /auth/login`, `GET /auth/clubs`, `POST /auth/register-club` (FR-001) — `POST /auth/register`, `POST /auth/login`, `GET /auth/clubs`
- [ ] T039 [US2] Add `GET /auth/me` to `auth.py` — resolves `sub → person_id` via `as_person_identity` and returns memberships from the database
- [ ] T040 [US2] Add `PATCH /auth/me/enable` and `PATCH /auth/me/disable` to `auth.py` — activation writer (FR-009); suspension refuses at verification time, not at logout
- [ ] T041 [US2] Add `PATCH /auth/me/password` to `auth.py`
- [ ] T042 [US2] Resolve `club_ids` / `roles_by_club` / `team_ids` at mint time from `as_club_membership` and mark them cache-only in the contract — authorization re-resolves per request, so a stale token cannot outlive a revoked membership - `api/user-management/backend/src/services/auth_service.py`

**Checkpoint**: US1 and US2 both work independently. This is the MVP boundary.

---

## Phase 5: User Story 3 - Parent sees their child's analytics (Priority: P2)

**Goal**: Replace the `athlete_ids` JWT claim with `as_person_link` + `app_is_guardian_of`.

**Independent Test**: Create a person with no login, register a parent, approve a link, and
confirm `app_is_guardian_of` passes for that child at that club only.

### Tests for User Story 3 ⚠️

- [ ] T043 [P] [US3] Contract test for person-link CRUD in `api/user-management/backend/tests/contract/test_person_links_contract.py`
- [ ] T044 [P] [US3] Integration test: an approved link passes `app_is_guardian_of(parent, child, clubA)` and fails for clubB — the link is club-scoped - `api/user-management/backend/tests/integration/test_guardian_resolution.py`
- [ ] T045 [P] [US3] Integration test: revoking the link denies access on the **next request with no re-login** (SC-004). This is the load-bearing test: it passes only if authorization is read from the table every time. - `api/user-management/backend/tests/integration/test_guardian_resolution.py`
- [ ] T046 [P] [US3] Integration test: `parent_person_id = child_person_id` is rejected by `ck_as_person_link_distinct` - `api/user-management/backend/tests/integration/test_guardian_resolution.py`

### Implementation for User Story 3

- [ ] T047 [US3] Create `PersonLink` model in `api/user-management/backend/src/models/person_link.py`
- [ ] T048 [US3] Implement `api/user-management/backend/src/api/routers/person_links.py` - full CRUD (FR-004) — CRUD, each transition audit-logged
- [ ] T049 [US3] Resolve guardianship through `app_is_guardian_of` in the authorization path; no token claim encodes it (REQ-008, FR-008) - `api/user-management/backend/src/core/security.py`
- [ ] T050 [US3] Assert no code path reads guardianship from a claim — grep gate in `api/user-management/backend/tests/test_no_guardian_claims.py`

**Checkpoint**: US3 independently functional.

---

## Phase 6: User Story 4 - Club admin adds a person with no login (Priority: P2)

**Goal**: `POST /persons` with no credential fields — the stated reason the design changed.

**Independent Test**: `POST /persons` with no credential fields, confirm the person appears in
`as_athlete` with results and videos and that no `auth.users` or `as_person_identity` row exists.

### Tests for User Story 4 ⚠️

- [ ] T051 [P] [US4] Contract test for `POST /persons` and `POST /persons/{id}/invite-account` in `api/user-management/backend/tests/contract/test_persons_contract.py`
- [ ] T052 [P] [US4] Integration test: `POST /persons` creates an `as_person` + `as_club_membership` and **zero** `auth.users`, `user_profile` and `as_person_identity` rows (REQ-001, SC-008) - `api/user-management/backend/tests/integration/test_person_without_login.py`
- [ ] T053 [P] [US4] Integration test: an empty `birth_date` does not block membership creation - `api/user-management/backend/tests/integration/test_person_without_login.py`
- [ ] T054 [P] [US4] Integration test: `invite-account` creates the identity and an `INVITED` account that still cannot log in until enabled - `api/user-management/backend/tests/integration/test_person_without_login.py`

### Implementation for User Story 4

- [ ] T055 [US4] Create `Person` / `PersonCreate` schemas in `api/user-management/backend/src/models/person.py`
- [ ] T056 [US4] Implement `POST /persons` per FR-002 in `api/user-management/backend/src/api/routers/persons.py` — no credential parameter is accepted at all, not merely optional
- [ ] T057 [US4] Implement `invite_account()` in `api/user-management/backend/src/services/person_service.py`
- [ ] T058 [US4] Add `POST /persons/{person_id}/invite-account` to `persons.py`

**Checkpoint**: A person with no login is fully usable and is never asked for a password.

---

## Phase 7: User Story 5 - Club admin manages teams and assigns a lead coach (Priority: P3)

**Goal**: Team CRUD with a lead coach who may have no account.

**Independent Test**: Create a team, set the lead coach to a person with no login, join two
swimmers, confirm both resolve the team's athletes.

> Column names differ from `design.md`. Use `lead_coach_person_id` (not `lead_coach_id`) and
> express captain as `team_role='CAPTAIN'` — there is no `as_team_member.title` column.
> data-model.md D2/D3.

### Tests for User Story 5 ⚠️

- [ ] T059 [P] [US5] Contract test for team CRUD in `api/user-management/backend/tests/contract/test_teams_contract.py`
- [ ] T060 [P] [US5] Integration test: `lead_coach_person_id` accepts a person with **no** account — a coach is a person, not a login - `api/user-management/backend/tests/integration/test_teams.py`
- [ ] T061 [P] [US5] Integration test: captain is `team_role='CAPTAIN'` and grants no additional permission - `api/user-management/backend/tests/integration/test_teams.py`
- [ ] T062 [P] [US5] Integration test: a coach with an active `coach` membership at club A is authorized for **every** team in club A via `app_has_club_role(club, ['coach'])`, and no `app_is_team_lead` function exists in the database (OQ #2, club-wide) - `api/user-management/backend/tests/integration/test_teams.py`

### Implementation for User Story 5

- [ ] T063 [US5] Create `Team` / `TeamMember` models in `api/user-management/backend/src/models/team.py` using the real column names
- [ ] T064 [US5] Implement `api/user-management/backend/src/api/routers/teams.py` - CRUD (FR-004), and allow `lead_coach_person_id` to reference a person with no account (REQ-003) — CRUD with roster management
- [ ] T065 [US5] Do **not** create `app_is_team_lead(team uuid)` — OQ #2 resolved 2026-10-04 to club-wide coach scope, so `app_has_club_role(club, ['coach'])` covers it. `as_team.lead_coach_person_id` is still maintained as data for display and athlete-team analytics, but grants no permission. T062 asserts the helper's absence. If team-scoped coaching is ever approved it MUST be a `SECURITY DEFINER` helper reading `as_team.lead_coach_person_id`, never a claim. - `api/user-management/supabase/migrations/05_org_model.sql`
- [ ] T066 [US5] Normalize role casing at the boundary — `as_club_membership.role` is lowercase, `as_team_member.team_role` is UPPERCASE; document which casing each endpoint uses (data-model.md D3)

**Checkpoint**: All four delivered stories independently functional.

---

## Phase 8: User Story 6 - Athlete claims an account (Priority: P3)

**Goal**: Controlled handover of an account that already exists. **OQ #9 resolved 2026-10-04 — no longer contingent.** Ingest does not create accounts (D1 confirmed); `claim-account` is retargeted from seeded conversion to **adoption** of an existing GoTrue account via a single-use, admin-issued `claim_token`.

**Independent Test**: Claim with a valid `claim_token` and a new password → `as_person_identity` created, `INVITED → ACTIVE`, token issued, audit row written; replay the token → `409 SEEDED_ACCOUNT_EXISTS`.

### Tests for User Story 6 ⚠️

- [ ] T067 [P] [US6] Contract test for `POST /auth/claim-account` in `api/user-management/backend/tests/contract/test_claim_account_contract.py`
- [ ] T068 [P] [US6] Integration test: claiming with a new password equal to the current one returns `400 PASSWORD_NOT_CHANGED` - `api/user-management/backend/tests/integration/test_claim_account.py`
- [ ] T069 [P] [US6] Integration test: a successful claim creates the `as_person_identity` row, rewrites the stored email and moves `INVITED → ACTIVE` with an audit row - `api/user-management/backend/tests/integration/test_claim_account.py`
- [ ] T070 [P] [US6] Integration test: a `claim_token` is single-use — replaying a consumed token returns `409 SEEDED_ACCOUNT_EXISTS` and creates no second identity row; an admin-issued token is required (a token cannot be self-minted) - `api/user-management/backend/tests/integration/test_claim_account.py`

### Implementation for User Story 6

- [ ] T071 [US6] Implement `claim_token` issue + consume in `api/user-management/backend/src/services/auth_service.py` — admin issues a single-use token bound to one `person_id`; claim consumes it, sets the chosen password, creates `as_person_identity`. Enforces the D2 ordering rule (`INVITED → ACTIVE` only; `409` on an `ACTIVE` profile). OQ #9 resolved — this is implementation, not a decision.
- [ ] T072 [US6] Implement `claim_account()` in `api/user-management/backend/src/services/auth_service.py`
- [ ] T073 [US6] Add `POST /auth/claim-account` per FR-002 to `api/user-management/backend/src/api/routers/auth.py`

---

## Phase 9: Dashboard consumer (cross-cutting, plan.md Phase B)

**Purpose**: Make the dashboard trust the service. **Unblocked** — the P16/P7 conflicts were ratified as constitution v2.0.0 amendments on 2026-10-04, which P16 clause 3 makes the legal basis for the authorization mirror read here.

- [ ] T074 [P] Implement the BFF login proxy in `backend/src/api/auth.py`, forwarding with `X-Internal-Secret` so the secret never reaches the browser (FR-006)
- [ ] T075 [P] Add BFF proxies for `/auth/register`, `/auth/register-club`, `/auth/clubs` in `backend/src/api/auth.py`
- [ ] T076 Derive `X-Tenant-Id` in `backend/src/api/auth.py` from the caller's own active membership, resolved through `as_club.tenant_id` (REQ-011) — **requires T006**
- [ ] T077 **Remove** `verify_jwt` from `backend/src/api/auth.py` — it decodes with `verify_signature: False` against a hard-coded `"SECRET"`, so any well-formed HS256 body passes (REQ-009, SC-003)
- [ ] T078 [P] Repoint `insights`, `markers`, `uploads` and `timers` onto `backend/src/core/auth.py:get_current_user`, reading rows by `person_id` rather than `auth.users.id`
- [ ] T079 [P] Verify JWT signatures unconditionally and gate the demo mint endpoints on (FR-011) `APP_ENV == "development"` **and** `DEMO_AUTH_ENABLED == true`; `/api/auth/demo-user` currently returns a working session for an arbitrary `person_id` with no gate at all - `backend/src/api/auth.py`
- [ ] T080 [P] Add RLS to `as_club`, `as_team`, `as_team_member` in a new `backend/supabase/migrations/*.sql`, driven by `as_club_membership` (SC-007) - `backend/supabase/migrations/20261003_as_org_rls.sql`
- [ ] T081 Implement `SyncService` in `backend/src/services/sync_service.py` — on-login + daily membership/link feed (REQ-010); 79 result links exist with no reader
- [ ] T082 [P] Add dashboard tests in `backend/tests/` for the BFF proxies and cross-tenant isolation - `backend/tests/test_bff_proxies.py`

**Checkpoint**: Exactly one verified auth path in the dashboard.

---

## Phase 10: Ingest de-credentialing (plan.md Phase B)

**Purpose**: Make SC-001 true. Ingest writes people and memberships, never credentials.

- [ ] T083 Delete `get_or_create_auth_user` and `DEFAULT_PASSWORD` from `scripts/user_mgmt_sync.py` (FR-010, SC-001). Unconditional — OQ #9 is resolved to "ingest creates no accounts", so there are no seeded placeholders left to keep.
- [ ] T084 Remove the runtime `ORG_MODEL_DDL` from `scripts/user_mgmt_sync.py:102-145`, superseded by T010 (research.md D9)
- [ ] T085 [P] Add a test in `tests/test_ingest_no_credentials.py` asserting an import run leaves `auth.users` unchanged and no `user_profile` row `ACTIVE`

---

## Phase 11: Frontend (plan.md Phase C)

**Purpose**: Make the flows reachable by a person. No story's independent test requires UI.

- [ ] T086 [P] Extend `frontend/src/app/core/services/auth.service.ts` with `register`, `registerClub`, `claimAccount`, `enable`, `disable`
- [ ] T087 [P] Create `frontend/src/app/auth/register/` — member registration - `frontend/src/app/auth/register/register.component.ts`
- [ ] T088 [P] Create `frontend/src/app/auth/register-club/` — club/tenant registration - `frontend/src/app/auth/register-club/register-club.component.ts`
- [ ] T089 Rework `frontend/src/app/auth/login/` to render `403 PENDING_APPROVAL` as a pending state rather than a generic error (OQ #3 — a pending user and a wrong password must not look alike) - `frontend/src/app/auth/login/login.component.ts`
- [ ] T090 [P] Give `frontend/src/app/core/guards/role.guard.ts` a club argument, matching `require_club_role`
- [ ] T091 Create `frontend/src/app/dashboards/club-admin/approvals/` — the approval queue - `frontend/src/app/dashboards/club-admin/approvals/approvals.component.ts`
- [ ] T092 [P] Create `frontend/src/app/dashboards/club-admin/add-person/` — no credential fields - `frontend/src/app/dashboards/club-admin/add-person/add-person.component.ts`
- [ ] T093 [P] Create `frontend/src/app/dashboards/club-admin/teams/` — teams and lead coach - `frontend/src/app/dashboards/club-admin/teams/teams.component.ts`
- [ ] T094 Create `frontend/src/app/dashboards/parent/` — family view - `frontend/src/app/dashboards/parent/parent-dashboard.component.ts`

---

## Phase 12: Polish & Cross-Cutting Concerns

- [ ] T095 End-to-end, timed against SC-002: register → approve → login (quickstart S1) - `backend/tests/e2e/test_register_approve_login.py`
- [ ] T096 [P] End-to-end: person with no login is fully usable (S2) - `backend/tests/e2e/test_person_without_login.py`
- [ ] T097 [P] End-to-end: revoke denies on the next request, no re-login (S3) - `backend/tests/e2e/test_revoke_without_relogin.py`
- [ ] T098 [P] Forbidden-claim conformance — `athlete_ids`, scalar `club_id`, flat `roles` (S4) - `backend/tests/e2e/test_forbidden_claims.py`
- [ ] T099 [P] Multi-club role resolution (S5) — **blocked by T008** - `backend/tests/e2e/test_multi_club_roles.py`
- [ ] T100 [P] Ingest creates no credential and stays idempotent (S6) - `tests/test_ingest_no_credentials.py`
- [ ] T101 [P] Exactly one verified auth path — wrong-key and `alg: none` both rejected (S7) - `backend/tests/e2e/test_single_auth_path.py`
- [ ] T102 [P] Add structured JSON logging with correlation IDs to the dashboard backend (principle 10) - `backend/src/core/logging.py`
- [ ] T103 Measure login p95 end to end against the 300ms budget — the extra cross-service hop must be measured, not assumed (principle 9) - `backend/tests/perf/test_login_latency.py`
- [ ] T104 WCAG 2.1 AA pass on the four new pages (principle 8) - `specs/002-club-user-integration/a11y-report.md`
- [ ] T105 Correct the stale references in `design.md` — `lead_coach_id` → `lead_coach_person_id` (§4.2 and §5.1); replace `as_team_member.title check (title = 'Team Captain')` with `team_role = 'CAPTAIN'` and delete the "captain lives in title, not a role" rationale (§4.2); rewrite §6.5 so captain is `team_role='CAPTAIN'` and lead-coach scoping reads as **deferred, not proposed** — OQ #2 resolved club-wide, so `app_is_team_lead(team)` must not read as a planned helper; fix the migration filenames `20260820_full_schema.sql` → `20260927_all_schema_from_scratch.sql`, and the `PASSWORD_NOT_CHANGED` typo (plan.md Complexity Tracking). Also close the three `design.md` passages that still assert the rulings are open: §4.1.1 "one membership upstream" / "relaxing the upstream constraint", §10 item 1 ("an upstream date to confirm") and item 2 (coach scope as an open question), and §11 "Phase 0 — Blocking dependency (upstream, separate repo)". design.md is normative and wins on precedence, so leaving these makes T008 and OQ #2 unruled in practice (plan.md, "Where this plan and design.md disagree, design.md wins").
- [ ] T106 Run the full `quickstart.md` validation and record results against SC-001…SC-008

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies. T006/T007/T008 are ordinary tasks now, not decisions and not an external PR — T006 and T008 touch user-service migrations, T007 is a documentation check. Start all three immediately.
- **Foundational (Phase 2)**: depends on T001; **blocks all user stories**.
- **User Stories (Phases 3–8)**: all depend on Phase 2. US1 → US2 is a real ordering (approval before login is testable); US3, US4, US5, US6 depend only on Phase 2 and can run in parallel.
- **Dashboard (Phase 9)**: depends on US2 (needs the issuer) **and** T007.
- **Ingest (Phase 10)**, **Frontend (Phase 11)**: independent of each other.
- **Polish (Phase 12)**: depends on the stories you intend to ship; T099 additionally needs T008.

### User Story Dependencies

- **US1 (P1)**: Foundational only. The MVP. Nothing else ships first.
- **US2 (P1)**: Foundational only; pairs with US1 — registration has nowhere to land without approval.
- **US3 (P2)**: Foundational only. Needs no account for the child, so it does not depend on US4.
- **US4 (P2)**: Foundational only. Independently valuable — it is the scenario the redesign exists for.
- **US5 (P3)**: Foundational only. T065 is now a *negative* task (do not create the helper); OQ #2 is resolved to club-wide.
- **US6 (P3)**: Foundational only. T071 is implementation, not a decision — OQ #9 is resolved, so US6 is deliverable and may still be deferred whole as a scope choice.

### Critical Path

```text
T001 → T010/T015 → T025 (approve) → T037 (login) → MVP
                                    ↓
                        T077 → T080 → T095 (end-to-end)
                                    ↓
                          T008 ──────→ T099 (multi-club)
```

### Within Each User Story

Tests are written and observed failing before implementation. Models before services,
services before endpoints, endpoint before integration. Story complete before the next.

### Parallel Opportunities

- T002, T003, T004 and T011–T014 are independent of each other.
- Within a story, all test tasks marked `[P]` run together, as do all model tasks.
- US3, US4, US5, US6 can be staffed in parallel once Phase 2 lands.
- Phase 10 (ingest) and Phase 11 (frontend) are fully independent of each other.

---

## Parallel Example: User Story 1

```bash
# All US1 tests together, before any implementation:
Task: "Contract test for GET /members, POST /members/{id}/approve in api/user-management/backend/tests/contract/test_members_contract.py"
Task: "Integration test: approval sets active and writes an audit_log row in api/user-management/backend/tests/integration/test_membership_approval.py"
Task: "Integration test: approving an already-active membership returns 409"
Task: "Integration test: non-admin caller receives 403"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2 only)

1. Phase 1 Setup (T001–T008; T006/T007/T008 are independent and can run in parallel)
2. Phase 2 Foundational (T010–T019)
3. Phase 3 US1 — approve
4. Phase 4 US2 — register + login
5. **STOP and VALIDATE**: run quickstart S1. If a member can register, be approved and log in, the feature has delivered its binding requirement.

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 → S1 validates → the approval gap is closed
3. US2 → S1 end-to-end validates → **MVP: the login path finally exists**
4. US4 → S2 validates → a person can exist without a login (the stated reason for the redesign)
5. US3 → S3 validates → guardianship replaces `athlete_ids`
6. US5 → teams scoped
7. US6 → only if T071 says to keep it

### Parallel Team Strategy

1. Team completes Setup + Foundational together.
2. Then: one developer on US4 (person, no login — highest value per task), one on US3
   (parent links), one on US5 (teams); US2 follows US1 on a single thread because login
   depends on the approval writer existing.
3. Phase 9 dashboard work starts once T007 is ruled and US2 is stable.

---

## Notes

- [P] means different files, no dependencies — verify before marking.
- Every task names a file. If a task cannot name one, it is not ready to be a task.
- T006, T007 and T008 were decision placeholders on 2026-10-03 and became implementation tasks
  on 2026-10-04. T065 is a **negative** task (assert a helper is absent) — it is still work, and
  skipping it lets a stale team-scoped helper ship.
- T008 lives in **this** repository. It was marked `[EXTERNAL REPO]` until 2026-10-04, which was
  wrong: `membership` is defined at `api/user-management/supabase/migrations/01_initial_schema.sql`.
  Nothing external blocks multi-club now.
- Commit after each task or logical group. Stop at every checkpoint to validate the story.
- Avoid: vague tasks, two [P] tasks touching the same file, and cross-story dependencies that break independence.