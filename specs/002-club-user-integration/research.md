# Research: Club / Coach / Athlete / Parent User Integration

**Phase**: 0 | **Date**: 2026-10-03 | **Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

Every decision below resolves a `NEEDS CLARIFICATION` from the plan's Technical Context,
or an Open Question carried from `design.md` §10. Each records what was chosen, why, and
what was rejected — so a later reader can tell a decision from a default.

Live-DB figures quoted here were read from the running `supabase-db` container
(`docker exec supabase-db psql`) on 2026-10-03, not inferred from migrations.

---

## D1. Does ingest keep creating accounts?

**Decision**: **Confirmed 2026-10-04 (OQ #9).** No. `scripts/user_mgmt_sync.py` writes
`as_person` + `as_club_membership` only. The `get_or_create_auth_user` branch (`:525`) is
deleted, not repurposed, and `DEFAULT_PASSWORD` (`:84`) goes with it.

**Rationale**: REQ-001 and REQ-010. The account-creation branch is the sole reason a
parsed PDF produces a credential: a repo-committed `DEFAULT_PASSWORD` (`:84`) and a
generated `<first>.<last>@<club>.swim` address. Live evidence: 9 `auth.users` rows for
18 `as_person`, with 8 people correctly holding no identity — so the model tolerates
account-less people, and the 10 that do have identities are the anomaly, not the norm.

The lifecycle plan already fixed the *status* half of this (`user_mgmt_sync.py:591` now
writes `INVITED`, pinned by `tests/test_auth_provisioning.py::SeededStatusTests`, and all
9 live `user_profile` rows are `INVITED`). What remains unfixed is the credential
itself: `INVITED` blocks login but leaves a valid password in the database.

**Consequence for US6**: rejecting the seeded-placeholder option would have left
`claim-account` with no subject population, because after this decision nothing creates
accounts. Rather than defer the endpoint, US6 is **retargeted to adoption**: the subject
is an existing GoTrue account presented with a single-use, admin-issued `claim_token`.
Claiming creates the `as_person_identity` link and sets the person's chosen password. This
is a strictly smaller attack surface than seeded conversion — no default password is ever
issued, and a claim token cannot be minted without an admin. The 9 pre-existing seeded
accounts are migrated once under this flow and their default passwords rotated.

**Alternatives considered**:
- *Keep seeded placeholders, let `claim-account` (§3.2 of the lifecycle plan) convert
  them.* Rejected as the default because a committed default password is a standing
  liability, and it makes "does this child have an account?" depend on whether a PDF was
  ever parsed for them. **Closed as OQ #9** — the owner adopted this decision.
- *Keep accounts but rotate the password at ingest.* Rejected: still creates an account
  for a minor, which is the thing the redesign exists to avoid.
- *Defer US6 entirely.* Rejected: the endpoint is also the clean path for the 9 accounts
  that already exist, so deferring leaves them with no migration route.

---

## D2. What is the single writer of `user_profile.status = 'ACTIVE'`?

**Decision**: **Amended 2026-10-04.** There are **two** audited writers, not one, and the
invariant is *no unaudited writer* rather than *one writer*:

| Writer | Caller | Precondition |
|---|---|---|
| `PATCH /auth/me/enable` | the account holder, authenticated | profile is `INVITED` or `SUSPENDED` |
| `POST /auth/claim-account` | holder of a single-use admin-issued `claim_token` | profile is `INVITED` |

Both write `ACTIVE` in one transaction with an `audit_log` row carrying `actor` and
`outcome`. Ingest never writes it. **Both routes are permitted** — the previous text of this
entry named two endpoints under a heading that asked for one, which is the contradiction
`/speckit.analyze` flagged as I3.

**Rationale**: Live DB: 9 of 9 `user_profile` rows are `INVITED`; zero `ACTIVE`. The
`status` CHECK already permits `INVITED｜ACTIVE｜SUSPENDED｜SOFT_DELETED`, so the column
is correct and the *transition* is simply missing. Lifecycle plan §2 requires that
"enabled" be answerable from a single column so two answers cannot drift — that guarantee
comes from writing the column in one place per code path, not from permitting only one path
overall. Since claim-account exists for accounts that have no usable password yet (D1),
an enable-only route would leave adoption unable to complete the transition.

**Ordering rule** (the part the two-writer form actually requires): both transitions are
`INVITED → ACTIVE` only. Neither may act on an `ACTIVE` profile (→ `409`), and neither may
move `ACTIVE` to `SUSPENDED` — that is `PATCH /auth/me/disable`, a third writer of a
different column transition, audited the same way.

**Alternatives considered**:
- *Let approval flip both `user_profile.status` and `as_club_membership.status`.*
  Rejected, explicitly and for a good reason (lifecycle §3.3): approving a minor's club
  membership must not hand a twelve-year-old a working login, and granting a login must
  not imply the club accepts the person. Two calls, two audit rows.
- *A database trigger.* Rejected: a trigger cannot authenticate the actor, so the audit
  row would have no `actor`, and P10 requires one.
- *Collapse to one endpoint and have claim-account call enable internally.* Rejected: it
  would hide a privileged actor behind a self-service route and make the audit `actor`
  ambiguous.

---

## D3. What may the JWT carry?

**Decision**: Identity only. Required `sub`, `iss`, `aud`, `exp`, `iat`. `person_id`,
`club_ids`, `roles_by_club`, `team_ids`, `permissions` are cache-only. `athlete_ids`,
scalar `club_id`, `tenant_id`, flat `roles`, `role_type` are forbidden.

**Rationale**: `design.md` §4.3 and `identity-contract.md` §4 are already normative and
`design.md`'s reasoning is sound — SC-004 requires that ending a membership denies access
on the *next* request, which is impossible if scope lives in the token. No new decision is
needed; this entry records that Phase 1 must implement it as written rather than
reopen it.

**Alternatives considered**: *Include roles for cheaper route matching.* This is exactly
what `roles_by_club` already is — cache-only, for UI route matching. Keeping the
distinction explicit is the point.

---

## D4. How is demo auth gated?

**Decision**: `APP_ENV == "development"` **and** `DEMO_AUTH_ENABLED == true`. Both.

**Rationale**: Today the guard is a single `APP_ENV` check (`backend/src/api/auth.py:65-66`)
and `APP_ENV` is **absent from the root `.env`**, so the development branch is the live
one. With `USER_SERVICE_JWT_SECRET` empty the endpoint 503s — but set that one variable
and every `auth.users` row becomes a valid dashboard session with no approval check.
`/api/auth/demo-user` additionally mints a session for an arbitrary `person_id` and is not
gated by anything at all.

**Alternatives considered**:
- *Rely on `APP_ENV=production` being set in real deployments.* Rejected: the failure
  mode is an open auth bypass, and the safe default must not depend on a variable being
  remembered.
- *Delete the demo endpoints.* Rejected — legitimate dev affordance, and `design.md`
  §5.2.1 says so explicitly. The defect is the *single*-flag gate, not the endpoints.

---

## D5. `tenant` ↔ `club` mapping — first-class table or `code` match?

**Status**: **RESOLVED 2026-10-04 (OQ #8) — first-class `as_club.tenant_id` FK.**

**Decision**: `as_club` gains a `tenant_id UUID NOT NULL REFERENCES tenant(id)` column.
Existing rows are backfilled by matching `as_club.code` = `tenant.code` (7 of 7 in the live
DB) and the mapping is verified to 7/7 before the NOT NULL is applied. No separate mapping
table is created.

**Rationale**: `design.md` §1 makes the user service the owner of clubs and tenancy, and
§5.1 has the BFF derive `X-Tenant-Id` from the caller's membership. Live DB: 7 `tenant`
and 7 `as_club` rows with **no table joining them** — they correspond only by the `code`
string. That works at n=7 and breaks the moment a club is renamed, a code is reused, or a
tenant spans more than one club (which P16's per-club membership model permits).

**Why a column and not a mapping table**: `as_club` is already the consumer-side tenant
boundary, and `as_club.code` is already `UNIQUE`. A join table would add a third object
that must be kept in sync with both sides and would still permit a many-to-many that the
product does not need — one club belongs to one tenant; a tenant may own several clubs,
which a FK expresses directly. It also keeps `X-Tenant-Id` derivable in a single indexed
lookup (`membership → as_club → tenant_id`) inside the BFF, with no second join.

**Alternatives considered**:
- *Match on `code`.* Simplest, no schema change, fine for the current dataset. Rejected
  as a default because it makes a rename a data-corruption event and cannot express a
  tenant with multiple clubs. Kept only as the **backfill mechanism**, which runs once
  under supervision.
- *Drop `tenant` entirely and make `club` the only tenancy boundary.* Attractive, and it
  removes a redundant concept — but it is a breaking change to the user service's existing
  `X-Tenant-Id` contract and every role/permission seed. Too large for this feature; worth
  raising separately.

---

## D6. Should the `as_result_person_link` backfill be in scope? (OQ #6)

**Decision**: **Out of scope as new work; verify existing coverage only.**

**Rationale**: Live DB has 79 links — 36 `as_meet_figure_result` and 43
`as_meet_routine_result` — against 36 figure results and 13 routine results, with **0
unlinked figure results**. The backfill the question asks about appears already done by
`scripts/routine_identity.py` (`LINK_TABLE`, `:40`) and `ingest_routines.py:1362`. What
is genuinely missing is the *consumer*: no service or API reads these links, so resolution
happens only inside ingest. That is Phase B `SyncService` work (REQ-010), not a backfill.

**Alternatives considered**: *Treat name-correction re-resolution as in scope.* It is a
real gap — `as_result_person_link.athlete_name` preserves the PDF's exact wording, so a
corrected name in a later PDF leaves older links pointing at the old string. Deferred
because the 178-PDF corpus still has unresolved names needing human decisions, not code.

---

## D7. `as_person` without a membership — permitted or not? (OQ #10)

**Decision**: Permit it, but do not create such rows yet.

**Rationale**: Live DB has 0 persons without a membership, and every creation path in
`design.md` §5.1 is club-scoped (`POST /persons` requires `club_id`). So the invariant
"every person belongs to at least one club" holds in practice. Leaving the schema
permissive costs nothing and avoids a future migration; creating such rows would break
the club switcher and every RLS helper, which would have no club to resolve.

**Alternatives considered**: *Add a `NOT NULL`-style constraint or a trigger enforcing at
least one membership.* Rejected as premature — it constrains a case the product does not
have, and triggers around membership creation would have to be deferred transactions.

---

## D8. Do we replace `membership` or relax its unique constraint? (OQ #1, blocking)

**Status**: **RESOLVED 2026-10-04 (OQ #1) — relax it, and land it here.** `membership`
keeps `user_id` as its subject and gains multi-role via `UNIQUE (tenant_id, user_id,
role_id)`. It is **not** replaced by the `as_*` tables. The migration is
`api/user-management/supabase/migrations/06_membership_multi_role.sql` — an ordinary
migration in this tree, not an upstream PR.

**Correction to the earlier assessment**: this was recorded as `[EXTERNAL REPO]` and
"blocking, upstream, needs an owner with a date". That was wrong on both counts. The
table is defined in this repository at
`api/user-management/supabase/migrations/01_initial_schema.sql`:

```sql
CREATE TABLE public.membership (
    ...
    UNIQUE (tenant_id, user_id)
);
```

The submodule sits in the same working tree with the same migration discipline, so
nothing about this change requires a second repository or a second owner. The blocker was
self-imposed.

**What the relaxation does and does not buy**: it permits one user to hold several roles
in one tenant, which is what unblocks US2 scenario 3 and the S5 cross-club check. It does
**not** make person-without-login representable — `membership.user_id` is `NOT NULL`, so a
person with no login cannot appear in it at all. REQ-001 is satisfied by the `as_*` tables
alongside `membership`, not by `membership`. Both statements are now in REQ-012 so the
distinction cannot be lost again.

Live: 9 `membership` rows, 15 `role` rows (`ORG_ADMIN`, `ORG_USER`, `PLATFORM_ENGINEER`
across three tenants) — the legacy tenant/role vocabulary, not the 002 role set. The
migration must therefore widen the constraint without attempting to migrate the legacy
rows into `as_club_membership`; that mapping stays a separate concern (research D5 note).

**Alternatives considered**:
- *Replace `membership` outright with the `as_*` tables.* Rejected: it is a breaking change
  to the user service's `X-Tenant-Id` contract, its role/permission seed and its audit
  triggers, and it buys nothing that D5's FK does not already give.
- *Migrate `membership` data into `as_club_membership` with a mapping table.* Required
  eventually, or the 9 existing memberships are orphaned, but not a prerequisite for
  unblocking multi-role.

---

## D9. Where does `ORG_MODEL_DDL` go?

**Decision**: Into `05_org_model.sql` as real migrations, and out of the ingest script.

**Rationale**: `scripts/user_mgmt_sync.py:102-145` defines `ORG_MODEL_DDL`, creating
`as_club_membership` and friends at runtime. The user service's own migration history
(`01_initial_schema.sql` … `04_audit_trigger.sql`) therefore does not describe the
schema the service actually runs against. That is the schema-drift class of bug P12's
gates exist to catch, and it makes `db reset` non-reproducible.

**Alternatives considered**: *Leave the DDL in the script and add a separate service
migration.* Rejected — two sources of truth for the same DDL.

---

## D10. Corrections to normative documents

`design.md` §2.1 (line 97) and §5.3 / §11 (line 1012) cite
`backend/supabase/migrations/20260820_full_schema.sql` as the file a fresh install gets.
**That file does not exist.** The chain is:

- `backend/supabase/migrations/20260826_person_identity_migration.sql`
- `backend/supabase/migrations/20260927_all_schema_from_scratch.sql`

`design.md` also refers to the latter as `20260827_…` elsewhere. Separately, the two
files' **filename order inverts their header order** (`20260826`'s header states it
follows `20260927`), which matters for a fresh apply.

Raised as a documentation-correction task rather than fixed here, because the citation
sits inside normative sections and the Phase B RLS verification step names it as its
target — so `design.md` must be corrected, not just this plan.

---

## Resolved vs deferred

**Resolved here**: D1 / OQ #9 (ingest credentials — confirmed; US6 retargeted to account
adoption), D2 (writers of `ACTIVE` — two audited writers plus an ordering rule), D3 (JWT
contents — implement `design.md` as written), D4 (demo-auth gating), D5 / OQ #8 (tenant↔club
— first-class `as_club.tenant_id` FK), D6 (result-link backfill scope), D7 (person without
membership — schema permits, no rows created), D8 / OQ #1 (the `membership` constraint —
relaxed, landing here as `06_membership_multi_role.sql`), D9 (runtime DDL → migration), D10
(doc corrections).

**Deferred to the owner**: `design.md` §10 items 3 (pending state rendering), 4
(`birth_date` source) and 5 (permission seed set, advisory). Plus OQ #10 (whether a person
may exist without any membership) — research D7 permits the schema but no current code path
creates such a row.

**Escalated as governance — now closed**: Constitution principles 16 and 7 were recorded
here as not resolvable at this level. They were escalated to the owner and **amended in
`.specify/memory/constitution.md` v1.2.0 → v2.0.0** on 2026-10-04: P16 now permits an
RLS-scoped authorization mirror under four conditions, P7 now sanctions GoTrue credential
authentication alongside OAuth2. See [plan.md](./plan.md) → Complexity Tracking and
[spec.md](./spec.md) → Clarifications, session 2026-10-04.