import psycopg2
conn = psycopg2.connect("postgres://postgres:d27096746169f71e6c16998af5dc5322c14c28a2@localhost:5432/postgres")
cur = conn.cursor()

for t in ['as_athlete', 'as_predictive_insights', 'as_coaching_recommendations']:
    cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{t}';")
    print(f"--- {t} ---")
    for col in cur.fetchall():
        print(f"  {col[0]}: {col[1]}")
