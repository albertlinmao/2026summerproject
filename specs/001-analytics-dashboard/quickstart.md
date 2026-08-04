# Quickstart Validation Guide: Analytics Dashboard

## Prerequisites
- Node.js 20+ and Angular CLI (for Angular 22 SPA)
- Python 3.11+ and Poetry (for FastAPI)
- Docker Desktop (for local Supabase and Redis instances)
- Supabase CLI installed

## Environment Setup
1. **Database & Auth**:
   ```bash
   # Start local Supabase (starts Postgres, GoTrue Auth, PostgREST)
   supabase start
   
   # Apply migrations (Creates RLS policies and Materialized Views)
   supabase db reset
   ```

2. **Backend (FastAPI)**:
   ```bash
   cd backend
   poetry install
   poetry run uvicorn src.api.main:app --reload --port 8000
   ```

3. **Frontend (Angular)**:
   ```bash
   cd frontend
   npm install
   ng serve
   ```

## End-to-End Validation Scenarios

### Scenario 1: Coach Unified View
1. Login at `http://localhost:4200` using the test coach credentials (`coach@testclub.com`).
2. **Expected**: The dashboard loads in under 2 seconds. You should see a team heatmap widget and a list of "At Risk" athletes.

### Scenario 2: Predictive Baseline Fallback
1. Login as coach. Navigate to the profile of a newly added swimmer (e.g., `< 5` competition records).
2. **Expected**: The prediction widget displays "Baseline Average" rather than an individualized ML prediction.

### Scenario 3: AI Service Unavailability
1. Stop your internet connection or change the `OPENAI_API_KEY` in the backend `.env` to an invalid key.
2. Navigate to a swimmer's "AI Coach" tab.
3. **Expected**: The widget degrades gracefully, displaying a "AI temporarily unavailable" error message rather than crashing the page or falling back silently.