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

create table if not exists as_figure_judge_panel (
  id uuid default gen_random_uuid() primary key,
  meet_id uuid references as_meet(id) on delete cascade,
  figure_id uuid references as_figure(id) on delete cascade,
  figure_code_short text,
  figure_name text,
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
  total_score numeric,
  routine_score numeric,
  figure_scores jsonb,
  source_file text,
  created_at timestamptz default now()
);
