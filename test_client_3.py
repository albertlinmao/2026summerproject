import sys
import os
import httpx
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

response = client.post('/api/auth/login', json={'email': 'sophie.lin@sst.example.com', 'password': 'demo123'})
if response.status_code == 200:
    token = response.json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}
    
    events_res = client.get('/api/results/events', headers=headers)
    print("Events code:", events_res.status_code)
    
    if events_res.status_code == 200:
        events = events_res.json().get('data', [])
        print(events)
        if events:
            event_id = events[0]['id']
            res2 = client.get(f'/api/results/events/{event_id}/meets', headers=headers)
            print("Meets code:", res2.status_code)
            
            meets = res2.json().get('data', [])
            print(meets)
            if meets:
                meet_id = meets[0]['id']
                res3 = client.get(f'/api/results/meets/{meet_id}/teams', headers=headers)
                print("Teams code:", res3.status_code)
                print(res3.json())
