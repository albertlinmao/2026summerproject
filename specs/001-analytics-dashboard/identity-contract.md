# Identity Contract: Person, Club, Membership

**Status**: Authoritative for `001-analytics-dashboard` and the request it makes of `001-multi-tenant-user-api`.
**Supersedes**: the login-centric model (`as_athlete.club_id`, `as_coach.club_id`, `athlete_ids` claim, `club_id` claim).

This document is the single source of truth for the vocabulary used across the SQL migrations,
backend, frontend, contracts, and prompts. If any of those disagree with this file, this file wins.

---

## 1. The core rule

A **person** is a human being. A **club** is the tenant. **Membership is the edge** between them.

Three consequences that drive every other decision:

1. **A person has no `club_id`.** Belonging to a club is a row in `as_club_membership`, never a column
   on the person. One login therefore does not imply one club.
2. **A login is optional.** `as_person_identity` may be absent. Minors, dormant swimmers, and alumni
   exist as `as_person` rows with no account and no credentials.
3. **Roles are scoped per club.** The same `person_id` may be a `swimmer` in club A and a `coach` in
   club B. Authorization is always evaluated as (person, club, role), never as a flat role list.

---

## 2. Physical tables

All tables use the repository's `as_` prefix. Logical names used in prose: Person, Person Identity,
Club Membership, Person Link, Result Person Link.

| Logical name | Physical name | Purpose |
|---|---|---|
| Club | `as_club` | The tenant. Unchanged. |
| Person | `as_person` | The human. No credentials, no `club_id`. |
| Person Identity | `as_person_identity` | Optional 1:1 link to an auth subject. |
| Club Membership | `as_club_membership` | Tenant-scoped edge. **Authorization source of truth.** |
| Person Link | `as_person_link` | Directed guardian edge, scoped to a club. |
| Result Person Link | `as_result_person_link` | Maps immutable PDF result rows to a person. |
| Athlete | `as_athlete` | **View.** Person with an active `swimmer` membership. |
| Coach | `as_coach` | **View.** Person with an active `coach` membership. |

### as_person
`id uuid pk`, `given_name text not null`, `family_name text`, `middle_name text`, `birth_date date`,
`created_at`, `updated_at`. Index on `lower(family_name), lower(given_name)`.

### as_person_identity
`person_id uuid pk references as_person(id) on delete cascade`, `subject_id uuid unique not null`,
`created_at`. Exactly one identity per person; a person may have none.

`subject_id` is the **only** link between this database and the identity provider. It is matched
against the verified `sub` claim. It is never used as a business key and never exposed in API payloads.

### as_club_membership
`id uuid pk`, `person_id uuid not null references as_person(id) on delete cascade`,
`club_id uuid not null references as_club(id)`, `role text not null check (role in (...))`,
`title text`, `status text not null check (status in (...))`, `joined_at date`, `left_at date`,
`created_at`, `updated_at`.

- `role` ∈ `admin | coach | swimmer | parent | official` — coarse, drives RLS.
- `title` — free-text, display only (`Lead Coach`, `Team Captain`, `Club Owner`). Never used for
  authorization. This is how the existing UI role vocabulary survives the migration.
- `status` ∈ `invited | active | dormant | left`. `invited` and `active` grant access; `dormant`
  and `left` do not.
- Partial unique index on `(person_id, club_id, role) where status in ('invited','active')`.
- Indexes on `(club_id, status)` and `(person_id)`.

### as_person_link
`id uuid pk`, `parent_person_id uuid not null references as_person(id) on delete cascade`,
`child_person_id uuid not null references as_person(id) on delete cascade`,
`club_id uuid not null references as_club(id) on delete cascade`,
`kind text not null check (kind in ('parent','guardian','emergency_contact'))`, `created_at`.

`check (parent_person_id <> child_person_id)`. Index on `(child_person_id, club_id, kind)`.
This table is what makes family-only video access expressible without forcing a login on minors.

### as_result_person_link
`id uuid pk`, `result_table text not null check (result_table in ('as_meet_figure_result','as_meet_routine_result'))`,
`result_id uuid not null`, `person_id uuid not null references as_person(id) on delete cascade`,
`athlete_name text not null`, `confidence numeric`, `resolved_by uuid references as_person(id)`,
`resolved_at timestamptz`.

`athlete_name` is required because `as_meet_routine_result.team_athletes` is a JSON array of names
sharing one `result_id` — the printed name is the only intra-row discriminator available.
Unique on `(result_table, result_id, athlete_name)`. Index on `person_id`.

`result_id` intentionally has no foreign key: the source is polymorphic across two result tables.
Referential integrity is enforced by the writer plus the immutability trigger on the results.

---

## 3. Imported-result columns that do NOT change

These are verbatim fields transcribed from official result PDFs and are part of the data's lineage.
They are **not** identity references and keep their names:

- `as_meet_figure_result.athlete_name`, `as_meet_figure_result.athlete_birth_year`
- `as_meet_routine_result.team_athletes` (JSON array of printed names)

Anything that references a **canonical person** is `person_id`.

---

## 4. Required claim contract for `001-multi-tenant-user-api`

The dashboard verifies the token signature and then resolves authorization **from the database**.
Claims are therefore a cache and a convenience, never the authority.

### Required

| Claim | Type | Required | Meaning |
|---|---|---|---|
| `sub` | uuid | **yes** | Opaque tenant-user subject. Must equal some `as_person_identity.subject_id`. This is the only claim RLS trusts. |
| `iss` | string | yes | Issuer identifier. |
| `aud` | string | yes | Must equal the dashboard app name. |
| `exp`, `iat` | number | yes | Standard. |

### Optional (cache; never authoritative)

| Claim | Type | Meaning |
|---|---|---|
| `person_id` | uuid | Convenience mirror of `as_person_identity.person_id` for the `sub` above. UI use only. |
| `club_ids` | uuid[] | Clubs with an `invited`/`active` membership. Rendered as club switcher options. |
| `roles_by_club` | object | `{ "<club_id>": ["swimmer", "coach"] }`. UI route matching only. |
| `permissions` | string[] | Retained for compatibility; the dashboard does not enforce from it. |

### Removed / forbidden

| Claim | Status | Reason |
|---|---|---|
| `athlete_ids` | **forbidden** | Encoded guardianship in the token, so it goes stale and cannot express coach-of or self. Replaced by `as_person_link`. |
| `club_id` (scalar) | **forbidden** | Implies one login equals one club. Replaced by `club_ids` + membership lookup. |
| `user_id` | renamed | The claim is `sub`; the database column is `person_id`. The two are different identifiers and must not be conflated. |

### Required change in the identity service

`supabase/migrations/01_initial_schema.sql` in the user service currently declares
`public.membership` with `unique (tenant_id, user_id)`. **That constraint makes multi-club
membership impossible** and must become `unique (tenant_id, user_id, role_id)`, or the membership
table must be replaced by a membership-per-role structure. This lives in the identity service
(`api/user-management`, a separate repository) and is out of scope for the dashboard; it is recorded
here as a blocking dependency.

Until that lands, the dashboard works single-club in practice, and the RLS predicates in
`20260827_all_schema_from_scratch.sql` are already written to handle the multi-club case correctly.

---

## 5. How authorization is resolved

Four SQL helper functions replace the old `current_user_club_id()` and `jwt_linked_athlete_ids()`.
All are `stable security definer set search_path = ''` with fully-qualified names, which is what
keeps RLS from recursing into itself.

| Function | Returns | Purpose |
|---|---|---|
| `app_current_person_id()` | `uuid` | `as_person_identity.person_id` for `subject_id = auth.uid()`. Null when the caller has no identity. |
| `app_active_memberships()` | `setof as_club_membership` | Memberships with status `invited`/`active`. |
| `app_current_club_ids()` | `uuid[]` | Clubs the caller belongs to. |
| `app_has_club_role(club, roles[])` | `boolean` | Membership-authoritative role check. |
| `app_is_club_staff(club)` | `boolean` | Role in (`coach`, `admin`). |
| `app_is_guardian_of(parent, child, club)` | `boolean` | `as_person_link` lookup. |
| `app_can_view_video(club, person)` | `boolean` | The family-access predicate, composed. |
| `app_can_edit_video(club, uploaded_by)` | `boolean` | Uploader or club staff. |

### Family video access

`app_can_view_video(club_id, person_id)` is true when any of:

1. **coach-of** — `app_is_club_staff(club_id)`.
2. **self** — `person_id = app_current_person_id()` **and** the caller holds an active `swimmer`
   membership in that same club.
3. **guardian-of** — `as_person_link` of kind `parent`/`guardian` joins the caller to `person_id`
   within that club.

Note branch 2 requires a membership, not just an identity: a former swimmer, or a parent who happens
to be a swimmer at the same club, does not gain blanket access to another athlete's footage.

The identical scope is applied to Supabase Storage objects.

---

## 6. Rename table (old → new)

| Old | New | Notes |
|---|---|---|
| `as_athlete.id` | `as_person.id` | View now exposes `person_id`. |
| `as_athlete.club_id` | *(dropped)* | Replaced by `as_club_membership`. |
| `as_athlete.name` | `as_person.given_name` + `family_name` | |
| `as_coach.club_id` | *(dropped)* | Replaced by `as_club_membership`. |
| `as_coach.name` | `as_person.given_name` + `family_name` | |
| `*.athlete_id` | `*.person_id` | insights, recommendations, videos, aggregations. |
| `as_competition_results_browser_widgets.user_id` | `.person_id` | |
| `auth.uid()` in data columns | `person_id` | `uploaded_by`, `created_by`, `resolved_by` now FK `as_person(id)`. |
| `auth.uid()` in RLS | `app_current_person_id()` | |
| `jwt -> 'athlete_ids'` | `as_person_link` | |
| `current_user_club_id()` | `app_current_club_ids()` / `app_has_club_role()` | |
| `current_user_club_id()` (storage path) | `{club_id}/{person_id}/` | |

`as_daily_aggregations.athlete_id` → `person_id`, and its resolution now prefers
`as_result_person_link` over fuzzy name matching.

---

## 7. API surface

Paths keep the domain word *athlete* (a swimmer is an athlete) while the identifier is explicitly a
person id. Example: `GET /analytics/athletes/{person_id}/prediction`.

Request and response field `athlete_id` becomes `person_id`. The literal import columns
`athlete_name` / `athlete_birth_year` keep their names in `FigureResult` and `RoutineResult`.

`as_athlete`-backed read endpoints keyed on `athlete_name` in the path
(`/meets/{meet_id}/athletes/{athlete_name}/figures`, `/athletes/{athlete_name}/figure-history`) are a
known weakness: display names are ambiguous. They remain for compatibility but are superseded by
`as_result_person_link` resolution; new work should key on `person_id`.
