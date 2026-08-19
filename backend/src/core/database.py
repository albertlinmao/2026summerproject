import os
from supabase import create_client, Client

env_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env')
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                try:
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value
                except ValueError:
                    pass

url: str = os.environ.get("SUPABASE_URL", "http://localhost:8000")
key: str = os.environ.get("SUPABASE_KEY", "")

supabase: Client = create_client(url, key)
