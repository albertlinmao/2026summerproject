# auth.users Lifecycle — Login, Register, Activate, Enable, Password

**Status:** plan, not implemented. Adds an implementation plan to the
`POST /auth/*` contract already written in [`design.md`](design.md) §4.1, §5.1 and
§6. Written because the endpoints are specified and the behaviours are not, and
because the ingest path now creates accounts that this lifecycle has to be able
to hand over to real people.

**Date:** 2026-10-01

---

## 1. What exists, and what does not

| Layer | State | Evidence |
|---|---|---|
| Endpoint contract (`/auth/login`, `/auth/register`, `/auth/login` errors, `/members/{person_id}/approve`, `/persons/{person_id}/invite-account`) | **Specified** | `design.md:570-596`, `design.md:797-824` |
| Lifecycle column (`user_profile.status`) | **In the database** | `CHECK (status IN ('INVITED','ACTIVE','SUSPENDED','SOFT_DELETED'))`, default `INVITED` |
| Password storage | **GoTrue owns it** | `auth.users.encrypted_password`, bcrypt `$2a$10$`, 480/480 populated |
| Account provisioning during ingest | **Implemented** | `scripts/user_mgmt_sync.py:516` `get_or_create_auth_user`, reached from both ingest scripts via `synchronized_meet` (`:648`) |
| JWT issuer in the user service | **Absent** | `api/user-management/backend/src/core/security.py` is 492 bytes and contains only `verify_gateway_psk`; no `jwt.encode` anywhere in that service |
| `/auth` router in the user service | **Absent** | routers present: `audit, roles, tenants, users, webhooks` |
| JWKS / shared verification secret | **Unconfigured** | `USER_SERVICE_JWKS_URL` defaults to `""`, so the RS256 branch in `backend/src/core/auth.py:76` is unreachable |
| Dashboard token issuer | **Exists, dev only** | `backend/src/api/auth.py` is the only `jwt.encode` in the repository, signed with `USER_SERVICE_JWT_SECRET` (HS256) |

The gap is not "there is no login". It is that the issuer named as authoritative
by `design.md` has no token code, and the dashboard issues its own tokens against
a secret that does not match Supabase's.

---

## 2. The one concept this plan turns on: **enabled**

"Enabled" must be answerable from a single column, or two answers will drift and
one of them will be wrong.

> **An account may sign in only when `user_profile.status = 'ACTIVE'`, and it must
> hold at least one `as_club_membership` with `status = 'active'`.**

| `user_profile.status` | GoTrue password | May sign in | Meaning |
|---|---|---|---|
| `INVITED` | set (seeded or chosen at registration) | **No** — 403 `PENDING_APPROVAL` | Account exists; nobody has claimed it |
| `ACTIVE` | set | Yes, if a membership is active too | The account is enabled |
| `SUSPENDED` | set | **No** — 403 `ACCOUNT_SUSPENDED` | Deliberately disabled by an admin |
| `SOFT_DELETED` | unset by the scrub | **No** — 401 | GDPR erasure, row retained for audit resolution |

Two gates, and they are different questions:

- **`user_profile.status`** — *may this person authenticate at all?* Account-level.
- **`as_club_membership.status`** — *may they act on this club?* Club-level.

A person may be `ACTIVE` with every membership `dormant` (correct: they can log
in and see that they belong nowhere) and may be `INVITED` with an `active`
membership (a bug: approval must not outrun activation). Both states are
reachable, so login checks both and reports them separately.

`encrypted_password` is deliberately **not** part of this table. It is a GoTrue
bcrypt hash, unreadable by this project by design, and it never indicates intent:
a set hash with `INVITED` means "a password exists", not "this account works".

### Why this needed changing

`scripts/user_mgmt_sync.py` wrote `'ACTIVE'` on insert. Every athlete named on a
result PDF therefore got an account that was immediately loggable-in with a
password that was committed to the repository. The gate in `design.md` §5.1 was
skipped at the only point where accounts are created in bulk.

Fixed by writing `'INVITED'` (`user_mgmt_sync.py:591`), and pinned by
`tests/test_auth_provisioning.py::SeededStatusTests`.

---

## 3. Flows

### 3.1 Register — a human asks for an account

```
POST /auth/register  {email, password, first_name, last_name, club_id, role}
```

1. `admin.create_user({email, password, email_confirm: true})` — GoTrue hashes.
   This service never sees or stores the password.
2. `user_profile.status = 'INVITED'`; `as_club_membership.status = 'invited'`.
3. **If the email matches a seeded account** (`<slug>@<club>.swim`, see §5): do
   not create a second person. Attach to the existing one —
   `INSERT INTO as_person_identity (person_id, subject_id)` — and rewrite the
   encrypted email on `user_profile` to the address the person chose. Return
   `409 SEEDED_ACCOUNT_EXISTS` if the caller must confirm first.
4. Return `{person_id, status: "invited"}`. **No token.** Registration is not
   authentication; issuing a token here would let anyone in.

### 3.2 Claim a seeded account — the handover the ingest path creates

A seeded athlete has an `auth.users` row, an `INVITED` profile, and a person. When
they join for real:

```
POST /auth/claim-account  {email, current_password, new_password, first_name, last_name}
```

1. Verify `current_password` against the seed default. If it is the seed default
   and `new_password == current_password`, reject: `400 PASSWORD_NOT_CHANGED`.
   This is the single control that makes a published seed password survivable.
2. `admin.update_user_by_id(id, {password: new_password, email: chosen_email})`.
3. `user_profile.status` `INVITED` → `ACTIVE`; rewrite encrypted email and names.
4. Audit-log: `auth.claim_account` with `actor = subject_id`, never the password.
5. Return a dashboard token.

`design.md:588` already names this shape as `POST /persons/{person_id}/invite-account`
(admin-invites). §3.2 is the self-service mirror and needs its own endpoint; the two
should share one service function.

### 3.3 Approve / activate / enable

| Action | Effect | Notes |
|---|---|---|
| `POST /members/{person_id}/approve` | `as_club_membership.status = 'active'` | Approves a **membership**, never a login (`design.md:604`) |
| `POST /persons/{person_id}/invite-account` | creates `auth.users` + `as_person_identity`, `user_profile` `INVITED` | The admin path to §3.2's end state |
| `PATCH /auth/me/enable` | `user_profile.status` `INVITED`/`SUSPENDED` → `ACTIVE` | Requires a verified current password, even for an admin enabling a subordinate |
| `PATCH /auth/me/disable` | → `SUSPENDED`, all live sessions revoked | `banned_until`/`sign_out_all` via GoTrue admin |

Enabling and approving are **separate calls on purpose**. Approving a minor's
membership must not hand a twelve-year-old a working login, and granting a login
must not imply the club accepts the person.

### 3.4 Update password

```
PATCH /auth/me/password  {current_password, new_password}
```

1. `sign_in_with_password` with the **current** password. This is the reauth step;
   a stolen refresh token must not be enough to set a new password.
2. `admin.update_user_by_id(id, {password: new_password})`.
3. Reject anything GoTrue rejects (length, similarity to the email, reuse).
4. Audit-log `auth.password_changed` — actor, target, outcome, no values.
5. Revoke all other sessions; keep the caller's.

Password reset (`/auth/forgot-password`) is GoTrue's, entirely: it emails a
recovery link, this service never receives a reset token. Account deletion
(`DELETE /auth/me`) is §4, not a status flip, because `auth.users` is the row.

### 3.5 Login

```
POST /auth/login  {email, password}
```

```
1. sign_in_with_password            -> 401 INVALID_CREDENTIALS   (GoTrue)
2. user_profile missing             -> 401 INVALID_CREDENTIALS   (do not confirm existence)
3. user_profile.status != ACTIVE    -> 403 PENDING_APPROVAL | ACCOUNT_SUSPENDED
4. no membership.status = 'active'  -> 403 NO_ACTIVE_MEMBERSHIP
5. mint dashboard JWT (RS256, aud = dashboard APP_NAME), claims per design.md 4.3
```

Step 1 precedes step 3 deliberately, and it has a consequence worth stating:
**GoTrue has already issued a refresh token by the time the status gate runs.**
A refusal at steps 3 or 4 must therefore sign the session out
(`admin.sign_out(jwt)`), or the caller holds a valid refresh token for an account
that is not enabled — which is exactly the seeded-account case. This is not
optional; without it the `INVITED` status does not actually block anything.

Responses never distinguish "no such account" from "wrong password" (§2 of the
error table), and never return `athlete_ids` or a scalar `club_id` (`design.md:574`).

---

## 4. Deletion

`sql/02_clear_alldata_for_club_using_id.sql` §5 deletes accounts for a club that
is finished. It is **not** a GDPR erasure path and must not be used as one:

- It destroys `user_profile` by cascade, taking the encrypted PII with it. The
  identity service's stated approach (`services/gdpr_service.py`) is to scrub PII
  in place and keep the UUID resolvable inside historical audit records.
- It is keyed on club membership, not on a person. Erasure is keyed on a person.

GDPR erasure therefore stays in the user service: scrub the encrypted PII, set
`SOFT_DELETED`, revoke sessions, keep the UUID. The two paths must not be
conflated in either direction.

---

## 5. Known limitation: a seeded address is not a real address

`_make_email(name, club_code)` produces `<slug(name)>@<slug(club_code)>.swim`.
Verified behaviour:

| Name | Club | Address |
|---|---|---|
| Alice Zhang | TUK | `alice.zhang@tuk.swim` |
| Alice Zhang | PDX | `alice.zhang@pdx.swim` |
| **Alice Zhang** | **TUK** | **`alice.zhang@tuk.swim`** — same as row 1 |

Two consequences, both real:

1. **Two same-named swimmers in one club collapse into one account and one
   person.** `_ensure_person` resolves on `subject_id` (`user_mgmt_sync.py:284`),
   which the address determines, so the second swimmer is written onto the first
   one's row. That is a data-integrity failure against Principle 4, and it is
   recorded as a known limitation rather than fixed here — the disambiguator
   changes the address format, which invalidates every already-seeded account.
2. **A seeded address can never be the address a person registers with.** So
   registration and seeding never converge on one identity without the §3.1
   attach step.

Both are closed by the same change: give the seeded address a discriminator that
cannot collide (`alice.zhang.tuk.0042@seed.swim`, derived from a hash of name +
club + a per-pdf sequence) and make it obviously non-deliverable. That is a
migration, and it is out of scope for this plan.

---

## 6. Verification against the Constitution

`.specify/memory/constitution.md` v1.2.0 — *"This Constitution supersedes all other
documentation and local practices."*

| Principle | Verdict | Note |
|---|---|---|
| **16 External User Management** — identity strictly delegated to the user service; "local databases MUST only store UUID references... never duplicating profile or auth data" | **CONFLICT** | The ingest path creates `auth.users` rows from `scripts/user_mgmt_sync.py`, which lives in the *analytics* repo, not the user service. It calls the GoTrue admin API directly rather than the user service's API. This is a pre-existing arrangement, not one this plan introduces, but the plan does not resolve it. Either the seeding path moves behind a user-service endpoint, or Principle 16 is amended to carve out machine seeding. **Needs a human decision.** |
| **7 Security** — "OAuth2 for authentication", JWT, RBAC | **PARTIAL** | The flows above use GoTrue's password grant, which is *not* OAuth2. GoTrue supports OIDC authorization-code + PKCE and the same `auth.users` table; that would satisfy Principle 7 properly but adds a client and a redirect URI. Recommend it before production, and note the constitution asks for it. |
| **1 API First** — "No code should be written until the API spec is defined and agreed upon" | **GAP** | `design.md` §5.1 is prose plus an error list, not an OpenAPI document. Principle 12 makes it a merge gate. `/auth/claim-account`, `/auth/me/password`, `/auth/me/enable` do not exist in the contract at all. Must land as OpenAPI before any of this is implemented. |
| **3 Test First** — unit, integration, contract, E2E | **PARTIAL** | `tests/test_auth_provisioning.py` (16 tests) covers the provisioning and gate behaviour with a fake GoTrue. Nothing covers the endpoints, because they do not exist. |
| **4 Data Integrity** — traceability to official results | **AT RISK** | Not about scores here, but §5's name collision merges two swimmers' data into one person, which is the same class of defect the principle exists to prevent. |
| **5 Immutable Competition Records** | **HELD** | Nothing in this plan writes to a competition table. §4's account delete cascades `user_profile`, which is PII, not a result. |
| **6 Multi-Tenant** | **PARTIAL** | Every enable/approve endpoint must be authorized against the caller's `admin` membership *in the target club*, not from a token claim — `design.md:598`. Not yet implemented anywhere, so not yet demonstrated. |
| **10 Observability** — audit logs for critical actions | **GAP** | §3.2/§3.4/§3.3 introduce password and activation events that must be audit-logged. `audit_log` exists; nothing writes to it from this path. |
| **13 Tech stack** — Supabase, FastAPI, Angular | **HELD** | GoTrue is the Supabase identity provider; no new runtime. |
| **2 Domain First** | **HELD** | The person/identity/membership split in `identity-contract.md` is unchanged by this plan. |
| **8 Accessibility, 9 Performance, 14 Layered Analytics, 15 ML** | **N/A** | Not touched. |
| **11 AI Governance** | **HELD** | Not touched. |
| **12 CI/CD** | **GAP** | Follows from Principle 1: no OpenAPI → no merge, so Principle 1's gap blocks the pipeline gate too. |

### Verdict

**Not clear to implement as written.** Two blocking items, both requiring a
decision that is not mine to make:

1. **Principle 16 vs. ingest-path provisioning.** Delegation or an amendment.
2. **Principle 7 vs. the password grant.** Password grant now, or OIDC + PKCE now.

And one structural prerequisite: **the OpenAPI document for `/auth/*`
(Principle 1),** without which Principle 12 blocks the merge regardless.

The design decisions above are still sound and worth keeping while those are
settled — §2 in particular is required under either resolution.

---

## 7. Implementation order

1. **OpenAPI for `/auth/*`** (§6, Principle 1). Blocks everything else.
2. **`security.py`**: RS256 signing/verification, JWKS fetch with cache, so a token
   exists at all. Closes the `USER_SERVICE_JWKS_URL` dead branch.
3. **Login** (§3.5) with both gates and the mandatory sign-out on refusal. The
   smallest end-to-end slice that proves the token contract.
4. **Register + seeded-account attach** (§3.1) — needs §5's collision answer first.
5. **Claim / invite-account** (§3.2, §3.3) — the handover the ingest path depends on.
6. **Password change and reset** (§3.4).
7. **Enable/disable** (§3.3) with session revocation.
8. **Audit logging** into `audit_log` for every step above (Principle 10).

Each step ships behind a flag until the seeded accounts have been claimed or
withdrawn; 480 identities already exist, of which 11 are reachable.

---

## 8. Verification performed for this plan

| Check | Result |
|---|---|
| `user_profile.status` constraint | `CHECK IN ('INVITED','ACTIVE','SUSPENDED','SOFT_DELETED')`, default `INVITED` |
| Status actually written by the seeding path before this change | `ACTIVE` for all 11 rows |
| GoTrue password hashes | 480/480 bcrypt `$2a$10$`, none blank |
| FKs into `auth.users` | 7, **all `ON DELETE CASCADE`** (`identities`, `sessions`, `mfa_factors`, `one_time_tokens`, `oauth_authorizations`, `oauth_consents`, `user_profile`) |
| `auth.users` RLS | enabled, **0 policies**, owner `supabase_auth_admin`; connecting role `postgres` has `BYPASSRLS` and `DELETE` |
| `auth.users` / `auth.identities` counts | 480 / 480 |
| `membership.user_id` semantics | matches `auth.users.id` (11), not `as_person.id` (0) |
| Server-side issuer in the user service | none; single `jwt.encode` is the dashboard's dev login |
| `sql/02` §5 end-to-end | ran with `apply`/`purge_people`/`purge_auth_users` all on, inside one transaction, rolled back: `auth.users` 480→469, `user_profile` 11→0, `auth.identities` 480→469, no drift after rollback |
| `sql/02` §5 safety guard | gave one subject a membership in a second club: preview reported KEEP 1 / DELETE 10 and the delete removed exactly 10, leaving the cross-club subject's `auth.users` and `user_profile` intact |
| Existing suite | 54 tests pass (38 pre-existing + 16 new) |

The club id committed in `sql/02` (`cac7197f-…`) does not exist in `as_club`; the
only club present is `75579ceb-…` (SST, SEATTLE SYNCHRO), which is where the 11
test identities live. Verification substituted the real id. The placeholder is
left in place deliberately — it is the operator's edit point.