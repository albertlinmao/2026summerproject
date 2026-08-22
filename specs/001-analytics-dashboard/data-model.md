# Data Model: Artistic Swimming Analytics Dashboard

## Core Entities (Existing Supabase Tables)

These tables already exist in Supabase with data imported from PDF files in the `swim-meets/` folder.

### as_event
Represents a competition event (e.g., "2026 Junior Olympic Championships").
- `id` (UUID): Primary key.
- `event_name` (Text): Name of the event.
- `host_city` (Text): Host city.
- `event_date` (Date): Event date.
- `created_at` (Timestamp): Record creation time.

### as_meet
Represents a specific meet within an event (e.g., "Youth Figure Competition").
- `id` (UUID): Primary key.
- `event_id` (UUID): Foreign key to `as_event` (cascade delete).
- `name` (Text): Meet name.
- `meet_date` (Date): Meet date.
- `created_at` (Timestamp): Record creation time.

### as_figure
Defines a figure performed at a meet with its degree of difficulty.
- `id` (UUID): Primary key.
- `meet_id` (UUID): Foreign key to `as_meet` (cascade delete).
- `figure_code` (Text): Full figure code.
- `figure_code_short` (Text): Short figure code.
- `name` (Text): Figure name.
- `degree_difficulty` (Numeric): Degree of difficulty.
- `created_at` (Timestamp): Record creation time.

### as_meet_judge_panel
Judge panel configuration for a figure at a meet.
- `id` (UUID): Primary key.
- `meet_id` (UUID): Foreign key to `as_meet` (cascade delete).
- `figure_id` (UUID): Foreign key to `as_figure` (cascade delete).
- `figure_code_short` (Text): Short figure code.
- `panel_name` (Text): Panel name.
- `panel` (JSON): Judge panel configuration.
- `created_at` (Timestamp): Record creation time.

### as_meet_figure_result
Individual athlete figure results for a meet.
- `id` (UUID): Primary key.
- `meet_id` (UUID): Foreign key to `as_meet` (cascade delete).
- `rank` (Text): Rank placement.
- `draw` (Text): Draw number.
- `team_code` (Text): Team code.
- `team_name` (Text): Team name.
- `athlete_name` (Text): Athlete name.
- `athlete_birth_year` (Integer): Athlete birth year.
- `penalty` (Text): Penalty applied.
- `total_score` (Numeric): Total score for figures (kept for consistency with routines).
- `figure_score` (Numeric): Weighted total score used for ranking.
- `figure_scores` (JSONB): Detailed scores per figure.
- `source_file` (Text): Source PDF filename.
- `created_at` (Timestamp): Record creation time.

### as_meet_routine_result
Team/athlete routine results for a meet.
- `id` (UUID): Primary key.
- `meet_id` (UUID): Foreign key to `as_meet` (cascade delete).
- `rank` (Text): Rank placement.
- `draw` (Text): Draw number.
- `team_code` (Text): Team code.
- `team_name` (Text): Team name.
- `team_athletes` (JSONB): Athletes in the routine.
- `total_difficulty` (JSONB): Total difficulty breakdown.
- `routine_scores` (JSONB): Detailed routine scores.
- `element_total` (Numeric): Elements score total.
- `artisticimpression_total` (Numeric): Artistic impression total.
- `synchronization_total` (Numeric): Synchronization total.
- `routine_score` (Numeric): Final routine score.
- `source_file` (Text): Source PDF filename.
- `created_at` (Timestamp): Record creation time.

---

## Reference Entities (Managed by Multi-Tenant User API)

### Club (Reference)
Used for row-level security and data isolation (Tenant).
- `id` (UUID): Primary key, managed by `001-multi-tenant-user-api`.
- `name` (String): Display name of the club.

### Athlete (Reference)
Represents a swimmer. Profile data is external; this stores references for aggregating scores.
- `id` (UUID): Primary key, managed by user API.
- `club_id` (UUID): Foreign key to Club.
- `name` (String): Athlete's display name.

### Coach (Reference)
Represents a team leader.
- `id` (UUID): Primary key, managed by user API.
- `club_id` (UUID): Foreign key to Club.
- `name` (String): Coach's display name.

---

## Analytical Entities (Dashboard-Specific)

### Daily Aggregations (Materialized View)
Pre-calculated statistics for dashboard rendering, derived from `as_meet_figure_result` and `as_meet_routine_result`.
- `athlete_id` (UUID): Foreign key to Athlete.
- `date` (Date): Aggregation date.
- `avg_figure_score` (Numeric): Calculated average figure score up to this date.
- `avg_routine_score` (Numeric): Calculated average routine score up to this date.
- `rolling_trend` (Numeric): Moving average indicator.

### Predictive Insight
Generated forecasts associated with an athlete.
- `athlete_id` (UUID): Foreign key to Athlete.
- `next_score_prediction` (Numeric): Expected score at the next competition.
- `plateau_risk` (Boolean): Flag indicating if the athlete is stagnating.
- `confidence_interval` (Numeric): Model confidence score.

### Coaching Recommendation
AI-generated natural language feedback.
- `athlete_id` (UUID): Foreign key to Athlete.
- `recommendation_text` (String): Natural language practice focus.
- `generated_at` (Timestamp): When the AI generated this insight.
- `weakest_figure` (String): Categorized figure needing improvement.

---

## Video Analysis Entities (FR-007)

### Video Upload
Uploaded routine videos for frame-by-frame analysis.
- `id` (UUID): Primary key.
- `club_id` (UUID): Foreign key to Club (row-level security scope).
- `athlete_id` (UUID): Foreign key to Athlete appearing in the video (required for family-access RLS).
- `uploaded_by` (UUID): Coach/athlete user reference.
- `storage_path` (String): Storage object key in Supabase Storage (never the URL; provider-swappable).
- `mime_type` (String): Video MIME type (e.g., `video/mp4`).
- `size_bytes` (Integer): File size in bytes.
- `duration_seconds` (Numeric): Video duration in seconds.
- `status` (Enum): Upload lifecycle — `uploading`, `uploaded`, `ready`.
- `created_at` (Timestamp): Record creation time.
- **Retention**: Rows and storage objects are auto-deleted 90 days after `created_at` (scheduled cleanup job; markers cascade-delete).

### Video Marker
Timestamp markers linked to scoring moments on a video.
- `id` (UUID): Primary key.
- `video_id` (UUID): Foreign key to Video Upload (cascade delete).
- `time_offset` (Numeric): Marker position in seconds from video start (indexed with `video_id`).
- `marker_type` (Enum): `audio_cue`, `figure`, `timing_mark`.
- `figure_id` (String, optional): Linked figure category if marker is a figure.
- `label` (String, optional): Display label.
- `created_by` (UUID): User reference.
- `created_at` (Timestamp): Record creation time.

---

## Routine Timer Entity (FR-008)

### Routine Timer
Client-side routine duration timer state for pool-deck use.
- `id` (UUID): Primary key.
- `club_id` (UUID): Foreign key to Club (row-level security scope).
- `title` (String, optional): Routine name.
- `duration_seconds` (Numeric): Target routine duration.
- `created_by` (UUID): User reference.
- `created_at` (Timestamp): Record creation time.
- Note: Running/paused state is transient client state managed with NgRx Signals; only saved configurations persist.

---
 
## Competition Results Browser Widget (FR-009)
 
### Competition Results Browser Widget
Modular dashboard widget providing a treeview browser over the `swim-meets/` folder hierarchy with database-backed results and PDF links.
- `widget_id` (UUID): Primary key (dashboard widget instance).
- `club_id` (UUID): Foreign key to Club (row-level security scope for widget placement).
- `user_id` (UUID): User who added the widget (for personalization).
- `tree_state` (JSONB): Persisted tree expansion/collapse state per user.
- `active_tab` (Enum): `figures` | `routines` — currently selected result type.
- `selected_node_path` (Text, optional): Currently selected tree node path (e.g., `2026/JuniorOlympicChampionships/figure/Summary`).
- `created_at` (Timestamp): Record creation time.
- `updated_at` (Timestamp): Last modification time.
- Note: The treeview structure is derived from the filesystem at runtime; no separate tree table needed. PDF links are resolved by mapping `source_file` in result tables to filesystem paths.
 
---
 
## Relationships
- A `Club` has many `Athlete`s and `Coach`es.
- An `Athlete` has many `Daily Aggregation`s, `Predictive Insight`s, and `Coaching Recommendation`s.
- An `as_event` has many `as_meet`s.
- An `as_meet` has many `as_figure`s, `as_meet_judge_panel`s, `as_meet_figure_result`s, and `as_meet_routine_result`s.
- An `as_figure` has many `as_meet_judge_panel`s.
- A `Video Upload` has many `Video Marker`s; a `Video Marker` belongs to one `Video Upload`.

---

## Data Integration Notes
- **Athlete Linking**: `as_meet_figure_result.athlete_name` and `as_meet_routine_result.team_athletes` contain athlete names. These must be matched to `Athlete` records (managed externally) for dashboard aggregation. Matching strategy: fuzzy name + birth year + club/team_code.
- **Team/Club Linking**: `team_code`/`team_name` in results map to `Club` records via external reference.
- **Immutability**: Supabase result tables (`as_meet_figure_result`, `as_meet_routine_result`) are immutable once imported (amendments require re-import).
- **Isolation**: Dashboard queries must filter by `club_id` matching the authenticated user's token claims (resolved via Multi-Tenant User Service).

---

## Validation & Rules
- **Immutability**: `as_meet_figure_result` and `as_meet_routine_result` records cannot be updated after import (amendments require re-import from source PDF).
- **Isolation**: Queries must filter by `club_id` matching the authenticated user's token claims.
- **Video privacy (family access)**: `Video Upload` and `Video Marker` access MUST be restricted to the filmed athlete, their coaches, and their parents. RLS predicates resolve the requesting user's relationship to `video_uploads.athlete_id` (self, coach-of, parent-of) using Multi-Tenant User Service claims; storage objects in Supabase Storage must use the same access scope.
- **Video immutability**: Uploaded video objects and `storage_path` cannot be changed after finalization; markers can be added/removed.
- **Video retention**: Videos older than 90 days (per `created_at`) are auto-deleted together with their markers and storage objects.