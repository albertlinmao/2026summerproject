# Ingest figure PDFs into a local Supabase instance

## 1. Create the tables in your Supabase project

Open the Supabase SQL editor and run the updated schema in `sql/create_figures_table.sql`.
This will create the newly normalized tables:
- `as_event`
- `as_meet`
- `as_figure`
- `as_figure_judge_panel`
- `as_meet_figure_result`

## 2. Configure environment variables

Create a `.env` file in the project root with:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-or-anon-key
```

*(Note: If using local Supabase via Docker Desktop, the URL will likely be `http://localhost:8000`)*

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
