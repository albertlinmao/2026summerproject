# Data Model: Club / Coach / Athlete / Parent User Integration

**Phase**: 1 | **Date**: 2026-10-03 | **Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)
**Authority**: [`../001-analytics-dashboard/identity-contract.md`](../001-analytics-dashboard/identity-contract.md)
**Architecture**: [`design.md`](./design.md)

All columns, constraints, indexes, policies and row counts below were read from the
running `supabase-db` container on 2026-10-03 (`information_schema`, `pg_constraint`,
`pg_indexes`, `pg_policies`). Nothing here is inferred from migration text. **Three places
where `design.md` disagrees with the live schema are flagged as D1–D3** and need a
documentation correction.

## Entity relationship

```text
auth.users ──1:1──> as_person_identity ──n:1──> as_person
                        (OPTIONAL)                │
                                                 │
as_club ──n:1──> as_club_membership ──n:1──────>─┤   (person_id, club_id, role)
   │                    ▲                        │
   │                    │ status:                │
   │              invited│active│dormant│left    │
   │                    │                        │
   │              as_team ──n:1──> as_team_member ┘
   │                 ▲               ▲
   │      lead_coach_person_id      │
   │                                 │
   └── as_person_link (club_id) ─────┘
          parent_person_id → child_person_id, kind: parent|guardian|emergency_contact

tenant ──1:n──> as_club (tenant_id FK)        ← REQ-011, resolved 2026-10-04 (OQ #8)
as_person ──1:n──> as_result_person_link ──n:1──> as_meet_figure_result | as_meet_routine_result

user_profile ──1:1──> auth.users          (account state; NOT the person)
```

## Entities

### `as_person` — a human at a club

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | PK |
| `given_name` | text | |
| `middle_name` | text | nullable |
| `family_name` | text | nullable (single-token names) |
| `birth_date` | date | nullable; **must not block a membership** |
| `created_at` / `updated_at` | timestamptz | |

**No `club_id`** — the central invariant. **Live: 18 rows.** 8 have no identity row
(minors / dormant / alumni), 0 have no membership.

### `as_person_identity` — optional link to an account

| Column | Type | Notes |
|---|---|---|
| `person_id` | uuid | PK **and** UNIQUE — one identity per person |
| `subject_id` | uuid | UNIQUE; must equal some JWT `sub` |
| `created_at` | timestamptz | |

UNIQUE on both columns: a person has at most one identity, and an auth subject maps to
at most one person. **This is what makes `athlete_ids` unnecessary** — the dashboard
resolves `sub → person_id` directly. **Live: 10 rows.**

### `as_club_membership` — the authorization source

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | PK |
| `person_id` / `club_id` | uuid | FKs |
| `role` | text | CHECK ∈ `admin｜coach｜swimmer｜parent｜official` (lowercase) |
| `status` | text | CHECK ∈ `invited｜active｜dormant｜left` |
| `title` | text | Display only: `Club Owner`, `Lead Coach`. Grants nothing. |
| `joined_at` / `left_at` | date | CHECK `left_at >= joined_at` |

**Partial unique index** `uq_as_club_membership_active ON (person_id, club_id, role) WHERE status IN ('invited','active')`.

> This index is why the dashboard schema **already supports multi-role**: one person may
> be `swimmer` and `coach` at the same club simultaneously, and may hold different roles
> at different clubs. The Phase 0 blocker (`membership` in the *user service*) is the only
> thing preventing that from being exercised end to end.

**Live: 18 rows** — 17 `swimmer/active`, 1 `coach/active`. **No** `parent`, `admin` or
`official` membership exists anywhere.

> **D1 — `design.md` §5.1 says approve sets `approved_by` / `approved_at`. Neither column
> exists.** Approval currently has nowhere to record who approved or when. Either the
> migration adds them, or `design.md` is corrected and attribution lives only in
> `audit_log`. *Recommend adding them* — REQ-004 and FR-012 both want approval
> attributable, and an audit row alone makes the membership row unreadable in isolation.

### `as_person_link` — parent / guardian / emergency contact

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | PK |
| `parent_person_id` / `child_person_id` | uuid | CHECK `parent <> child` |
| `club_id` | uuid | Link is **club-scoped** |
| `kind` | text | CHECK ∈ `parent｜guardian｜emergency_contact` |
| `created_at` | timestamptz | |

**Live: 0 rows.** RLS enabled (2 policies) and `app_is_guardian_of()` exists — but
**nothing in the repository ever inserts here**. The Parent role is currently
unreachable end to end (spec User Story 3).

### `as_team` / `as_team_member`

| `as_team` | Type | | `as_team_member` | Type |
|---|---|---|---|---|
| `id` | uuid | | `id` | uuid |
| `club_id` | uuid | | `team_id` / `person_id` | uuid, UNIQUE together |
| `name` | text | | `team_role` | text |
| `lead_coach_person_id` | uuid | | `created_at` | timestamptz |
| `created_at` | timestamptz | | | |

**Live: 7 teams, 9 members — all `team_role='ATHLETE'`. No lead coach on any team.**

> **D2 — the column is `lead_coach_person_id`, not `lead_coach_id`.** `design.md` §5.1
> says "create, set `lead_coach_id`". Correct the document or the API will be built
> against a column that does not exist.

> **D3 — there is no `as_team_member.title` column, and `team_role` CHECK is
> `COACH｜CAPTAIN｜ATHLETE` in UPPERCASE.** `design.md` §6.5 says the captain "is set as
> `as_team_member.title = 'Team Captain'`". The schema already expresses this as
> `team_role='CAPTAIN'`. Two consequences: (a) §6.5's mechanism does not exist and must
> not be built; (b) **the two role vocabularies disagree on casing** — `as_club_membership.role`
> is lowercase, `as_team_member.team_role` is uppercase. Any future code that compares
> them must normalize, and the contract must document which casing each endpoint uses.

### `as_result_person_link` — imported result → person

| Column | Type | Notes |
|---|---|---|
| `result_table` / `result_id` | text / uuid | Polymorphic target |
| `athlete_name` | text | **The PDF's exact wording** — lineage (P4) |
| `person_id` | uuid | Resolved person, nullable |
| `confidence` / `resolved_at` / `resolved_by` | numeric / timestamptz / uuid | |

UNIQUE `(result_table, result_id, athlete_name)`.

**Live: 79 rows** — 36 figure + 43 routine, against 36 figure and 13 routine results.
**0 unlinked figure results**, so the backfill (OQ #6) is already complete. The missing
piece is a *reader*: no service consumes these links, so resolution happens only inside
ingest (REQ-010, Phase B `SyncService`).

### `user_profile` — account state (user service)

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | PK, FK → `auth.users(id)` |
| `email` | text | declared TEXT — **see below** |
| `first_name` / `middle_name` / `last_name` | text | |
| `status` | text | CHECK ∈ `INVITED｜ACTIVE｜SUSPENDED｜SOFT_DELETED` |
| `deleted_at` / `created_at` / `updated_at` | timestamptz | |

**Live: 9 rows, all `INVITED`.** No `ACTIVE` row exists, so the approval/enable gate has
never been exercised end to end.

> `user_mgmt_sync.py` writes `pgp_sym_encrypt(email)` into this `TEXT` column and reads it
> back with `pgp_sym_decrypt`. That defeats any unique index on `email`, breaks
> reset-by-email lookup, and couples every read to pgcrypto plus a key that is not
> configured under `supabase/.env`. Either encrypt-then-store deliberately with a
> documented lookup strategy (blind index), or store plaintext and rely on
> at-rest encryption. Current state is the worst of both.

## State machines

### `user_profile.status` — may this person *authenticate*?

```text
              ┌──────────────────────────────┐
              │                              │
  (register)  ▼          PATCH /auth/me/enable│  POST /auth/claim-account
  ┌────────────────┐   ┌──────────┐   ┌───────┐
  │ INVITED        │──▶│ ACTIVE   │──▶│ACTIVE │
  │ 403 PENDING_   │   │ may sign │   │       │
  │ APPROVAL       │   │ in       │   │
  └────────────────┘   └─────┬────┘   └───────┘
        ▲                    │ PATCH /auth/me/disable
        │                    ▼
        │            ┌──────────────┐
        └────────────│ SUSPENDED    │  403 ACCOUNT_SUSPENDED
     reactivate      └──────────────┘  all sessions revoked
                            │ GDPR scrub (§4 of lifecycle plan)
                            ▼
                    ┌──────────────┐
                    │ SOFT_DELETED │  401, row retained for audit
                    └──────────────┘
```

`encrypted_password` is deliberately **not** an input: it is a GoTrue bcrypt hash,
unreadable by this project, and a set hash with `INVITED` means "a password exists", not
"this account works" (lifecycle plan §2).

### `as_club_membership.status` — may they act *on this club*?

```text
  POST /auth/register          POST /members/{id}/approve
  or POST /persons        ──▶  invited ──────────────▶ active
                                   │                      │
                                   │ reject               │ DELETE /members/{id}
                                   ▼                      ▼
                                 left ◀──────────────────┘
                                   
                     admin marks           rejoins → invited
                     dormant ◀───────▶ active
```

`user_profile.status` and `as_club_membership.status` are **different questions** and
login checks both, reporting them separately: a person may be `ACTIVE` with every
membership `dormant` (log in, belong nowhere → `403 NO_ACTIVE_MEMBERSHIP`), and `INVITED`
with an `active` membership is a bug meaning approval outran activation.

## RLS helpers (all present)

| Function | Signature |
|---|---|
| `app_current_person_id()` | → uuid |
| `app_current_club_ids()` | → uuid[] |
| `app_active_memberships()` | — |
| `app_has_club_role(p_club_id uuid, p_roles text[])` | → bool |
| `app_is_club_staff(p_club_id uuid)` | → bool |
| `app_is_active_member(p_person_id uuid)` | → bool |
| `app_is_guardian_of(p_parent, p_child, p_club uuid)` | → bool |
| `app_shares_club(p_person_id uuid)` | → bool |
| `app_visible_person_ids()` | → uuid[] |
| `app_can_view_video(p_club_id uuid, p_person_id uuid)` | → bool |
| `app_can_edit_video(p_club_id uuid, p_uploaded_by uuid)` | → bool |

`app_has_club_role` already takes a **role array**, so per-club role checks are supported
without a new helper. **No `app_is_team_lead()` helper is added** — coach authorization is
club-wide in this feature (OQ #2, ruled 2026-10-04), so `app_has_club_role(club,
['coach'])` is sufficient. `as_team.lead_coach_person_id` is maintained as data for
display and athlete-team analytics, but grants nothing on its own. If team-scoped coaching
is ever built it MUST be a `SECURITY DEFINER` helper, never a claim.

### Policies present vs absent

Present: `as_person` (2), `as_person_identity` (1), `as_club_membership` (2),
`as_person_link` (2), `as_result_person_link` (3), `user_profile` (1), plus video/timer/
insight/result tables.

**Absent — no policies at all**: `as_club`, `as_team`, `as_team_member`.

`as_club` is a 7-row global lookup, so the exposure is small. `as_team` and
`as_team_member` hold roster data and are readable by any role reaching the database.
SC-007 requires policies driven by `as_club_membership` for all three.

## Migration target — `05_org_model.sql` (user service)

Replaces the runtime `ORG_MODEL_DDL` at `scripts/user_mgmt_sync.py:102-145`, which
currently creates these tables outside migration history (research D9). Contents:

1. `as_club`, `as_person`, `as_person_identity`, `as_club_membership`, `as_person_link`, `as_team`, `as_team_member` — same shapes as the dashboard mirrors, owned by the service (permitted by constitution v2.0.0 P16 as an RLS-scoped authorization mirror).
2. **`approved_by` / `approved_at` on `as_club_membership`** (D1).
3. **`tenant_id` on `as_club`**, NOT NULL FK to `tenant(id)`, backfilled by `code` match per the four-step procedure in §"Resolved: `tenant` ↔ `club`" (REQ-011, OQ #8).
4. `tenant_api_keys` promoted from `supabase/init/` into a migration (currently init-only).
5. Seed `permission` rows: approve memberships, manage teams, upload/annotate video, view analytics (OQ #5 — advisory; the dashboard does not enforce from them).

**Separate migration, also in this repo**: `06_membership_multi_role.sql` drops
`UNIQUE (tenant_id, user_id)` on `membership` and adds `UNIQUE (tenant_id, user_id,
role_id)` (REQ-012, OQ #1). It is *not* part of `05_org_model.sql` because it alters a
table that file does not create. It widens multi-role but does **not** make
person-without-login representable — `membership.user_id` is `NOT NULL`, so REQ-001 is
carried by the `as_*` tables (research D8).

## Resolved: `tenant` ↔ `club`

**Decision (OQ #8, 2026-10-04)**: `as_club` gains
`tenant_id UUID NOT NULL REFERENCES tenant(id) ON DELETE RESTRICT`. One club belongs to
exactly one tenant; a tenant may own several clubs. Live data has 7 `tenant` and 7
`as_club` rows, so the backfill is 7 rows.

**Backfill procedure** (run once, in this order, verified at each step):

1. `ALTER TABLE as_club ADD COLUMN tenant_id UUID REFERENCES tenant(id);` — nullable first,
   so the existing 7 rows are not blocked.
2. `UPDATE as_club SET tenant_id = tenant.id FROM tenant WHERE tenant.code = as_club.code;`
   — `as_club.code` is already `UNIQUE`, so this is a 1:1 match. Verified 7/7.
3. Assert `SELECT count(*) FROM as_club WHERE tenant_id IS NULL` returns `0`. If it does
   not, **stop** — do not apply step 4. A NULL here means a club exists whose code matches
   no tenant, and forcing a value would invent a tenancy relationship.
4. `ALTER TABLE as_club ALTER COLUMN tenant_id SET NOT NULL;`

> **Applied 2026-10-07 (T006), with one correction to step 2.** Live `public.tenant`
> is `(id, name, status, created_at, updated_at)` — it has **no `code` column**, so
> `WHERE tenant.code = as_club.code` cannot run as written. The real correspondence
> is identity: `as_club.id = tenant.id` for all 7 rows (`design.md` §4.1 "club ==
> tenant"; the same invariant `sql/02_clear_alldata_for_club_using_id.sql` uses).
> `05_org_model.sql` backfills on `id` first with exact `name` equality as a
> fallback, keeps the zero-NULL assertion, and sets `NOT NULL`. Result: 7/7,
> `ON DELETE RESTRICT`, idempotent on re-run. The `code` match is retained here as
> the description of the correspondence, not as executable SQL.

**Why a column and not a join table**: `as_club` is already the consumer-side tenant
boundary and `as_club.code` is already `UNIQUE`; a mapping table would be a third object to
keep in sync and would permit a many-to-many the product does not need. Full reasoning and
rejected alternatives in [research.md](./research.md) D5.

**Effect on `X-Tenant-Id`**: derivation becomes a single indexed lookup —
`as_club_membership → as_club → as_club.tenant_id` — instead of a string comparison against
`tenant.code` that silently breaks on rename.