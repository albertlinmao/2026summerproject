---
description: "Task list for Artistic Swimming Analytics Dashboard implementation"
---

# Tasks: Artistic Swimming Analytics Dashboard

**Input**: Design documents from `/specs/001-analytics-dashboard/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: OPTIONAL - only include if explicitly requested in the feature specification.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Web app**: `backend/src/`, `frontend/src/`
- Paths follow plan.md structure

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create project directory structure per implementation plan (backend/src/{models,api,services,core}, frontend/src/{app,styles})
- [x] T002 Initialize FastAPI backend with Python 3.11+, dependencies: fastapi, uvicorn, supabase-py, redis, pydantic, pydantic-settings
- [x] T003 Initialize Angular 22 frontend with Angular Material, Apache ECharts, NgRx Signals
- [x] T004 [P] Configure linting: ruff (backend), eslint/prettier (frontend)
- [x] T005 [P] Configure formatting: black (backend), prettier (frontend)
- [x] T006 [P] Setup pytest with pytest-asyncio, pytest-cov for backend
- [x] T007 [P] Setup Jest with @angular-builders/jest for frontend
- [x] T008 [P] Configure Supabase CLI for local development and migrations
- [x] T009 [P] Setup GitHub Actions CI workflow (lint, typecheck, test)
- [x] T010 [P] Create .env.example with all required environment variables

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T011 Setup database schema and Supabase migrations framework (baseline migration)
- [x] T012 [P] Apply existing Supabase tables migration (as_event, as_meet, as_figure, as_meet_judge_panel, as_meet_figure_result, as_meet_routine_result) from sql/create_figures_table.sql
- [x] T013 [P] Create migration for dashboard-specific tables: video_uploads, video_markers, routine_timers, as_competition_results_browser_widgets, as_daily_aggregations (materialized view), as_predictive_insights, as_coaching_recommendations
- [x] T014 [P] Configure Row Level Security (RLS) policies for club isolation on all tables
- [x] T015 [P] Configure RLS for video_uploads with family-access predicate (athlete_id link, coach-of, parent-of via Multi-Tenant User Service claims)
- [x] T016 Implement FastAPI app structure with lifespan, middleware, exception handlers
- [x] T017 [P] Implement JWT authentication middleware (BearerAuth from Multi-Tenant User Service API)
- [x] T018 [P] Implement role/claim extraction and club_id resolution from JWT
- [x] T019 [P] Setup Redis client and caching utilities
- [x] T020 Implement error handling and structured logging infrastructure
- [x] T021 [P] Configure environment configuration management (pydantic-settings)
- [x] T022 [P] Setup OpenAPI/Swagger UI at /docs
- [x] T023 [P] Create base Pydantic models for API responses (ListResponse, ErrorResponse, etc.)
- [x] T024 [P] Create Angular app structure with CoreModule, SharedModule, routing
- [x] T025 [P] Implement ThemeService with M3 color-scheme tokens (light/dark, persisted toggle, inline script for FOUC prevention)
- [x] T026 [P] Create design system tokens: colors (navy/teal primary, coral/gold accents), typography (Inter/Roboto, display-large for scores/timers, tabular-nums), spacing
- [x] T027 [P] Configure axe-core/Lighthouse CI for accessibility testing (WCAG 2.1 AA)
- [x] T028 [P] Implement NgRx Signals store structure for dashboard state (widgets, theme, user preferences)
- [x] T029 [P] Create shared UI components: Card, Button, Icon, Typography (deck-readable), LoadingSpinner, ErrorDisplay
- [x] T030 [P] Implement API client service with interceptors (auth, error handling, retry)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Coach Team Analysis & Prediction (Priority: P1) 🎯 MVP

**Goal**: Deliver coach dashboard with team overview, figure weakness heatmap, and qualification predictions

**Independent Test**: Log in as a coach, navigate to dashboard, view team heat map of figure weaknesses and qualification predictions for their team

### Implementation for User Story 1

**Backend Models & Services**
- [x] T031 [P] [US1] Create AthleteReference model in backend/src/models/athlete_ref.py (UUID, club_id, name)
- [x] T032 [P] [US1] Create CoachReference model in backend/src/models/coach_ref.py (UUID, club_id, name)
- [x] T033 [P] [US1] Create ClubReference model in backend/src/models/club_ref.py (UUID, name)
- [x] T034 [P] [US1] Create CompetitionResult model in backend/src/models/as_competition_result.py (aggregation from as_meet_figure_result + as_meet_routine_result)
- [x] T035 [P] [US1] Create PredictiveInsight model in backend/src/models/predictive_insight.py (athlete_id, next_score_prediction, plateau_risk, confidence_interval)
- [x] T036 [P] [US1] Create CoachingRecommendation model in backend/src/models/coaching_recommendation.py (athlete_id, recommendation_text, generated_at, weakest_figure)
- [x] T037 [US1] Implement AnalyticsService in backend/src/services/analytics/analytics_service.py (score distributions, ranking histories, figure radar chart data)
- [x] T038 [US1] Implement MaterializedViewService in backend/src/services/analytics/materialized_view_service.py (on-demand refresh, caching for daily aggregations)
- [x] T039 [US1] Implement PredictionService in backend/src/services/predictions/prediction_service.py (Phase 1: rolling averages, percentiles, std dev; Phase 2: linear regression, XGBoost)
- [x] T040 [US1] Implement AI Coach Service in backend/src/services/ai/ai_coach_service.py (OpenAI integration, baseline average fallback for new swimmers, error handling for AI unavailability)

**Backend API Endpoints**
- [x] T041 [US1] Implement GET /analytics/dashboard in backend/src/api/dashboard.py (role-based widget data aggregation)
- [x] T042 [US1] Implement GET /analytics/athletes/{athlete_id}/prediction in backend/src/api/predictions.py (predictive insight endpoint)
- [x] T043 [US1] Implement GET /analytics/athletes/{athlete_id}/recommendation in backend/src/api/recommendations.py (AI coach endpoint)
- [x] T044 [US1] Implement GET /analytics/team/heatmap in backend/src/api/team.py (figure weakness heatmap for coach's club)
- [x] T045 [US1] Add validation, error handling, and logging for all US1 endpoints

**Frontend Dashboard & Widgets**
- [x] T046 [P] [US1] Create DashboardLayoutComponent in frontend/src/app/dashboards/dashboard-layout.component.ts (card-based grid, responsive, sticky navigation per DR-003/DR-004)
- [x] T047 [P] [US1] Create TeamOverviewWidgetComponent in frontend/src/app/shared/widgets/team-overview/ (team athletes list, most improved, at-risk)
- [x] T048 [P] [US1] Create FigureHeatmapWidgetComponent in frontend/src/app/shared/widgets/figure-heatmap/ (Apache ECharts radar/heatmap for figure weaknesses)
- [x] T049 [P] [US1] Create PredictionWidgetComponent in frontend/src/app/shared/widgets/prediction/ (next score forecast, plateau risk, qualification probability)
- [x] T050 [P] [US1] Create AIRecommendationWidgetComponent in frontend/src/app/shared/widgets/ai-recommendation/ (natural language practice focus, error state "AI temporarily unavailable")
- [x] T051 [US1] Create CoachDashboardComponent in frontend/src/app/dashboards/coach-dashboard.component.ts (assembles widgets, role-based)
- [x] T052 [US1] Implement dashboard routing and lazy-loading for coach role
- [x] T053 [US1] Add extra-large typography (display-large, tabular-nums) to all score/timer displays per DR-005
- [x] T054 [US1] Apply WCAG 2.1 AA contrast validation to all US1 components per DR-007

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - Swimmer Personal Progress & AI Coach (Priority: P2)

**Goal**: Deliver swimmer dashboard with personal progress charts, personal bests, and AI recommendations

**Independent Test**: Log in as a swimmer, view dashboard with figure/routine trends over time, current personal bests, and AI-generated focus recommendation

### Implementation for User Story 2

**Backend Services** (reuses models from US1)
- [ ] T055 [US2] Extend AnalyticsService with athlete-specific trend queries (figure/routine trends over time, personal bests)
- [ ] T056 [US2] Implement GET /analytics/athletes/{athlete_id}/progress in backend/src/api/athlete_progress.py (personal trends, bests)

**Frontend Dashboard & Widgets**
- [ ] T057 [P] [US2] Create PersonalProgressWidgetComponent in frontend/src/app/shared/widgets/personal-progress/ (ECharts line charts for figure/routine trends)
- [ ] T058 [P] [US2] Create PersonalBestsWidgetComponent in frontend/src/app/shared/widgets/personal-bests/ (current PBs for figures and routines)
- [ ] T059 [P] [US2] Reuse AIRecommendationWidgetComponent from US1 (shared component)
- [ ] T060 [US2] Create SwimmerDashboardComponent in frontend/src/app/dashboards/swimmer-dashboard.component.ts (assembles widgets for athlete role)
- [ ] T061 [US2] Implement dashboard routing and lazy-loading for athlete role
- [ ] T062 [US2] Apply extra-large typography and WCAG 2.1 AA contrast per DR-005/DR-007

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - Club Administration Overview (Priority: P3)

**Goal**: Deliver club admin dashboard with aggregated statistics, rankings, coach effectiveness, athlete retention

**Independent Test**: Log in as a club administrator, view aggregated medal counts, retention rates, and overall club rankings

### Implementation for User Story 3

**Backend Models & Services**
- [ ] T063 [P] [US3] Create ClubAggregation model in backend/src/models/club_aggregation.py (medal counts, avg scores, retention rates, rankings)
- [ ] T064 [US3] Implement ClubAnalyticsService in backend/src/services/analytics/club_analytics_service.py (club-wide aggregations, coach effectiveness metrics)
- [ ] T065 [US3] Implement GET /analytics/club/overview in backend/src/api/club.py (club admin endpoint)

**Frontend Dashboard & Widgets**
- [ ] T066 [P] [US3] Create ClubOverviewWidgetComponent in frontend/src/app/shared/widgets/club-overview/ (medal counts, retention rates, rankings)
- [ ] T067 [P] [US3] Create CoachEffectivenessWidgetComponent in frontend/src/app/shared/widgets/coach-effectiveness/ (coach performance metrics)
- [ ] T068 [P] [US3] Create AthleteRetentionWidgetComponent in frontend/src/app/shared/widgets/athlete-retention/ (retention trends)
- [ ] T069 [US3] Create ClubAdminDashboardComponent in frontend/src/app/dashboards/club-admin-dashboard.component.ts (assembles widgets for club admin role)
- [ ] T070 [US3] Implement dashboard routing and lazy-loading for club admin role
- [ ] T071 [US3] Apply extra-large typography and WCAG 2.1 AA contrast per DR-005/DR-007

**Checkpoint**: At this point, User Stories 1, 2, AND 3 should all work independently

---

## Phase 6: User Story 4 - Competition Results Browser (Priority: P2)

**Goal**: Deliver Competition Results Browser widget with treeview mirroring swim-meets folder, figure/routine results, PDF links

**Independent Test**: Log in as any role, add Competition Results Browser widget, navigate treeview to specific meet, open database results and linked source PDF

### Implementation for User Story 4

**Backend Services**
- [ ] T072 [P] [US4] Create ResultsBrowserService in backend/src/services/media/results_browser.py (filesystem scanning, tree building, PDF path resolution)
- [ ] T073 [US4] Implement GET /results/tree in backend/src/api/results_browser.py (tree structure with nodes for year/meet/figure-routine/pdf)
- [ ] T074 [US4] Implement GET /results/figure/{meet_id} in backend/src/api/results_browser.py (paginated as_meet_figure_result data)
- [ ] T075 [US4] Implement GET /results/routine/{meet_id} in backend/src/api/results_browser.py (paginated as_meet_routine_result data)
- [ ] T076 [US4] Implement GET /results/pdf/{year}/{meet}/{type}/{filename} in backend/src/api/results_browser.py (FileResponse with path traversal protection)
- [ ] T077 [US4] Add validation, error handling, and logging for all US4 endpoints
- [ ] T078 [US4] Add caching for tree structure (refresh on interval or file watcher)

**Frontend Widget**
- [ ] T079 [P] [US4] Create ResultsBrowserWidgetComponent in frontend/src/app/shared/widgets/results-browser/ (CDK virtual scroll tree, lazy-loading children)
- [ ] T080 [P] [US4] Create ResultsTreeComponent in frontend/src/app/shared/widgets/results-browser/results-tree.component.ts (tree nodes with expansion state)
- [ ] T081 [P] [US4] Create FigureResultsTableComponent in frontend/src/app/shared/widgets/results-browser/figure-results-table.component.ts (paginated table for figure results)
- [ ] T082 [P] [US4] Create RoutineResultsTableComponent in frontend/src/app/shared/widgets/results-browser/routine-results-table.component.ts (paginated table for routine results with element/artistic/sync breakdowns)
- [ ] T083 [P] [US4] Create FigureRoutineTabComponent in frontend/src/app/shared/widgets/results-browser/figure-routine-tab.component.ts (toggle between figure/routine views)
- [ ] T084 [US4] Implement PDF link handling and FileResponse streaming
- [ ] T085 [US4] Persist tree_state (expansion, active_tab, selected_node) in CompetitionResultsBrowserWidget model
- [ ] T086 [US4] Register Results Browser as addable/removable/resizable dashboard widget
- [ ] T087 [US4] Apply extra-large typography and WCAG 2.1 AA contrast per DR-005/DR-007

**Checkpoint**: At this point, User Story 4 should be fully functional and testable independently

---

## Phase 7: Video Analysis Widget (FR-007) (Priority: P2)

**Goal**: Deliver video upload, frame-by-frame playback, timestamp markers with audio cues

**Independent Test**: Upload MP4 via widget, playback video, add markers at scoring moments, click-to-seek, audio_cue markers emit tone, family access enforced

### Implementation for FR-007

**Backend Services** (models from Phase 2 migration)
- [ ] T088 [P] [FR007] Create VideoUploadService in backend/src/services/media/video_upload.py (presigned URL flow: sign → client PUT → finalize with HEAD verification)
- [ ] T089 [P] [FR007] Create VideoMarkerService in backend/src/services/media/video_marker.py (CRUD for markers, cascade delete with video)
- [ ] T090 [US4] Implement POST /uploads/sign in backend/src/api/video_upload.py (validates size/type, athlete_id for family access)
- [ ] T091 [US4] Implement POST /uploads/finalize in backend/src/api/video_upload.py (verifies upload, creates video_uploads row)
- [ ] T092 [US4] Implement GET/POST /videos/{video_id}/markers in backend/src/api/video_markers.py
- [ ] T093 [US4] Implement scheduled cleanup job for 90-day video retention (DELETE where created_at < now() - 90 days)

**Frontend Widget**
- [ ] T094 [P] [FR007] Create VideoAnalysisWidgetComponent in frontend/src/app/shared/widgets/video-analysis/ (native <video> + custom overlay)
- [ ] T095 [P] [FR007] Create VideoUploadComponent in frontend/src/app/shared/widgets/video-analysis/video-upload.component.ts (presigned URL flow, progress)
- [ ] T096 [P] [FR007] Create VideoPlayerComponent in frontend/src/app/shared/widgets/video-analysis/video-player.component.ts (sticky controls, fullscreen wrapper, click-to-seek markers)
- [ ] T097 [P] [FR007] Create TimestampMarkerOverlayComponent in frontend/src/app/shared/widgets/video-analysis/marker-overlay.component.ts (marker divs on progress bar, audio_cue tone via Web Audio API)
- [ ] T098 [FR007] Implement family-access checks in frontend (hide widget if no access)
- [ ] T099 [FR007] Apply extra-large typography and WCAG 2.1 AA contrast per DR-005/DR-007

---

## Phase 8: Routine Timer Widget (FR-008) (Priority: P3)

**Goal**: Deliver routine duration countdown timer with start/pause, save/restore config, visual+audio alert at zero

**Independent Test**: Open timer widget, start 2:00 countdown, verify extra-large digits, start/pause works, save config, reload restores, zero triggers flash+beep

### Implementation for FR-008

**Backend Services** (model from Phase 2 migration)
- [ ] T100 [P] [FR008] Create RoutineTimerService in backend/src/services/media/routine_timer.py (CRUD for timer configurations)
- [ ] T101 [US4] Implement GET/POST /routines/timers in backend/src/api/routine_timers.py

**Frontend Widget**
- [ ] T102 [P] [FR008] Create RoutineTimerWidgetComponent in frontend/src/app/shared/widgets/routine-timer/ (NgRx Signals for timer state)
- [ ] T103 [P] [FR008] Create TimerControlsComponent in frontend/src/app/shared/widgets/routine-timer/timer-controls.component.ts (start/pause, duration input, save)
- [ ] T104 [P] [FR008] Create TimerDisplayComponent in frontend/src/app/shared/widgets/routine-timer/timer-display.component.ts (extra-large digits, tabular-nums, visual flash at zero)
- [ ] T105 [FR008] Implement audible beep at zero via Web Audio API
- [ ] T106 [FR008] Persist timer config to backend, restore on reload
- [ ] T107 [FR008] Apply extra-large typography and WCAG 2.1 AA contrast per DR-005/DR-007

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T108 [P] Documentation updates: API docs, component docs, deployment guide in docs/
- [ ] T109 Code cleanup and refactoring (remove dead code, consolidate duplicates)
- [ ] T110 Performance optimization: query optimization, bundle size reduction, lazy-loading verification
- [ ] T111 [P] Additional unit tests in backend/tests/unit/ and frontend/src/tests/unit/
- [ ] T112 Security hardening: CSP headers, rate limiting, input validation audit
- [ ] T113 Run quickstart.md validation scenarios (all 8 scenarios)
- [ ] T114 [P] Accessibility audit: full axe-core/Lighthouse pass in both themes
- [ ] T115 Configure production deployment: Cloudflare Pages (frontend), Cloud Container (backend), Supabase production

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-8)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Phase 9)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **US2 (P2)**: Can start after Foundational (Phase 2) - Reuses US1 models/services (AnalyticsService, AI Coach) but independently testable
- **US3 (P3)**: Can start after Foundational (Phase 2) - Uses AnalyticsService extensions but independently testable
- **US4 (P2)**: Can start after Foundational (Phase 2) - Independent (different API endpoints, widget)
- **FR-007 (P2)**: Can start after Foundational (Phase 2) - Independent widget
- **FR-008 (P3)**: Can start after Foundational (Phase 2) - Independent widget

### Within Each User Story

- Tests (if included) MUST be written and FAIL before implementation
- Models before services
- Services before endpoints
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational phase completes, all user stories can start in parallel (if team capacity allows)
- All tests for a user story marked [P] can run in parallel
- Models within a story marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: User Story 1

```bash
# Launch all models for User Story 1 together:
Task: "Create AthleteReference model in backend/src/models/athlete_ref.py"
Task: "Create CoachReference model in backend/src/models/coach_ref.py"
Task: "Create ClubReference model in backend/src/models/club_ref.py"
Task: "Create CompetitionResult model in backend/src/models/as_competition_result.py"
Task: "Create PredictiveInsight model in backend/src/models/predictive_insight.py"
Task: "Create CoachingRecommendation model in backend/src/models/coaching_recommendation.py"

# Launch all widgets for User Story 1 together:
Task: "Create TeamOverviewWidgetComponent in frontend/src/app/shared/widgets/team-overview/"
Task: "Create FigureHeatmapWidgetComponent in frontend/src/app/shared/widgets/figure-heatmap/"
Task: "Create PredictionWidgetComponent in frontend/src/app/shared/widgets/prediction/"
Task: "Create AIRecommendationWidgetComponent in frontend/src/app/shared/widgets/ai-recommendation/"
```

---

## Parallel Example: User Story 4

```bash
# Launch all backend endpoints for User Story 4 together:
Task: "Implement GET /results/tree in backend/src/api/results_browser.py"
Task: "Implement GET /results/figure/{meet_id} in backend/src/api/results_browser.py"
Task: "Implement GET /results/routine/{meet_id} in backend/src/api/results_browser.py"
Task: "Implement GET /results/pdf/{year}/{meet}/{type}/{filename} in backend/src/api/results_browser.py"

# Launch all frontend components for User Story 4 together:
Task: "Create ResultsTreeComponent in frontend/src/app/shared/widgets/results-browser/results-tree.component.ts"
Task: "Create FigureResultsTableComponent in frontend/src/app/shared/widgets/results-browser/figure-results-table.component.ts"
Task: "Create RoutineResultsTableComponent in frontend/src/app/shared/widgets/results-browser/routine-results-table.component.ts"
Task: "Create FigureRoutineTabComponent in frontend/src/app/shared/widgets/results-browser/figure-routine-tab.component.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test User Story 1 independently (quickstart Scenario 1)
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo
4. Add User Story 4 → Test independently → Deploy/Demo
5. Add User Story 3 → Test independently → Deploy/Demo
6. Add FR-007 (Video Analysis) → Test independently → Deploy/Demo
7. Add FR-008 (Routine Timer) → Test independently → Deploy/Demo
8. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (P1)
   - Developer B: User Story 2 (P2) + FR-007
   - Developer C: User Story 4 (P2) + FR-008
   - Developer D: User Story 3 (P3)
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence