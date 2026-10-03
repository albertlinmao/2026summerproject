-- ============================================================================
-- Artistic Swimming Analytics Dashboard - COMPLETE SCHEMA, FROM THE GROUND UP
--
-- One script. Apply it to an EMPTY database and it creates every table, view,
-- materialized view, function, trigger, index, RLS policy and grant the
-- application needs. There is nothing to run before it and nothing to run
-- after it.
--
--   psql -v ON_ERROR_STOP=1 -U postgres -d <yourdb> -f 20260827_all_schema_from_scratch.sql
--
--   docker compose exec -T db psql -v ON_ERROR_STOP=1 -U postgres -d <yourdb> \
--     -f /path/to/this/file.sql          (PowerShell: pipe with Get-Content -Raw)
--
-- Supersedes four schema migrations, which have been removed from this
-- directory. Assembled from them, not rewritten from memory:
--
--   20260804_initial_schema.sql ............ identity + core tables, the
--                                            as_competition_result DDL, and the
--                                            first copy of the helpers
--   20260819_dashboard_tables.sql .......... matview, predictions, widgets
--   20260819_video_and_timer.sql ........... video, markers, timers
--   20260820_full_schema.sql ............... the authoritative body
--   20260826_person_identity_migration.sql .. the corrected helpers, and the
--                                            legacy-row transform
--
-- STAYS IN THIS DIRECTORY, NOT SUPERSEDED:
-- 20260826_person_identity_migration.sql. This file takes the corrected
-- app_*() helpers from it (change 2 below) but not its sections 2-5, the
-- one-way transform of legacy rows. An already-migrated database still applies
-- that file; a fresh one never needs it. Do not delete it.
--
-- What changed while merging. Items 1-2 are latent failures: no database had
-- ever applied this schema in one piece without hitting them.
--
--   1. as_competition_result is DECLARED here. Three RLS policies in section 10
--      target it, but its DDL existed only in 20260804 - so the file that
--      declares itself a standalone "full schema" could never be applied alone.
--   2. The app_*() helpers come from 20260826, not 20260804/20260820. All three
--      files set `search_path = ''` on the helpers, but only 20260826 qualifies
--      the table references with `public.`. The other two left them bare, and
--      with an empty search_path a bare name cannot be resolved - so
--      app_current_person_id() failed at CREATE time with
--      "relation as_person_identity does not exist" even though the table was
--      right there. Verified: the chain and 20260820 alone both abort on a fresh
--      database for exactly this reason.
--
-- Items 3-5 are gaps that only a from-scratch run exposes. Each exists in one
-- source file and is silently dropped by the later file that re-declares the
-- same object, so the chain ends up with the object but not with everything the
-- chain needs:
--
--   3. The `auth` schema, the `anon` / `authenticated` / `service_role` group
--      roles, and a fallback `auth.uid()`. Supabase installs all three in its
--      own init scripts, which is why no source file declares them - but
--      "from the ground up" has to survive a bare server, and section 11 grants
--      to `authenticated`. See the SUPABASE AUTH / ROLE SHIM blocks below.
--   4. `updated_at` on as_video_uploads and as_routine_timers, plus their two
--      triggers. Declared by 20260819_video_and_timer.sql; the 20260820
--      re-declaration of both tables omits them. data-model.md names 20260819
--      as the sole source, so a single-file run had triggers-without-columns.
--   5. chk_as_club_membership_dates. Declared by 20260804, omitted by the 20260820
--      and 20260826 re-declarations of as_club_membership. A bare
--      `references` on the person FKs in the same tables was likewise upgraded
--      to the `on delete restrict` that 20260826 section 7 re-attaches.
--
-- NOT INCLUDED, ON PURPOSE: the legacy-row transform. 20260826 sections 2-5
-- backfill as_person / as_club_membership from the old as_athlete / as_coach
-- tables and then DROP those tables. That is a data migration for a database
-- that already holds legacy rows; it has nothing to do with creating a schema,
-- and running it here would be a no-op at best. A database that needs the
-- transform must still apply 20260826_person_identity_migration.sql to it.
--
-- Idempotent: safe to re-run (IF NOT EXISTS and DO-block guards throughout).
--
-- Source of truth: specs/001-analytics-dashboard/identity-contract.md
--                 specs/001-analytics-dashboard/data-model.md
--
-- IDENTITY MODEL: a person is a human, a club is the tenant, and membership is
-- the edge between them. No table carries a denormalized club_id on a person,
-- so one login does not imply one club, and a login is optional.
--
-- All tables use the as_ prefix. Covers all data-model entities:
--   Identity  .................................. as_club, as_person,
--                                                as_person_identity, as_club_membership,
--                                                as_person_link, as_athlete (view),
--                                                as_coach (view)
--   Core (competition tables) .................. as_event ... as_meet_routine_result,
--                                                as_competition_result
--   Result resolution ........................ as_result_person_link
--   Analytical ............................... as_daily_aggregations (mat. view),
--                                                as_predictive_insights, as_coaching_recommendations
--   Video Analysis (FR-007) ................... as_video_uploads, as_video_markers
--   Routine Timer (FR-008) .................... as_routine_timers
--   Results Browser Widget (FR-009) ........... as_competition_results_browser_widgets
-- Plus: indexes, RLS (club isolation + family access), immutability guards,
--       materialized-view refresh and 90-day video retention functions.
-- ============================================================================

create extension if not exists "pgcrypto";


-- ---------------------------------------------------------------------------
-- SUPABASE AUTH SHIM
--    The helpers below call auth.uid() to resolve the caller's person. On a
--    Supabase database that function is installed by the container's own init
--    scripts, so this block is a no-op there and the real one is left untouched.
--
--    It exists because "from the ground up" has to mean a database that is
--    genuinely empty. CREATE DATABASE does not give you the auth schema - only
--    the Supabase image does - so without this the script aborts on a bare
--    server with `schema "auth" does not exist`. The body is Supabase's own
--    definition, copied from the live database, so behaviour is identical.
-- ---------------------------------------------------------------------------
create schema if not exists auth;

-- ---------------------------------------------------------------------------
-- SUPABASE ROLE SHIM
--    Same reasoning, and the reason the auth shim above is not sufficient on its
--    own: section 11 grants to `authenticated`, and the same paragraph refers to
--    service-role writes. Neither role exists on a bare server, so the grant in
--    section 11 aborted with `role "authenticated" does not exist` even with the
--    auth schema in place. Only `authenticated` is actually granted to, but all
--    three are created so the script reproduces the role model it documents -
--    `service_role` in particular is what the RLS policies assume can write
--    insights, recommendations and identity rows (Principle 11, section 11).
--
--    These are group roles, not logins: nologin noinherit, exactly as Supabase
--    creates them. The real login is `authenticator`, which the platform owns and
--    this script deliberately does not create. On Supabase all three already
--    exist, so every statement here is a no-op and the platform's definitions win.
-- ---------------------------------------------------------------------------
do $$
declare
  r text;
begin
  foreach r in array array['anon', 'authenticated', 'service_role'] loop
    if not exists (select 1 from pg_roles where rolname = r) then
      execute format('create role %I nologin noinherit', r);
    end if;
  end loop;
end
$$;

do $bootstrap$
begin
  if to_regprocedure('auth.uid()') is null then
    execute $fn$
      create function auth.uid()
      returns uuid
      language sql
      stable
      as $body$
        select coalesce(
          nullif(current_setting('request.jwt.claim.sub', true), ''),
          (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')
        )::uuid
      $body$
    $fn$;
  end if;
end
$bootstrap$;

-- ============================================================================
-- 1. IDENTITY AND TENANCY
--    Identity is owned by the external Multi-Tenant User Service. This
--    database stores references and membership only — never credentials
--    (Constitution Principle 16).
-- ============================================================================

-- The tenant.
-- `code` is the stable short handle the application keys on (results_browser
-- selects it, and demo login resolves a club by code before falling back to
-- name), so it is part of the table rather than an optional extra. `created_by`
-- is the FK to the administrator who provisioned the tenant; as_person is
-- created below, so the constraint is added after it exists.
create table if not exists as_club (
  id         uuid primary key,          -- UUID issued by the user service
  name       text not null,
  code       text not null unique,      -- short handle, e.g. 'SST'
  city       text,
  created_by uuid
);

-- The human being. No credentials, no club_id: belonging to a club is a row in
-- as_club_membership. Minors, dormant swimmers and alumni exist here whether or
-- not they ever log in.
create table if not exists as_person (
  id          uuid primary key,   -- UUID issued by the user service
  given_name  text not null,
  family_name text,
  middle_name text,
  birth_date  date,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create index if not exists idx_as_person_name
  on as_person (lower(family_name), lower(given_name));

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'fk_as_club_created_by'
  ) then
    alter table as_club
      add constraint fk_as_club_created_by
      foreign key (created_by) references as_person(id) on delete set null;
  end if;
end
$$;

-- Optional 1:1 link to an authentication subject. Absent until the person first
-- logs in. subject_id is the only bridge to the identity provider and is
-- matched against the verified `sub` claim; it is never a business key and is
-- never exposed in API payloads.
create table if not exists as_person_identity (
  person_id  uuid primary key references as_person(id) on delete cascade,
  subject_id uuid not null unique,
  created_at timestamptz not null default now()
);

-- The tenant-scoped edge, and the authorization source of truth. Roles are
-- scoped per club, so one person may be a swimmer in one club and a coach in
-- another. `title` is display-only ("Lead Coach", "Team Captain") and never
-- authorizes; `role` is the coarse vocabulary the RLS policies match on.
create table if not exists as_club_membership (
  id         uuid primary key default gen_random_uuid(),
  person_id  uuid not null references as_person(id) on delete cascade,
  club_id    uuid not null references as_club(id) on delete cascade,
  role       text not null
             check (role in ('admin', 'coach', 'swimmer', 'parent', 'official')),
  title      text,
  status     text not null default 'active'
             check (status in ('invited', 'active', 'dormant', 'left')),
  joined_at  date,
  left_at    date,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  -- A membership cannot end before it began. Carried over from
  -- 20260804_initial_schema.sql, which declared it; 20260820 and 20260826 both
  -- re-declare this table verbatim minus this check, so the constraint only
  -- exists on a database that ran 20260804 first. The only way to run any
  -- single file is to have the whole chain's constraint set, so it is restated
  -- here - and the data model lists joined_at/left_at as a pair.
  constraint chk_as_club_membership_dates
    check (left_at is null or left_at >= joined_at)
);

create unique index if not exists uq_as_club_membership_active
  on as_club_membership (person_id, club_id, role)
  where status in ('invited', 'active');

create index if not exists idx_as_club_membership_club_status
  on as_club_membership (club_id, status);
create index if not exists idx_as_club_membership_person
  on as_club_membership (person_id);

-- Directed guardian edge, scoped to a club. This is what makes family-only
-- video access expressible without forcing an account on every minor.
create table if not exists as_person_link (
  id                uuid primary key default gen_random_uuid(),
  parent_person_id  uuid not null references as_person(id) on delete cascade,
  child_person_id   uuid not null references as_person(id) on delete cascade,
  club_id           uuid not null references as_club(id) on delete cascade,
  kind              text not null
                    check (kind in ('parent', 'guardian', 'emergency_contact')),
  created_at        timestamptz not null default now(),
  constraint ck_as_person_link_distinct check (parent_person_id <> child_person_id)
);

create index if not exists idx_as_person_link_child
  on as_person_link (child_person_id, club_id, kind);
create index if not exists idx_as_person_link_parent
  on as_person_link (parent_person_id, club_id);

-- Athlete and Coach are projections, not tables. A view over club-scoped
-- memberships cannot carry a single club_id without collapsing a multi-club
-- person into several rows, so neither exposes one.
create or replace view as_athlete as
select p.id as person_id,
       p.given_name,
       p.family_name,
       p.middle_name,
       p.birth_date,
       btrim(coalesce(p.middle_name || ' ', '')
             || p.given_name || ' ' || coalesce(p.family_name, '')) as name
from as_person p
where exists (
  select 1 from as_club_membership m
  where m.person_id = p.id
    and m.role = 'swimmer'
    and m.status in ('invited', 'active')
);

create or replace view as_coach as
select p.id as person_id,
       p.given_name,
       p.family_name,
       p.middle_name,
       btrim(coalesce(p.middle_name || ' ', '')
             || p.given_name || ' ' || coalesce(p.family_name, '')) as name
from as_person p
where exists (
  select 1 from as_club_membership m
  where m.person_id = p.id
    and m.role in ('coach', 'admin')
    and m.status in ('invited', 'active')
);

-- ---------------------------------------------------------------------------
-- COMPETITION RESULT
--    The one entity the rest of the chain referenced but never declared. Three
--    RLS policies in section 10 are written against this table, yet its DDL
--    lived only in 20260804_initial_schema.sql, so applying 20260820 on its own
--    - which it claims to support - failed on a missing relation. Declared here,
--    verbatim from 20260804, so this script stands alone.
--
--    Vestigial in practice: as_daily_aggregations resolves through
--    as_meet_figure_result / as_meet_routine_result and as_result_person_link,
--    not through this table. It is kept because the policies and the API models
--    still reference it.
-- ---------------------------------------------------------------------------
create table if not exists as_competition_result (
    id        uuid primary key default gen_random_uuid(),
    person_id uuid references as_person(id),
    score     decimal(5,2) not null,
    date      date not null
);

-- ============================================================================
-- 2. CORE ENTITIES (competition records imported from official PDFs)
--    Immutable once imported (Constitution Principle 5).
--
--    athlete_name / athlete_birth_year / team_athletes are verbatim fields
--    transcribed from the source PDFs. They are lineage, not identity
--    references, and keep their names. Canonical person references live in
--    as_result_person_link.
-- ============================================================================

create table if not exists as_event (
  id         uuid default gen_random_uuid() primary key,
  event_name text,
  host_city  text,
  event_date date,
  created_at timestamptz default now()
);

create table if not exists as_meet (
  id         uuid default gen_random_uuid() primary key,
  event_id   uuid references as_event(id) on delete cascade,
  name       text,
  meet_date  date,
  created_at timestamptz default now()
);

create table if not exists as_figure (
  id                 uuid default gen_random_uuid() primary key,
  meet_id            uuid references as_meet(id) on delete cascade,
  figure_code        text,
  figure_code_short  text,
  name               text,
  degree_difficulty  numeric,
  created_at         timestamptz default now()
);

create table if not exists as_meet_judge_panel (
  id                uuid default gen_random_uuid() primary key,
  meet_id           uuid references as_meet(id) on delete cascade,
  figure_id         uuid references as_figure(id) on delete cascade,
  figure_code_short text,
  panel_name        text,
  panel             json,
  created_at        timestamptz default now()
);

create table if not exists as_meet_figure_result (
  id                 uuid default gen_random_uuid() primary key,
  meet_id            uuid references as_meet(id) on delete cascade,
  rank               text,
  draw               text,
  team_code          text,
  team_name          text,
  athlete_name       text,   -- printed name, lineage (immutable)
  athlete_birth_year integer,
  penalty            text,
  total_score        numeric,   -- consistency with routines; not used for ranking
  figure_score       numeric,   -- weighted total used for ranking
  figure_scores      jsonb,     -- detailed scores per figure
  source_file        text,      -- lineage to source PDF (Principle 4)
  created_at         timestamptz default now()
);

create table if not exists as_meet_routine_result (
  id                       uuid default gen_random_uuid() primary key,
  meet_id                  uuid references as_meet(id) on delete cascade,
  rank                     text,
  draw                     text,
  team_code                text,
  team_name                text,
  team_athletes            jsonb,  -- printed names, lineage (immutable)
  total_difficulty         jsonb,
  routine_scores           jsonb,
  element_total            numeric,
  artisticimpression_total numeric,
  synchronization_total    numeric,
  routine_score            numeric,
  source_file              text,
  created_at               timestamptz default now()
);

-- Reconcile legacy databases with the data model (no-op on fresh installs):
-- older imports stored the weighted figure total as routine_score.
alter table as_meet_figure_result add column if not exists figure_score numeric;

-- Indexes for analytics queries
create index if not exists idx_as_meet_event             on as_meet(event_id);
create index if not exists idx_as_figure_meet            on as_figure(meet_id);
create index if not exists idx_as_judge_panel_meet       on as_meet_judge_panel(meet_id);
create index if not exists idx_as_judge_panel_figure     on as_meet_judge_panel(figure_id);
create index if not exists idx_fig_result_meet           on as_meet_figure_result(meet_id);
create index if not exists idx_fig_result_team_code      on as_meet_figure_result(team_code);
create index if not exists idx_fig_result_athlete_name   on as_meet_figure_result(athlete_name);
create index if not exists idx_fig_result_created_at     on as_meet_figure_result(created_at);
create index if not exists idx_routine_result_meet       on as_meet_routine_result(meet_id);
create index if not exists idx_routine_result_team_code  on as_meet_routine_result(team_code);
create index if not exists idx_routine_result_created_at on as_meet_routine_result(created_at);

-- Immutability guard: official results cannot be modified after publication.
-- Corrections are applied by deleting + re-importing from the source PDF.
create or replace function forbid_result_updates()
returns trigger as $$
begin
  raise exception 'Competition results are immutable; re-import from source PDF instead'
    using errcode = 'check_violation';
end;
$$ language plpgsql;

drop trigger if exists trg_fig_result_immutable on as_meet_figure_result;
create trigger trg_fig_result_immutable
  before update on as_meet_figure_result
  for each row execute function forbid_result_updates();

drop trigger if exists trg_routine_result_immutable on as_meet_routine_result;
create trigger trg_routine_result_immutable
  before update on as_meet_routine_result
  for each row execute function forbid_result_updates();

-- ============================================================================
-- 3. RESULT RESOLUTION
--    Maps immutable result rows to canonical persons so dashboard aggregation
--    does not have to guess. Kept in its own table so identity corrections
--    never violate result immutability.
--    result_id is polymorphic across the two result tables and so carries no
--    foreign key; athlete_name disambiguates rows inside a routine's
--    team_athletes array, which all share one result_id.
-- ============================================================================

create table if not exists as_result_person_link (
  id           uuid primary key default gen_random_uuid(),
  result_table text not null
               check (result_table in ('as_meet_figure_result', 'as_meet_routine_result')),
  result_id    uuid not null,
  person_id    uuid not null references as_person(id) on delete cascade,
  athlete_name text not null,   -- the name exactly as printed in the result row
  confidence   numeric,
  resolved_by  uuid references as_person(id) on delete set null,
  resolved_at  timestamptz not null default now()
);

create unique index if not exists uq_as_result_person_link
  on as_result_person_link (result_table, result_id, athlete_name);
create index if not exists idx_as_result_person_link_person
  on as_result_person_link (person_id);

-- ============================================================================
-- 4. ANALYTICAL ENTITIES
-- ============================================================================

-- Predictive Insight: ML-generated forecasts (read-only, Principle 11)
create table if not exists as_predictive_insights (
  id                    uuid primary key default gen_random_uuid(),
  person_id             uuid not null references as_person(id) on delete cascade,
  next_score_prediction numeric,
  plateau_risk          boolean default false,
  confidence_interval   numeric,
  model_version         text,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

create index if not exists idx_as_predictive_insights_person
  on as_predictive_insights(person_id);

-- Coaching Recommendation: AI-generated natural language feedback
create table if not exists as_coaching_recommendations (
  id                  uuid primary key default gen_random_uuid(),
  person_id           uuid not null references as_person(id) on delete cascade,
  recommendation_text text not null,
  generated_at        timestamptz not null default now(),
  weakest_figure      text,
  model_version       text,
  created_at          timestamptz not null default now()
);

create index if not exists idx_as_coaching_recommendations_person
  on as_coaching_recommendations(person_id, generated_at desc);

-- Daily Aggregations: pre-calculated statistics for dashboard rendering
-- (layered analytics, Principle 14). Derived from the two result tables.
-- Resolution order: explicit as_result_person_link first, then a normalized
-- name match. Unresolved rows are dropped rather than guessed, so a fuzzy match
-- can never attribute a score to the wrong human.
create materialized view if not exists as_daily_aggregations as
with source as (
  select 'as_meet_figure_result'::text as result_table,
         f.id                         as result_id,
         f.meet_id,
         lower(btrim(f.athlete_name)) as athlete_name,
         f.figure_score               as figure_score,
         null::numeric                as routine_score
  from as_meet_figure_result f

  union all

  select 'as_meet_routine_result',
         r.id,
         r.meet_id,
         lower(btrim(a ->> 'name')),
         null::numeric,
         r.routine_score
  from as_meet_routine_result r,
       lateral jsonb_array_elements(
         case
           when jsonb_typeof(r.team_athletes) = 'array' then r.team_athletes
           when jsonb_typeof(r.team_athletes) = 'string'
                and jsonb_typeof((r.team_athletes #>> '{}')::jsonb) = 'array'
             then (r.team_athletes #>> '{}')::jsonb
           else '[]'::jsonb
         end
       ) as a
),
resolved as (
  select s.meet_id, s.figure_score, s.routine_score,
         coalesce(l.person_id, byname.id) as person_id
  from source s
  left join as_result_person_link l
    on  l.result_table = s.result_table
    and l.result_id    = s.result_id
    and lower(btrim(l.athlete_name)) = s.athlete_name
  left join as_person byname
    on  l.person_id is null
    and s.athlete_name is not null
    and lower(btrim(coalesce(byname.given_name, '') || ' '
                    || coalesce(byname.family_name, ''))) = s.athlete_name
)
select r.person_id,
       m.meet_date as date,
       avg(r.figure_score)  as avg_figure_score,
       avg(r.routine_score) as avg_routine_score,
       avg(coalesce(r.figure_score, r.routine_score)) as rolling_trend
from resolved r
join as_meet m on m.id = r.meet_id
where r.person_id is not null
group by r.person_id, m.meet_date;

create unique index if not exists uq_as_daily_aggregations_person_date
  on as_daily_aggregations(person_id, date);

-- On-demand CONCURRENT refresh (research decision: refresh-on-access + cache)
create or replace function refresh_as_daily_aggregations()
returns void as $$
begin
  refresh materialized view concurrently as_daily_aggregations;
end;
$$ language plpgsql;

grant select on as_daily_aggregations to authenticated;

-- ============================================================================
-- 5. VIDEO ANALYSIS ENTITIES (FR-007)
-- ============================================================================

create table if not exists as_video_uploads (
  id               uuid primary key default gen_random_uuid(),
  club_id          uuid not null references as_club(id),
  -- `on delete restrict` is not cosmetic: 20260826 section 7 re-attaches these
  -- FKs with restrict after the legacy detach, so a person who has ever been
  -- filmed cannot be deleted out from under the footage. A bare `references`
  -- would default to no action and quietly permit it.
  person_id        uuid not null references as_person(id) on delete restrict,
  uploaded_by      uuid not null references as_person(id) on delete restrict,
  storage_path     text not null,   -- storage object key, never the URL
  mime_type        text not null default 'video/mp4',
  -- bigint, not integer: the backend caps a video at 2GB = 2147483648 bytes,
  -- which is exactly one past the integer maximum, so a file of the maximum
  -- allowed size would fail to insert.
  size_bytes       bigint not null,
  duration_seconds numeric,
  status           text not null default 'uploading'
                   check (status in ('uploading', 'uploaded', 'ready')),
  created_at       timestamptz not null default now(),
  -- Required by the update_as_video_uploads_updated_at trigger in section 8.
  -- 20260819_video_and_timer.sql added both; the 20260820 re-declaration of
  -- this table dropped them, and specs/001-analytics-dashboard/data-model.md
  -- names 20260819 as their only source. Without the column the trigger fails
  -- with "record NEW has no field updated_at" on every UPDATE.
  updated_at       timestamptz not null default now()
);

create index if not exists idx_as_video_uploads_club      on as_video_uploads(club_id);
create index if not exists idx_as_video_uploads_person     on as_video_uploads(person_id);
create index if not exists idx_as_video_uploads_retention on as_video_uploads(created_at);

create table if not exists as_video_markers (
  id          uuid primary key default gen_random_uuid(),
  video_id    uuid not null references as_video_uploads(id) on delete cascade,
  time_offset numeric(10,3) not null,
  marker_type text not null check (marker_type in ('audio_cue', 'figure', 'timing_mark')),
  figure_id   text,
  label       text,
  created_by  uuid not null references as_person(id) on delete restrict,
  created_at  timestamptz not null default now()
);

create index if not exists idx_as_video_markers_video_offset on as_video_markers(video_id, time_offset);

-- ============================================================================
-- 6. ROUTINE TIMER ENTITY (FR-008)
--    Only saved configurations persist; running state is client-side.
-- ============================================================================

create table if not exists as_routine_timers (
  id               uuid primary key default gen_random_uuid(),
  club_id          uuid not null references as_club(id),
  title            text,
  duration_seconds numeric not null,
  created_by       uuid not null references as_person(id) on delete restrict,
  created_at       timestamptz not null default now(),
  -- Same provenance as as_video_uploads.updated_at: 20260819 declared it, the
  -- 20260820 re-declaration dropped it, and the trigger in section 8 needs it.
  updated_at       timestamptz not null default now()
);

create index if not exists idx_as_routine_timers_club on as_routine_timers(club_id);

-- ============================================================================
-- 7. COMPETITION RESULTS BROWSER WIDGET (FR-009)
-- ============================================================================

create table if not exists as_competition_results_browser_widgets (
  widget_id          uuid primary key default gen_random_uuid(),
  club_id            uuid not null references as_club(id),
  person_id          uuid not null references as_person(id) on delete cascade,
  tree_state         jsonb default '{}',
  active_tab         text default 'figures' check (active_tab in ('figures', 'routines')),
  selected_node_path text,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now()
);

create index if not exists idx_as_results_browser_widgets_person on as_competition_results_browser_widgets(person_id);
create index if not exists idx_as_results_browser_widgets_club  on as_competition_results_browser_widgets(club_id);

-- ============================================================================
-- 8. updated_at TRIGGERS
-- ============================================================================

create or replace function update_updated_at_column()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_as_person_updated_at on as_person;
create trigger trg_as_person_updated_at
  before update on as_person
  for each row execute function update_updated_at_column();

drop trigger if exists trg_as_club_membership_updated_at on as_club_membership;
create trigger trg_as_club_membership_updated_at
  before update on as_club_membership
  for each row execute function update_updated_at_column();

drop trigger if exists trg_as_predictive_insights_updated_at on as_predictive_insights;
create trigger trg_as_predictive_insights_updated_at
  before update on as_predictive_insights
  for each row execute function update_updated_at_column();

drop trigger if exists trg_results_browser_widgets_updated_at on as_competition_results_browser_widgets;
create trigger trg_results_browser_widgets_updated_at
  before update on as_competition_results_browser_widgets
  for each row execute function update_updated_at_column();

-- Both triggers come from 20260819_video_and_timer.sql. 20260820 re-declares
-- those two tables without the `updated_at` column, so on a full chain these
-- triggers exist with nothing to stamp: they are kept here, together with the
-- columns, so the pair is never half-present.
drop trigger if exists update_as_video_uploads_updated_at on as_video_uploads;
create trigger update_as_video_uploads_updated_at
  before update on as_video_uploads
  for each row execute function update_updated_at_column();

drop trigger if exists update_as_routine_timers_updated_at on as_routine_timers;
create trigger update_as_routine_timers_updated_at
  before update on as_routine_timers
  for each row execute function update_updated_at_column();

-- ============================================================================
-- 9. AUTHORIZATION HELPERS
--    Taken from 20260826_person_identity_migration.sql, which is the only one of
--    the three files that declare these to qualify every table reference with
--    `public.`. That qualification is load-bearing, not cosmetic: each helper is
--    SECURITY DEFINER with `set search_path = ''`, so a bare table name is
--    unresolvable and CREATE FUNCTION fails outright.
--
--    They live after the tables and before the policies on purpose. A policy's
--    expression is parsed and analysed at CREATE POLICY time, so a policy
--    cannot call a helper that does not exist yet - and a SECURITY DEFINER
--    helper is what stops RLS on the identity tables from recursing when a
--    policy reads as_club_membership.
--
--    Club scope and role come from as_club_membership, never from a single
--    club_id claim, so offboarding and a role change take effect immediately
--    rather than at token expiry. These replace the old current_user_club_id()
--    and jwt_linked_athlete_ids().
-- ============================================================================

drop function if exists public.current_user_club_id();
drop function if exists public.jwt_linked_athlete_ids();

create or replace function public.app_current_person_id()
returns uuid
language sql stable security definer
set search_path = ''
as $$
  select pi.person_id
  from public.as_person_identity pi
  where pi.subject_id = auth.uid()
$$;

create or replace function public.app_active_memberships()
returns setof public.as_club_membership
language sql stable security definer
set search_path = ''
as $$
  select m.*
  from public.as_club_membership m
  where m.person_id = public.app_current_person_id()
    and m.status in ('invited', 'active')
$$;

create or replace function public.app_current_club_ids()
returns uuid[]
language sql stable security definer
set search_path = ''
as $$
  select coalesce(
    array(select m.club_id from public.app_active_memberships() m),
    '{}'::uuid[])
$$;

create or replace function public.app_has_club_role(p_club_id uuid, p_roles text[])
returns boolean
language sql stable security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.app_active_memberships() m
    where m.club_id = p_club_id
      and m.role = any(p_roles)
  )
$$;

create or replace function public.app_is_club_staff(p_club_id uuid)
returns boolean
language sql stable security definer
set search_path = ''
as $$
  select public.app_has_club_role(p_club_id, array['coach', 'admin'])
$$;

create or replace function public.app_is_guardian_of(
  p_parent_person_id uuid, p_child_person_id uuid, p_club_id uuid
)
returns boolean
language sql stable security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.as_person_link l
    where l.parent_person_id = p_parent_person_id
      and l.child_person_id  = p_child_person_id
      and l.club_id          = p_club_id
      and l.kind in ('parent', 'guardian')
  )
$$;

-- Person is visible to the caller if they share any active club.
create or replace function public.app_shares_club(p_person_id uuid)
returns boolean
language sql stable security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.as_club_membership mine
    where mine.person_id = public.app_current_person_id()
      and mine.status in ('invited', 'active')
      and exists (
        select 1 from public.as_club_membership theirs
        where theirs.club_id   = mine.club_id
          and theirs.person_id = p_person_id
          and theirs.status in ('invited', 'active')
      )
  )
$$;

create or replace function public.app_is_active_member(p_person_id uuid)
returns boolean
language sql stable security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.as_club_membership m
    where m.person_id = p_person_id
      and m.status in ('invited', 'active')
  )
$$;

-- People whose analytics the caller may read: the swimmers they coach, plus
-- themselves, plus their own children.
create or replace function public.app_visible_person_ids()
returns uuid[]
language sql stable security definer
set search_path = ''
as $$
  select coalesce(
    array(
      select distinct candidate
      from (
        select m.person_id as candidate
        from public.as_club_membership m
        where m.club_id in (
                select cm.club_id
                from public.as_club_membership cm
                where cm.person_id = public.app_current_person_id()
                  and cm.status in ('invited', 'active')
                  and cm.role in ('coach', 'admin'))
          and m.status in ('invited', 'active')
          and m.role = 'swimmer'

        union

        select public.app_current_person_id()

        union

        select l.child_person_id
        from public.as_person_link l
        where l.parent_person_id = public.app_current_person_id()
          and l.kind in ('parent', 'guardian')
      ) x
      where candidate is not null
        and public.app_is_active_member(candidate)
    ),
    '{}'::uuid[])
$$;

-- Family-only video access: coach-of, self (with membership), or guardian-of.
create or replace function public.app_can_view_video(p_club_id uuid, p_person_id uuid)
returns boolean
language sql stable security definer
set search_path = ''
as $$
  select
       public.app_is_club_staff(p_club_id)
    or (
         p_person_id = public.app_current_person_id()
         and public.app_has_club_role(p_club_id, array['swimmer'])
       )
    or (
         public.app_current_person_id() is not null
         and public.app_is_guardian_of(
               public.app_current_person_id(), p_person_id, p_club_id)
       )
$$;

create or replace function public.app_can_edit_video(p_club_id uuid, p_uploaded_by uuid)
returns boolean
language sql stable security definer
set search_path = ''
as $$
  select
       public.app_is_club_staff(p_club_id)
    or (
         p_uploaded_by is not null
         and p_uploaded_by = public.app_current_person_id()
       )
$$;

-- 10. ROW LEVEL SECURITY
--     The identity tables gain RLS here. Previously as_athlete / as_coach had
--     none, which left them world-readable and directly queried by policies.
--     Every membership read inside a policy now goes through a SECURITY
--     DEFINER helper, so there is no recursion.
-- ============================================================================

alter table as_person             enable row level security;
alter table as_person_identity    enable row level security;
alter table as_club_membership    enable row level security;
alter table as_person_link        enable row level security;
alter table as_result_person_link enable row level security;

alter table as_predictive_insights                 enable row level security;
alter table as_coaching_recommendations            enable row level security;
alter table as_video_uploads                       enable row level security;
alter table as_video_markers                       enable row level security;
alter table as_routine_timers                      enable row level security;
alter table as_competition_results_browser_widgets enable row level security;
-- Created by 20260804_initial_schema.sql. RLS is switched on there, but the policy
-- has to wait until after the helpers exist, because CREATE POLICY parses and
-- analyses its expression immediately and would fail on an unknown function.
alter table as_competition_result                  enable row level security;

-- -- as_competition_result ------------------------------------------------------

drop policy if exists "Users can only view competition results for visible persons"
  on as_competition_result;
create policy "Users can only view competition results for visible persons"
  on as_competition_result
  for select using (
    person_id = any (app_visible_person_ids())
  );

-- -- as_person -----------------------------------------------------------------

drop policy if exists "Members can view persons in their clubs" on as_person;
create policy "Members can view persons in their clubs" on as_person
  for select using (
    id = app_current_person_id() or app_shares_club(id)
  );

drop policy if exists "Persons can update their own profile" on as_person;
create policy "Persons can update their own profile" on as_person
  for update using (id = app_current_person_id())
  with check (id = app_current_person_id());

-- No insert/delete policy: persons are provisioned by the identity service.

-- -- as_person_identity --------------------------------------------------------

drop policy if exists "Persons can view their own identity" on as_person_identity;
create policy "Persons can view their own identity" on as_person_identity
  for select using (person_id = app_current_person_id());

-- -- as_club_membership --------------------------------------------------------

drop policy if exists "Members can view their own memberships" on as_club_membership;
create policy "Members can view their own memberships" on as_club_membership
  for select using (
    person_id = app_current_person_id() or app_is_club_staff(club_id)
  );

drop policy if exists "Admins can manage club memberships" on as_club_membership;
create policy "Admins can manage club memberships" on as_club_membership
  for all using (app_has_club_role(club_id, array['admin']))
  with check (app_has_club_role(club_id, array['admin']));

-- -- as_person_link ------------------------------------------------------------

drop policy if exists "Families can view their own links" on as_person_link;
create policy "Families can view their own links" on as_person_link
  for select using (
    parent_person_id = app_current_person_id()
    or child_person_id  = app_current_person_id()
    or app_is_club_staff(club_id)
  );

drop policy if exists "Admins can manage family links" on as_person_link;
create policy "Admins can manage family links" on as_person_link
  for all using (app_has_club_role(club_id, array['admin']))
  with check (app_has_club_role(club_id, array['admin']));

-- -- as_result_person_link -----------------------------------------------------

drop policy if exists "Members can view result person links" on as_result_person_link;
create policy "Members can view result person links" on as_result_person_link
  for select using (app_shares_club(person_id));

drop policy if exists "Members can resolve result person links" on as_result_person_link;
create policy "Members can resolve result person links" on as_result_person_link
  for insert with check (resolved_by = app_current_person_id() and app_shares_club(person_id));

drop policy if exists "Resolvers can update result person links" on as_result_person_link;
create policy "Resolvers can update result person links" on as_result_person_link
  for update using (resolved_by = app_current_person_id())
  with check (resolved_by = app_current_person_id());

-- -- as_predictive_insights / as_coaching_recommendations -----------------------
--     AI is read-only (Principle 11): authenticated callers get SELECT only and
--     writes require the service role.

drop policy if exists "Club members can view predictive insights" on as_predictive_insights;
create policy "Club members can view predictive insights" on as_predictive_insights
  for select using (person_id = any (app_visible_person_ids()));

drop policy if exists "Club members can view coaching recommendations" on as_coaching_recommendations;
create policy "Club members can view coaching recommendations" on as_coaching_recommendations
  for select using (person_id = any (app_visible_person_ids()));

-- -- as_video_uploads ----------------------------------------------------------

drop policy if exists "Family can view athlete videos" on as_video_uploads;
create policy "Family can view athlete videos" on as_video_uploads
  for select using (app_can_view_video(club_id, person_id));

drop policy if exists "Club members can upload videos" on as_video_uploads;
create policy "Club members can upload videos" on as_video_uploads
  for insert with check (
    app_is_club_staff(club_id)
    or app_is_guardian_of(app_current_person_id(), person_id, club_id)
  );

drop policy if exists "Uploader can update own videos" on as_video_uploads;
create policy "Uploader can update own videos" on as_video_uploads
  for update using (app_can_edit_video(club_id, uploaded_by));

drop policy if exists "Uploader can delete own videos" on as_video_uploads;
create policy "Uploader can delete own videos" on as_video_uploads
  for delete using (app_can_edit_video(club_id, uploaded_by));

-- -- as_video_markers ----------------------------------------------------------

drop policy if exists "Video-scoped marker access" on as_video_markers;
create policy "Video-scoped marker access" on as_video_markers
  for select using (
    video_id in (
      select v.id from as_video_uploads v
      where app_can_view_video(v.club_id, v.person_id)
    )
  );

drop policy if exists "Club members can create markers" on as_video_markers;
create policy "Club members can create markers" on as_video_markers
  for insert with check (
    video_id in (
      select v.id from as_video_uploads v
      where app_can_edit_video(v.club_id, v.uploaded_by)
    )
  );

drop policy if exists "Creator can update markers" on as_video_markers;
create policy "Creator can update markers" on as_video_markers
  for update using (
    exists (
      select 1 from as_video_uploads v
      where v.id = as_video_markers.video_id
        and app_can_edit_video(v.club_id, v.uploaded_by)
    )
  );

drop policy if exists "Creator can delete markers" on as_video_markers;
create policy "Creator can delete markers" on as_video_markers
  for delete using (
    exists (
      select 1 from as_video_uploads v
      where v.id = as_video_markers.video_id
        and app_can_edit_video(v.club_id, v.uploaded_by)
    )
  );

-- -- as_routine_timers ---------------------------------------------------------

drop policy if exists "Club members can view timers" on as_routine_timers;
create policy "Club members can view timers" on as_routine_timers
  for select using (club_id = any (app_current_club_ids()));

drop policy if exists "Club members can save timers" on as_routine_timers;
create policy "Club members can save timers" on as_routine_timers
  for insert with check (club_id = any (app_current_club_ids()));

drop policy if exists "Creator can update timers" on as_routine_timers;
create policy "Creator can update timers" on as_routine_timers
  for update using (created_by = app_current_person_id() or app_is_club_staff(club_id));

drop policy if exists "Creator can delete timers" on as_routine_timers;
create policy "Creator can delete timers" on as_routine_timers
  for delete using (created_by = app_current_person_id() or app_is_club_staff(club_id));

-- -- as_competition_results_browser_widgets -------------------------------------

drop policy if exists "Users can view own widget config" on as_competition_results_browser_widgets;
create policy "Users can view own widget config" on as_competition_results_browser_widgets
  for select using (person_id = app_current_person_id());

drop policy if exists "Users can insert own widget config" on as_competition_results_browser_widgets;
create policy "Users can insert own widget config" on as_competition_results_browser_widgets
  for insert with check (
    person_id = app_current_person_id() and club_id = any (app_current_club_ids())
  );

drop policy if exists "Users can update own widget config" on as_competition_results_browser_widgets;
create policy "Users can update own widget config" on as_competition_results_browser_widgets
  for update using (person_id = app_current_person_id());

drop policy if exists "Users can delete own widget config" on as_competition_results_browser_widgets;
create policy "Users can delete own widget config" on as_competition_results_browser_widgets
  for delete using (person_id = app_current_person_id());

-- ============================================================================
-- 11. GRANTS
--     Provisioning of persons and memberships is an identity-service duty and
--     runs as the service role; there is no authenticated write path into the
--     identity tables.
-- ============================================================================

grant select on
  as_person, as_person_identity, as_club_membership, as_person_link,
  as_result_person_link, as_athlete, as_coach,
  as_video_uploads, as_video_markers, as_routine_timers,
  as_competition_results_browser_widgets
  to authenticated;

grant insert, update, delete on
  as_video_uploads, as_video_markers, as_routine_timers,
  as_competition_results_browser_widgets
  to authenticated;

revoke insert, update, delete on
  as_person, as_person_identity, as_club_membership, as_person_link,
  as_predictive_insights, as_coaching_recommendations
  from authenticated;

-- ============================================================================
-- 12. VIDEO RETENTION (90 days, FR-007)
--     Markers cascade-delete with their video. Storage objects must be removed
--     by the scheduled job calling this function (Supabase Storage API), since
--     SQL can only clean database rows.
-- ============================================================================

create or replace function cleanup_expired_videos(
  retention_days integer default 90
)
returns integer as $$
declare
  deleted_count integer;
begin
  with expired as (
    delete from as_video_uploads
    where created_at < now() - make_interval(days => retention_days)
    returning id
  )
  select count(*) into deleted_count from expired;

  raise log 'cleanup_expired_videos: removed % videos older than % days',
    deleted_count, retention_days;
  return deleted_count;
end;
$$ language plpgsql;

-- Scheduled execution (pg_cron, if available):
-- select cron.schedule(
--   'cleanup-expired-videos', '0 3 * * *',
--   $$select cleanup_expired_videos(90)$$
-- );
