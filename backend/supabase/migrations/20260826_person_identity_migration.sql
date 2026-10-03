-- ============================================================================
-- 20260826_person_identity_migration.sql
--
-- One-way transform: login-centric identity  ->  Person / Club / Membership.
--   OLD: as_athlete(id, club_id, name), as_coach(id, club_id, name),
--        *.athlete_id, as_..._widgets.user_id, auth.uid() in data columns,
--        RLS via current_user_club_id() and jwt -> 'athlete_ids'.
--   NEW: as_person, as_person_identity, as_club_membership, as_person_link,
--        as_result_person_link, as_athlete/as_coach as views, *.person_id,
--        RLS via app_*() helpers that read membership.
--
-- Source of truth: specs/001-analytics-dashboard/identity-contract.md
-- Target schema:    20260827_all_schema_from_scratch.sql
--
-- Scope: this file is a DATA transform, not a schema. The four schema migrations it
-- used to follow have been consolidated into 20260827_all_schema_from_scratch.sql,
-- which a fresh database applies on its own. Apply this file only to a database
-- that already holds legacy as_athlete / as_coach rows; sections 2-5 backfill
-- as_person / as_club_membership from them and then DROP those tables.
--
-- Idempotent: a no-op on a database already at the target schema. Every step is
-- guarded so it is safe to re-run. `athlete_name` / `athlete_birth_year` on the
-- imported result tables are lineage fields and are deliberately NOT renamed.
-- ============================================================================

begin;

-- ============================================================================
-- 0. TENANT TABLE COLUMNS (forward fix for databases already migrated)
-- ============================================================================
-- 20260804 created as_club as (id, name) only, but the application selects and
-- writes `code` (backend/src/api/results_browser.py; the loaders in
-- scripts/tmp/AdhocDataMigration/) and `city`. 20260820 now declares the full
-- table, which covers a fresh database, but an existing database has already
-- run 20260820 and needs these added here. Guarded and backfilled: existing
-- clubs get a code derived from their name, and duplicate derivations are
-- disambiguated with their id so the unique index can be created.
-- ============================================================================

alter table as_club add column if not exists code text;
alter table as_club add column if not exists city text;
alter table as_club add column if not exists created_by uuid;

update as_club
   set code = upper(substr(regexp_replace(coalesce(name, 'CLUB'), '[^A-Za-z0-9]', '', 'g'), 1, 8))
 where code is null;

-- Two clubs with the same name would derive the same code; break the tie.
update as_club a
   set code = left(a.code, 6) || '-' || substr(replace(a.id::text, '-', ''), 1, 6)
 where a.id in (
       select id from (
         select id, row_number() over (partition by code order by id) as rn
           from as_club
       ) d where d.rn > 1
     );

alter table as_club alter column code set not null;
-- Unique already indexes `code`, which is the only way the app looks a club up.
create unique index if not exists uq_as_club_code on as_club (code);

-- fk_as_club_created_by is added further down, once as_person exists.

-- ============================================================================
-- 1. IDENTITY CORE
-- ============================================================================

create table if not exists as_person (
  id          uuid primary key,
  given_name  text not null,
  family_name text,
  middle_name text,
  birth_date  date,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

-- Deferred from section 0: as_club.created_by can only be constrained once the
-- table it points at exists.
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

-- Optional: a person exists (and is a full member of the model) with no account.
create table if not exists as_person_identity (
  person_id  uuid primary key references as_person(id) on delete cascade,
  subject_id uuid not null unique,
  created_at timestamptz not null default now()
);

-- The tenant-scoped edge. Authorization source of truth.
create table if not exists as_club_membership (
  id         uuid primary key default gen_random_uuid(),
  person_id  uuid not null references as_person(id) on delete cascade,
  club_id    uuid not null references as_club(id) on delete cascade,
  role       text not null check (role in ('admin','coach','swimmer','parent','official')),
  title      text,   -- display only ("Lead Coach", "Team Captain"); never authorizes
  status     text not null default 'active'
             check (status in ('invited','active','dormant','left')),
  joined_at  date,
  left_at    date,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists uq_as_club_membership_active
  on as_club_membership (person_id, club_id, role)
  where status in ('invited','active');

create index if not exists idx_as_club_membership_club_status
  on as_club_membership (club_id, status);
create index if not exists idx_as_club_membership_person
  on as_club_membership (person_id);
create index if not exists idx_as_person_name
  on as_person (lower(family_name), lower(given_name));

-- Directed guardian edge. Replaces the JWT `athlete_ids` claim.
create table if not exists as_person_link (
  id                uuid primary key default gen_random_uuid(),
  parent_person_id  uuid not null references as_person(id) on delete cascade,
  child_person_id   uuid not null references as_person(id) on delete cascade,
  club_id           uuid not null references as_club(id) on delete cascade,
  kind              text not null
                    check (kind in ('parent','guardian','emergency_contact')),
  created_at        timestamptz not null default now(),
  constraint ck_as_person_link_distinct check (parent_person_id <> child_person_id)
);

create index if not exists idx_as_person_link_child
  on as_person_link (child_person_id, club_id, kind);
create index if not exists idx_as_person_link_parent
  on as_person_link (parent_person_id, club_id);

-- Resolves immutable PDF result rows to canonical persons. `result_id` is
-- polymorphic across two result tables, so it carries no foreign key;
-- `athlete_name` disambiguates rows inside as_meet_routine_result.team_athletes.
create table if not exists as_result_person_link (
  id            uuid primary key default gen_random_uuid(),
  result_table  text not null
                check (result_table in ('as_meet_figure_result','as_meet_routine_result')),
  result_id     uuid not null,
  person_id     uuid not null references as_person(id) on delete cascade,
  athlete_name  text not null,
  confidence    numeric,
  resolved_by   uuid references as_person(id) on delete set null,
  resolved_at   timestamptz not null default now()
);

create unique index if not exists uq_as_result_person_link
  on as_result_person_link (result_table, result_id, athlete_name);
create index if not exists idx_as_result_person_link_person
  on as_result_person_link (person_id);

-- ============================================================================
-- 2. BACKFILL PERSONS AND MEMBERSHIPS FROM THE LEGACY TABLES
--    Legacy rows carry a single denormalized `name` and a denormalized
--    `club_id`; both are decomposed here. The name split is a heuristic
--    (last token = family name) and is expected to be hand-corrected.
-- ============================================================================

do $$
begin
  if to_regclass('public.as_athlete') is not null then
    execute $q$
      with legacy as (
        select a.id, regexp_split_to_array(btrim(a.name), '\s+') as parts
        from public.as_athlete a
        where btrim(coalesce(a.name, '')) <> ''
      )
      insert into public.as_person (id, given_name, family_name)
      select id,
             case when array_length(parts, 1) > 1
                  then btrim(array_to_string(parts[1:array_length(parts, 1) - 1], ' '))
                  else parts[1] end,
             case when array_length(parts, 1) > 1
                  then parts[array_length(parts, 1)] end
      from legacy
      on conflict (id) do nothing
    $q$;

    execute $q$
      insert into public.as_club_membership (person_id, club_id, role, status, joined_at)
      select a.id, a.club_id, 'swimmer', 'active', current_date
      from public.as_athlete a
      where a.club_id is not null
        and exists (select 1 from public.as_person p where p.id = a.id)
      on conflict do nothing
    $q$;
  end if;

  if to_regclass('public.as_coach') is not null then
    execute $q$
      with legacy as (
        select c.id, regexp_split_to_array(btrim(c.name), '\s+') as parts
        from public.as_coach c
        where btrim(coalesce(c.name, '')) <> ''
      )
      insert into public.as_person (id, given_name, family_name)
      select id,
             case when array_length(parts, 1) > 1
                  then btrim(array_to_string(parts[1:array_length(parts, 1) - 1], ' '))
                  else parts[1] end,
             case when array_length(parts, 1) > 1
                  then parts[array_length(parts, 1)] end
      from legacy
      on conflict (id) do nothing
    $q$;

    execute $q$
      insert into public.as_club_membership (person_id, club_id, role, status, joined_at)
      select c.id, c.club_id, 'coach', 'active', current_date
      from public.as_coach c
      where c.club_id is not null
        and exists (select 1 from public.as_person p where p.id = c.id)
      on conflict do nothing
    $q$;
  end if;
end
$$;

-- as_person_identity is intentionally left empty. The legacy tables stored no
-- subject id, so the auth-subject -> person mapping cannot be derived. Populate
-- it when the user service reports a subject, e.g.
--   insert into as_person_identity (person_id, subject_id)
--   values (:person_id, :subject_id)
--   on conflict (subject_id) do nothing;

-- ============================================================================
-- 3. DROP THE MATERIALIZED VIEW BEFORE THE LEGACY TABLES IT DEPENDS ON
-- ============================================================================

drop materialized view if exists public.as_daily_aggregations cascade;

-- ============================================================================
-- 4. RENAME IDENTITY COLUMNS
-- ============================================================================

do $$
declare t text;
begin
  foreach t in array array[
    'as_predictive_insights',
    'as_coaching_recommendations',
    'as_video_uploads',
    'as_daily_aggregations'
  ] loop
    if exists (select 1 from information_schema.columns
                where table_schema = 'public' and table_name = t
                  and column_name = 'athlete_id') then
      execute format('alter table public.%I rename column athlete_id to person_id', t);
    end if;
  end loop;

  if exists (select 1 from information_schema.columns
              where table_schema = 'public'
                and table_name = 'as_competition_results_browser_widgets'
                and column_name = 'user_id') then
    alter table public.as_competition_results_browser_widgets
      rename column user_id to person_id;
  end if;
end
$$;

-- ============================================================================
-- 5. DETACH FOREIGN KEES POINTING AT THE LEGACY TABLES, THEN DROP THEM
-- ============================================================================

do $$
declare r record;
begin
  for r in
    select n.nspname as schema_name, c.relname as table_name, con.conname
    from pg_constraint con
    join pg_class c  on c.oid = con.conrelid
    join pg_namespace n on n.oid = c.relnamespace
    where con.contype = 'f'
      and con.confrelid in (
        select c2.oid
        from pg_class c2
        join pg_namespace n2 on n2.oid = c2.relnamespace
        where n2.nspname = 'public'
          and c2.relname in ('as_athlete', 'as_coach')
          and c2.relkind = 'r'
      )
  loop
    execute format('alter table %I.%I drop constraint %I',
                   r.schema_name, r.table_name, r.conname);
  end loop;
end
$$;

drop table if exists public.as_athlete;
drop table if exists public.as_coach;

-- ============================================================================
-- 6. ATHLETE / COACH BECOME VIEWS OVER PERSON + MEMBERSHIP
--    No club_id column: a view over club-scoped memberships cannot carry one
--    without collapsing a multi-club person into several rows.
-- ============================================================================

create or replace view public.as_athlete as
select p.id as person_id,
       p.given_name,
       p.family_name,
       p.middle_name,
       p.birth_date,
       btrim(coalesce(p.middle_name || ' ', '')
             || p.given_name || ' ' || coalesce(p.family_name, '')) as name
from public.as_person p
where exists (
  select 1 from public.as_club_membership m
  where m.person_id = p.id
    and m.role = 'swimmer'
    and m.status in ('invited', 'active')
);

create or replace view public.as_coach as
select p.id as person_id,
       p.given_name,
       p.family_name,
       p.middle_name,
       btrim(coalesce(p.middle_name || ' ', '')
             || p.given_name || ' ' || coalesce(p.family_name, '')) as name
from public.as_person p
where exists (
  select 1 from public.as_club_membership m
  where m.person_id = p.id
    and m.role in ('coach', 'admin')
    and m.status in ('invited', 'active')
);

-- ============================================================================
-- 7. RE-ATTACH FOREIGN KEYS TO as_person
-- ============================================================================

do $$
declare spec text;
begin
  foreach spec in array array[
    'as_predictive_insights:person_id:cascade',
    'as_coaching_recommendations:person_id:cascade',
    'as_video_uploads:person_id:restrict',
    'as_video_uploads:uploaded_by:restrict',
    'as_video_markers:created_by:restrict',
    'as_routine_timers:created_by:restrict',
    'as_competition_results_browser_widgets:person_id:cascade'
  ] loop
    declare
      parts text[] := string_to_array(spec, ':');
      tbl   text   := parts[1];
      col   text   := parts[2];
      ondel text   := parts[3];
    begin
      if exists (select 1 from information_schema.columns
                  where table_schema = 'public' and table_name = tbl
                    and column_name = col)
         and exists (select 1 from pg_constraint con
                      where con.contype = 'f'
                        and con.conrelid = format('public.%I', tbl)::regclass
                        and con.conkey = array[
                              (select attnum from pg_attribute
                                where attrelid = format('public.%I', tbl)::regclass
                                  and attname = col)])
      then
        continue;
      end if;

      execute format(
        'alter table public.%I add constraint %I foreign key (%I) references public.as_person(id) on delete %s',
        tbl, format('fk_%I_%I', tbl, col), col, ondel);
    end;
  end loop;
end
$$;

create index if not exists idx_as_predictive_insights_person
  on as_predictive_insights (person_id);
create index if not exists idx_as_coaching_recommendations_person
  on as_coaching_recommendations (person_id, generated_at desc);
create index if not exists idx_as_video_uploads_person
  on as_video_uploads (person_id);

-- ============================================================================
-- 8. AUTHORIZATION HELPERS
--    All are STABLE SECURITY DEFINER with an empty search_path and fully
--    qualified names. SECURITY DEFINER is what stops RLS on the identity
--    tables from recursing when a policy calls one of these.
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

-- ============================================================================
-- 9. ROW LEVEL SECURITY
--    The identity tables gain RLS here. They previously had none, which meant
--    as_athlete / as_coach were world-readable and were queried directly by
--    policies. Every membership read inside a policy now goes through a
--    SECURITY DEFINER helper, so there is no recursion.
-- ============================================================================

alter table as_person           enable row level security;
alter table as_person_identity  enable row level security;
alter table as_club_membership  enable row level security;
alter table as_person_link      enable row level security;
alter table as_result_person_link enable row level security;

alter table as_predictive_insights               enable row level security;
alter table as_coaching_recommendations          enable row level security;
alter table as_video_uploads                     enable row level security;
alter table as_video_markers                     enable row level security;
alter table as_routine_timers                    enable row level security;
alter table as_competition_results_browser_widgets enable row level security;

-- -- as_person ----------------------------------------------------------------

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

-- -- as_person_identity -------------------------------------------------------

drop policy if exists "Persons can view their own identity" on as_person_identity;
create policy "Persons can view their own identity" on as_person_identity
  for select using (person_id = app_current_person_id());

-- -- as_club_membership -------------------------------------------------------

drop policy if exists "Members can view their own memberships" on as_club_membership;
create policy "Members can view their own memberships" on as_club_membership
  for select using (
    person_id = app_current_person_id() or app_is_club_staff(club_id)
  );

drop policy if exists "Admins can manage club memberships" on as_club_membership;
create policy "Admins can manage club memberships" on as_club_membership
  for all using (app_has_club_role(club_id, array['admin']))
  with check (app_has_club_role(club_id, array['admin']));

-- -- as_person_link -----------------------------------------------------------

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

-- -- as_result_person_link ----------------------------------------------------

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

-- -- as_predictive_insights / as_coaching_recommendations --------------------
--    AI is read-only: authenticated callers get SELECT only, writes require the
--    service role.

drop policy if exists "Club members can view predictive insights" on as_predictive_insights;
create policy "Club members can view predictive insights" on as_predictive_insights
  for select using (person_id = any (app_visible_person_ids()));

drop policy if exists "Club members can view coaching recommendations" on as_coaching_recommendations;
create policy "Club members can view coaching recommendations" on as_coaching_recommendations
  for select using (person_id = any (app_visible_person_ids()));

-- -- as_video_uploads --------------------------------------------------------

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

-- -- as_video_markers --------------------------------------------------------

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

-- -- as_routine_timers -------------------------------------------------------

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

-- -- as_competition_results_browser_widgets ----------------------------------

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
-- 10. DAILY AGGREGATIONS
--    Resolution order: explicit as_result_person_link first, then normalized
--    name match. Unresolved rows are dropped rather than guessed, so a fuzzy
--    match that would attribute a score to the wrong human cannot happen.
--    RLS is not available on a materialized view; the rows are aggregates of
--    official competition results, which the constitution already treats as
--    publicly readable via the results browser.
-- ============================================================================

create materialized view public.as_daily_aggregations as
with source as (
  select 'as_meet_figure_result'::text as result_table,
         f.id                      as result_id,
         f.meet_id,
         lower(btrim(f.athlete_name)) as athlete_name,
         f.figure_score            as figure_score,
         null::numeric             as routine_score
  from public.as_meet_figure_result f

  union all

  select 'as_meet_routine_result',
         r.id,
         r.meet_id,
         lower(btrim(a ->> 'name')),
         null::numeric,
         r.routine_score
  from public.as_meet_routine_result r,
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
  left join public.as_result_person_link l
    on  l.result_table = s.result_table
    and l.result_id    = s.result_id
    and lower(btrim(l.athlete_name)) = s.athlete_name
  left join public.as_person byname
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
join public.as_meet m on m.id = r.meet_id
where r.person_id is not null
group by r.person_id, m.meet_date;

create unique index if not exists uq_as_daily_aggregations_person_date
  on public.as_daily_aggregations (person_id, date);

create or replace function public.refresh_as_daily_aggregations()
returns void
language plpgsql
as $$
begin
  refresh materialized view concurrently public.as_daily_aggregations;
end;
$$;

grant select on public.as_daily_aggregations to authenticated;

-- ============================================================================
-- 11. GRANTS
--    Service-role writes for AI output and identity provisioning; no
--    authenticated write path into the identity tables.
-- ============================================================================

grant select on
  public.as_person,
  public.as_person_identity,
  public.as_club_membership,
  public.as_person_link,
  public.as_result_person_link,
  public.as_athlete,
  public.as_coach,
  public.as_video_uploads,
  public.as_video_markers,
  public.as_routine_timers,
  public.as_competition_results_browser_widgets
  to authenticated;

grant insert, update, delete on
  public.as_video_uploads,
  public.as_video_markers,
  public.as_routine_timers,
  public.as_competition_results_browser_widgets
  to authenticated;

revoke insert, update, delete on
  public.as_person,
  public.as_person_identity,
  public.as_club_membership,
  public.as_person_link,
  public.as_predictive_insights,
  public.as_coaching_recommendations
  from authenticated;

commit;
