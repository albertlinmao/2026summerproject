# Implementation Plan: Artistic Swimming Analytics Dashboard

**Branch**: `001-analytics-dashboard` | **Date**: 2026-08-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-analytics-dashboard/spec.md`

## Summary

Implement a full-stack Artistic Swimming Analytics Dashboard to track athlete progression, predict improvement, and support long-term development. The solution leverages Angular 22, FastAPI, and Supabase to provide secure, role-based views (keyed on the per-club membership roles `admin`, `coach`, `swimmer`, `parent`, `official`), utilizing Apache ECharts for visualization and phased machine learning models for predictive coaching insights. Expanded scope (2026-08-18) adds a video analysis widget with timestamp markers (FR-007), routine timers (FR-008), and a dual light/dark design system with deck-readable typography (DR-001 to DR-007). Clarified 2026-08-19: videos auto-delete after 90 days, family-only video access (person filmed/coaches/guardians), audio tones for `audio_cue` markers, visual+audio timer alerts, and Competition Results Browser widget (FR-009) with treeview mirroring swim-meets folder hierarchy, PDF links, and toggle between figure/routine results.

**Identity model (2026-08-26)**: superseded the login-centric model. A **person** is a human, a **club** is the tenant, and **membership is the edge**. There is no `club_id` on a person and a login is optional; roles are scoped per club, so one person may be a `swimmer` in one club and a `coach` in another. Authorization resolves from `as_club_membership` in the database, never from a single tenant claim. See [identity-contract.md](identity-contract.md) for the full vocabulary and claim contract.

## Technical Context

**Language/Version**: Python 3.11+, TypeScript 5+

**Primary Dependencies**: Angular 22, Angular Material (M3 theming), FastAPI, Supabase (PostgreSQL + Storage), Redis, Apache ECharts, NgRx Signals

**Storage**: PostgreSQL (via Supabase) with Row Level Security, Materialized Views, and pg_cron for scheduled tasks; Supabase Storage (presigned-URL uploads) for routine videos

**Testing**: pytest (backend), Jest (frontend), axe-core/Lighthouse (accessibility CI)

**Target Platform**: Cloudflare Pages (Frontend SPA), Cloud Container (FastAPI)

**Project Type**: Full-stack Web Application (SPA + REST API)

**Performance Goals**: Dashboard rendering < 2 seconds, API response < 300ms

**Constraints**: Membership-authoritative RBAC per club (`admin`/`coach`/`swimmer`/`parent`/`official`, roles resolved from `as_club_membership`; JWT claims are a cache only), immutable competition records, AI is read-only, WCAG 2.1 AA contrast in both themes, videos immutable after finalization, 90-day video retention, family-only video access (person filmed/coaches/guardians), public read access to competition results browser

**Blocking dependency**: the identity service's `public.membership` table declares `unique (tenant_id, user_id)`, which makes multi-club membership impossible. It must become `unique (tenant_id, user_id, role_id)` in `api/user-management` (a separate repository). Until it lands the dashboard behaves single-club in practice, while the RLS predicates already handle the multi-club case.

**Scale/Scope**: 1,000 concurrent users

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **API First**: Addressed via OpenAPI requirement (incl. video upload, timer endpoints, and competition results browser endpoints). `contracts/openapi.yaml` is the canonical contract; `api.yaml`/`api.yml` are subsets of it.
- **Domain First**: Data models built before UI. Identity is modelled as Person / Club / Club Membership / Person Link ([identity-contract.md](identity-contract.md)), with `as_athlete`/`as_coach` reduced to club-less views.
- **Test First**: Required for implementation phase.
- **Data Integrity**: Enforced by immutable records and tracking.
- **Security & Multi-Tenant**: Supabase RLS and JWT defined. RLS resolves authorization from `as_club_membership` through `app_*()` helpers; only the `sub` claim is trusted, `athlete_ids` and scalar `club_id` are forbidden. Includes family-only video access scoped to `video_uploads.person_id` (self / coach-of / guardian-of via `as_person_link`) and a competition results browser accessible to all authenticated users.
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
├── identity-contract.md   # authoritative: Person / Club / Membership + claim contract
├── quickstart.md
├── contracts/
│   ├── openapi.yaml       # canonical contract; api.yaml + api.yml are subsets
│   ├── api.yaml
│   └── api.yml
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
│   │       ├── video_upload.py      # FR-007 presigned-URL flow
│   │       └── results_browser.py   # FR-009 treeview + PDF resolution
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
│   │   │   │   ├── routine-timer/    # FR-008 NgRx Signals timer
│   │   │   │   └── results-browser/  # FR-009 treeview + PDF links
│   │   │   └── theme/                # DR-001 ThemeService (M3 color-scheme)
│   │   └── store/
│   ├── styles/
│   │   └── themes/                   # DR-002/DR-005 M3 theme map + typography
│   └── tests/
```

**Structure Decision**: Web application (frontend + backend) to cleanly separate the Angular 22 SPA from the FastAPI analytics engine; media upload, theme services, and competition results browser get dedicated modules reflecting the FR-007/FR-008/FR-009/DR scope.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

*(No violations. Standard web application separation applied as specified in architecture.)*
