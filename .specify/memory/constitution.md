<!--
Sync Impact Report
Version Change: 1.1.1 -> 1.2.0
Modified Principles: None
Added Sections: 
- Principle 16: External User Management
Removed Sections: N/A
Templates requiring updates: 
- .specify/templates/plan-template.md (✅ checked)
- .specify/templates/spec-template.md (✅ checked)
- .specify/templates/tasks-template.md (✅ checked)
Follow-up TODOs: None
-->
# Artistic Swimming Analytics Platform Constitution

## Core Principles

### 1. API First
Every feature MUST begin with an OpenAPI specification. The API contract serves as the ultimate source of truth for communication and capabilities. No code should be written until the API spec is defined and agreed upon.

### 2. Domain First
Business rules and the core domain model MUST be defined before any UI implementation. The application architecture should reflect the domain boundaries and aggregate roots (e.g., Club, Athlete, Competition, Meet, Figure, Routine).

### 3. Test First
A rigorous test-first approach is MANDATORY. This includes:
- Unit tests for all business logic
- Integration tests for data persistence and external interactions
- Contract tests for OpenAPI spec validation
- End-to-end tests for critical user journeys

### 4. Data Integrity
Every imported score MUST be strictly traceable to the official meet results (PDF, CSV, Excel). Data lineage should be preserved to verify the authenticity of all metrics and rankings.

### 5. Immutable Competition Records
Official results MUST NOT be modified after publication. Any required corrections must be applied as distinct amendment records rather than in-place overwrites to maintain a verifiable audit trail.

### 6. Multi-Tenant
The system MUST isolate data by Club. Tenants (clubs) must only have access to their own athletes' data, configurations, and insights, ensuring complete data privacy across organizations.

### 7. Security
The platform MUST implement strict security standards:
- OAuth2 for authentication
- JWT for stateless authorization
- Role-Based Access Control (RBAC) to differentiate permissions between swimmers, coaches, administrators, and judges.

### 8. Accessibility
The user interface MUST comply with WCAG AA standards, ensuring the application is usable by all individuals, including those with visual or motor impairments.

### 9. Performance
The system MUST meet the following performance Service Level Agreements (SLAs):
- Dashboard rendering and interaction: < 2 seconds
- API endpoint response times: < 300ms

### 10. Observability
Comprehensive observability MUST be implemented across the stack:
- Structured Logging
- Metrics (e.g., latency, error rates)
- Distributed Tracing
- Audit logs for critical actions (e.g., manual corrections, imports)

### 11. AI Governance
AI-powered features (recommendations, summaries, predictions) MUST be explainable and read-only regarding core data. AI recommendations MUST NEVER overwrite official scores or authoritative records.

### 12. CI/CD
Continuous Integration and Deployment pipelines MUST enforce quality gates:
- No API spec -> No Merge
- No tests -> No Merge
- Contract validation required before any deployment.

### 13. Standardized Technology Stack
The platform MUST be built using the approved technology stack to ensure maintainability and consistency:
- **Frontend**: Angular 22 SPA using Angular Material, Apache ECharts, and NgRx Signals.
- **Backend**: Python/FastAPI for REST APIs and analytics.
- **Database**: Supabase (PostgreSQL) leveraging Row Level Security, Views, and Materialized Views.
- **Cache**: Redis.

### 14. Layered Analytics Architecture
Analytics MUST NOT be calculated directly on raw data per request. The system MUST implement a layered approach:
- Raw competition results are aggregated daily.
- Materialized Views store pre-calculated statistics.
- A centralized Analytics Engine (FastAPI) serves all dashboard widgets to ensure consistency across visualizations (Score Trend, Improvement Rate, Consistency, etc.).

### 15. Phased Machine Learning Delivery
AI and ML features MUST be introduced iteratively, prioritizing stability and explainability:
- **Phase 1 (Statistics)**: Rolling averages, percentiles, standard deviation.
- **Phase 2 (Predictive)**: Linear regression, Random Forest, XGBoost for next score and ranking predictions.
- **Phase 3 (LLM Coach)**: OpenAI-driven conversational analytics (e.g., explaining score plateaus and recommending practice focus).

### 16. External User Management
Identity, Roles (Athlete, Team Captain, Coach, Lead Coach, Parent, Club Admin, Club Owner), and Tenancy (Club) MUST be strictly delegated to the centralized Multi-Tenant User Service API (`001-multi-tenant-user-api`). The Analytics service and dashboards act solely as downstream consumers of these identities. Local databases MUST only store UUID references to these external identities, never duplicating profile or auth data.

## Governance

This Constitution supersedes all other documentation and local practices. 
- **Amendments**: Any changes to these principles must increment the Constitution version according to Semantic Versioning (MAJOR for breaking governance changes, MINOR for new principles, PATCH for wording/clarifications).
- **Compliance**: All Pull Requests must be evaluated against these principles. Code reviews must explicitly check for adherence to Test First, API First, Data Integrity, and the Approved Technology Stack.
- **Enforcement**: CI/CD pipelines will automatically enforce testing and API specification gates where technically feasible.

**Version**: 1.2.0 | **Ratified**: 2026-07-30 | **Last Amended**: 2026-08-01