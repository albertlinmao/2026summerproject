# Data Model: Artistic Swimming Analytics Dashboard

## Core Entities

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

### Competition Result
The core factual data point used for aggregation. Immutable once published.
- `id` (UUID): Primary key.
- `athlete_id` (UUID): Foreign key to Athlete.
- `meet_id` (UUID): Reference to the meet event.
- `figure_score` (Numeric): Score received for figures.
- `routine_score` (Numeric): Score received for routines.
- `date` (Date): When the competition took place.
- `created_at` (Timestamp): Record creation time.

### Daily Aggregations (Materialized View)
Pre-calculated statistics for dashboard rendering.
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

### Video Upload (FR-007)
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

### Video Marker (FR-007)
Timestamp markers linked to scoring moments on a video.
- `id` (UUID): Primary key.
- `video_id` (UUID): Foreign key to Video Upload (cascade delete).
- `time_offset` (Numeric): Marker position in seconds from video start (indexed with `video_id`).
- `marker_type` (Enum): `audio_cue`, `figure`, `timing_mark`.
- `figure_id` (String, optional): Linked figure category if marker is a figure.
- `label` (String, optional): Display label.
- `created_by` (UUID): User reference.
- `created_at` (Timestamp): Record creation time.

### Routine Timer (FR-008)
Client-side routine duration timer state for pool-deck use.
- `id` (UUID): Primary key.
- `club_id` (UUID): Foreign key to Club (row-level security scope).
- `title` (String, optional): Routine name.
- `duration_seconds` (Numeric): Target routine duration.
- `created_by` (UUID): User reference.
- `created_at` (Timestamp): Record creation time.
- Note: Running/paused state is transient client state managed with NgRx Signals; only saved configurations persist.

## Relationships
- A `Club` has many `Athlete`s and `Coach`es.
- An `Athlete` has many `Competition Result`s, `Predictive Insight`s, and `Coaching Recommendation`s.
- A `Video Upload` has many `Video Marker`s; a `Video Marker` belongs to one `Video Upload`.

## Validation & Rules
- **Immutability**: `Competition Result` records cannot be updated after creation (amendments required).
- **Isolation**: Queries must filter by `club_id` matching the authenticated user's token claims.
- **Video privacy (family access)**: `Video Upload` and `Video Marker` access MUST be restricted to the filmed athlete, their coaches, and their parents. RLS predicates resolve the requesting user's relationship to `video_uploads.athlete_id` (self, coach-of, parent-of) using Multi-Tenant User Service claims; storage objects in Supabase Storage must use the same access scope.
- **Video immutability**: Uploaded video objects and `storage_path` cannot be changed after finalization; markers can be added/removed.
- **Video retention**: Videos older than 90 days (per `created_at`) are auto-deleted together with their markers and storage objects.
