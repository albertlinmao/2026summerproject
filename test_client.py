import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)
response = client.get('/api/results/events')
print("Events:", response.status_code, response.text)

if response.status_code == 200:
    events = response.json().get('data', [])
    if events:
        event_id = events[0]['id']
        res2 = client.get(f'/api/results/events/{event_id}/meets')
        print("Meets:", res2.status_code, res2.text)
