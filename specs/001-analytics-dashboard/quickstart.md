# Quickstart & Validation Guide: Analytics Dashboard

## Prerequisites
- A running instance of the `001-multi-tenant-user-api` (or a mock providing valid JWTs).
- Database migrations applied (Supabase CLI).
- Mock competition data seeded.
- FastAPI backend running on `localhost:8000`.
- Angular 22 frontend running on `localhost:4200`.

## Validation Scenarios

### Scenario 1: Coach Team Overview (P1)
1. **Setup**: Obtain a JWT for a user with the `Coach` role.
2. **Action**: Navigate to `http://localhost:4200/dashboard`.
3. **Expected Outcome**:
   - Dashboard renders within 2 seconds.
   - The Team Heatmap widget is visible, showing a list of athletes.
   - `figure_score` and `routine_score` are displayed for each athlete.
   - Clicking an athlete opens their predictive insight panel (verifying the `/analytics/athletes/{id}/prediction` contract).

### Scenario 2: Swimmer AI Recommendation (P2)
1. **Setup**: Obtain a JWT for a user with the `Athlete` role.
2. **Action**: Navigate to `http://localhost:4200/dashboard`.
3. **Expected Outcome**:
   - The AI Coaching Insights widget is visible.
   - A natural language recommendation is displayed (verifying `/analytics/athletes/{id}/recommendation`).
4. **Action (Failure test)**: Turn off the external OpenAI service connection or simulate a 503 response.
5. **Expected Outcome**: The widget displays the generic error "AI temporarily unavailable".

### Scenario 3: Identity API Unreachable
1. **Setup**: Shut down the mock `001-multi-tenant-user-api` so session validation fails.
2. **Action**: Attempt to load the dashboard.
3. **Expected Outcome**: The application displays a full-page critical error with a "Retry" button, preventing any dashboard widgets from loading.

### Scenario 4: Materialized View On-Demand Refresh
1. **Setup**: Insert a new `Competition Result` directly into the database for an existing athlete.
2. **Action**: Navigate to the dashboard as that athlete's coach.
3. **Expected Outcome**: The dashboard query triggers an on-demand refresh of the Materialized View (observable in database logs), and the new score is immediately reflected in the dashboard trends.

### Scenario 5: Video Upload & Timestamp Markers (FR-007)
1. **Setup**: Obtain a JWT for a user with the `Coach` role.
2. **Action**: Upload a short MP4 via the video analysis widget (triggers `/uploads/sign` with `athlete_id` → client PUT → `/uploads/finalize`).
3. **Expected Outcome**: Upload completes; video appears in the widget and plays back. Add a marker at a scoring moment (e.g., figure at 00:12).
4. **Expected Outcome**: Marker appears at the correct position on the progress bar; clicking it seeks the video to that time (verifying `GET/POST /videos/{video_id}/markers`). Sticky play/pause controls remain visible in fullscreen.
5. **Action (Failure test)**: Attempt to upload a file exceeding the size limit.
6. **Expected Outcome**: Upload rejected with a 413 response and no storage object committed.
7. **Action (Access test)**: Log in as a user unrelated to the filmed athlete (different club or no coach/parent link).
8. **Expected Outcome**: Access to the video and its markers is denied (403) — family access enforced (athlete, coaches, parents only).
9. **Action (Retention test)**: Backdate a `video_uploads` row's `created_at` beyond 90 days and run the cleanup job.
10. **Expected Outcome**: The video row, its markers, and the storage object are deleted.

### Scenario 6: Routine Timer (FR-008)
1. **Setup**: Obtain a JWT for a coach or athlete role.
2. **Action**: Open the routine timer widget and start a 2:00 countdown.
3. **Expected Outcome**: Timer counts down with extra-large, distance-readable digits; start/pause controls work; save the configuration.
4. **Expected Outcome**: Saved configuration is retrievable via `GET /routines/timers` and restores on reload.

### Scenario 7: Theme Toggle & Contrast (DR-001, DR-002, DR-007)
1. **Setup**: Load the dashboard in a fresh browser.
2. **Action**: Toggle between light and dark themes from the persisted control; reload the page.
3. **Expected Outcome**: Theme switches instantly with no flash of the wrong theme on reload (inline script); preference persists across sessions. Navy/ocean teal primary tones, coral/gold accents render correctly in both themes.
4. **Expected Outcome**: Programmatic contrast check (axe-core/Lighthouse, both themes) passes WCAG 2.1 AA (4.5:1 normal text, 3:1 large text).

### Scenario 8: Competition Results Browser (FR-009)
1. **Setup**: Obtain a JWT for any authenticated user role; ensure `swim-meets/` folder exists with sample PDFs.
2. **Action**: Add the Competition Results Browser widget to the dashboard; open it.
3. **Expected Outcome**: Treeview loads and renders the full swim-meets hierarchy (Year > Meet > Figure/Routine > PDF type) within 3 seconds (verifying `GET /results/tree` contract).
4. **Action**: Navigate the tree to a specific figure meet (e.g., `2026/JuniorOlympicChampionships/figure/Summary`).
5. **Expected Outcome**: Figure results table displays data from `as_meet_figure_result` (verifying `GET /results/figure/{meet_id}`); PDF links for Summary and Detailed are present and clickable.
6. **Action**: Click a PDF link (Summary or Detailed).
7. **Expected Outcome**: Original PDF file opens from the filesystem (verifying `GET /results/pdf/{year}/{meet}/{type}/{filename}`) within 1 second.
8. **Action**: Navigate to a routine meet and switch the tab to "Routines".
9. **Expected Outcome**: Routine results table displays data from `as_meet_routine_result` with element/artistic/sync breakdowns.
10. **Action**: Toggle the tree expansion state, reload the page.
11. **Expected Outcome**: Tree expansion state persists per user (widget `tree_state` JSONB).
