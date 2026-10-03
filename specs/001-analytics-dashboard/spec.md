# Feature Specification: Artistic Swimming Analytics Dashboard

**Feature Branch**: `001-analytics-dashboard`
**Created**: 2026-08-01
**Status**: Draft

## Clarifications

### Session 2026-08-19
- Q: What is the video retention policy for uploaded routine videos? → A: Option C (Auto-delete after 90 days, competition season retention).
- Q: Who can access uploaded routine videos? → A: Option D (The person filmed, their coaches, and their guardians — family access, resolved from club membership and guardian links rather than from token claims).
- Q: What do timestamp markers do during playback? → A: Option A (Click-to-seek plus audio tone playback for audio_cue markers).
- Q: What alert should a routine timer give when the countdown reaches zero? → A: Option A (Visual flash plus audible beep).
- Q: What does "extendable board" mean for browsing competition results? → A: Option D (Dashboard widgets — modular widgets like leaderboards, score distributions, heatmaps that users can add/remove/resize).
- Q: Which competition result types should the board display? → A: Option C (Both figures and routines with unified view and toggle/tabs).
- Q: How should users filter and access competition results on the board? → A: All users can view; organized as treeview matching the swim-meets folder structure.
- Q: Should the treeview also provide access to the original PDF files in swim-meets folder? → A: Option A (Yes, link to PDFs — tree nodes link to original summary/detailed PDFs for each meet/event).
- Q: How should the treeview structure map to the swim-meets folder hierarchy? → A: Option A (Exact folder mirror — Year > Meet > Figure/Routine > PDF type matching filesystem).

### Session 2026-08-18
- Q: Should the dashboard use a light or dark mode layout? → A: Option A (Both modes, user-selectable toggle, persisted per user).
- Q: Should video analysis and routine timers be added as dashboard features? → A: Option A (Yes, add both as new dashboard widgets; they become in-scope).
- Q: Which features need extra-large, distance-readable typography? → A: Option D (All key metrics — team analysis/predictions, video/timers/scores, personal progress/AI coach).
- Q: What contrast/accessibility standard should the design adhere to? → A: Option A (WCAG 2.1 AA, 4.5:1 for normal text).

### Session 2026-08-09
- Q: How should the dashboard respond if the external `001-multi-tenant-user-api` is unreachable during session validation? → A: Option C (Display a full-page critical error with a retry button within the app).
- Q: How frequently should the materialized views for daily score aggregations be refreshed to balance performance and freshness? → A: Option C (On-demand refresh when first accessed, with caching).

### Session 2026-08-01
- Q: How should the system handle users who belong to multiple clubs or have multiple roles? → A: Unified View (Merge permissions into a single dashboard view with all available widgets).
- Q: How does the system handle predictive insights for a new swimmer with insufficient historical data? → A: Baseline Average (Use club or age-group averages as a baseline for early predictions).
- Q: What should the system display if the external AI coach service is temporarily unavailable? → A: Error Message (Display a generic error message "AI temporarily unavailable" in the widget).

## User Scenarios & Testing

### User Story 1 - Coach Team Analysis & Prediction (Priority: P1)

Coaches need to evaluate entire team performance, identify athletes at risk of plateauing, and view predicted qualification statuses so they can adjust training regimens efficiently.

**Why this priority**: Coaches are the primary decision-makers who will drive adoption of the platform. Providing them with actionable team insights is the core value proposition.

**Independent Test**: Can be fully tested by logging in as a coach, navigating to the dashboard, and viewing a heat map of figure weaknesses and qualification predictions for their team.

**Acceptance Scenarios**:
1. **Given** a coach is logged into the system, **When** they access the dashboard, **Then** they see an overview of their entire team, including the most improved athletes and those at risk.
2. **Given** a coach views an athlete's profile, **When** they access the prediction section, **Then** they can view the projected next competition score and expected ranking.

---

### User Story 2 - Swimmer Personal Progress & AI Coach (Priority: P2)

Swimmers need to track their personal bests, current rankings, and receive personalized practice recommendations to understand their long-term development.

**Why this priority**: Swimmer engagement relies on clear visibility into their individual progression and goals.

**Independent Test**: Can be fully tested by logging in as a swimmer and successfully retrieving personal progress charts and the latest AI-generated focus recommendation.

**Acceptance Scenarios**:
1. **Given** a swimmer is logged into the system, **When** they view their dashboard, **Then** they see their figure and routine trends over time and current personal bests.
2. **Given** a swimmer reviews recent competition data, **When** they access the AI coach insights, **Then** they receive a targeted recommendation (e.g., specific practice focus for their weakest figures).

---

### User Story 3 - Club Administration Overview (Priority: P3)

Club administrators need to monitor club rankings, average scores, coach effectiveness, and athlete retention to manage the business and competitive standing of the club.

**Why this priority**: Critical for organizational management, but less impactful to day-to-day training than swimmer/coach views.

**Independent Test**: Can be fully tested by logging in as a club administrator and viewing aggregated statistics across all teams and age groups.

**Acceptance Scenarios**:
1. **Given** a club administrator is on the dashboard, **When** they select the club overview, **Then** they can view aggregated medal counts, retention rates, and overall club rankings.

---

### User Story 4 - Competition Results Browser (Priority: P2)

Coaches, athletes, and club administrators need to browse historical competition results organized by the original meet structure, with direct access to source PDFs for verification and detailed review.

**Why this priority**: The swim-meets folder contains the authoritative source data. Users need a navigable interface that mirrors the familiar folder hierarchy while providing database-driven results with PDF links.

**Independent Test**: Can be fully tested by logging in as any role, adding the Competition Results Browser widget, navigating the treeview to a specific meet, and opening both the database results and the linked source PDF.

**Acceptance Scenarios**:
1. **Given** a user adds the Competition Results Browser widget, **When** they open it, **Then** they see a treeview matching the `swim-meets/` folder structure (Year > Meet > Figure/Routine > PDF type).
2. **Given** a user navigates to a specific figure meet in the tree, **When** they select a figure event, **Then** they see the figure results from `as_meet_figure_result` and links to the Summary/Detailed PDFs.
3. **Given** a user navigates to a routine meet in the tree, **When** they select a routine event, **Then** they see the routine results from `as_meet_routine_result` and links to the Summary/Detailed PDFs.
4. **Given** a user clicks a PDF link in the tree, **When** the link opens, **Then** the original PDF file from the swim-meets folder is displayed.

---

### Edge Cases & Failure Handling

- **User Service Unavailability**: If the `001-multi-tenant-user-api` is unreachable during session validation, the application MUST display a full-page critical error with a retry button within the app.
- **Multiple Roles/Clubs**: If a user possesses multiple roles (e.g., Coach and Parent) or belongs to multiple clubs, the system MUST merge permissions into a single, unified dashboard view containing all widgets authorized for their combined roles. Roles are evaluated per club, so a `coach` role in one club grants no authority in another.
- **Insufficient Historical Data**: For new swimmers lacking sufficient historical data to generate individualized predictive models (e.g., fewer than 5 records), the system MUST use club or age-group averages as a baseline for early predictions.
- **AI Service Unavailability**: If the external AI coach service (OpenAI) times out or is unavailable, the AI recommendation widget MUST display a generic error message ("AI temporarily unavailable") rather than hiding the section or falling back to statistics.
- **Video Access Control**: Video access is limited to the person filmed, their coaches, and their guardians; attempts to access a video outside this scope MUST be denied (403). This requires linking each video to the person appearing in it (`video_uploads.person_id`) and resolving the caller's relationship from club membership and guardian links.

## Requirements

### Functional Requirements

- **FR-001**: System MUST provide distinct, role-based dashboard views and varying permissions derived from the per-club membership roles `admin`, `coach`, `swimmer`, `parent`, and `official`. Presentation-only distinctions (e.g. `Team Captain`, `Lead Coach`, `Club Owner`) MUST be carried as a display `title` on the membership and MUST NOT affect authorization. A member with the `parent` role MUST see only the people their guardian links connect them to — never the whole club.
- **FR-002**: System MUST visualize historical score distributions, ranking histories, and figure radar charts.
- **FR-003**: System MUST provide predictive analytics indicating a swimmer's expected ranking and qualification probability based on historical data.
- **FR-004**: System MUST surface natural language explanations (AI coach) detailing why a swimmer's score changed and providing practice focus recommendations.
- **FR-005**: System MUST aggregate raw competition results into daily summaries for performant dashboard rendering. Materialized views for these aggregations MUST be refreshed on-demand when first accessed, and then cached.
- **FR-006**: System MUST enforce data privacy, ensuring users only see data they are authorized to access based on their per-club role and club affiliation. Authorization MUST resolve from `as_club_membership` (roles and status `invited`/`active`) rather than from a single tenant claim; the identity service's claims are a cache only, per [identity-contract.md](identity-contract.md).
- **FR-007**: System MUST provide a video analysis widget allowing upload of routine videos, frame-by-frame playback, and timestamp markers linked to figure/routine scoring moments. Uploaded videos MUST be automatically deleted 90 days after upload (competition season retention). Access to a video MUST be restricted to the person filmed, their coaches, and their guardians (family access), resolved as (person, club, role) from club membership and guardian links. Markers MUST support click-to-seek during playback; `audio_cue` markers MUST additionally emit an audio tone when reached during playback.
- **FR-008**: System MUST provide routine timer widgets (e.g., routine duration countdown) with start/pause controls for use on the pool deck. When a countdown reaches zero, the timer MUST alert with both a visual flash and an audible beep.
- **FR-009**: System MUST provide an extendable Competition Results Browser as a dashboard widget. The browser MUST:
  - Display a treeview mirroring the exact `swim-meets/` folder hierarchy (Year > Meet > Figure/Routine > PDF type).
  - Support both figure and routine results with toggle/tabs between them.
  - Link tree nodes to original source PDF files (Summary and Detailed) for each meet/event.
  - Be accessible to all authenticated users (no club-scoping restriction on viewing).
  - Be implemented as a modular dashboard widget that users can add/remove/resize alongside other widgets.
  - Load result data from the Supabase tables (`as_meet_figure_result`, `as_meet_routine_result`) with PDF links resolved from the filesystem structure.

### Key Entities

- **Person (Reference)**: Represents a human being — swimmer, coach, parent, official, or administrator. Carries no credentials and no `club_id`, so one person may belong to several clubs and a login is optional (minors, dormant swimmers, and alumni are first-class records). The dashboard stores UUID references only, linking historical scores, routines, and personal bests.
- **Club (Reference)**: Represents the tenant. Managed externally; used locally as the grouping mechanism and row-level security scope.
- **Club Membership (Reference)**: The edge between a Person and a Club, and the **authorization source of truth**. Carries a coarse `role`, a display-only `title`, and a `status` that revokes access when set to `dormant` or `left`. Vocabulary is defined in [identity-contract.md](identity-contract.md).
- **Person Link (Reference)**: A directed guardian edge (`parent` / `guardian` / `emergency_contact`) between two people within a club. This is what makes family video access expressible without forcing an account on every minor.
- **Athlete (Reference, view)**: Compatibility projection of a Person holding an active `swimmer` membership (`person_id`, `name`, `birth_date`); deliberately carries no `club_id`.
- **Coach (Reference, view)**: Compatibility projection of a Person holding an active `coach` membership (`person_id`, `name`); deliberately carries no `club_id`.
- **Competition Result**: The core factual data point (figure score, routine score) used for aggregation. Imported rows keep their verbatim PDF fields (`athlete_name`, `athlete_birth_year`, `team_athletes`) and are mapped to a Person via a Result Person Link.
- **Predictive Insight**: Generated forecasts (e.g., next score, plateau risk) associated with a person.
- **Coaching Recommendation**: AI-generated natural language feedback and practice priorities.
- **Competition Results Browser Widget (FR-009)**: Modular dashboard widget providing a treeview browser over the `swim-meets/` folder hierarchy with database-backed results and PDF links.

### Design System & UX Requirements

- **DR-001**: System MUST support both light and dark themes, user-selectable via a persisted toggle (per user), with no automatic environment-based switching.
- **DR-002**: Color palette MUST use deep navy blue and ocean teal as primary tones, clean white (light mode) or dark slate gray (dark mode) backgrounds, and bright coral or gold for high-priority alerts, top scores, and action buttons.
- **DR-003**: Dashboard layout MUST use a card-based grid, with video analysis, routine timers, and score breakdowns in separate cards with generous whitespace/padding so content remains readable in bright sunlight or under harsh pool lights.
- **DR-004**: Main controls (play, pause, timestamp markers) MUST remain visible on screen at all times via sticky navigation.
- **DR-005**: Typography MUST use clean sans-serif fonts (Inter or Roboto) for fast reading of numbers and text; scores and timers MUST be extra large so they are readable from a distance across the pool deck. Extra-large typography applies to all key metrics, including team analysis/predictions, video/timers/scores, and personal progress/AI coach widgets.
- **DR-006**: Icons MUST be simple, filled vector icons for quick actions such as video upload, audio cue, and timing marks.
- **DR-007**: All text MUST meet WCAG 2.1 AA contrast ratios (4.5:1 for normal text, 3:1 for large text) in both light and dark themes.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 95% of dashboard pages render in under 2 seconds.
- **SC-002**: Coaches can identify a swimmer's weakest figure and access a practice recommendation in 3 clicks or fewer.
- **SC-003**: The predictive engine provides a next-competition score forecast for 100% of athletes who have at least 5 historical competition records.
- **SC-004**: System supports simultaneous access by 1,000 users without degrading response times.
- **SC-005**: Competition Results Browser treeview loads and renders the full swim-meets hierarchy in under 3 seconds.
- **SC-006**: PDF links in the treeview open the correct source file within 1 second of click.

## Assumptions

- Users have modern web browsers capable of rendering complex interactive charts.
- Adequate historical competition data exists to train and execute the predictive models.
- The underlying authentication and identity management is fully handled by the `001-multi-tenant-user-api` service. It asserts only the `sub` subject claim as authoritative; role, club, and profile claims (`person_id`, `club_ids`, `roles_by_club`, `permissions`) are a non-authoritative cache. All authorization resolves from `as_club_membership` in the dashboard database, per [identity-contract.md](identity-contract.md).