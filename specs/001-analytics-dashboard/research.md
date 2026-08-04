# Research: Artistic Swimming Analytics Dashboard

## Technology Stack Validation

**Decision**: Use Angular 22, FastAPI, Supabase (PostgreSQL), and Redis.
**Rationale**: Mandated by project Constitution (Principle 13). Provides a robust separation of concerns, fast analytics processing, and secure multi-tenant data isolation.
**Alternatives considered**: None. Strictly bound by architectural guidelines.

## Charting Library

**Decision**: Apache ECharts.
**Rationale**: Native support for complex visualizations required (radar charts for figures, heat maps, standard distribution charts). Easily integrates with Angular 22.
**Alternatives considered**: Chart.js, D3.js. Rejected in favor of ECharts due to explicit recommendation in feature specification for interactive coaching visuals.

## Predictive Modeling (Phase 1 & 2)

**Decision**: Begin with PostgreSQL Materialized Views for descriptive statistics (Phase 1), and implement Scikit-learn/XGBoost via FastAPI for predictive insights (Phase 2).
**Rationale**: Supabase Materialized Views handle rolling averages efficiently without Python overhead. For ML, Python/FastAPI natively integrates with the richest ML ecosystem.
**Alternatives considered**: Pure SQL ML (pgvector). Python is better suited for complex Random Forest/XGBoost training loops.

## AI Coach (Phase 3)

**Decision**: OpenAI API integration within the FastAPI backend.
**Rationale**: Backend integration protects API keys and allows prompt augmentation with secure, club-specific context retrieved via Row Level Security (RLS) policies.
**Alternatives considered**: Client-side LLM calls (rejected due to security and inability to safely inject context).