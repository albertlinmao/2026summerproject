# Prompts to load data from Figure result

<details>
<summary><h2>2026-08-XX</h2></summary>

```text

```

</details>

---

<details>
<summary><h2>2026-08-27</h2></summary>

OOTO at home. Want to add data integration function to the dashboard. After manually load competition result, build an admin page to sort the data

## Step1: Browse the data

build an admin page to browse the competition results

1. login as Coach Sophie Lin
2. browse the figure results which stored in table as_meet_figure_result,as_event, as_meet, as_figure , as_meet_judge_panel
   I should be able to navigate on a tree build up from an event, to a meet in the event, to a meet with team, to an athlete, then see all figure scores of the athlete
3. browse the routin results which stored in table as_meet_routin_result, as_event, as_meet, as_meet_judge_panel
   I should be able to navigate on a tree build up from an event, to a meet in the event, to a meet with team, then I should see the routine scores of the team, and the athletes if athletes exist in the table
4. login to the app as an admin

## Integration

1. After competitions result is loaded to the database from PDF files, build a front end admin tool to try mapping the data with club, swimmer, and scores.
   Here is the mapping rules.
   Figure result is loaded into the table as_meet_figure_result.
   Routine result is laoded into the table as_meet_routine_result.
2. the tool shold be able to upload the PDF to Superbase, and create a meta data table for the PDF, it should have fields for fileName, competition name, competition date, host city, tags.

```text

```

</details>

---

<details>
<summary><h2>2026-08-19</h2></summary>

How to demo the progress? Documented in the MD - specs\001-analytics-dashboard\demo-steps.md

#Task3: how to use OpenCode while switching between CPP Google/Zen?

#Task2:  
Prompts: enhance the demo data creation script generate_demo_data.py, scan the data in the superbase, create a SST coach Sophie Lin, and generate all dashboards for Coach Sophie Lin, and also enable login/logout for Coach Sophie Lin

#Task1: update the data-model
Prompts: update the data-model to leverage the existing event, meet, scores tables defined in the file sql\create_figures_table.sql

```text
postgres://postgres:d27096746169f71e6c16998af5dc5322c14c28a2@localhost:5432/postgres

demo data creation
>Python generate_demo_data.py


# Execution Summary: Data Generation for User Story 1

## Objective
Create demonstration data to fulfill the requirements of **User Story 1 - Coach Team Analysis & Prediction** for the Artistic Swimming Analytics Dashboard.

## Actions Taken
1. **Analyzed Requirements**:
   - Reviewed `specs/001-analytics-dashboard/spec.md` to understand User Story 1, which requires tracking team performance, plateau risk, next score predictions, and AI-driven coaching insights for athletes under a coach's purview.
   - Reviewed `specs/001-analytics-dashboard/data-model.md` to identify the required tables (`as_athlete`, `as_predictive_insights`, `as_coaching_recommendations`, and `as_club`).

2. **Database Introspection**:
   - Verified that the relevant tables existed in the local PostgreSQL instance.
   - Checked the columns for the analytical entities to construct proper insert queries.

3. **Data Generation Script (`generate_demo_data.py`)**:
   - Created a Python script that connects to the local PostgreSQL database using `psycopg2`.
   - **Club Initialization**: Ensures a base club (Seattle Synchro - 'SST') exists to group the athletes.
   - **Athletes**: Inserted a set of mock athletes (e.g., Emma Johnson, Olivia Davis) linked to the 'SST' club.
   - **Predictive Insights**: Populated the `as_predictive_insights` table with randomly generated `next_score_prediction`, `plateau_risk` (25% chance of being true), and `confidence_interval`.
   - **Coaching Recommendations**: Populated the `as_coaching_recommendations` table with a mock `weakest_figure` and an AI-style `recommendation_text`.

4. **Execution**:
   - Executed the script, successfully seeding the local database with the required dummy data.
   - The script also prints a summary of the inserted data for immediate verification.

## Next Steps
The backend and frontend can now query these tables for the 'SST' club to accurately render the Coach Dashboard, testing UI components like the team overview, plateau warnings, and predicted scores.
```

</details>

---

<details>
<summary><h2>2026-08-16</h2></summary>

Prompt1:
to enhance the dashboard with the following styles -

Color PalettePrimary Tones: Deep navy blue and ocean teal to represent the pool and water.Backgrounds: Clean white or dark slate gray depending on indoor or outdoor coaching environments.Accent Colors: Bright coral or gold for high-priority alerts, top scores, and action buttons.Layout and StructureCard-Based Grid: Put video analysis, routine timers, and score breakdowns into separate, clean boxes.Sticky Navigation: Keep main controls like play, pause, and timestamp markers visible on the screen at all times.Whitespace: Leave empty space around elements so the screen does not look crowded in bright sunlight or under harsh pool lights.Typography and IconsFont Choice: Use clean sans-serif fonts like Inter or Roboto for fast reading of numbers and text.Font Sizing: Make scores and timers extra large so you can read them from a distance across the pool deck.Waterproof Icons: Use simple, filled vector icons for quick actions like video upload, audio cue, and timing marks.If you'd like, tell me:Do you prefer a light mode or dark mode layout?What are the top three features you use most on the deck?I can give you more specific design ideas.Woodmark Consulting5 Layout Tips for BI Dashboards - Woodmark ConsultingFeb 3, 2022 — Tip 3: Space is ace: inner padding is your secret weapon The biggest challenge in a dashboard is to visually

```text
+ Thought: Confirming Successful Build · 243ms
I've successfully updated the dashboard with your requested styles:
1. Color Palette: Added deep navy blue (--primary-navy) and ocean teal (--primary-teal) as main colors, with white/slate gray backgrounds. Added bright coral (--accent-coral) and gold (--accent-gold) for actions and highlights. Supports a basic light/dark mode preference via media query.
2. Layout and Structure: Implemented a card-based grid layout with generous padding (--card-padding). Added a sticky navigation bar with primary controls and icons at the top of the screen.
3. Typography and Icons: Integrated Google Fonts (Inter and Roboto). Made the scores and timers extra large (3.5rem to 3rem) for easy reading across the pool deck. Used simple filled icons (e.g. 🏷️, ⏱, ▶) for fast recognition.
The changes have been applied to the global CSS (styles.css), the main application shell (shell.component.ts), and the specific widgets (video-correction, routine-choreography, coach-overview) to match the desired look.
The application builds successfully with the new styling integrated.
```

</details>

---

<details>
<summary><h2>2026-08-05</h2></summary>
TODO: 1. merge Data Model with User Management API and Meet result import pipeline
TODO: 2. Merge the database design with sql\create_figures_table.sql and backend\supabase\migrations\20260804_initial_schema.sql to support the dashboard
refine the design to use swimming score of firure and routine. The data model is documented in sql\create_figures_table.sql

### Prompts:

refactor the frontend to consume the /analytics/dashboard API via an @ngrx/signals store, and the UI components need to visualize the predictive data beyond just passing the heatmap payload.

```text
Here's what was accomplished:
1. Created an NgRx Signals Store (frontend/src/app/store/dashboard.store.ts):
- Introduced a new DashboardStore using @ngrx/signals (signalStore).
- The store encapsulates the loading state, error state, and the teamHeatmap data containing our newly added predictive scores.
- It cleanly delegates data fetching to the ApiService.
2. Refactored ShellComponent (frontend/src/app/dashboards/shell/shell.component.ts):
- Removed the direct API fetching logic.
- Injected the new DashboardStore and tied the component's ngOnInit lifecycle to this.store.loadDashboard().
- Wired the template to reactively read from the store's signals (store.isLoading(), store.error(), store.teamHeatmap()) and pass the payload down.
3. Visualized Predictive Data (frontend/src/app/shared/widgets/coach-overview.component.ts):
- Replaced the placeholder logic with a detailed "Predictions Panel" UI alongside the heatmap.
- The component now iterates over the typed HeatmapData[] and displays figure_score, routine_score, and the prediction_score for each athlete.
- Added clean, inline CSS styles to format the data into a readable grid/card layout so coaches can easily spot predicted outcomes based on the baseline logic.
```

### Prompts:

enhance the frontend to enable routine choreography calculations or swimmer fitness tracking, Video Integration Card: Side-by-side clip uploader with timestamp tags for instant stroke or hybrid correction, similar to tools like Dartfish

```text
1. Video Correction Integration (video-correction.component.ts):
- Developed a side-by-side Dartfish-style video analysis card.
- Includes a mock video player workspace with an interactive progress bar.
- Built a tagging system allowing coaches/swimmers to create timestamped correction tags.
- Tags are dynamically categorized by type: Stroke (blue), Hybrid (green), and Timing (yellow), mapping visual markers onto the timeline to jump to specific points of improvement.
2. Routine Choreography Calculator (routine-choreography.component.ts):
- Created a dynamic choreography planning table powered by Angular signals (computed and signal).
- Allows users to add routine elements (Acrobatic, Hybrid, Transition) by defining the element name and its Base Mark (Degree of Difficulty - DD).
- Automatically calculates the Total Difficulty of the routine dynamically as elements are added or removed, aiding coaches in building highly competitive routines mathematically.
3. Dashboard Layout Update (shell.component.ts):
- Added an analysis-tools-grid layout to cleanly render both the new Routine Choreography tool and the Video Correction UI directly below the Coach Team Overview.
These components are built cleanly as standalone Angular components leveraging the modern framework capabilities (Signals, standalone imports) and styled to feel like a premium coaching toolkit!
```

</details>

---

<details>
<summary><h2>2026-08-04</h2></summary>

```text
I have verified the Phase 3 implementation based on the plan and tasks in specs/001-analytics-dashboard/.
Here is the status of the Phase 3 (User Story 1 - Coach Team Analysis & Prediction) implementation:
1. FastAPI Data Models & Endpoints
- ✅ backend/src/models/aggregations.py: Present.
- ✅ backend/src/api/dashboard.py: Implemented /analytics/dashboard endpoint for the Coach role, incorporating JWT token verification and using the coach service.
- ✅ backend/src/services/analytics/coach_service.py: Contains the team overview aggregation logic. It also correctly implements T022 (predictive baseline average fallback logic), returning an age-group average baseline of 70.0 when an athlete has fewer than 5 historical records.
2. Angular Dashboard & Widgets
- ✅ frontend/src/app/shared/widgets/coach-overview.component.ts: Present.
- ✅ frontend/src/app/shared/widgets/heatmap.component.ts: Present.
- ✅ frontend/src/app/dashboards/shell/shell.component.ts: The unified Dashboard Shell is implemented. It conditionally loads the app-coach-overview widget based on the role and calls the /analytics/dashboard endpoint via ApiService.
Notes on Completion Quality:
While the tasks are marked as complete [x] in tasks.md, T021 (Integrate Dashboard Shell with backend API and NgRx Signals store) currently utilizes a basic fetch/then promise on the ApiService directly inside shell.component.ts rather than a full NgRx Signals store integration. It effectively fulfills the functional requirement for the Coach view, but may need refinement in Phase 7 for better state management.
Overall, the foundational artifacts and logical pathways for Phase 3 are successfully in place!
```

</details>

---

<details>
<summary><h2>2026-08-01</h2></summary>

### Prompts to ask AI chat for spec

**Prompt:**

> I have imported Artistic swimming event figures and routines score to SuperBase progresSQL db, I want to build a dashboard for swimmers and coach to track progress and predict improvement, and support long-term athlete development. What kind frameworks I should use to build the system?

#### ChatGPT Response

Since I know you're already using **Angular**, **Python/FastAPI**, **Supabase (PostgreSQL)**, and you're adopting **Spec-Driven Development (SpecKit)**, I would build around those technologies rather than introducing an entirely new stack. They fit this use case well and allow you to iterate quickly while keeping the architecture maintainable.

## Recommended Architecture

```text
                    +---------------------+
                    |   Angular 22 SPA    |
                    |---------------------|
                    | Dashboards          |
                    | Charts              |
                    | AI Coach            |
                    | Rankings            |
                    +----------+----------+
                               |
                     HTTPS / REST APIs
                               |
                    +----------v----------+
                    | FastAPI Backend     |
                    |---------------------|
                    | Authentication      |
                    | Ranking Engine      |
                    | Analytics Engine    |
                    | Prediction Service  |
                    | PDF Import Service  |
                    +----------+----------+
                               |
                 +-------------+-------------+
                 |                           |
        +--------v-------+          +--------v-------+
        | Supabase       |          | Redis          |
        | PostgreSQL     |          | Cache          |
        +----------------+          +----------------+
                 |
        Materialized Views
                 |
        Analytics Queries

                Future
                 |
        +--------v--------+
        | AI/ML Services  |
        | XGBoost         |
        | LightGBM        |
        | Prophet         |
        | OpenAI          |
        +-----------------+
```

---

## Frontend: Angular 22

This is still one of the best choices because you already know it.

Recommended libraries:

| Purpose          | Framework                    |
| ---------------- | ---------------------------- |
| UI               | Angular Material             |
| Charts           | Apache ECharts               |
| Data Tables      | AG Grid Community            |
| State Management | NgRx Signals or Signal Store |
| Authentication   | Supabase Auth                |
| Forms            | Reactive Forms               |
| Maps (future)    | Leaflet                      |
| PDF Viewer       | ngx-extended-pdf-viewer      |

I recommend **Apache ECharts** because coaches will want interactive visualizations.
Examples include:

- Progress curves
- Figure radar charts
- Ranking history
- Heat maps
- Score distributions
- Judge comparison
- Trend prediction

---

## Backend: FastAPI

FastAPI is an excellent fit for analytics-heavy applications. Suggested modules:

```text
app/
    auth/
    athletes/
    clubs/
    competitions/
    figures/
    routines/
    rankings/
    analytics/
    predictions/
    reports/
    ai/
    import/
    notifications/
```

---

## Database

Since you already have Supabase PostgreSQL, use:

- Views
- Materialized Views
- Stored Procedures
- Row Level Security
- Full Text Search
- pgvector (future)

For analytics:
`Competition Results` → `Daily Aggregation` → `Materialized Views` → `Dashboard`
_(This avoids recalculating expensive statistics on every request)_

---

## Machine Learning

This is where the application becomes truly valuable. Start simple.

### Phase 1: Statistics

- Rolling Average
- Exponential Moving Average
- Percentile
- Standard deviation
- Consistency Score
  _(These often provide highly actionable insights without requiring complex models)_

### Phase 2: Predictive Models

`Next Figure Score` → `Linear Regression` → `Random Forest` → `XGBoost`
Predict:

- next competition score
- expected ranking
- qualification probability
- probability of achieving personal best

### Phase 3: LLM Coach

Example output:

> Sophie improved her Barracuda from 58.2 to 63.7 during the last 5 meets. Her consistency increased by 17%. Her weakest figures remain:
> • Knight
> • Walkover
> Focus recommendation: Spend 40% of practice improving vertical stability and rotation speed.
> Projected provincial ranking: Top 12 next season.

---

## Analytics Framework

I would build an Analytics Engine rather than putting all logic into SQL.
Every dashboard widget should use this shared service.

`Analytics Service` → `Score Trend` → `Improvement Rate` → `Ranking History` → `Percentiles` → `Consistency` → `Personal Best` → `Club Average` → `Provincial Average` → `National Average`

---

## AI Layer

Eventually add an OpenAI coaching assistant. Example prompt:

> _Explain why the athlete's figure scores plateaued despite higher difficulty, citing consistency, execution, and historical trends._

---

## Dashboard Pages

### Swimmer Dashboard

- Personal Bests
- Current Ranking
- Figure & Routine Trends
- Medal History
- Goal Progress
- Qualification Status
- Practice Recommendations
- Upcoming Meets

### Coach Dashboard

- Entire Team Overview
- Most Improved Athletes
- Athletes at Risk of Plateauing
- Figure Weakness Heat Map
- Routine Comparisons
- Club Rankings & Statistics
- Qualification Predictions

### Parent Dashboard

Simplified metrics:

- Progress over time
- Coach comments
- Goal tracking
- Meet history
- Videos (future)

### Club Dashboard

- Club Rankings
- Medal Counts
- Average Scores
- Coach Effectiveness
- Athlete Retention
- Meet Performance
- Age Group Analysis

---

## Visualization Library

I recommend **Apache ECharts** because it supports virtually every chart you'll need (Line charts, Radar charts, Heat maps, Sankey diagrams, Box plots, Scatter plots, Geographic maps, etc.).

---

## Deployment

```text
Cloudflare
        │
Angular SPA
        │
FastAPI
        │
Supabase
        │
Redis
```

For an MVP, Cloudflare Pages (frontend) and a lightweight FastAPI deployment work well, with Supabase providing PostgreSQL, authentication, and storage.

---

## Long-Term Athlete Development (LTAD)

Design the system around athlete development rather than just competition results. Organize analytics into pillars such as:

| Category        | Example Metrics                                                                    |
| --------------- | ---------------------------------------------------------------------------------- |
| Growth          | Score improvement rate, personal best progression, consistency index               |
| Skills          | Figure-by-figure mastery, routine element performance, execution trends            |
| Performance     | Rankings, qualification status, medal history, season summaries                    |
| Training        | Practice attendance, coach feedback, goal completion (future integration)          |
| Health (future) | Recovery, injuries, wellness tracking, wearable data                               |
| AI Insights     | Predicted scores, improvement opportunities, personalized training recommendations |

By separating raw competition data, analytics services, prediction models, and AI coaching, you'll have a modular architecture that supports today's dashboards while making it straightforward to add features like video analysis, choreography assistance, or federation integrations in the future.

---

#### Gemini Response

To build a full-stack performance dashboard for **Artistic Swimming**, you will want an architecture that pairs seamlessly with **Supabase (PostgreSQL)** while providing robust role-based access, data visualization, and analytical forecasting capabilities.

## 1. Primary Full-Stack Web Framework

### **Next.js (React / TypeScript)** — _Recommended_

- **Why:** Next.js is deeply integrated with Supabase. It handles SSR, static generation for fast dashboard loads, and secure API routes.
- **Role-Based Access:** Enforce distinct UX views for **Swimmers** vs. **Coaches** using **Supabase RLS** combined with Next.js middleware.
- **Alternative:** **Remix / React Router v7** or **SvelteKit** if you prefer lighter client bundles.

## 2. UI Components & Data Visualization Libraries

- **UI Components:** **Shadcn UI** + **Tailwind CSS**
- **Interactive Charts:** **Recharts** or **Tremor** (Great for displaying time-series progression, radar charts for multi-dimensional skill ratings, and benchmark comparisons)
- **Advanced Tables:** **TanStack Table (React Table)** (Vital for handling large scoring tables, sorting elements by DD, and filtering)

## 3. Analytics & Predictive Modeling Engine

### **Option A: Embedded Python Microservice (Best for Advanced ML)**

- **Stack:** **FastAPI (Python)** + **scikit-learn** / **Prophet** / **PyTorch**
- **Why:** Python handles predictive modeling, statistical regression, and routine diff analysis.

### **Option B: Supabase Edge Functions + SQL Views (Lightweight Option)**

- **Stack:** **Deno / TypeScript Edge Functions** + **Postgres Window Functions**
- **Why:** Computations like linear trendlines and moving averages can be directly computed via PostgreSQL materialized views without a separate Python service.

## 4. Database & Auth Layer (Leveraging Supabase)

- **Authentication & Authorization:** Use **Supabase Auth**. Assign roles (`coach`, `swimmer`, `admin`).
- **Realtime Updates:** Use **Supabase Realtime** so coaches entering live practice scores instantaneously update dashboards.
- **Media / Video Analysis:** Use **Supabase Storage** to link video recordings of routines.

## Recommended Architecture Blueprint

```text
┌─────────────────────────────────────────────────────────┐
│                    Next.js Frontend                     │
│  (Tailwind CSS + Shadcn UI + Recharts / TanStack Table) │
└───────────────┬─────────────────────────┬───────────────┘
                │                         │
     Supabase Client (Auth/RLS)     Predictive API Calls
                │                         │
                ▼                         ▼
┌──────────────────────────────┐  ┌───────────────────────┐
│       Supabase Backend       │  ┌  FastAPI Microservice │
│ - PostgreSQL DB              │◄─┤  (Python / Prophet /  │
│ - Auth & Row-Level Security  │  │   scikit-learn)       │
│ - Storage (Video/Docs)       │  └───────────────────────┘
└──────────────────────────────┘
```

## Domain Features to Plan For

1. **Figure vs. Routine Decomposition:** Track figure scores individually and compare them with technical routine scores.
2. **LTAD Growth & Benchmark Mapping:** Overlay swimmer trajectories onto World Aquatics age-group benchmark curves.
3. **Judges' Score Variance Tracker:** Analyze score variations across judges to detect biased scoring patterns.

</details>

---

<details>
<summary><h2>2026-07-31</h2></summary>

### Prompts to create constitutions

Here is a collection of master prompts that you can use with AI generation tools to scaffold the project properly:

#### 1. Master Product Prompt

> Build a production-quality, cloud-native Artistic Swimming Analytics Platform that allows swimmers, coaches, clubs, and judges to analyze Figure and Routine competition results over time.
> The system shall ingest official meet result files (PDF, CSV, Excel), normalize them into a relational data model, calculate rankings and statistics, and present interactive dashboards.
> The architecture must follow Spec-Driven Development using SpecKit Constitution, API-first development, test-first implementation, OpenAPI contracts, CI validation, and domain-driven design.

#### 2. Product Vision Prompt

> Create a Product Requirements Document (PRD) for an Artistic Swimming Dashboard.
> Primary users: Swimmers, Parents, Coaches, Club administrators, Judges, Competition organizers.
> Goals: Track athlete progress, analyze figure/routine scores, compare competitions, predict athlete improvement, rank swimmers, benchmark rankings, and support long-term athlete development.

#### 3. Functional Requirements Prompt

> Generate detailed functional requirements.
> Modules: Authentication, Athlete Management, Club Management, Competition Management, Meet Import, Figure Results, Routine Results, Judge Analysis, Ranking Engine, Dashboard, Statistics, Trend Analysis, Goal Tracking, Coach Workspace, Athlete Workspace, Parent View, Administration.
> Each module should include: Actors, Use cases, Business rules, Acceptance criteria, API requirements, and Security requirements.

#### 4. Domain Model Prompt

> Design a normalized domain model.
> Entities include: Club, Coach, Athlete, Competition, Event, Meet, Session, AgeGroup, Figure, Routine, RoutineElement, Judge, Score, Penalty, Ranking, Season, Qualification, Award.
> Include relationships, primary/foreign keys, aggregate roots, and DDD boundaries.

#### 5. Figure Analytics Prompt

> Design a complete Figure Analytics dashboard.
> Support: Figure history, Figure averages, Difficulty factors, Judge consistency, Percentile ranking, Provincial ranking, National ranking, Personal best, Trend over time.
> Visualizations: Radar charts, Trend lines, Box plots, Heat maps, Percentile distributions.
> Filtering: Season, Competition, Age group, Figure, Club, Coach.

#### 6. Routine Analytics Prompt

> Design an Artistic Swimming Routine dashboard.
> Track: Technical Routine, Free Routine, Team, Duet, Solo, Acrobatic Routine.
> Metrics: Difficulty, Execution, Artistic Impression, Synchronization, Coach comments, Penalty history.
> Visualizations: Score breakdown, Trend, Waterfall, Judge comparison, Execution consistency.

#### 7. Ranking Engine Prompt

> Design a ranking engine.
> Support rankings by: Club, Province, State, National, International, Season, Competition, Age Group.
> Ranking types: Overall, Figure, Routine, Technical, Free.
> Support: Best score, Average score, Rolling average, Weighted ranking, Official ranking. Include tie-breaking rules.

#### 8. Dashboard UX Prompt

> Design an Angular dashboard optimized for coaches.
> Features: Dark mode, Responsive, Mobile friendly.
> Widgets: Top swimmers, Most improved athletes, Upcoming competitions, Training goals, Recent competitions, Figure trends, Routine trends, Rank changes, Coach alerts.

#### 9. AI Features Prompt

> Design AI-powered coaching features.
> Capabilities: Summarize athlete progress, Identify weakest figures, Predict next competition score, Recommend practice priorities, Generate coach reports, Estimate qualification probability, Detect judging anomalies. Use explainable AI.

#### 10. PDF Import Prompt

> Design a PDF ingestion pipeline.
> Support importing official Artistic Swimming result PDFs.
> Automatically extract: Competition, Athlete, Club, Figure, Routine, Judge, Score, Penalty, Rank.
> Validate imported data, prevent duplicates, track import history, allow manual corrections, and produce normalized database records.

#### 11. Analytics Prompt

> Design analytical dashboards.
> Metrics include: Average score, Median, Percentile, Best score, Worst score, Consistency, Improvement, Moving average, Season average.
> Support: Coach dashboard, Athlete dashboard, Club dashboard, Provincial dashboard.

#### 12. SpecKit Constitution Prompt (Recommended)

> Generate a SpecKit Constitution for the Artistic Swimming Analytics Platform.
> Principles:
>
> 1. API First (Every feature begins with OpenAPI spec)
> 2. Domain First (Business rules before UI)
> 3. Test First (Unit, integration, contract, e2e)
> 4. Data Integrity (Traceable scores)
> 5. Immutable Competition Records
> 6. Multi-Tenant
> 7. Security (OAuth2, JWT, RBAC)
> 8. Accessibility (WCAG AA)
> 9. Performance (Dashboard <2s, API <300ms)
> 10. Observability (Logging, Metrics, Audit logs)
> 11. AI Governance (No overwriting official scores)
> 12. CI/CD (No API spec/tests -> No Merge)

#### 13. Future Roadmap Prompt

> Design the platform to support future features.
> Planned modules: Video analysis, Underwater camera synchronization, AI movement scoring, Routine choreography planner, Training planner, Wearable integration, Olympic qualification tracking.

---

## Suggested MVP Scope

For an MVP that delivers value quickly while leaving room to grow, I would prioritize:

| Phase               | Features                                                                                                                               |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| **MVP (6–8 weeks)** | Authentication, athlete/club management, PDF import, figure results, routine results, athlete profile, basic rankings, trend dashboard |
| **Phase 2**         | Coach dashboards, season analytics, judge analysis, team comparisons                                                                   |
| **Phase 3**         | AI-generated coaching insights, performance predictions, training recommendations                                                      |
| **Phase 4**         | Video analysis, choreography planning, federation integration, mobile app                                                              |

This phased approach aligns well with Spec-Driven Development: define the domain and contracts first, build a stable analytics core, and then layer on advanced AI and visualization capabilities without disrupting the underlying architecture.

</details>
