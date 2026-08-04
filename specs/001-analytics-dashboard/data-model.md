# Data Model: Artistic Swimming Analytics Dashboard

## Core Entities

### Athlete
Represents a swimmer.
- `id` (UUID, Primary Key)
- `club_id` (UUID, Foreign Key)
- `first_name`, `last_name` (String)
- `date_of_birth` (Date)
- `active` (Boolean)
- **Relationships**: Belongs to a `Club`, has many `Competition Result`s, has many `Predictive Insight`s.

### Coach
Represents a team leader.
- `id` (UUID, Primary Key)
- `club_id` (UUID, Foreign Key)
- `user_id` (UUID, Supabase Auth Reference)
- `level` (String)
- **Relationships**: Belongs to a `Club`, oversees many `Athlete`s.

### Competition Result
Core factual data point. Immutable once published.
- `id` (UUID, Primary Key)
- `athlete_id` (UUID, Foreign Key)
- `meet_name` (String)
- `date` (Date)
- `event_type` (Enum: Figure, Technical Routine, Free Routine)
- `score` (Decimal)
- `difficulty`, `execution`, `artistic_impression` (Decimal, optional)
- **Relationships**: Belongs to an `Athlete`.

### Predictive Insight
Generated forecasts (e.g., next score, plateau risk).
- `id` (UUID, Primary Key)
- `athlete_id` (UUID, Foreign Key)
- `generated_at` (Timestamp)
- `insight_type` (Enum: Score Forecast, Plateau Risk, Baseline Average)
- `projected_score` (Decimal)
- `confidence_score` (Decimal)
- **Relationships**: Belongs to an `Athlete`.

### Coaching Recommendation
AI-generated natural language feedback.
- `id` (UUID, Primary Key)
- `athlete_id` (UUID, Foreign Key)
- `coach_id` (UUID, Foreign Key)
- `generated_at` (Timestamp)
- `content` (Text)
- `focus_areas` (Array of Strings)
- **Relationships**: Belongs to an `Athlete` and `Coach`.

## Database Rules

- **Row Level Security (RLS)**: Every table MUST have RLS enabled based on `club_id`.
- **Immutability**: `Competition Result` records cannot be UPDATED. Corrections must be handled via soft-deletes and inserts (audit trailing).