import psycopg2

def main():
    try:
        conn = psycopg2.connect("postgres://postgres:d27096746169f71e6c16998af5dc5322c14c28a2@localhost:5432/postgres")
        conn.autocommit = True
        cur = conn.cursor()
        
        cur.execute("ALTER TABLE IF EXISTS public.club RENAME TO as_club;")
        print("Successfully renamed 'club' table to 'as_club'.")
        
        cur.close()
        conn.close()
    except Exception as e:
        print("Failed to rename table:", e)

if __name__ == "__main__":
    main()
