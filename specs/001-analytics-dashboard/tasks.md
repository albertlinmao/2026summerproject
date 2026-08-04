---
description: "Task list for Artistic Swimming Analytics Dashboard implementation"
---

# Tasks: Artistic Swimming Analytics Dashboard

**Input**: Design documents from `/specs/001-analytics-dashboard/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, basic structure, and cross-cutting foundation

- [ ] T001 Create Angular 22 frontend workspace in `frontend/`
- [ ] T002 Create FastAPI backend project with Poetry in `backend/`
- [ ] T003 [P] Configure Jest testing framework in `frontend/`
- [ ] T004 [P] Configure pytest and Ruff linting in `backend/`
- [ ] T005 [P] Install and configure Apache ECharts and NgRx Signals in `frontend/package.json`
- [ ] T006 Initialize local Supabase instance and Redis cache configuration

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T007 **Author OpenAPI Contract**: Define `openapi.yaml` in `contracts/openapi.yaml` mapping all endpoints (API First principle)
- [ ] T008 [P] Configure Observability - Structured Logging and Distributed Tracing (OpenTelemetry) in `backend/src/core/observability.py`
- [ ] T009 Create database migration for core tables (`Athlete`, `Coach`, `Club` references) in `backend/supabase/migrations/`
- [ ] T010 Create database migration for `Competition Result` table with RLS policies in `backend/supabase/migrations/`
- [ ] T011 Create Supabase Materialized Views for daily aggregations in `backend/supabase/migrations/`
- [ ] T012 Implement JWT token verification middleware linking to `001-multi-tenant-user-api` in `backend/src/api/auth.py`
- [ ] T013 [P] Setup base layout, unified role-based routing module in `frontend/src/app/app.routes.ts`
- [ ] T014 [P] Create HTTP client service for backend communication in `frontend/src/app/shared/api.service.ts`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel.

---

## Phase 3: User Story 1 - Coach Team Analysis & Prediction (Priority: P1) 🎯 MVP

**Goal**: Coaches can view entire team performance, identify at-risk athletes, and view predictions.

**Independent Test**: Login as Coach, view heatmap of figure weaknesses and qualification predictions.

### Implementation for User Story 1

- [ ] T015 [P] [US1] Create FastAPI data models for Aggregations in `backend/src/models/aggregations.py`
- [ ] T016 [US1] Implement Analytics service logic for coaches in `backend/src/services/analytics/coach_service.py`
- [ ] T017 [US1] Implement `/analytics/dashboard` endpoint for Coach role in `backend/src/api/dashboard.py` (matching OpenAPI contract)
- [ ] T018 [P] [US1] Create unified Dashboard Shell component to handle dynamic widget loading based on role in `frontend/src/app/dashboards/shell/shell.component.ts`
- [ ] T019 [P] [US1] Create Coach-specific widgets (Team Overview) in `frontend/src/app/shared/widgets/coach-overview.component.ts`
- [ ] T020 [P] [US1] Create ECharts Heatmap widget component in `frontend/src/app/shared/widgets/heatmap.component.ts`
- [ ] T021 [US1] Integrate Dashboard Shell with backend API and NgRx Signals store for Coach view
- [ ] T022 [US1] Implement predictive baseline average fallback logic (UI/API) for new athletes

**Checkpoint**: Unified Dashboard Shell is operational; Coach widgets render correctly based on role claims.

---

## Phase 4: User Story 2 - Swimmer Personal Progress & AI Coach (Priority: P2)

**Goal**: Swimmers track personal bests and receive AI-generated practice recommendations.

**Independent Test**: Login as Athlete, view personal progress charts and the AI recommendation widget in the unified shell.

### Implementation for User Story 2

- [ ] T023 [P] [US2] Create `PredictiveInsight` and `CoachingRecommendation` models in `backend/src/models/insights.py`
- [ ] T024 [US2] Implement OpenAI integration in `backend/src/services/ai/openai_service.py`
- [ ] T025 [US2] Implement ML predictions (Random Forest/XGBoost logic) in `backend/src/services/predictions/ml_service.py`
- [ ] T026 [US2] Implement `/athletes/{athlete_id}/insights` endpoint in `backend/src/api/insights.py`
- [ ] T027 [P] [US2] Create Swimmer-specific overview widget in `frontend/src/app/shared/widgets/swimmer-overview.component.ts`
- [ ] T028 [P] [US2] Create ECharts Radar Chart component in `frontend/src/app/shared/widgets/radar-chart.component.ts`
- [ ] T029 [P] [US2] Create AI Coach insight widget in `frontend/src/app/shared/widgets/ai-coach.component.ts`
- [ ] T030 [US2] Integrate Swimmer widgets into the unified Dashboard Shell
- [ ] T031 [US2] Implement graceful error handling (UI fallback) for AI Service unavailability

**Checkpoint**: Dashboard Shell correctly resolves both Athlete and Coach roles, showing respective widgets.

---

## Phase 5: User Story 3 - Club Administration Overview (Priority: P3)

**Goal**: Club administrators monitor club rankings, average scores, and coach effectiveness.

**Independent Test**: Login as Club Admin, view aggregated medal counts and club rankings in the unified shell.

### Implementation for User Story 3

- [ ] T032 [P] [US3] Extend Analytics service logic for Admin aggregations in `backend/src/services/analytics/admin_service.py`
- [ ] T033 [US3] Update `/analytics/dashboard` endpoint to support Club Admin role in `backend/src/api/dashboard.py`
- [ ] T034 [P] [US3] Create summary statistics widgets (medal counts, retention rates) in `frontend/src/app/shared/widgets/summary-stats.component.ts`
- [ ] T035 [US3] Integrate Admin widgets into the unified Dashboard Shell

**Checkpoint**: Dashboard Shell successfully dynamically loads Admin widgets when Club Admin role is present.

---

## Phase 6: Extended Role Coverage (FR-001)

**Goal**: Full coverage for Team Captain, Lead Coach, Parent, and Club Owner roles to satisfy FR-001.

**Independent Test**: Log in with each extended role and verify appropriate widget access via the unified shell.

### Implementation for Extended Roles

- [ ] T036 [P] [US4] Implement data permission filters for Parent role (view only linked athlete) in `backend/src/services/analytics/parent_service.py`
- [ ] T037 [P] [US4] Implement data permission filters for Team Captain (limited team views) in `backend/src/services/analytics/captain_service.py`
- [ ] T038 [P] [US4] Implement Lead Coach (multi-team overview) aggregation logic in `backend/src/services/analytics/lead_coach_service.py`
- [ ] T039 [US4] Update `/analytics/dashboard` endpoint to authorize all 7 roles in `backend/src/api/dashboard.py`
- [ ] T040 [US4] Update Dashboard Shell routing guards and widget rendering logic to support 7 distinct roles in `frontend/src/app/dashboards/shell/shell.component.ts`

**Checkpoint**: System supports all 7 roles specified in FR-001.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories, encompassing performance, accessibility, and E2E testing.

- [ ] T041 [P] Implement WCAG AA Accessibility Standards (ARIA labels, keyboard navigation) across all Dashboard components
- [ ] T042 [P] Verify performance SLA (< 2 seconds dashboard render) and optimize Materialized Views if needed
- [ ] T043 Configure application Metrics (latency, error rates) in `backend/src/core/metrics.py`
- [ ] T044 [P] Complete end-to-end testing of UX paths (e.g., practice recommendation in 3 clicks) and `quickstart.md` validation scenarios
- [ ] T045 Standardize Angular Material theme and responsive CSS across all dashboard widgets
- [ ] T046 Finalize API documentation (Swagger UI mapping of OpenAPI contract)
- [ ] T047 [P] Implement concurrent load testing script (e.g., using k6 or Locust) to verify SC-004 scaling (1,000 concurrent users) in `backend/tests/load/`

---

## Dependencies & Execution Order

### Phase Dependencies
- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### Parallel Opportunities
- Within **Phase 1**, frontend (Jest, ECharts) and backend (pytest) configurations can be run in parallel.
- Within **Phase 2**, the API base (`auth.py`), OpenAPI specification (`openapi.yaml`), and Frontend base (`app.routes.ts`) can be built in parallel.
- Within **Phase 3**, the FastAPI models/endpoints and Angular components (`heatmap`, `dashboard shell`) can be developed simultaneously.

### Implementation Strategy
1. **MVP First**: Complete Phase 1 & 2, then complete Phase 3 (Coach widgets + Unified Shell). Deploy and validate.
2. **Incremental Delivery**: Roll out Phase 4 (Swimmers + AI) and Phase 5 (Club Admin) sequentially or in parallel depending on capacity.
3. **Role Expansion**: Finally, expand the Unified Shell and backend permissions to handle the remaining 4 roles.
