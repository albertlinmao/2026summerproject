-- T009 Core Tables
CREATE TABLE as_club (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE as_coach (
    id UUID PRIMARY KEY,
    club_id UUID REFERENCES as_club(id),
    name TEXT NOT NULL
);

CREATE TABLE as_athlete (
    id UUID PRIMARY KEY,
    club_id UUID REFERENCES as_club(id),
    name TEXT NOT NULL
);

-- T010 Competition Result with RLS
CREATE TABLE competition_result (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    athlete_id UUID REFERENCES as_athlete(id),
    score DECIMAL(5,2) NOT NULL,
    date DATE NOT NULL
);

ALTER TABLE competition_result ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can only view their club's competition results"
ON competition_result
FOR SELECT
USING (
    athlete_id IN (
        SELECT id FROM as_athlete WHERE club_id = (SELECT club_id FROM as_coach WHERE id = auth.uid())
    )
);

-- T011 Materialized Views
CREATE MATERIALIZED VIEW as_daily_aggregations AS
SELECT 
    athlete_id, 
    date, 
    AVG(score) as avg_score 
FROM competition_result 
GROUP BY athlete_id, date;
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
