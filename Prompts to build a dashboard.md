# Prompts to load data from Figure result

<details>
<summary><h2>2026-08-02</h2></summary>

### Prompts

/speckit.specify

````

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
*(This avoids recalculating expensive statistics on every request)*

---

## Machine Learning

This is where the application becomes truly valuable. Start simple.

### Phase 1: Statistics
- Rolling Average
- Exponential Moving Average
- Percentile
- Standard deviation
- Consistency Score
*(These often provide highly actionable insights without requiring complex models)*

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
> *Explain why the athlete's figure scores plateaued despite higher difficulty, citing consistency, execution, and historical trends.*

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

### **Next.js (React / TypeScript)** — *Recommended*
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
````
