import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from src.core.database import get_supabase
supabase = get_supabase()
res = supabase.table('as_meet_routine_result').select('team_athletes').limit(1).execute()
print(res.data)
