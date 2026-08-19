import psycopg2
import uuid

def main():
    conn = psycopg2.connect("postgres://postgres:d27096746169f71e6c16998af5dc5322c14c28a2@localhost:5432/postgres")
    conn.autocommit = True
    cur = conn.cursor()

    # 1. Create the club table if it doesn't exist
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS public.as_club (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        description TEXT,
        city TEXT,
        website TEXT,
        email TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        opid TEXT
    );
    """
    cur.execute(create_table_sql)
    print("Club table created (or already exists).")

    # 2. Scan as_meet_figure_result and as_meet_routine_result to find SST teams
    # We will look for team_code = 'SST' or team_code containing 'SST'
    cur.execute("SELECT DISTINCT team_name, team_code FROM public.as_meet_figure_result WHERE team_code ILIKE '%SST%';")
    figure_teams = cur.fetchall()
    
    cur.execute("SELECT DISTINCT team_name, team_code FROM public.as_meet_routine_result WHERE team_code ILIKE '%SST%';")
    routine_teams = cur.fetchall()

    all_teams = set(figure_teams + routine_teams)
    print("Found teams:", all_teams)

    # 3. Add 'SST' club to the club table
    for team_name, team_code in all_teams:
        if 'SST' in team_code.upper():
            try:
                cur.execute(
                    "INSERT INTO public.club (name, code, city) VALUES (%s, %s, %s) ON CONFLICT (code) DO NOTHING;",
                    (team_name, team_code, 'Seattle, WA')
                )
                print(f"Inserted/Verified club: {team_name} ({team_code})")
            except Exception as e:
                print(f"Failed to insert {team_name}:", e)

    # If no data found in the tables, let's insert it manually based on datamodeling requirement
    if not all_teams:
        print("No SST teams found in parsed results, inserting default SST club.")
        cur.execute(
            "INSERT INTO public.club (name, code, city) VALUES (%s, %s, %s) ON CONFLICT (code) DO NOTHING;",
            ('SEATTLE SYNCHRONIZED SWIM TEAM', 'SST', 'Seattle, WA')
        )
        print("Inserted default SST club.")

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
