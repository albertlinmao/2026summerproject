import psycopg2

try:
    conn = psycopg2.connect("postgres://postgres:d27096746169f71e6c16998af5dc5322c14c28a2@localhost:5432/postgres")
    cur = conn.cursor()
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
    print("Tables found:", [t[0] for t in cur.fetchall()])
except Exception as e:
    print("DB error:", e)
