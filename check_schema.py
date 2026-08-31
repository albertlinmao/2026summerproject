import sys
import os
import json
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from src.core.database import get_supabase
supabase = get_supabase()

res1 = supabase.table('as_meet_figure_result').select('*').limit(1).execute()
print('figure result:\n', json.dumps(res1.data, indent=2))

res2 = supabase.table('as_meet_routine_result').select('*').limit(1).execute()
print('routine result:\n', json.dumps(res2.data, indent=2))
