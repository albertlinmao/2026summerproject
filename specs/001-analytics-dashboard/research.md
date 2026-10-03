# Research: Artistic Swimming Analytics Dashboard

## Decision: Materialized View Refresh Strategy
- **Context**: The dashboard requires daily score aggregations for fast rendering, but scores are imported asynchronously.
- **Decision**: On-demand refresh with caching when first accessed.
- **Rationale**: Based on the clarification in the spec, this balances performance and freshness, ensuring users get up-to-date data without overloading the database with scheduled or event-driven refreshes.
- **Alternatives considered**: Event-driven (refresh on import) and scheduled batch refresh.

## Decision: Identity API Integration Fallback
- **Context**: The `001-multi-tenant-user-api` handles all identity management.
- **Decision**: Display a full-page critical error with a retry button.
- **Rationale**: Mandated by security requirements and recent clarifications to prevent unauthorized access or confusing state due to missing claims.
- **Alternatives considered**: Read-only mode with cached JWT, generic redirect.

## Decision: Data Visualization Library
- **Context**: The frontend needs to visualize score distributions, radar charts for figures, and trend lines.
- **Decision**: Apache ECharts
- **Rationale**: Specifically mandated by the Constitution (Principle 13) for the Angular 22 SPA. It handles large datasets efficiently and provides built-in support for radar and scatter plots required for figure and routine analysis.
- **Alternatives considered**: Chart.js, D3.js (rejected due to constitution constraint).

## Decision: Video Storage & Upload Flow (FR-007)
- **Context**: The video analysis widget must allow coaches to upload routine videos and attach timestamp markers for figure/routine scoring moments.
- **Decision**: Supabase Storage with presigned-URL uploads (`POST /uploads/sign` → client PUT → `POST /uploads/finalize` verifying size/type via HEAD). Store the storage object key, never the URL, so providers can be swapped later.
- **Rationale**: Keeps the whole stack on Supabase with a single auth model and RLS join between storage objects and owning rows; per-club private videos are low-traffic, so egress savings of R2 are not needed yet.
- **Alternatives considered**: Cloudflare R2/other S3 (migrate only if egress dominates), direct client upload (rejected: loses auth/MIME/size validation).

## Decision: Timestamp Marker UI (FR-007)
- **Context**: Coaches need frame-by-frame playback with timestamp markers linked to scoring moments, with play/pause and marker controls always visible.
- **Decision**: Native `<video>` element with a custom Angular overlay — absolutely-positioned marker divs over the progress bar (`left = (offset/duration)*100%`), click-to-seek via `currentTime`. Fullscreen is applied to the wrapper container so custom controls remain visible; native controls hidden; controls never auto-hide.
- **Rationale**: Marker plugins for video.js are stale (video.js v4–7 era) and upgrade-fragile; routine videos (3–5 min MP4/H.264) need no HLS, so video.js adds little. Custom overlay keeps pool-deck UX requirements (≥56px touch targets, high-contrast filled icons, persistent sticky controls) fully controllable.
- **Alternatives considered**: Video.js + marker plugins (stale), HLS streaming (unnecessary for short routine videos).

## Decision: Dual Light/Dark Theme System (DR-001, DR-002, DR-007)
- **Context**: Dashboard must support user-selectable light and dark themes (deep navy/ocean teal primaries, white or dark slate gray backgrounds, coral/gold accents), WCAG 2.1 AA contrast in both.
- **Decision**: Angular Material M3 `mat.theme()` Sass API (current standard in Angular 22) with `theme-type: color-scheme` so tokens emit as CSS variables wrapped in `light-dark()`; `color-scheme` on `<html>` flips the entire system with zero duplication. Custom palettes generated via `ng generate @angular/material:theme-color` (navy → primary, teal → tertiary), coral/gold accents via `mat.theme-overrides`. Three-state preference (`system|light|dark`) in localStorage, applied by a synchronous inline script in `index.html` before first paint (kills FOUC); Angular `ThemeService` (signals) manages `data-theme` + `color-scheme`.
- **Rationale**: Single theme definition avoids duplication of two explicit themes; inline script prevents flash of wrong theme on pool-deck devices; contrast-tuned palettes from the theme-color schematic plus CI axe-core/Lighthouse checks enforce DR-007.
- **Alternatives considered**: Two explicit body-class themes (valid pre-v19, more duplication), CSS-only theme, pure `prefers-color-scheme` media queries (breaks manual toggle).

## Decision: Deck-Readable Typography (DR-005)
- **Context**: Scores and timers must be readable across the pool deck; fonts must be Inter or Roboto.
- **Decision**: Inter/Roboto as `plain-family`/`brand-family` in the theme map; score/timer styles built on display-scale tokens (`var(--mat-sys-display-large)`); `font-variant-numeric: tabular-nums` to stop timer digits jittering; `clamp()` for distance readability.
- **Rationale**: Theme-map/token customization is more maintainable than scattered utility classes and stays consistent with Material typography scales.
- **Alternatives considered**: Scattered utility classes (rejected: hard to maintain), default Material type scale (rejected: insufficiently large for pool-deck readability).

## Decision: Video Retention Policy (FR-007)
- **Context**: Uploaded routine videos accumulate storage; no lifecycle was defined.
- **Decision**: Auto-delete videos 90 days after upload (competition season retention), via scheduled cleanup job plus RLS/API-level enforcement. Markers cascade-delete with their video.
- **Rationale**: Aligns retention with a competition season, bounds storage cost per club, and is simple to implement as a daily scheduled delete on `created_at < now() - interval '90 days'`.
- **Alternatives considered**: Manual-delete-only (unbounded storage), 1-year retention (too long for routine video value), keep forever (storage grows unbounded).

## Decision: Video Access Control — Family Access (FR-007)
- **Context**: Routine videos depict athletes; access scope was unspecified beyond club isolation.
- **Decision**: Per-video access restricted to the person filmed, their coaches, and their guardians. Each `video_uploads` row carries a `person_id` link, and the caller's relationship to that person is resolved in the database, never from token claims: **self** (the row's `person_id` equals the caller's `person_id` *and* the caller holds an active `swimmer` membership in the row's club), **coach-of** (active `coach`/`admin` membership in that club), or **guardian-of** (an `as_person_link` row of kind `parent`/`guardian` joining the caller to that person in the same club).
- **Rationale**: Protects footage of minors (privacy-sensitive) and keeps the coach analysis workflow intact, while remaining expressible without an account for every minor: the child needs only an `as_person` row plus a guardian `as_person_link`, and only the parent authenticates. An earlier design resolved guardianship from an `athlete_ids` JWT claim, which baked the edge into the token — it went stale on transfer or offboarding, could not express coach-of or self, and forced account creation for children. `as_person_link` also carries its own `club_id`, so a guardian relationship in one club never leaks into another. The identical predicate is applied to Supabase Storage objects.
- **Alternatives considered**: Club-wide access (over-exposes footage), uploader-only + admins (breaks athlete/parent access to their own routines), `athlete_ids` claim (rejected: stale, unable to express coach-of or self), login per minor (rejected: privacy and onboarding cost).

## Decision: Marker & Timer Audio Behavior (FR-007, FR-008)
- **Context**: Markers have types `audio_cue`/`figure`/`timing_mark`; timer end alert unspecified. Pool deck is noisy.
- **Decision**: `audio_cue` markers emit a short tone when playback reaches the marker's time offset (in addition to click-to-seek for all markers); routine timers alert with both a visual flash and an audible beep at zero.
- **Rationale**: Audio provides hands-free timing reference for coaches during routines; dual visual+audio timer alert covers noisy-deck use and silent/hard-of-hearing contexts. Web Audio API for tones (no audio assets needed).
- **Alternatives considered**: Visual-only markers/timers (missed on loud decks), audio-only timer alert (fails accessibility).

## Decision: Competition Results Browser Treeview (FR-009)
- **Context**: Users need to browse competition results organized by the exact `swim-meets/` folder hierarchy (Year > Meet > Figure/Routine > PDF type) with database-backed results and PDF links.
- **Decision**: Backend service scans the `swim-meets/` directory at startup/cached interval to build an in-memory tree structure. API endpoint `GET /results/tree` returns the tree nodes with metadata (path, type, meet_id, has_figure_results, has_routine_results, pdf_summary_path, pdf_detailed_path). Frontend uses Angular CDK virtual scroll tree with lazy-loading children. Toggle between figure/routine results via tab component switching the displayed data table.
- **Rationale**: Exact folder mirror matches user mental model; database results joined via `source_file` field in `as_meet_figure_result`/`as_meet_routine_result`; PDF paths resolved from filesystem structure. No separate tree table needed — structure is derived from filesystem + DB join.
- **Alternatives considered**: Separate tree table in DB (sync complexity), recursive CTE on filesystem metadata table (over-engineering), flat list with filters (loses hierarchical navigation).

## Decision: PDF File Serving (FR-009)
- **Context**: Treeview nodes must link to original PDF files in `swim-meets/` folder (Summary and Detailed PDFs for each meet/event).
- **Decision**: Serve PDFs via FastAPI endpoint `GET /results/pdf/{year}/{meet}/{type}/{filename}` with `FileResponse` and `media_type=application/pdf`. Backend validates path traversal (resolve absolute path, ensure within `swim-meets/` root). In production, configure Cloudflare Workers or nginx to serve static PDFs directly from the mounted volume for performance.
- **Rationale**: Keeps PDF access authenticated (via JWT middleware) while leveraging FastAPI's efficient file streaming. Production static serving offloads to CDN/edge.
- **Alternatives considered**: Supabase Storage for PDFs (duplicate storage, sync complexity), direct filesystem links (breaks auth, CORS), presigned URLs (unnecessary for non-expiring public-ish PDFs).

## Decision: Figure/Routine Toggle in Results Browser (FR-009)
- **Context**: Users need to switch between viewing figure results and routine results for the same meet/event.
- **Decision**: Frontend tab component with two states (`figures`, `routines`). When a tree node for a figure meet is selected, fetch `/results/figure/{meet_id}` returning paginated `as_meet_figure_result` data. When routine meet selected, fetch `/results/routine/{meet_id}` returning paginated `as_meet_routine_result` data. Tab state persisted in widget `tree_state` JSONB.
- **Rationale**: Separate API endpoints match the separate Supabase tables; pagination handles large result sets; tab state restoration improves UX.
- **Alternatives considered**: Single combined endpoint with type filter (more complex response), client-side filtering (loads all data).
