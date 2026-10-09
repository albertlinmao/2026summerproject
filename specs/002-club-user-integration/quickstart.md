# Quickstart: Validating Club / Coach / Athlete / Parent User Integration

**Phase**: 1 | **Date**: 2026-10-03 | **Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)
**Contracts**: [`openapi.yaml`](./contracts/openapi.yaml) (user service) ·
[`dashboard-bff.yaml`](./contracts/dashboard-bff.yaml) (dashboard BFF)

Runnable scenarios that prove the feature works end to end. Each maps to a numbered
success criterion or a user story, so a failure here is traceable to a requirement rather
than to "something is broken".

These scenarios are **Phase D acceptance checks**. They are written now, before
implementation, so the contract cannot drift from what is actually verified — and so the
Phase 0/Phase B ordering has a fixed definition of done.

> Assumes the migration chain is applied and `05_org_model.sql` exists. Several scenarios
> are expected to **fail today**; that is the point — they are the acceptance bar.

## Prerequisites

```powershell
# Both Supabase stacks + services
docker compose up -d                      # dashboard stack (supabase-db, kong, gotrue…)
docker compose -f api/user-management up -d   # user-management stack

# Dashboard API on :8080, user service on :8001
cd backend; uvicorn src.main:app --port 8080
cd api/user-management/backend; uvicorn src.main:app --port 8001
```

Required configuration — **both** flags, per research.md D4:

```dotenv
# .env — demo auth must be OFF for any acceptance run
APP_ENV=development
DEMO_AUTH_ENABLED=false
USER_SERVICE_JWT_SECRET=            # must be empty; a real secret here defeats the gate
```

```powershell
# DB access: host-side DATABASE_URL is not usable (password differs).
# Authenticate over the container's local socket instead:
docker exec -it supabase-db psql -U postgres -d postgres
```

## Baseline — confirm the starting state

```sql
-- Expect: 18 as_person | 10 as_person_identity | 0 as_person_link
--         18 as_club_membership (17 swimmer, 1 coach, all active)
--         9 user_profile, ALL 'INVITED'
SELECT 'as_person' t, count(*) FROM as_person
UNION ALL SELECT 'as_person_identity', count(*) FROM as_person_identity
UNION ALL SELECT 'as_person_link', count(*) FROM as_person_link
UNION ALL SELECT 'as_club_membership', count(*) FROM as_club_membership
UNION ALL SELECT 'user_profile', count(*) FROM user_profile;

-- Expect: every row 'INVITED'. Any 'ACTIVE' here means ingest wrote it — a defect.
SELECT status, count(*) FROM user_profile GROUP BY status;

-- Expect: three tables with no policies at all
SELECT relname, relrowsecurity FROM pg_class
WHERE relname IN ('as_club','as_team','as_team_member','as_person','as_club_membership');
```

---

## S1 — Register → approve → login *(US1, US2; SC-001, SC-002)*

The binding scenario. Until it passes, nothing else in the feature is reachable.

```powershell
$BFF = "http://127.0.0.1:8080/api"

# 1. Register → expect 201, status "invited", and NO access_token in the response
curl.exe -X POST "$BFF/auth/register" -H "Content-Type: application/json" `
  -d '{"email":"coach.test@ast.swim","password":"Str0ng-Pass-1","first_name":"Test","last_name":"Coach","club_id":"<CLUB_UUID>","role":"coach"}'

# 2. Login before approval → expect 403 PENDING_APPROVAL (NOT 401)
curl.exe -X POST "$BFF/auth/login" -H "Content-Type: application/json" `
  -d '{"email":"coach.test@ast.swim","password":"Str0ng-Pass-1"}'

# 3. Approve as the club admin (Bearer = admin token)
curl.exe -X POST "$BFF/members/<PERSON_ID>/approve" -H "Authorization: Bearer <ADMIN_TOKEN>"

# 4. Login again → expect 200 + access_token
curl.exe -X POST "$BFF/auth/login" -H "Content-Type: application/json" `
  -d '{"email":"coach.test@ast.swim","password":"Str0ng-Pass-1"}'
```

Verify in SQL:

```sql
SELECT status, approved_by, approved_at FROM as_club_membership WHERE person_id = '<PERSON_ID>';
-- Expect: status='active', approved_by NOT NULL, approved_at NOT NULL
-- (approved_by/approved_at arrive with 05_org_model.sql — data-model.md D1)

SELECT status FROM user_profile WHERE id = '<AUTH_USER_ID>';
-- Expect: 'INVITED' — approval does NOT activate the login
```

**Negative checks**
- `role: "admin"` at registration → rejected.
- Approving an already-`active` membership → `409`.
- A non-admin token calling `/members/{id}/approve` → `403`.
- An `ACTIVE` profile with every membership `dormant`/`left` → `403 NO_ACTIVE_MEMBERSHIP`, **not** `401`.

---

## S2 — A person with no login *(US4; REQ-001, SC-008)*

The scenario the whole redesign exists for.

```powershell
# Create a person with NO credential fields
curl.exe -X POST "$BFF/members/../persons" -H "Authorization: Bearer <ADMIN_TOKEN>" `
  -H "Content-Type: application/json" `
  -d '{"given_name":"Mia","family_name":"Novak","birth_date":"2015-04-02","club_id":"<CLUB_UUID>","role":"swimmer","status":"active"}'
```

```sql
-- Expect 1 row, and crucially an identity count of 0 for her
SELECT p.id, p.given_name, p.family_name,
       (SELECT count(*) FROM as_person_identity i WHERE i.person_id = p.id) AS identities
FROM as_person p WHERE p.family_name = 'Novak';
-- Expect: identities = 0

-- She appears in the athlete view with her results, having never been asked for a password
SELECT count(*) FROM as_athlete WHERE family_name = 'Novak';   -- view over person+membership
SELECT count(*) FROM as_result_person_link WHERE person_id = p.id;
```

**Negative check** — the account-creation path must not have run:
```sql
SELECT count(*) FROM auth.users;  -- unchanged from baseline
```

Optional follow-up: `POST /persons/{id}/invite-account` → identity appears, status
`INVITED`, and login still returns `403 PENDING_APPROVAL`.

---

## S3 — Parent link, club scoping, and revocation *(US3; SC-004)*

```sql
INSERT INTO as_person_link (parent_person_id, child_person_id, club_id, kind)
VALUES ('<PARENT_PERSON_ID>', '<CHILD_PERSON_ID>', '<CLUB_A_UUID>', 'parent');

-- Helper is the authorization source
SELECT app_is_guardian_of('<PARENT_PERSON_ID>', '<CHILD_PERSON_ID>', '<CLUB_A_UUID>');  -- true
SELECT app_is_guardian_of('<PARENT_PERSON_ID>', '<CHILD_PERSON_ID>', '<CLUB_B_UUID>');  -- false — club-scoped

-- Revocation: delete, then re-check WITHOUT re-issuing a token
DELETE FROM as_person_link WHERE parent_person_id = '<PARENT_PERSON_ID>';
SELECT app_is_guardian_of('<PARENT_PERSON_ID>', '<CHILD_PERSON_ID>', '<CLUB_A_UUID>');  -- false
```

**The revocation check is the important one.** It only passes because the token carries no
club scope — the answer comes from the table on every request. If it passes only after a
re-login, authorization has leaked into the token and SC-004 fails.

**Negative check**: `parent_person_id = child_person_id` → rejected by
`ck_as_person_link_distinct`.

---

## S4 — Forbidden-claim conformance *(SC-005)*

`design.md` §4.3 marks these claims forbidden. A claim that is only *documented* as
forbidden will eventually be used, so assert the behaviour.

```python
# Mint a token carrying the legacy claims, then assert the dashboard rejects or ignores it.
# athlete_ids  — encodes guardianship, goes stale, cannot express coach-of or self
# club_id      — implies one login == one club
# roles        — flat list, cannot say which club a role applies to
```

| Assertion | Expected |
|---|---|
| Token with `athlete_ids` | Rejected, or the claim ignored and `as_person_link` consulted |
| Token with scalar `club_id` | Rejected, or ignored in favour of a `as_club_membership` lookup |
| Token with flat `roles` | Ignored; `require_club_role(club, [...])` resolves from the database |

Also assert the positive case: `roles_by_club` present and consistent with
`as_club_membership` for a multi-club person (US2 scenario 3).

---

## S5 — Multi-club role resolution *(US2; REQ-002, REQ-012)*

```sql
-- The dashboard schema already permits this via uq_as_club_membership_active
INSERT INTO as_club_membership (person_id, club_id, role, status)
VALUES ('<PERSON_ID>', '<CLUB_A_UUID>', 'swimmer', 'active'),
       ('<PERSON_ID>', '<CLUB_B_UUID>', 'coach',   'active');
```

Log in, then confirm the effective role is `swimmer` at club A and `coach` at club B —
resolved from the database, not from `roles_by_club`.

> **Blocked until T008 lands, and T008 is in this repository.** The user service's
> `membership` table still carries `UNIQUE (tenant_id, user_id)` — one role per user per
> tenant — so it cannot represent a swimmer at club A and a coach at club B. The dashboard
> schema already permits this via `uq_as_club_membership_active`, so the two halves disagree
> until the constraint is relaxed. That is the local migration
> `api/user-management/supabase/migrations/06_membership_multi_role.sql` (research.md D8,
> OQ #1 / REQ-012, tasks.md T008) — **not** an upstream dependency. It was recorded as one
> until 2026-10-04; that was wrong, `membership` is defined in this tree at
> `01_initial_schema.sql`.

---

## S6 — Ingest creates no credential *(SC-001)*

```powershell
python scripts/ingest_figures.py "swim-meets\2026\20260305_WestZone_Sacramento_CA\AG 12U Female Solo Details.pdf"
```

```sql
-- Baseline auth.users count, captured before the run, must be identical after
SELECT count(*) FROM auth.users;
SELECT count(*) FROM user_profile WHERE status <> 'INVITED';   -- expect 0
```

**Negative checks**
- `user_mgmt_sync.py` must no longer contain `get_or_create_auth_user` or `DEFAULT_PASSWORD` (research.md D1).
- No `as_person_identity` row may be created by an import that was not previously linked.
- Re-running the same import must not duplicate persons or memberships (idempotency, P4).

---

## S7 — Exactly one verified auth path *(SC-003)*

```powershell
# The legacy dependency must be gone entirely, not merely unused
Select-String -Path backend/src/**/*.py -Pattern "verify_jwt"
# Expect: no matches
```

```python
# A token signed with the wrong key, and an unsigned/garbage token, must both fail
```

| Case | Expected |
|---|---|
| Valid RS256 token, active membership | `200` |
| Valid RS256 token, membership ended | `403` on the **next request**, no re-login |
| Token signed with a different key | `401` |
| `alg: none` / unsigned | `401` |
| HS256 token when the service issues RS256 | `401` |

Also confirm the four routers that depended on the old path — `insights`, `markers`,
`uploads`, `timers` — now resolve identity through `core/auth.get_current_user`, and that
they read rows as `person_id` rather than `auth.users.id` (`design.md` §5.2.1).

---

## Definition of done

| Criterion | Scenario |
|---|---|
| SC-001 ingest never activates an account | S6 |
| SC-002 register → approve → login < 3 min | S1 |
| SC-003 one verified auth path | S7 |
| SC-004 revoke denies on next request | S3 |
| SC-005 forbidden claims rejected | S4 |
| SC-006 every transition audit-logged | S1, S3 |
| SC-007 RLS on `as_club`/`as_team`/`as_team_member` | S3, S7 |
| SC-008 person with no login fully usable | S2 |
| REQ-002 roles scoped per club | S5 |
| REQ-010 membership feed populates | S6 |

**SC-006 check**
```sql
SELECT action, actor_id, created_at FROM audit_log
WHERE created_at > now() - interval '1 hour' ORDER BY created_at DESC;
-- Expect: auth.register, member.approve, person_link.create, auth.login — no credential values
```

## Known blockers for this run

1. **`06_membership_multi_role.sql` does not exist** — the user service's `membership` table still has `UNIQUE (tenant_id, user_id)`, so S5 cannot pass. This is a **local** migration in `api/user-management/supabase/migrations/`, not an upstream PR (tasks.md T008).
2. **`05_org_model.sql` does not exist** — S1 (`approved_by`/`approved_at`), S2 (`/persons`), S3 (link CRUD) all depend on it. It also carries the `as_club.tenant_id` FK that `X-Tenant-Id` derives through (tasks.md T006).
3. **RS256 issuer does not exist** — the user service has no signer and no JWKS. S1 and S7 cannot pass.
4. **`APP_ENV` is unset in `.env`** — until `DEMO_AUTH_ENABLED` exists, the demo branch is live. Set both flags before any acceptance run.