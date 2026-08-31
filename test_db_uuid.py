import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from src.core.database import get_supabase
supabase = get_supabase()

try:
    fig_res = supabase.table("as_meet_figure_result").select("team_code, team_name").eq("meet_id", "101").execute()
    print("Success", fig_res)
except Exception as e:
    print("Error:", e)
