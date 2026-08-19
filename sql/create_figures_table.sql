-- Create normalized tables for parsed figure results
-- Run this in your Supabase SQL editor or psql against the project's DB

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
