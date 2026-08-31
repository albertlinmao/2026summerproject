import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from src.core.database import get_supabase
supabase = get_supabase()

def test_meets(event_id):
    result = supabase.table('as_meet').select('id, name').eq('event_id', event_id).execute()
    print('Meets:', result.data)
    
def test_teams(meet_id):
    fig_res = supabase.table("as_meet_figure_result").select("team_code, team_name").eq("meet_id", meet_id).execute()
    rout_res = supabase.table("as_meet_routine_result").select("team_code, team_name").eq("meet_id", meet_id).execute()
    print('Fig teams count:', len(fig_res.data or []))
    print('Rout teams count:', len(rout_res.data or []))

event_res = supabase.table('as_event').select('id').execute()
if event_res.data:
    ev_id = event_res.data[0]['id']
    test_meets(ev_id)
    meet_res = supabase.table('as_meet').select('id').eq('event_id', ev_id).execute()
    if meet_res.data:
        test_teams(meet_res.data[0]['id'])
