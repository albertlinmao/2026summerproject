# Ingest figure PDFs into a local Supabase instance
  
## 1. Create the tables in your Supabase project
  
The local stack is the self-hosted Docker Compose project in `supabase/` — **there is no Supabase
SQL editor or published Studio in this setup** (the base compose file maps no UI port, and the dev
overlay that would publish one cannot build). Run the schema through the container's `psql` instead,
from the `supabase/` directory:

```bash
cd supabase
docker compose up -d
```

Apply `20260827_all_schema_from_scratch.sql` — a single script that creates every table, view,
materialized view, function, trigger, index, RLS policy and grant, including `as_event`, `as_meet`,
`as_figure`, `as_meet_judge_panel`, `as_meet_figure_result`, `as_meet_routine_result` and the
identity tables:

```bash
Get-Content backend/supabase/migrations/20260827_all_schema_from_scratch.sql -Raw | \
  docker exec -i supabase-db psql -v ON_ERROR_STOP=1 -U postgres -d postgres
```

`20260826_person_identity_migration.sql` is **not** part of this step. It is a one-way *data*
transform for databases that still hold the legacy `as_athlete` / `as_coach` tables, and it is the
only way to convert them. A fresh database never needs it.

`sql/create_figures_table.sql` is the earlier standalone version of the same tables. Do not run
both: the migration already creates them, and running the standalone file afterwards will fail on
existing objects. Prefer the migration.
  
## 2. Configure environment variables
  
Create a `.env` file in the project root with:
  
```env
SUPABASE_URL=http://localhost:8000
SUPABASE_KEY=your-service-role-or-anon-key
```
  
`http://localhost:8000` is **Kong**, the only HTTP entry point to the Docker stack (`KONG_HTTP_PORT`
in `supabase/.env`). The Supabase CLI's `54321` does not apply. A hosted project would instead use
`https://your-project.supabase.co`.
  
The loaders need the **service-role** key, because they write RLS-protected tables.
  

## 3. Install dependencies

Use your virtualenv and run:

```bash
pip install -r requirements.txt
```

## 4. Run the ingestion script

Pass the detailed figure PDF path (adjust path to your workspace):

```bash
python scripts/ingest_figures.py "swim-meets/2026/YouthChampionshipand12uinvitational/figure/Detailed_-_Age_Group_12_and_Under_Figures.pdf"
```

To run without inserting data to verify parsing logic:
```bash
python scripts/ingest_figures.py "swim-meets/2026/YouthChampionshipand12uinvitational/figure/Detailed_-_Age_Group_12_and_Under_Figures.pdf" --dry-run
```

## 5. Data model notes

- The data is now fully relational.
- Meet and Event data are inserted first. 
- Figures are inserted and linked to the Meet.
- Judges are inserted and linked to the Meet and Figures.
- Each row of `as_meet_figure_result` includes the athlete's information as well as `figure_scores` serialized as JSONB to preserve all judge sub-scores and calculated routine values.

## 6. Notes and improvements

- The current parser is tuned to the `Detailed_-_Age_Group_12_and_Under_Figures.pdf` layout. If other PDFs deviate, the parser may need adjustment.
- If text extraction fails or formatting changes, consider adding OCR or explicit `pdfplumber` table extraction.
