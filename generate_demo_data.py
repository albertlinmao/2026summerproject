import psycopg2
import uuid
import random
from datetime import datetime, timedelta
import json

def main():
    conn = psycopg2.connect("postgres://postgres:d27096746169f71e6c16998af5dc5322c14c28a2@localhost:5432/postgres")
    conn.autocommit = True
    cur = conn.cursor()

    # 1. Ensure SST Club exists
    cur.execute("SELECT id FROM as_club WHERE code = 'SST';")
    club = cur.fetchone()
    if not club:
        club_id = str(uuid.uuid4())
        cur.execute("INSERT INTO as_club (id, name, code, city) VALUES (%s, 'Seattle Synchro', 'SST', 'Seattle');", (club_id,))
    else:
        club_id = club[0]
        
    # 2. Ensure Athletes exist
    athlete_names = ["Emma Johnson", "Olivia Davis", "Sophia Martinez", "Isabella Rodriguez", "Mia Smith", "Charlotte Lee"]
    athlete_ids = []
    
    for name in athlete_names:
        cur.execute("SELECT id FROM as_athlete WHERE name = %s AND club_id = %s;", (name, club_id))
        ath = cur.fetchone()
        if not ath:
            a_id = str(uuid.uuid4())
            cur.execute("INSERT INTO as_athlete (id, club_id, name) VALUES (%s, %s, %s);", (a_id, club_id, name))
            athlete_ids.append(a_id)
        else:
            athlete_ids.append(ath[0])

    # 3. Add SST Coach Sophie Lin
    cur.execute("SELECT id FROM as_coach WHERE name = 'Sophie Lin' AND club_id = %s;", (club_id,))
    coach = cur.fetchone()
    if not coach:
        coach_id = str(uuid.uuid4())
        cur.execute("INSERT INTO as_coach (id, club_id, name) VALUES (%s, %s, 'Sophie Lin');", (coach_id, club_id))
    else:
        coach_id = coach[0]

    # 4. Generate Raw Competition Data for Analytics Engine
    figures = ["Ballet Leg", "Barracuda", "Kip", "Swordfish"]
    
    # We need at least 5 records per athlete to trigger linear regression predictions
    # Let's generate 6 past meets
    meets = []
    base_date = datetime.now() - timedelta(days=180)
    
    # Needs a dummy event_id
    cur.execute("SELECT id FROM as_event LIMIT 1;")
    event_row = cur.fetchone()
    if not event_row:
        event_id = str(uuid.uuid4())
        cur.execute("INSERT INTO as_event (id, event_name, host_city, event_date) VALUES (%s, 'Demo Event', 'Seattle', %s);", (event_id, base_date.date()))
    else:
        event_id = event_row[0]

    for i in range(6):
        meet_id = str(uuid.uuid4())
        meet_date = base_date + timedelta(days=30 * i)
        meet_name = f"Demo Meet {i+1}"
        meets.append({"id": meet_id, "date": meet_date, "name": meet_name})
        
        # Insert meet into as_meet
        cur.execute("""
            INSERT INTO as_meet (id, event_id, name, meet_date)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING;
        """, (meet_id, event_id, meet_name, meet_date.date()))
        
    # Clear old demo results for these athletes to avoid duplicates stacking endlessly
    cur.execute("DELETE FROM as_meet_figure_result WHERE team_code = 'SST';")
    cur.execute("DELETE FROM as_meet_routine_result WHERE team_code = 'SST';")
    
    print("Generating raw competition results...")
    
    for meet in meets:
        # Figure Results
        for idx, name in enumerate(athlete_names):
            # Simulate a trend: starting lower and gradually improving
            base_score = 55.0 + (idx * 2) + (meets.index(meet) * 1.5)
            # Add some randomness
            actual_score = round(base_score + random.uniform(-2, 2), 2)
            
            # Generate individual figure scores (jsonb)
            figure_scores = {
                fig: round(actual_score + random.uniform(-3, 3), 2)
                for fig in figures
            }
            # Make Kip consistently the weakest for Mia Smith, Swordfish for Emma, etc.
            if name == "Mia Smith":
                figure_scores["Kip"] -= 5.0
            elif name == "Emma Johnson":
                figure_scores["Swordfish"] -= 4.0
            elif name == "Olivia Davis":
                figure_scores["Ballet Leg"] -= 4.5
                
            cur.execute("""
                INSERT INTO as_meet_figure_result 
                (id, meet_id, team_code, athlete_name, figure_score, figure_scores, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                str(uuid.uuid4()), 
                meet["id"], 
                'SST', 
                name, 
                actual_score, 
                json.dumps(figure_scores),
                meet["date"]
            ))

        # Routine Result for the team
        team_athletes_json = json.dumps([{"name": n} for n in athlete_names])
        routine_score = round(65.0 + (meets.index(meet) * 2) + random.uniform(-1, 2), 2)
        
        cur.execute("""
            INSERT INTO as_meet_routine_result 
            (id, meet_id, team_code, team_athletes, routine_score, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            str(uuid.uuid4()),
            meet["id"],
            'SST',
            team_athletes_json,
            routine_score,
            meet["date"]
        ))

    print("Successfully generated foundational raw data for Coach Sophie Lin's dashboard.")
    print(f"Club ID: {club_id}")
    print(f"Coach ID: {coach_id}")
    print("The backend login endpoint (POST /api/auth/login) resolves these IDs automatically.")

if __name__ == '__main__':
    main()
