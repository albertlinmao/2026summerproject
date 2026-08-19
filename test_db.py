import psycopg2
try:
    conn = psycopg2.connect("postgres://postgres:d27096746169f71e6c16998af5dc5322c14c28a2@localhost:5432/postgres")
    print("Connected")
    conn.close()
except Exception as e:
    print("Error:", e)
