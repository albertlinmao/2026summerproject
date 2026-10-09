# Implementation Plan: Club / Coach / Athlete / Parent User Integration

**Branch**: `002-club-user-integration` | **Date**: 2026-10-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/speckit.specify` → `specs/002-club-user-integration/spec.md`

**Normative companions**: [`design.md`](./design.md) (architecture, data model, claims
contract, flows) · [`auth-users-lifecycle-plan.md`](./auth-users-lifecycle-plan.md)
(account lifecycle) · [`../001-analytics-dashboard/identity-contract.md`](../001-analytics-dashboard/identity-contract.md)
(identity vocabulary). Where this plan and `design.md` disagree, `design.md` wins and
this plan is wrong.

## Summary

Turn the dashboard from single-club demo auth into multi-club, membership-authorized
identity, with the user-management service as the sole token issuer. Deliver, in order:
the approval gate that today has no writer (nothing can leave `user_profile.status =
'INVITED'`), the login/register surface that does not exist, the person-without-login
path that is the stated reason the design changed, and removal of the unverified
`verify_jwt` dependency that four data routers rely on.

Technical approach: a new `05_org_model.sql` in the user service owning
`as_person` / `as_person_identity` / `as_club_membership` / `as_person_link` / `as_team` /
`as_team_member`; RS256 issuance with a published JWKS; the dashboard BFF proxying public
auth calls and resolving authorization per request from `as_club_membership` through
`SECURITY DEFINER` helpers rather than from claims; and ingest restricted to writing
people and memberships, never credentials.

## Technical Context

**Language/Version**: Python 3.11+ (dashboard FastAPI; user service FastAPI ≥0.115.0), TypeScript ~6.0.0 (Angular 22)

**Primary Dependencies**:
- Dashboard backend: `fastapi>=0.100.0`, `uvicorn>=0.23.0`, `pyjwt>=2.8.0`
- User service: `fastapi>=0.115.0`, `pyjwt>=2.10.1`, `pytest>=8.3.3`, `pytest-cov>=4.1.0`, `httpx>=0.27.2`
- Frontend: `@angular/core ^22.0.0`, `@angular/material ^22.0.0`, `@ngrx/signals ^21.1.1`
- Supabase (GoTrue, PostgREST, Kong, Postgres 15.8) for both stacks

**Storage**: PostgreSQL 15.8 via Supabase, RLS for tenant isolation. Dashboard stack `supabase-db`; user service `api/user-management/supabase/`. Redis present in the dashboard compose but not on this feature's path.

**Testing**: `pytest` + `pytest-cov` (user service). **Gap: `backend/requirements.txt` declares no test dependency at all** — the dashboard has `tests/test_auth_provisioning.py` but no pinned runner. Add `pytest`/`pytest-cov`/`httpx` to the dashboard backend before Phase B, or P3 compliance is unverifiable.

**Target Platform**: Local Docker Compose (Windows host). Dashboard FastAPI on `:8080`, Kong `:8000`, Postgres `:5432`; user service FastAPI on `:8001`.

**Project Type**: web-service — two FastAPI backends + one Angular SPA + Python ingest scripts

**Performance Goals**: API p95 < 300ms (constitution §9). Login now costs an extra user-service round trip plus a GoTrue password verification; the budget must be measured end-to-end, not asserted. `as_club_membership` lookups inside RLS helpers must stay indexed on `(person_id, club_id, status)`.

**Constraints**: Signature verification is unconditional (P7). `X-Internal-Secret` never reaches the browser. GoTrue owns credentials — the project never stores or reads a plaintext password. Ingest stays idempotent and preserves the PDF's exact `athlete_name`.

**Scale/Scope**: Local dev dataset is small — 18 `as_person`, 10 identities, 18 memberships, 7 clubs/tenants, 9 `auth.users`, 79 result links (36 figure / 43 routine). But the corpus is 178 routine PDFs → 1,607 athletes → 17,065 scoring rows, so sync must batch.

## Constitution Check

*GATE: re-checked 2026-10-04 against constitution **v2.0.0**. **PASS.** The two conflicts
that produced a CONDITIONAL PASS were escalated to the owner and ratified as amendments
(P16 and P7); see Complexity Tracking for what changed and why. No remaining principle is
unresolved.*

| # | Principle | Status | Evidence / Required action |
|---|---|---|---|
| 1 | API First | **WAS FAILING → fixed by this plan** | 002 had no OpenAPI at all; `design.md` §5 specified endpoints as markdown prose. `contracts/openapi.yaml` is a Phase 1 deliverable. P12 makes this a merge gate. |
| 2 | Domain First | Pass | Domain model precedes UI; `identity-contract.md` normative; no UI work in Phases 0–B. |
| 3 | Test First | **At risk → Phase 0** | Dashboard backend pins no test runner. P3 v2.0.0 now states all four suites are normative and that "No tests → No Merge" requires a *recorded run*, not a test directory. T001 pins the runner before any test task. Required suites: unit (status gates), contract (OpenAPI validation), integration (RLS helpers, cross-tenant), e2e (register → approve → login; revoke → next-request denial). |
| 4 | Data Integrity | Pass | `as_result_person_link.athlete_name` keeps the PDF's exact wording; ingest is idempotent. |
| 5 | Immutable Competition Records | N/A | This feature adds no write path to results. |
| 6 | Multi-Tenant | **At risk → Phase 1** | Live DB has **no RLS on `as_club`, `as_team`, `as_team_member`**. `as_team`/`as_team_member` hold roster data. SC-007 requires policies driven by `as_club_membership`. Also OQ #8: no `tenant`↔`club` mapping exists — the two 7-row tables join only by `code` string. |
| 7 | Security | **Amended — sanctioned by v2.0.0** | P7 v2.0.0 permits *either* OAuth2 *or* GoTrue-managed credential authentication, delegated to the user service, and adds RS256-with-published-JWKS, unconditional verification, per-request database authorization, and absolute credential ownership. `design.md` §5.1's GoTrue `sign_in_with_password` is now compliant. Signature verification is currently *absent* on four routers (`verify_jwt`, `verify_signature: False`) — REQ-009 fixes this. |
| 8 | Accessibility | **At risk** | Four new pages (register, register-club, club-admin, parent dashboard) plus a reworked login pending-state. WCAG 2.1 AA is a Phase C gate; no automated check exists yet. |
| 9 | Performance | **At risk** | Login gains a cross-service hop. Needs a measured budget, not an assumption. |
| 10 | Observability | **At risk** | FR-012 covers `audit_log`. Structured JSON logging + correlation IDs are **not** yet present in the dashboard backend; the user service has its own constitution requiring them. |
| 11 | AI Governance | N/A | No AI surface in this feature. |
| 12 | CI/CD | **Blocked by #1** | "No API spec → No Merge" cannot pass until `contracts/` exists. |
| 13 | Standardized Technology Stack | Pass | Angular 22 + Material + NgRx Signals, FastAPI, Supabase/Postgres/RLS. Stack matches. |
| 14 | Layered Analytics | N/A | Feature gates access to analytics; it computes none. |
| 15 | Phased ML Delivery | N/A | — |
| 16 | External User Management | **Amended — sanctioned by v2.0.0** | P16 v2.0.0 permits an **RLS-scoped authorization mirror**: the dashboard MAY hold `as_person`, `as_club_membership`, `as_person_link` and `as_team`, provided it is populated only from the user service's feed, every mirror table has RLS driven by `as_club_membership`, authorization resolves per request rather than from claims, and the mirror is rebuildable from the feed. Credentials, password material and refresh tokens remain absolutely prohibited. The user service is still the single system of record. |

### Gate verdict

**PASS as of 2026-10-04.** Phases 0 and 1 proceed, and Phase B implementation is unblocked:
the P16 and P7 conflicts are ratified amendments, `contracts/` exists (P12's first gate), and
the dashboard test runner is T001. Principle 3 remains the live risk — it is satisfiable but
only once T001 lands, so it is tracked as a gate on the first Phase B merge rather than on the
plan.

Note what changed since the previous verdict: "an owner ruling for principle 16" is closed by
amendment, not by exception. Nothing in this plan was permitted to proceed silently in the
meantime, which is why the deviation was recorded rather than absorbed.

## Phase 0 — Research decisions

Recorded in [`research.md`](./research.md). Decisions taken, each with rationale and
rejected alternatives:

1. **Ingest writes no credentials** — **confirmed 2026-10-04 (OQ #9).** `user_mgmt_sync.py` keeps creating `as_person` + membership; the account-creation branch (`:525`) and `DEFAULT_PASSWORD` (`:84`) are deleted rather than kept. `claim-account` is retained but retargeted from seeded conversion to **account adoption** via a single-use, admin-issued `claim_token`, so US6 keeps a subject population without ingest minting credentials.
2. **Writers of `ACTIVE`.** Two audited writers — `PATCH /auth/me/enable` (self-service) and `POST /auth/claim-account` (adoption) — plus `PATCH /auth/me/disable` for the reverse transition. The invariant is *no unaudited writer*, with an explicit `INVITED → ACTIVE`-only ordering rule. Never ingest.
3. **Authorization from the database, always.** Claims stay cache-only; `athlete_ids` branch deleted with no fallback. Coach scope is **club-wide** (OQ #2); no `app_is_team_lead()`.
4. **Demo auth double-gated.** `APP_ENV=development` **and** `DEMO_AUTH_ENABLED=true`.
5. **Approval ≠ activation.** Separate calls, separate audit rows (lifecycle §3.3).
6. **Migration `05_org_model.sql` replaces the runtime `ORG_MODEL_DDL`.** Inline DDL at `user_mgmt_sync.py:102-145` currently creates the org tables outside migration history.
7. **`unique (tenant_id, user_id)` → `(tenant_id, user_id, role_id)`** — **resolved 2026-10-04 (OQ #1)**, landing in this repo as `06_membership_multi_role.sql`. It unblocks multi-*role* only; person-without-login stays with the `as_*` tables (REQ-012).
8. **`tenant` ↔ `club` mapping — first-class `as_club.tenant_id` FK** — resolved 2026-10-04 (OQ #8), backfilled by `code` match with a 7/7 verification gate.

## Phase 1 — Design artifacts

| Artifact | Contents |
|---|---|
| [`data-model.md`](./data-model.md) | Entities, fields, relationships, state machines for `user_profile` and `as_club_membership`, plus the tenant↔club mapping decision (OQ #8). |
| [`contracts/openapi.yaml`](./contracts/openapi.yaml) | **User-management service** (`/api/v1`) — 22 paths / 24 operations / 20 schemas: `POST /auth/login｜register｜register-club｜claim-account`, `GET /auth/clubs｜me`, `PATCH /auth/me/enable｜disable｜password`, `POST /persons`, `POST /persons/{id}/invite-account`, `GET /members`, `POST /members/{id}/approve｜reject｜roles`, `DELETE /members/{id}`, person-link CRUD, team CRUD. |
| [`contracts/dashboard-bff.yaml`](./contracts/dashboard-bff.yaml) | **Dashboard BFF** (`/api`) — 4 public proxies. Split from the user-service contract because the two have different base paths and trust models; a single merged document silently collapses duplicate path keys. Documents the `verify_jwt` and demo-auth defects this contract must not carry forward. |
| Error model (both) | `401 INVALID_CREDENTIALS` · `403 PENDING_APPROVAL` · `403 ACCOUNT_SUSPENDED` · `403 NO_ACTIVE_MEMBERSHIP` · `400 PASSWORD_NOT_CHANGED` · `409 SEEDED_ACCOUNT_EXISTS`. Each 403 is distinguishable, because a pending user and a wrong password must not read the same. |
| [`quickstart.md`](./quickstart.md) | Runnable validation of register → approve → login, person-with-no-login, parent link + revoke-without-relogin, forbidden-claim rejection, and cross-club isolation. |

## Project Structure

### Documentation (this feature)

```text
specs/002-club-user-integration/
├── spec.md                      # requirements (created this session)
├── plan.md                      # this file
├── design.md                    # normative architecture (pre-existing)
├── auth-users-lifecycle-plan.md # normative account lifecycle (pre-existing)
├── research.md                  # Phase 0
├── data-model.md                # Phase 1
├── quickstart.md                # Phase 1
└── contracts/
    ├── openapi.yaml             # Phase 1 — user service (/api/v1)
    └── dashboard-bff.yaml       # Phase 1 — dashboard BFF (/api)
```

### Source Code (repository root)

```text
api/user-management/                  # IDENTITY + ORG SERVICE — token issuer (Phase A)
├── backend/src/
│   ├── api/routers/                 # add: auth.py, members.py, persons.py,
│   │                                #       teams.py, person_links.py
│   ├── api/v1/endpoints/            # existing tenants/users/roles/audit
│   ├── core/                        # security.py — needs RS256 signer + JWKS
│   ├── services/                    # auth service, membership approval, sync
│   ├── models/ repositories/ schemas/
│   └── tests/                       # pytest + pytest-cov, cross-tenant isolation
└── supabase/
    ├── migrations/                  # + 05_org_model.sql (Phase A)
    └── init/                        # tenant_api_keys.sql, seed_permissions.sql

backend/                              # DASHBOARD — consumer (Phase B)
├── src/
│   ├── api/                         # auth.py BFF proxies; + members.py, teams.py
│   │                                # auth.py:verify_jwt REMOVED (REQ-009)
│   ├── core/                        # auth.py JWKS verify; config.py DEMO_AUTH_ENABLED
│   ├── models/ services/            # + SyncService (membership/link feed)
│   └── main.py
├── supabase/migrations/             # RLS for as_club, as_team, as_team_member
└── tests/                           # + pytest runner (currently undeclared)

frontend/src/app/                     # SPA (Phase C)
├── core/services/auth.service.ts    # + register, claimAccount, enable, disable
├── core/guards/                     # role.guard.ts gains club scope
├── auth/login/                      # rework: pending-approval state
├── auth/register/                   # new: member registration
├── auth/register-club/              # new: club/tenant registration
└── dashboards/{club-admin,parent}/  # approval queue, add-person, teams, family

scripts/                              # ingest (Phase B)
└── user_mgmt_sync.py                # ORG_MODEL_DDL removed; account branch deleted

supabase/functions/api-gateway/       # edge gateway — header propagation
tests/                                # repo-level: test_auth_provisioning.py, test_ingest.py
```

**Structure decision**: keep the existing two-backend split. `design.md` §1 fixed the
boundary — the user service *issues* identity, the dashboard *authorizes* against its own
membership mirror — and collapsing it was explicitly rejected in `design.md` §1.1. Phases
are sequenced by that boundary, not by directory.

## Phase sequencing

Per `design.md` §11, ordered by dependency:

- **Phase 0** (this repo, blocking) — `06_membership_multi_role.sql`: drop `UNIQUE (tenant_id, user_id)` on `membership`, add `(tenant_id, user_id, role_id)`. Lands here, not upstream (OQ #1, ruled 2026-10-04). Multi-club roles are untestable until it does.
- **Phase A** — `05_org_model.sql`, RS256 signer + JWKS, auth endpoints, approve/enable/claim, membership + person-link + team CRUD, RLS in the service.
- **Phase B** — BFF proxies, remove `verify_jwt`, `SyncService`, ingest de-credentialing, dashboard RLS completion, `require_club_role`.
- **Phase C** — frontend: login pending state, register, register-club, club switcher, club-admin approval + add-person + teams, parent dashboard.
- **Phase D** — e2e hardening: seed the full journey, forbidden-claim conformance, revoke-without-relogin, load/observability checks, docs.

Phase D is verification across A–C, not a separate build.

## Complexity Tracking

> Filled because the Constitution Check has deviations that must be justified.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| **Principle 16 conflict** — dashboard holds `as_person`, `as_club_membership`, `as_person_link`, `as_team` locally, which v1.2.0 forbade ("only UUID references… never duplicating profile or auth data") | RLS must evaluate membership **inside** Postgres at query time. A remote HTTP call per row is not viable inside a policy, and a token claim cannot express revocation (SC-004 requires denial on the next request). | *Single service owning both identity and analytics* — rejected in `design.md` §1.1: the dashboard would then hold credentials and PII. *Claims-only authorization* — rejected: goes stale, no revocation. **RESOLVED 2026-10-04: ratified as a constitution amendment**, not an exception. P16 v2.0.0 now permits an RLS-scoped authorization mirror under four conditions (feed-only population, RLS on every mirror table, per-request resolution, rebuildable from the feed). Credentials and tokens stay prohibited absolutely. This is the one entry here that required a MAJOR version bump, because it reverses an existing MUST. |
| **Principle 7 deviation** — GoTrue `sign_in_with_password` instead of OAuth2 | GoTrue is the identity provider and does support OAuth providers, but the club-registration and claim-account flows are email/password by nature; a minor is created by an admin, not by an OAuth redirect. | *Adding an OAuth provider* — deferred; password auth is required regardless for seeded-account claim. **RESOLVED 2026-10-04: ratified as a constitution amendment.** P7 v2.0.0 permits GoTrue-managed credential authentication alongside OAuth2, with the explicit condition that the user service MUST NOT present it as a general-purpose OAuth2 grant nor expose it to third-party clients. The amendment also added RS256-with-published-JWKS, unconditional verification, per-request database authorization, and absolute credential ownership — all of which this plan already assumed. |
| **Two FastAPI services + one SPA** (rather than one) | Issuer/consumer split is the corrected model (`design.md` §1.1) and the constitution mandates delegation to an external user service. | *One service* — rejected: dashboard would own credentials/PII. |
| **Migration naming drift** — `design.md` §2.1 and §5.3 cite `20260820_full_schema.sql` as the fresh-install path; that file does not exist. Actual files are `20260927_all_schema_from_scratch.sql` and `20260826_person_identity_migration.sql`, and their filename order inverts relative to their header order | Documents written before the migration chain was rewritten. | *Silently fixing* — no: the citation appears in normative sections and in the Phase B RLS verification step, so it must be corrected in `design.md`, not just here. **Action: raise a doc-correction task; the RLS verification pass must target the real filenames.** |