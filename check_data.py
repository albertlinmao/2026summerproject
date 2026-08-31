import psycopg2
conn = psycopg2.connect('postgres://postgres:d27096746169f71e6c16998af5dc5322c14c28a2@localhost:5432/postgres')
cur = conn.cursor()

# Check club
cur.execute("SELECT id, name, code FROM as_club WHERE code = 'SST'")
club = cur.fetchone()
print('Club:', club)

# Check athletes
athlete_club_id = club[0]
cur.execute("SELECT id, name FROM as_athlete WHERE club_id = %s", (athlete_club_id,))
print('Athletes:')
for row in cur.fetchall():
    print(' ', row)

# Check figure results
cur.execute("SELECT id, athlete_name, team_code FROM as_meet_figure_result WHERE team_code = 'SST' LIMIT 5")
print('Figure results (first 5):')
for row in cur.fetchall():
    print(' ', row)

# Check routine results
cur.execute("SELECT id, team_athletes FROM as_meet_routine_result WHERE team_code = 'SST' LIMIT 2")
print('Routine results (first 2):')
for row in cur.fetchall():
    print(' ', row)

# Check coach
cur.execute("SELECT id, name FROM as_coach WHERE club_id = %s", (athlete_club_id,))
print('Coach:')
for row in cur.fetchall():
    print(' ', row)