-- Create normalized tables for parsed figure results
-- Run this in your Supabase SQL editor or psql against the project's DB
--
-- IDENTITY: these are imported-result tables, not identity tables. They carry no
-- club_id and no reference to a canonical person. `athlete_name`,
-- `athlete_birth_year` and `team_athletes` are verbatim fields transcribed from
-- the official result PDFs and keep their names as data lineage; they are NOT
-- identity references.
--
-- The authoritative identity model is specs/001-analytics-dashboard/identity-contract.md:
-- a person is `as_person`, a club is `as_club`, and membership is the edge in
-- `as_club_membership`. A person has no club_id; a login (as_person_identity) is
-- optional. Anything that references a canonical person is `person_id`.
--
-- Mapping an immutable result row to a person lives in `as_result_person_link`
-- (result_table, result_id, athlete_name, person_id) -- see
-- backend/src/supabase/migrations/20260826_person_identity_migration.sql. Until
-- that link is populated, per-person analytics resolve these rows by printed name.

create extension if not exists "pgcrypto";

create table if not exists as_event (
  id uuid default gen_random_uuid() primary key,
  event_name text,
  host_city text,
  event_date date,
  created_at timestamptz default now()
);

create table if not exists as_meet (
  id uuid default gen_random_uuid() primary key,
  event_id uuid references as_event(id) on delete cascade,
  name text,
  meet_date date,
  created_at timestamptz default now()
);

create table if not exists as_figure (
  id uuid default gen_random_uuid() primary key,
  meet_id uuid references as_meet(id) on delete cascade,
  figure_code text,
  figure_code_short text,
  name text,
  degree_difficulty numeric,
  created_at timestamptz default now()
);

create table if not exists as_meet_judge_panel (
  id uuid default gen_random_uuid() primary key,
  meet_id uuid references as_meet(id) on delete cascade,
  figure_id uuid references as_figure(id) on delete cascade,
  figure_code_short text,
  panel_name text,
  panel json,
  created_at timestamptz default now()
);

create table if not exists as_meet_figure_result (
  id uuid default gen_random_uuid() primary key,
  meet_id uuid references as_meet(id) on delete cascade,
  rank text,
  draw text,
  team_code text,
  team_name text,
  athlete_name text,
  athlete_birth_year integer,
  penalty text,
  total_score numeric,   -- total score for the figures, it is useless for the routines, but we keep it for consistency
  figure_score numeric,  -- weighted total score for the figures, it is used to rank the swimmers
  figure_scores jsonb,   -- the detailed scores for each figure
  source_file text,
  created_at timestamptz default now()
);

create table if not exists as_meet_routine_result (
  id uuid default gen_random_uuid() primary key,
  meet_id uuid references as_meet(id) on delete cascade,
  rank text,
  draw text,
  team_code text,
  team_name text,
  team_athletes jsonb,
  total_difficulty jsonb,
  routine_scores jsonb,
  element_total numeric,
  artisticimpression_total numeric,
  synchronization_total numeric,
  routine_score numeric,
  source_file text,
  created_at timestamptz default now()
);
