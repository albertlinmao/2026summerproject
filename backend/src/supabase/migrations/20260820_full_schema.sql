-- ============================================================================
-- Artistic Swimming Analytics Dashboard — Table Creation Script
-- Source of truth: specs/001-analytics-dashboard/data-model.md
--
-- Idempotent: safe to re-run (IF NOT EXISTS / DO-block guards throughout).
-- All tables use the as_ prefix. Covers all data-model entities:
--   Core (existing competition tables) ......... as_event ... as_meet_routine_result
--   Reference (Multi-Tenant User Service) ...... as_club, as_athlete, as_coach
--   Analytical ................................. as_daily_aggregations (mat. view),
--                                                as_predictive_insights, as_coaching_recommendations
--   Video Analysis (FR-007) .................... as_video_uploads, as_video_markers
--   Routine Timer (FR-008) ..................... as_routine_timers
--   Results Browser Widget (FR-009) ............ as_competition_results_browser_widgets
-- Plus: indexes, RLS (club isolation + family access), immutability guards,
--       materialized-view refresh and 90-day video retention functions.
-- ============================================================================

create extension if not exists "pgcrypto";

-- ============================================================================
-- 1. REFERENCE ENTITIES (managed by the Multi-Tenant User Service)
--    Local DB stores UUID references only — never profile/auth data
--    (Constitution Principle 16).
-- ============================================================================

create table if not exists as_club (
  id   uuid primary key,          -- UUID issued by the user service
  name text not null
);

create table if not exists as_athlete (
  id      uuid primary key,       -- UUID issued by the user service
  club_id uuid not null references as_club(id),
  name    text not null
);

create table if not exists as_coach (
  id      uuid primary key,       -- UUID issued by the user service
  club_id uuid not null references as_club(id),
  name    text not null
);

create index if not exists idx_as_athlete_club on as_athlete(club_id);
create index if not exists idx_as_coach_club   on as_coach(club_id);

-- ============================================================================
-- 2. CORE ENTITIES (competition records imported from official PDFs)
--    Immutable once imported (Constitution Principle 5).
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
  athlete_name       text,
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
  team_athletes            jsonb,
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
-- 3. ANALYTICAL ENTITIES
-- ============================================================================

-- Predictive Insight: ML-generated forecasts (read-only, Principle 11)
create table if not exists as_predictive_insights (
  id                    uuid primary key default gen_random_uuid(),
  athlete_id            uuid not null references as_athlete(id) on delete cascade,
  next_score_prediction numeric,
  plateau_risk          boolean default false,
  confidence_interval   numeric,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

create index if not exists idx_as_predictive_insights_athlete on as_predictive_insights(athlete_id);

-- Coaching Recommendation: AI-generated natural language feedback
create table if not exists as_coaching_recommendations (
  id                  uuid primary key default gen_random_uuid(),
  athlete_id          uuid not null references as_athlete(id) on delete cascade,
  recommendation_text text not null,
  generated_at        timestamptz not null default now(),
  weakest_figure      text,
  created_at          timestamptz not null default now()
);

create index if not exists idx_as_coaching_recommendations_athlete
  on as_coaching_recommendations(athlete_id, generated_at desc);

-- Daily Aggregations: pre-calculated statistics for dashboard rendering
-- (layered analytics, Principle 14). Derived from the two result tables.
-- NOTE: rows are matched to Athlete references by normalized name; production
-- matching should extend to fuzzy name + birth year + club per the
-- Data Integration Notes in data-model.md.
create materialized view if not exists as_daily_aggregations as
select
  a.id                        as athlete_id,
  m.meet_date                 as date,
  avg(src.figure_score)       as avg_figure_score,
  avg(src.routine_score)      as avg_routine_score,
  avg(coalesce(src.figure_score, src.routine_score)) as rolling_trend
from (
  select
    athlete_name as matched_name,
    meet_id,
    figure_score  as figure_score,
    null::numeric as routine_score
  from as_meet_figure_result
  union all
  select
    (r->>'name')  as matched_name,
    meet_id,
    null::numeric as figure_score,
    routine_score as routine_score
  from as_meet_routine_result,
       jsonb_array_elements(
         case
           -- team_athletes may be a JSON array or a JSON-encoded string (legacy imports)
           when jsonb_typeof(team_athletes) = 'array' then team_athletes
           when jsonb_typeof(team_athletes) = 'string'
                and jsonb_typeof((team_athletes #>> '{}')::jsonb) = 'array'
             then (team_athletes #>> '{}')::jsonb
           else '[]'::jsonb
         end
       ) as r
) src
join as_meet m on src.meet_id = m.id
join as_athlete a on lower(a.name) = lower(trim(src.matched_name))
group by a.id, m.meet_date;

create unique index if not exists idx_as_daily_aggregations_athlete_date
  on as_daily_aggregations(athlete_id, date);

-- On-demand CONCURRENT refresh (research decision: refresh-on-access + cache)
create or replace function refresh_as_daily_aggregations()
returns void as $$
begin
  refresh materialized view concurrently as_daily_aggregations;
end;
$$ language plpgsql;

grant select on as_daily_aggregations to authenticated;

-- ============================================================================
-- 4. VIDEO ANALYSIS ENTITIES (FR-007)
-- ============================================================================

create table if not exists as_video_uploads (
  id               uuid primary key default gen_random_uuid(),
  club_id          uuid not null references as_club(id),
  athlete_id       uuid not null references as_athlete(id),  -- family-access scope
  uploaded_by      uuid not null,
  storage_path     text not null,   -- storage object key, never the URL
  mime_type        text not null default 'video/mp4',
  size_bytes       integer not null,
  duration_seconds numeric,
  status           text not null default 'uploading'
                   check (status in ('uploading', 'uploaded', 'ready')),
  created_at       timestamptz not null default now()
);

create index if not exists idx_as_video_uploads_club      on as_video_uploads(club_id);
create index if not exists idx_as_video_uploads_athlete   on as_video_uploads(athlete_id);
create index if not exists idx_as_video_uploads_retention on as_video_uploads(created_at);

create table if not exists as_video_markers (
  id          uuid primary key default gen_random_uuid(),
  video_id    uuid not null references as_video_uploads(id) on delete cascade,
  time_offset numeric(10,3) not null,
  marker_type text not null check (marker_type in ('audio_cue', 'figure', 'timing_mark')),
  figure_id   text,
  label       text,
  created_by  uuid not null,
  created_at  timestamptz not null default now()
);

create index if not exists idx_as_video_markers_video_offset on as_video_markers(video_id, time_offset);

-- ============================================================================
-- 5. ROUTINE TIMER ENTITY (FR-008)
--    Only saved configurations persist; running state is client-side.
-- ============================================================================

create table if not exists as_routine_timers (
  id               uuid primary key default gen_random_uuid(),
  club_id          uuid not null references as_club(id),
  title            text,
  duration_seconds numeric not null,
  created_by       uuid not null,
  created_at       timestamptz not null default now()
);

create index if not exists idx_as_routine_timers_club on as_routine_timers(club_id);

-- ============================================================================
-- 6. COMPETITION RESULTS BROWSER WIDGET (FR-009)
-- ============================================================================

create table if not exists as_competition_results_browser_widgets (
  widget_id          uuid primary key default gen_random_uuid(),
  club_id            uuid not null references as_club(id),
  user_id            uuid not null,
  tree_state         jsonb default '{}',
  active_tab         text default 'figures' check (active_tab in ('figures', 'routines')),
  selected_node_path text,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now()
);

create index if not exists idx_as_results_browser_widgets_user on as_competition_results_browser_widgets(user_id);
create index if not exists idx_as_results_browser_widgets_club on as_competition_results_browser_widgets(club_id);

-- ============================================================================
-- 7. updated_at TRIGGERS
-- ============================================================================

create or replace function update_updated_at_column()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_as_predictive_insights_updated_at on as_predictive_insights;
create trigger trg_as_predictive_insights_updated_at
  before update on as_predictive_insights
  for each row execute function update_updated_at_column();

drop trigger if exists trg_results_browser_widgets_updated_at on as_competition_results_browser_widgets;
create trigger trg_results_browser_widgets_updated_at
  before update on as_competition_results_browser_widgets
  for each row execute function update_updated_at_column();

-- ============================================================================
-- 8. ROW LEVEL SECURITY
--    Club isolation everywhere; family access (athlete / coaches / parents)
--    on videos via the athlete_id link and Multi-Tenant User Service claims
--    (auth.jwt() -> 'athlete_ids' carries self/parent-linked athlete IDs).
-- ============================================================================

alter table as_predictive_insights enable row level security;
alter table as_coaching_recommendations enable row level security;
alter table as_video_uploads enable row level security;
alter table as_video_markers enable row level security;
alter table as_routine_timers enable row level security;
alter table as_competition_results_browser_widgets enable row level security;

-- Helper predicates ---------------------------------------------------------

create or replace function current_user_club_id()
returns uuid as $$
  select coalesce(
    (select club_id from as_coach where id = auth.uid()),
    (select club_id from as_athlete where id = auth.uid())
  );
$$ language sql stable security definer;

create or replace function jwt_linked_athlete_ids()
returns uuid[] as $$
  select coalesce(
    array(select jsonb_array_elements_text(coalesce(auth.jwt() -> 'athlete_ids', '[]'::jsonb))::uuid),
    '{}'::uuid[]
  );
$$ language sql stable;

-- as_predictive_insights --------------------------------------------------------

drop policy if exists "Club members can view predictive insights" on as_predictive_insights;
create policy "Club members can view predictive insights" on as_predictive_insights
  for select using (
    athlete_id in (select id from as_athlete where club_id = current_user_club_id())
  );

-- as_coaching_recommendations ----------------------------------------------------

drop policy if exists "Club members can view coaching recommendations" on as_coaching_recommendations;
create policy "Club members can view coaching recommendations" on as_coaching_recommendations
  for select using (
    athlete_id in (select id from as_athlete where club_id = current_user_club_id())
  );

-- as_video_uploads: family access (self, coaches of the athlete, parents) ------

drop policy if exists "Family can view athlete videos" on as_video_uploads;
create policy "Family can view athlete videos" on as_video_uploads
  for select using (
    athlete_id = auth.uid()                                   -- the filmed athlete
    or athlete_id = any (jwt_linked_athlete_ids())            -- parents / linked family
    or club_id = current_user_club_id()                       -- coaches & club staff
  );

drop policy if exists "Club members can upload videos" on as_video_uploads;
create policy "Club members can upload videos" on as_video_uploads
  for insert with check (club_id = current_user_club_id());

-- Immutable after finalization: only the uploader may update (status flow),
-- nobody may change storage_path afterwards.
drop policy if exists "Uploader can update own videos" on as_video_uploads;
create policy "Uploader can update own videos" on as_video_uploads
  for update using (uploaded_by = auth.uid());

drop policy if exists "Uploader can delete own videos" on as_video_uploads;
create policy "Uploader can delete own videos" on as_video_uploads
  for delete using (uploaded_by = auth.uid());

-- as_video_markers: inherit access from the parent video -----------------------

drop policy if exists "Video-scoped marker access" on as_video_markers;
create policy "Video-scoped marker access" on as_video_markers
  for select using (
    video_id in (
      select id from as_video_uploads
      where athlete_id = auth.uid()
         or athlete_id = any (jwt_linked_athlete_ids())
         or club_id = current_user_club_id()
    )
  );

drop policy if exists "Club members can create markers" on as_video_markers;
create policy "Club members can create markers" on as_video_markers
  for insert with check (
    video_id in (
      select id from as_video_uploads where club_id = current_user_club_id()
    )
  );

drop policy if exists "Creator can update markers" on as_video_markers;
create policy "Creator can update markers" on as_video_markers
  for update using (created_by = auth.uid());

drop policy if exists "Creator can delete markers" on as_video_markers;
create policy "Creator can delete markers" on as_video_markers
  for delete using (created_by = auth.uid());

-- as_routine_timers --------------------------------------------------------------

drop policy if exists "Club members can view timers" on as_routine_timers;
create policy "Club members can view timers" on as_routine_timers
  for select using (club_id = current_user_club_id());

drop policy if exists "Club members can save timers" on as_routine_timers;
create policy "Club members can save timers" on as_routine_timers
  for insert with check (club_id = current_user_club_id());

drop policy if exists "Creator can update timers" on as_routine_timers;
create policy "Creator can update timers" on as_routine_timers
  for update using (created_by = auth.uid());

drop policy if exists "Creator can delete timers" on as_routine_timers;
create policy "Creator can delete timers" on as_routine_timers
  for delete using (created_by = auth.uid());

-- as_competition_results_browser_widgets -------------------------------------------

drop policy if exists "Users can view own widget config" on as_competition_results_browser_widgets;
create policy "Users can view own widget config" on as_competition_results_browser_widgets
  for select using (user_id = auth.uid());

drop policy if exists "Users can insert own widget config" on as_competition_results_browser_widgets;
create policy "Users can insert own widget config" on as_competition_results_browser_widgets
  for insert with check (user_id = auth.uid() and club_id = current_user_club_id());

drop policy if exists "Users can update own widget config" on as_competition_results_browser_widgets;
create policy "Users can update own widget config" on as_competition_results_browser_widgets
  for update using (user_id = auth.uid());

drop policy if exists "Users can delete own widget config" on as_competition_results_browser_widgets;
create policy "Users can delete own widget config" on as_competition_results_browser_widgets
  for delete using (user_id = auth.uid());

-- ============================================================================
-- 9. VIDEO RETENTION (90 days, FR-007)
--    Markers cascade-delete with their video. Storage objects must be removed
--    by the scheduled job calling this function (Supabase Storage API), since
--    SQL can only clean database rows.
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
