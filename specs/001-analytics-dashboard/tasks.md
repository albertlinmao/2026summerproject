---
description: "Task list for Artistic Swimming Analytics Dashboard implementation"
---

# Tasks: Artistic Swimming Analytics Dashboard

**Input**: Design documents from `/specs/001-analytics-dashboard/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, basic structure, and cross-cutting foundation

- [x] T001 Create Angular 22 frontend workspace in `frontend/`
- [x] T002 Create FastAPI backend project with standard pip/requirements.txt in `backend/`
- [x] T003 [P] Configure Jest testing framework in `frontend/`
- [x] T004 [P] Configure pytest and Ruff linting in `backend/`
- [x] T005 [P] Install and configure Apache ECharts and NgRx Signals in `frontend/package.json`
- [x] T006 Initialize local Supabase instance and Redis cache configuration

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T007 **Author OpenAPI Contract**: Define `openapi.yaml` in `contracts/openapi.yaml` mapping all endpoints (API First principle)
- [x] T008 [P] Configure Observability - Structured Logging and Distributed Tracing (OpenTelemetry) in `backend/src/core/observability.py`
- [x] T009 Create database migration for core tables (`Athlete`, `Coach`, `Club` references) in `backend/supabase/migrations/`
- [x] T010 Create database migration for `Competition Result` table with RLS policies in `backend/supabase/migrations/`
- [x] T011 Create Supabase Materialized Views for daily aggregations in `backend/supabase/migrations/`
- [x] T012 Implement JWT token verification middleware linking to `001-multi-tenant-user-api` in `backend/src/api/auth.py`
- [x] T013 [P] Setup base layout, unified role-based routing module in `frontend/src/app/app.routes.ts`
- [x] T014 [P] Create HTTP client service for backend communication in `frontend/src/app/shared/api.service.ts`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel.

---

## Phase 3: User Story 1 - Coach Team Analysis & Prediction (Priority: P1) 🎯 MVP

**Goal**: Coaches can view entire team performance, identify at-risk athletes, and view predictions.

**Independent Test**: Login as Coach, view heatmap of figure weaknesses and qualification predictions.

### Implementation for User Story 1

- [x] T015 [P] [US1] Create FastAPI data models for Aggregations in `backend/src/models/aggregations.py`
- [x] T016 [US1] Implement Analytics service logic for coaches in `backend/src/services/analytics/coach_service.py`
- [x] T017 [US1] Implement `/analytics/dashboard` endpoint for Coach role in `backend/src/api/dashboard.py` (matching OpenAPI contract)
- [x] T018 [P] [US1] Create unified Dashboard Shell component to handle dynamic widget loading based on role in `frontend/src/app/dashboards/shell/shell.component.ts`
- [x] T019 [P] [US1] Create Coach-specific widgets (Team Overview) in `frontend/src/app/shared/widgets/coach-overview.component.ts`
- [x] T020 [P] [US1] Create ECharts Heatmap widget component in `frontend/src/app/shared/widgets/heatmap.component.ts`
- [x] T021 [US1] Integrate Dashboard Shell with backend API and NgRx Signals store for Coach view
- [x] T022 [US1] Implement predictive baseline average fallback logic (UI/API) for new athletes

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

## Phase 7: Video Analysis & Routine Timers (FR-007, FR-008)

**Goal**: Coaches can upload routine videos with timestamp markers; athletes/coaches can use deck-side routine timers.

**Independent Test**: Login as Coach, upload a video, add markers, play back with sticky controls. Login as Coach/Athlete, start/pause a routine timer with extra-large digits.

### Implementation for Video Analysis & Routine Timers

- [ ] T041 [P] Create database migration for `Video Upload`, `Video Marker`, and `Routine Timer` tables with RLS policies in `backend/supabase/migrations/`
- [ ] T042 [P] Create FastAPI data models for `VideoUpload`, `VideoMarker`, `RoutineTimer` in `backend/src/models/media.py`
- [ ] T043 Implement Supabase Storage presigned-URL upload service (sign → PUT → finalize flow with HEAD verification) in `backend/src/services/media/video_upload_service.py`
- [ ] T044 Implement `/uploads/sign` endpoint in `backend/src/api/uploads.py` (matching OpenAPI contract)
- [ ] T045 Implement `/uploads/finalize` endpoint in `backend/src/api/uploads.py` (matching OpenAPI contract)
- [ ] T046 Implement `/videos/{video_id}/markers` GET and POST endpoints in `backend/src/api/markers.py` (matching OpenAPI contract)
- [ ] T047 Implement `/routines/timers` GET and POST endpoints in `backend/src/api/timers.py` (matching OpenAPI contract)
- [ ] T048 [P] Create video analysis Angular component with native `<video>` + marker overlay in `frontend/src/app/shared/widgets/video-analysis/video-analysis.component.ts`
- [ ] T049 [P] Create video marker overlay component (absolutely-positioned divs over progress bar, click-to-seek) in `frontend/src/app/shared/widgets/video-analysis/marker-overlay.component.ts`
- [ ] T050 [P] Create video upload component (sign → client PUT → finalize flow) in `frontend/src/app/shared/widgets/video-analysis/video-upload.component.ts`
- [ ] T051 [P] Create routine timer Angular component with start/pause controls using NgRx Signals in `frontend/src/app/shared/widgets/routine-timer/routine-timer.component.ts`
- [ ] T052 [US1] Integrate video analysis and routine timer widgets into the unified Dashboard Shell for Coach and Athlete roles

**Checkpoint**: Video analysis widget plays back with visible markers; routine timer counts down with extra-large digits; sticky controls remain visible in fullscreen.

---

## Phase 8: Design System (DR-001 to DR-007)

**Goal**: Dual light/dark themes with pool-deck-appropriate color palette, typography, and WCAG AA contrast.

**Independent Test**: Toggle light/dark mode; verify no FOUC on reload; run axe-core/Lighthouse contrast checks in both themes; verify scores/timers are extra-large and readable at distance.

### Implementation for Design System

- [ ] T053 [P] Generate custom Angular Material M3 palettes (navy → primary, teal → tertiary) via `ng generate @angular/material:theme-color` in `frontend/src/styles/themes/`
- [ ] T054 [P] Configure M3 `mat.theme()` Sass API with coral/gold accent overrides and light/dark mode token output in `frontend/src/styles/themes/_theme.scss`
- [ ] T055 [P] Implement inline FOUC-prevention script in `frontend/src/index.html` (reads localStorage + matches OS preference, sets `data-theme` before first paint)
- [ ] T056 [P] Create Angular `ThemeService` (signals) for three-state toggle (`system|light|dark`) in `frontend/src/app/shared/theme/theme.service.ts`
- [ ] T057 [P] Create theme toggle UI component in `frontend/src/app/shared/theme/theme-toggle.component.ts`
- [ ] T058 [P] Configure Inter/Roboto fonts and deck-readable typography scale (display tokens, `tabular-nums`, `clamp()`) in `frontend/src/styles/themes/_typography.scss`
- [ ] T059 [P] Add WCAG 2.1 AA contrast verification to CI (axe-core + Lighthouse, both themes) in `frontend/tests/accessibility/`
- [ ] T060 Standardize Angular Material theme and card-based grid layout with generous whitespace (DR-003) across all dashboard widgets in `frontend/src/styles/`
- [ ] T061 Add simple filled vector icons for video upload, audio cue, and timing marks (Material Icons filled) in `frontend/src/app/shared/widgets/`

**Checkpoint**: Dashboard supports user-selectable light/dark themes with no FOUC; navy/ocean teal/coral/gold palette renders correctly; scores/timers are extra-large; WCAG AA contrast passes in both themes.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories, encompassing performance, accessibility, and E2E testing.

- [ ] T062 [P] Implement WCAG AA Accessibility Standards (ARIA labels, keyboard navigation) across all Dashboard components
- [ ] T063 [P] Verify performance SLA (< 2 seconds dashboard render) and optimize Materialized Views if needed
- [ ] T064 Configure application Metrics (latency, error rates) in `backend/src/core/metrics.py`
- [ ] T065 [P] Complete end-to-end testing of UX paths (e.g., practice recommendation in 3 clicks) and `quickstart.md` validation scenarios (Scenarios 1–7)
- [ ] T066 Finalize API documentation (Swagger UI mapping of OpenAPI contract)
- [ ] T067 [P] Implement concurrent load testing script (e.g., using k6 or Locust) to verify SC-004 scaling (1,000 concurrent users) in `backend/tests/load/`

---

## Dependencies & Execution Order

### Phase Dependencies
- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3–6)**: All depend on Foundational phase completion; can proceed in parallel
- **Video Analysis & Timers (Phase 7)**: Depends on Foundational phase completion; can run in parallel with user stories
- **Design System (Phase 8)**: Depends on Foundational phase completion; can run in parallel with user stories and Phase 7
- **Polish (Phase 9)**: Depends on all desired user stories being complete

### Parallel Opportunities
- Within **Phase 1**, frontend (Jest, ECharts) and backend (pytest) configurations can be run in parallel.
- Within **Phase 2**, the API base (`auth.py`), OpenAPI specification (`openapi.yaml`), and Frontend base (`app.routes.ts`) can be built in parallel.
- Within **Phase 3**, the FastAPI models/endpoints and Angular components (`heatmap`, `dashboard shell`) can be developed simultaneously.
- **Phases 4–8** can all run in parallel after Phase 2 completes, as they work on distinct files.
- Within **Phase 7**, video backend (models, services, endpoints) and frontend components can run in parallel.
- Within **Phase 8**, M3 theme setup, FOUC script, ThemeService, and typography can all run in parallel.

### Implementation Strategy
1. **MVP First**: Complete Phase 1 & 2, then Phase 3 (Coach widgets + Unified Shell). Deploy and validate.
2. **Incremental Delivery**: Roll out Phases 4–8 in parallel depending on capacity.
3. **Role Expansion**: Phase 6 (Extended roles) and Phase 7 (Video/Timers) expand the shell and backend permissions.
4. **Design System**: Phase 8 can be layered onto existing widgets incrementally — themes, typography, and contrast checks are cross-cutting.
5. **Polish**: Phase 9 ties everything together with accessibility, performance, and E2E validation.
