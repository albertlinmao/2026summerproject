# Feature Specification: Club / Coach / Athlete / Parent User Integration

**Feature Branch**: `002-club-user-integration`
**Created**: 2026-10-03
**Status**: Draft
**Input**: User description: "capture the analysis to modify the design and plan"
**Design**: [`design.md`](./design.md) · **Lifecycle**: [`auth-users-lifecycle-plan.md`](./auth-users-lifecycle-plan.md)
**Identity authority**: [`../001-analytics-dashboard/identity-contract.md`](../001-analytics-dashboard/identity-contract.md) — normative on all identity vocabulary.

> This spec does not restate the design. `design.md` is normative for architecture,
> data model, claims contract and flows; `auth-users-lifecycle-plan.md` is normative for
> the account lifecycle. This document states **what must be true when the feature is
> done**, and carries forward the requirement numbering that `design.md` §6 already
> references but never defined.

## Clarifications

### Session 2026-10-04
Rulings issued to clear the CRITICAL/HIGH findings from `/speckit.analyze`. Each is now
closed; the reasoning lives in `research.md`, and the two governance items were carried
into `.specify/memory/constitution.md` **v2.0.0** rather than waived.

- Q: K1 — P16 forbids local profile/role mirrors, but the design puts `as_person` and `as_club_membership` in the dashboard. → A: **Amended P16.** The user service remains the single system of record for *who a person is* and *what roles they hold*; local databases MAY hold an RLS-scoped authorization mirror under four conditions (feed-only population, RLS on every mirror table, per-request resolution from the database rather than claims, and rebuildable from the feed). Credentials, password material and refresh tokens remain absolutely prohibited. Reversing a MUST is MAJOR, hence 2.0.0.
- Q: K2 — P7 requires OAuth2, but GoTrue `sign_in_with_password` is specified. → A: **Amended P7.** Authentication MUST be delegated to the user service using *either* OAuth2 *or* GoTrue-managed credential authentication, with credential auth explicitly not presented as a general OAuth2 grant. Added RS256-with-published-JWKS and unconditional verification, plus per-request database authorization and an absolute credential-ownership rule.
- Q: T008 was `[EXTERNAL REPO]` and therefore blocked US2 scenario 3, US5 and S5. → A: **Landed in this phase.** `membership` is defined in this tree at `api/user-management/supabase/migrations/01_initial_schema.sql`, so the constraint change is a normal migration here, not an upstream PR. It no longer gates Phase 9.
- Q: OQ #9 — research D1 deletes ingest account creation, which would leave US6 with no seeded population. → A: **Ingest stays de-credentialed; `POST /auth/claim-account` is still built, retargeted to adoption rather than seeded conversion.** Its subject becomes an existing GoTrue account claimed via an admin-issued claim token. `scripts/user_mgmt_sync.py:84` `DEFAULT_PASSWORD` and `:525` `get_or_create_auth_user` stay deleted. US6 is no longer contingent.
- Q: OQ #8 — no `tenant` ↔ `as_club` mapping exists; the two 7-row tables join only by the `code` string, which blocks `X-Tenant-Id`. → A: **First-class `as_club.tenant_id` FK.** Not a separate mapping table: `as_club` is already the consumer-side tenant boundary, `as_club.code` is already `UNIQUE`, and a mapping table would be a third place to keep in sync. Existing 7 clubs backfilled by `code` match and verified to 7/7.
- Q: OQ #2 — is coach scope club-wide or team-scoped? → A: **Club-wide for this feature.** `app_is_team_lead()` is explicitly **not** built here. Coach scope means "any active `coach` membership at the club"; a coach sees all club athletes and teams. Team-scoped authorization is deferred to a follow-up feature.

### Session 2026-10-03
- Q: Which feature owns this spec, given `.specify/feature.json` pointed at `001-analytics-dashboard`? → A: `002-club-user-integration`. `design.md` is the spec-of-record; this file is the requirements surface the plan and tasks derive from.
- Q: May meet-score ingest create a login account? → A: No. Ingest writes `as_person` + `as_club_membership` only. Credentials originate solely from `POST /auth/register` or `POST /auth/claim-account`. (Closes the gap where every parsed athlete received a repo-committed default password.)
- Q: What is the login gate? → A: Two independent gates, reported separately — `user_profile.status = 'ACTIVE'` **and** at least one `as_club_membership.status = 'active'`. (`auth-users-lifecycle-plan.md` §2.)
- Q: Is approving a membership the same as activating a login? → A: No — deliberately separate calls. Approving must not grant a working credential to a minor; activating must not imply the club accepts the person. (lifecycle §3.3)
- Q: What goes in the JWT? → A: Identity only. `sub`, `iss`, `aud`, `exp`, `iat` required; `person_id`/`club_ids`/`roles_by_club` are cache-only; `athlete_ids`, scalar `club_id`, flat `roles`, `tenant_id`, `role_type` are forbidden. Authorization is resolved per request from `as_club_membership`. (`design.md` §4.3)
- Q: What gates the dev-only login/mint endpoints? → A: `APP_ENV == "development"` **and** an explicit `DEMO_AUTH_ENABLED = true`. Single-flag gating is rejected — `APP_ENV` is currently unset, so the dev branch is live by default.

## User Scenarios & Testing

### User Story 1 - Club admin approves a pending member (Priority: P1)

A club administrator must be able to see who is waiting and activate their membership.

**Why this priority**: This is the binding constraint on the entire feature. Every
account currently lands in `user_profile.status = 'INVITED'` and nothing in the
repository ever writes `ACTIVE`. Until one endpoint performs that transition, no user
can complete a login and every other story is undeliverable.

**Independent Test**: Register a member through `POST /auth/register`, confirm login returns `403 PENDING_APPROVAL`, approve via `POST /members/{person_id}/approve`, confirm login now succeeds and the membership reads `active`.

**Acceptance Scenarios**:
1. **Given** a member registered with `status=invited`, **When** the admin lists `GET /members?status=invited`, **Then** the member appears, keyed on `person_id`.
2. **Given** an invited membership, **When** the admin approves it, **Then** `as_club_membership.status` becomes `active`, `approved_by`/`approved_at` are set, and an audit row is written.
3. **Given** an `ACTIVE` profile, **When** every membership is `dormant`/`left`, **Then** login returns `403 NO_ACTIVE_MEMBERSHIP`, not a 401.

---

### User Story 2 - Coach self-registers and logs in (Priority: P1)

A coach must be able to sign up for a club, be approved, and reach club-wide analytics.

**Why this priority**: Coaches are the primary consumer of the dashboard; multi-club role scoping (coach in one club, swimmer in another) is the model correction that motivated this feature.

**Independent Test**: `POST /auth/register` with `role=coach`, approve, log in, and confirm the token carries `roles_by_club` with `coach` for that club and no forbidden claims.

**Acceptance Scenarios**:
1. **Given** a valid club id and `role=coach`, **When** the coach registers, **Then** `user_profile` is `INVITED`, one `as_club_membership(status='invited')` exists, and **no token is returned**.
2. **Given** an `ACTIVE` coach, **When** they log in, **Then** the RS256 token verifies against the dashboard JWKS with `aud` = dashboard `APP_NAME`.
3. **Given** a coach who is a `swimmer` at club B, **When** they switch clubs, **Then** club B resolves `swimmer`, not `coach`, and the dashboard reads that from `as_club_membership`, not from a claim.
4. **Given** a self-registering member requesting `role=admin`, **When** the request is submitted, **Then** it is rejected — admin is granted in-club only.

---

### User Story 3 - Parent sees their child's analytics (Priority: P2)

A parent must be able to register, link to their child, and see that child's scores and videos at the child's club.

**Why this priority**: Replaces the `athlete_ids` JWT claim, which encoded guardianship in a token that went stale and could not express coach-of or self. The table exists and RLS exists, but **no code writes it** — verified `as_person_link = 0` rows.

**Independent Test**: Create a person with no login, register a parent, create an approved link, log in as the parent, and confirm `app_is_guardian_of` passes for that child at that club only.

**Acceptance Scenarios**:
1. **Given** a child with no login, **When** a parent registers and an admin approves a `person-link`, **Then** the parent's session passes `app_is_guardian_of(parent, child, club)`.
2. **Given** the link is revoked, **When** the parent makes a request **without re-logging-in**, **Then** access is denied on the next request.
3. **Given** a parent linked at club A, **When** they query club B, **Then** the child is invisible — the link is club-scoped.

---

### User Story 4 - Club admin adds a person with no login (Priority: P2)

A coach must be able to add a minor, dormant swimmer or alumnus to the roster without ever creating credentials for them.

**Why this priority**: This is the stated reason the design changed. A login-centric model forces either no record, a fabricated account, or modelling the child as their parent.

**Independent Test**: `POST /persons` with no credential fields, then confirm the person appears in `as_athlete` (view) with results and videos, and that no `auth.users` or `as_person_identity` row exists.

**Acceptance Scenarios**:
1. **Given** a club admin, **When** they `POST /persons {given_name, family_name, birth_date, club_id, role, status}`, **Then** an `as_person` row and an `as_club_membership` exist, and **no** auth user, `user_profile`, or `as_person_identity` row exists.
2. **Given** a person with no login, **When** an admin later runs `POST /persons/{person_id}/invite-account`, **Then** `as_person_identity` and an `INVITED` `auth.users` appear — and the person still cannot log in until enabled.
3. **Given** an empty `birth_date`, **When** the membership is created, **Then** the membership is not blocked.

---

### User Story 5 - Club admin manages teams and assigns a lead coach (Priority: P3)

An admin must be able to create a team, assign a lead coach who may have no account, and manage the roster.

**Why this priority**: Teams are required for coach scoping and athlete-team analytics, but `as_team.lead_coach_person_id` is currently unpopulated — all 9 `as_team_member` rows are `ATHLETE` and no coach is attached to any team.

**Independent Test**: Create a team, set `lead_coach_person_id` to a person with no login, join two swimmers, and confirm both resolve the team's athletes.

**Scope note (OQ #2, ruled 2026-10-04)**: coach authorization is **club-wide** in this
feature. Any active `coach` membership at a club grants visibility of every athlete and team
in that club. `app_is_team_lead()` is explicitly **not** built here — see the non-goal below.

**Acceptance Scenarios**:
1. **Given** a person with no account, **When** they are set as `lead_coach_person_id`, **Then** the assignment succeeds — a coach is a person, not a login.
2. **Given** a swimmer on a team, **When** they are marked captain, **Then** `as_team_member.team_role = 'CAPTAIN'` and **no** additional permission is granted.
3. **Given** a coach with an active `coach` membership at club A, **When** they request any team in club A, **Then** it is authorized by `app_has_club_role(club, ['coach'])` and no team-lead helper is consulted.

**Non-goal for this feature**: team-scoped coach authorization (`app_is_team_lead(team uuid)`
reading `as_team.lead_coach_person_id`). Deferred to a follow-up feature; if it is ever built it
MUST be a `SECURITY DEFINER` helper and never a token claim.

---

### User Story 6 - Athlete claims a seeded account (Priority: P3)

An athlete who was ingested from a result PDF must be able to claim their placeholder account and set a real password.

**Why this priority**: This is the controlled handover that lets a person adopt an account
which already exists. Ingest no longer creates one — see the scope note.

**Scope note (OQ #9, ruled 2026-10-04)**: `POST /auth/claim-account` is **built**, but its
purpose is **adoption, not seeded conversion**. The subject is an existing GoTrue account
claimed by presenting a single-use `claim_token` that an admin issues; claiming creates the
`as_person_identity` link and sets the person's chosen password. Ingest does **not** create
accounts (`scripts/user_mgmt_sync.py:84` `DEFAULT_PASSWORD` and `:525`
`get_or_create_auth_user` stay deleted), so this story no longer depends on a PDF ever having
been parsed. The 9 pre-existing seeded accounts are migrated once under this flow.

**Independent Test**: Claim an account with an admin-issued token and a new password, confirm the `as_person_identity` link exists, `status` goes `INVITED` → `ACTIVE`, a token is issued and an audit row is written; then confirm reuse of a claim token returns `409 SEEDED_ACCOUNT_EXISTS`.

**Acceptance Scenarios**:
1. **Given** an admin-issued `claim_token` and an existing GoTrue account, **When** the person claims it with a chosen address and password, **Then** an `as_person_identity` row is created, the email is rewritten to the chosen address, and `status` goes `INVITED` → `ACTIVE`.
2. **Given** the current password still equals a seed default and the new password matches it, **When** claiming, **Then** `400 PASSWORD_NOT_CHANGED`.
3. **Given** a claim token that has already been consumed, **When** it is replayed, **Then** `409 SEEDED_ACCOUNT_EXISTS` and no second identity row is created.

### Edge Cases

- **Membership approved but profile still `INVITED`** — must not happen; if it does, login reports the account gate, not the club gate.
- **Profile `ACTIVE`, every membership `dormant`/`left`** — login succeeds, club scope is empty; return `403 NO_ACTIVE_MEMBERSHIP` rather than a 401, so the user is not told their password is wrong.
- **Token carries a forbidden claim** (`athlete_ids`, scalar `club_id`) — must be rejected or ignored; a documented-but-present claim will eventually be used.
- **Same person, same name, same club** — seeded names are not unique; unresolved links need a human decision, not a guess.
- **Demo auth reachable** — `APP_ENV` unset in `.env` means the dev branch is live; `/api/auth/demo-user` currently returns a session for an arbitrary `person_id`.
- **Unverified `verify_jwt`** — four routers (`insights`, `markers`, `uploads`, `timers`) depend on a decoder with `verify_signature: False` against a hard-coded secret; any well-formed HS256 body passes.
- **Encrypted email defeats uniqueness** — `user_profile.email` is `TEXT` but written via `pgp_sym_encrypt`, so the unique index and any reset-by-email flow do not work as declared.
- **Three tables have no RLS** — `as_club`, `as_team`, `as_team_member` are readable by any role that reaches the database.

## Requirements

Numbering note: `design.md` §6 references `REQ #3`–`#7` but no document ever defined them.
This spec adopts that numbering so the existing cross-references resolve, and extends it.

| Legacy ref | ID | Requirement |
|---|---|---|
| — | REQ-001 | A person MUST be creatable with no login, no credentials and no `as_person_identity` row. |
| — | REQ-002 | The user service MUST own the org model; roles MUST be scoped per `(person, club, role)`. In this feature a `coach` role is scoped **club-wide** (OQ #2); team-scoped coaching is a follow-up. |
| REQ #3 | REQ-003 | Teams MUST support a `lead_coach_person_id` that MAY reference a person with no account. |
| REQ #4 | REQ-004 | Membership approval MUST exist, MUST be the only path that sets a membership `active`, and MUST be audit-logged. |
| REQ #5 | REQ-005 | Login MUST verify credentials and both status gates before minting an RS256 token; a pending user MUST NOT receive a session. |
| REQ #6 | REQ-006 | Club registration MUST create tenant + owner with `role='admin'`, `title='Club Owner'`, `status='active'`, and MUST link the new club to that tenant via `as_club.tenant_id`. |
| REQ #7 | REQ-007 | Member registration MUST accept `coach｜swimmer｜parent｜official` and MUST reject self-selected `admin`. |
| — | REQ-008 | Parent/guardian access MUST resolve from `as_person_link` via `app_is_guardian_of`, never from a token claim. |
| — | REQ-009 | Exactly one verified auth path MUST exist in the dashboard backend; `verify_jwt` MUST be removed or collapsed onto `core/auth.get_current_user`. |
| — | REQ-010 | The dashboard MUST receive a membership/link feed from the user service (on-login + daily), since the schema exists but nothing populates it. |
| — | REQ-011 | `as_club.tenant_id` MUST be a NOT NULL FK to `tenant.id` (OQ #8); `X-Tenant-Id` MUST be derived through it. The `code`-string join MUST NOT remain the only link. |
| — | REQ-012 | `membership` MUST permit more than one role per `(tenant, user)` by relaxing `UNIQUE (tenant_id, user_id)`; person-without-login is represented by the `as_*` tables, not by `membership`. |

### Functional Requirements

- **FR-001**: System MUST expose `POST /auth/login`, `POST /auth/register`, `POST /auth/register-club`, `GET /auth/clubs`, `GET /auth/me` in the user service.
- **FR-002**: System MUST expose `POST /persons` (no-login person), `POST /persons/{person_id}/invite-account`, `POST /auth/claim-account`.
- **FR-003**: System MUST expose membership administration: `GET /members`, `POST /members/{person_id}/approve`, `POST /members/{person_id}/reject`, `DELETE /members/{person_id}`, `POST /members/{person_id}/roles`.
- **FR-004**: System MUST expose person-link CRUD and team CRUD with `lead_coach_person_id`.
- **FR-005**: System MUST require an `admin` membership in the target club for all membership/person/team administration, enforced by the user service's own RLS rather than by a claim.
- **FR-006**: The dashboard BFF MUST proxy public auth calls so `X-Internal-Secret` is never exposed to the browser, and MUST derive `X-Tenant-Id` from the caller's own active membership resolved through `as_club.tenant_id`.
- **FR-007**: `require_role` MUST take a club argument; the `athlete_ids` branch MUST be deleted with no fallback.
- **FR-008**: RLS policies MUST read membership through `SECURITY DEFINER` helper functions; no policy may read a claim other than `sub`.
- **FR-009**: The single writer of `user_profile.status = 'ACTIVE'` MUST be an authenticated, audited endpoint — never the ingest path.
- **FR-010**: Ingest MUST NOT write a usable credential for any person.
- **FR-011**: The dashboard MUST verify JWT signatures unconditionally; demo minting MUST require `APP_ENV=development` AND `DEMO_AUTH_ENABLED=true`.
- **FR-012**: Every state transition on membership, identity and person-link MUST write an `audit_log` row with actor and outcome, never with credential values.

### Key Entities

- **Person** — a human at the club. Carries **no** `club_id`. May have zero or one identity.
- **Person Identity** — optional link from a person to an `auth.users` subject. Absent for minors, dormant swimmers, alumni.
- **Club** — the tenant boundary, referenced by membership and never by person. Carries `tenant_id` → the user service's `tenant` (REQ-011).
- **Club Membership** — `(person, club, role, status, title)`. The authorization source. `title` is display-only and grants nothing.
- **Person Link** — `(parent_person_id, child_person_id, club_id, kind)`. Both ends may lack accounts.
- **Team** — within a club, with an optional `lead_coach_person_id` referencing a person.
- **Team Member** — `(team, person, team_role)`. Captain is `team_role='CAPTAIN'`; there is no `title` column.
- **User Profile** — account state (`INVITED｜ACTIVE｜SUSPENDED｜SOFT_DELETED`), FK to `auth.users`. Distinct from Person.
- **Result Person Link** — maps an imported result row to a person, preserving the PDF's exact `athlete_name`.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of `user_profile` rows created by ingest remain `INVITED`; zero are `ACTIVE` without an audited approval or claim.
- **SC-002**: A registered member can complete register → approve → login unaided in under 3 minutes.
- **SC-003**: 0 of the dashboard's routers resolve identity through `verify_jwt`; exactly one verified auth path remains.
- **SC-004**: Ending a membership denies access on the caller's **next** request, with no re-login.
- **SC-005**: A token carrying `athlete_ids` or a scalar `club_id` is rejected or ignored by the dashboard (conformance test).
- **SC-006**: 100% of membership/person-link/identity state transitions appear in `audit_log`.
- **SC-007**: All of `as_club`, `as_team`, `as_team_member` have RLS enabled with policies driven by `as_club_membership`.
- **SC-008**: A person with no login is fully usable in the dashboard — appears in `as_athlete`, has results and videos, and is never asked for a password.

## Assumptions

- `identity-contract.md` remains normative; this spec does not revisit the 2026-09-16 model correction.
- The user-management service is a separate deployment with its own Supabase stack; in local dev both halves may share one Postgres, so the boundary is enforced by configuration, not by topology.
- GoTrue owns credentials. This project never stores or reads a plaintext password, and `encrypted_password` is never an authorization signal.
- Phase 0 (relaxing `membership`'s `unique (tenant_id, user_id)` → `(tenant_id, user_id, role_id)`) **lands in this repository** as `api/user-management/supabase/migrations/06_membership_multi_role.sql` (OQ #1, ruled 2026-10-04). It is no longer an upstream dependency. Note it unblocks multi-*role* only; person-without-login remains represented by the `as_*` tables, not by `membership` (REQ-001).
- Constitution **v2.0.0** governs this feature: P16 permits an RLS-scoped authorization mirror and P7 sanctions GoTrue credential authentication. Both amendments are ratified as of 2026-10-04.
- Ingest remains idempotent and preserves the PDF's exact athlete name on `as_result_person_link`.

## Open Questions

Carried from `design.md` §10. **Closed 2026-10-04** unless noted; reasoning in `research.md`.

1. ~~**Phase 0 timing**~~ — **RESOLVED.** Lands in this repo as `06_membership_multi_role.sql`; tracked as task T008. See REQ-012.
2. ~~**Coach scope**~~ — **RESOLVED: club-wide.** No `app_is_team_lead()` in this feature; team-scoped coaching deferred. See REQ-002 and US5.
3. **Pending state at login** — `design.md` §7.1 shows a "pending approval" message; the lifecycle plan returns `403 PENDING_APPROVAL`. Confirm the UI renders the 403 as a pending state rather than a generic error. *Still open — frontend phase.*
4. **`birth_date` source** — club-admin person form, and confirm an empty value never blocks a membership. *Still open.*
5. **Permission seed set** — define `permission` rows for approve memberships, manage teams, upload/annotate video, view analytics. Advisory only; the dashboard does not enforce from them. *Still open — advisory.*
6. **`as_result_person_link` backfill** — out of scope as new work (research D6); verify existing coverage only. 79 links, 0 unlinked figure results. *Effectively closed.*
7. **Person with no login** — `invite-account` **is** in scope (US4 scenario 2). *Closed.*
8. ~~**`tenant` ↔ `club` mapping**~~ — **RESOLVED: first-class `as_club.tenant_id` FK**, backfilled from the `code` match. See REQ-011 and research D5.
9. ~~**Ingest credential policy**~~ — **RESOLVED: ingest stops creating accounts** (research D1 confirmed); `claim-account` is retained and retargeted to account adoption via an admin-issued `claim_token`. US6 is no longer contingent on this question.
10. **`as_person` without membership** — Live data has 0 such rows. Should the schema permit it (a person known to the platform but not yet in a club), or is person creation always club-scoped? *Still open — research D7 permits the schema but creates no such rows; needs a product answer before ingest relies on it.*