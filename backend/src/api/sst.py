from fastapi import APIRouter
from src.core.database import supabase

router = APIRouter()

@router.get('/scores/sst')
def get_sst_scores():
    try:
        # Fetch from the parsed figure results
        fig_resp = supabase.table('as_meet_figure_result')\
            .select('rank, draw, team_name, athlete_name, total_score, routine_score, meet_id, as_meet(name)')\
            .eq('team_code', 'SST')\
            .execute()
            
        # Fetch from the parsed routine results
        rout_resp = supabase.table('as_meet_routine_result')\
            .select('rank, draw, team_name, routine_score, meet_id, as_meet(name)')\
            .eq('team_code', 'SST')\
            .execute()
        
        # Combine and format them to match the frontend expectations
        results = []
        
        for fig in (fig_resp.data or []):
            meet_name = fig.get('as_meet', {}).get('name') if fig.get('as_meet') else 'Unknown Meet'
            results.append({
                'team': {'name': fig.get('team_name')},
                'athlete_name': fig.get('athlete_name'),
                'swim_game': {
                    'name': meet_name,
                    'game_type': 'Figure'
                },
                'rank': fig.get('rank'),
                'draw': fig.get('draw'),
                'score': fig.get('routine_score') or fig.get('total_score')
            })
            
        for rout in (rout_resp.data or []):
            meet_name = rout.get('as_meet', {}).get('name') if rout.get('as_meet') else 'Unknown Meet'
            results.append({
                'team': {'name': rout.get('team_name')},
                # Display label only: a routine is scored for the whole team, so
                # there is no single person to name. Not an identifier, and not a
                # person_id — resolve rows to people via as_result_person_link.
                'athlete_name': 'Team/Routine', # Routines usually belong to the whole team, or we'd parse team_athletes
                'swim_game': {
                    'name': meet_name,
                    'game_type': 'Routine'
                },
                'rank': rout.get('rank'),
                'draw': rout.get('draw'),
                'score': rout.get('routine_score')
            })
            
        return {"data": results}
    except Exception as e:
        return {"error": str(e), "data": []}

