# Implementation Plan: Artistic Swimming Analytics Dashboard

**Branch**: `001-analytics-dashboard` | **Date**: 2026-08-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-analytics-dashboard/spec.md`

## Summary

Implement a full-stack Artistic Swimming Analytics Dashboard to track athlete progression, predict improvement, and support long-term development. The solution leverages Angular 22, FastAPI, and Supabase to provide secure, role-based views (Coach, Swimmer, Parent, Admin), utilizing Apache ECharts for visualization and phased machine learning models for predictive coaching insights. Expanded scope (2026-08-18) adds a video analysis widget with timestamp markers (FR-007), routine timers (FR-008), and a dual light/dark design system with deck-readable typography (DR-001 to DR-007). Clarified 2026-08-19: videos auto-delete after 90 days, family-only video access (athlete/coaches/parents), audio tones for `audio_cue` markers, and visual+audio timer alerts.

## Technical Context

**Language/Version**: Python 3.11+, TypeScript 5+

**Primary Dependencies**: Angular 22, Angular Material (M3 theming), FastAPI, Supabase (PostgreSQL + Storage), Redis, Apache ECharts, NgRx Signals

**Storage**: PostgreSQL (via Supabase) with Row Level Security and Materialized Views; Supabase Storage (presigned-URL uploads) for routine videos

**Testing**: pytest (backend), Jest (frontend), axe-core/Lighthouse (accessibility CI)

**Target Platform**: Cloudflare Pages (Frontend SPA), Cloud Container (FastAPI)

**Project Type**: Full-stack Web Application (SPA + REST API)

**Performance Goals**: Dashboard rendering < 2 seconds, API response < 300ms

**Constraints**: Strict RBAC per club, Immutable competition records, AI is read-only, WCAG 2.1 AA contrast in both themes, videos immutable after finalization, 90-day video retention, family-only video access (athlete/coaches/parents)

**Scale/Scope**: 1,000 concurrent users

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **API First**: Addressed via OpenAPI requirement (incl. video upload and timer endpoints).
- **Domain First**: Data models built before UI.
- **Test First**: Required for implementation phase.
- **Data Integrity**: Enforced by immutable records and tracking.
- **Security & Multi-Tenant**: Supabase RLS and JWT defined (incl. family-only video access with per-athlete RLS).
- **Accessibility**: WCAG AA contrast is an explicit design requirement (DR-007); dual visual+audio timer alert (FR-008).
- **Architecture**: Tech stack aligns strictly with Principles 13-15.
*(All checks passed)*

## Project Structure

### Documentation (this feature)

```text
specs/001-analytics-dashboard/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
└── tasks.md
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   ├── api/
│   ├── services/
│   │   ├── analytics/
│   │   ├── ai/
│   │   ├── predictions/
│   │   └── media/
│   │       └── video_upload.py      # FR-007 presigned-URL flow
│   ├── core/
│   └── supabase/migrations/          # incl. video_uploads, video_markers, routine_timers
├── tests/

frontend/
├── src/
│   ├── app/
│   │   ├── dashboards/
│   │   ├── shared/
│   │   │   ├── widgets/
│   │   │   │   ├── video-analysis/   # FR-007 native <video> + marker overlay
│   │   │   │   └── routine-timer/    # FR-008 NgRx Signals timer
│   │   │   └── theme/                # DR-001 ThemeService (M3 color-scheme)
│   │   └── store/
│   ├── styles/
│   │   └── themes/                   # DR-002/DR-005 M3 theme map + typography
│   └── tests/
```

**Structure Decision**: Web application (frontend + backend) to cleanly separate the Angular 22 SPA from the FastAPI analytics engine; media upload and theme services get dedicated modules reflecting the new FR-007/FR-008/DR scope.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

*(No violations. Standard web application separation applied as specified in architecture.)*
