import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

# Bypass auth for test
from src.api.results_browser import get_current_user
app.dependency_overrides[get_current_user] = lambda: {"id": "test_user"}

response = client.get('/api/results/events')
if response.status_code == 200:
    events = response.json().get('data', [])
    if events:
        event_id = events[0]['id']
        res2 = client.get(f'/api/results/events/{event_id}/meets')
        meets = res2.json().get('data', [])
        if meets:
            meet_id = meets[0]['id']
            res3 = client.get(f'/api/results/meets/{meet_id}/teams')
            print("Teams code:", res3.status_code)
            print("Teams:", res3.text[:200])
