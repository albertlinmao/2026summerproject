import psycopg2
conn = psycopg2.connect("postgres://postgres:d27096746169f71e6c16998af5dc5322c14c28a2@localhost:5432/postgres")
cur = conn.cursor()
cur.execute("SELECT DISTINCT team_code, athlete_name FROM as_meet_figure_result WHERE team_code ILIKE '%SST%';")
rows = cur.fetchall()
print(f"Found {len(rows)} athletes in as_meet_figure_result for SST:")
for r in rows[:10]:
    print(r)
