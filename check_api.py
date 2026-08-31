import requests
import json

sess = requests.Session()

# Try login
resp = sess.post('http://127.0.0.1:8000/api/auth/login', json={
    'email': 'sophie.lin@sst.example.com',
    'password': 'demo123'
})
print('Login status:', resp.status_code)
if resp.status_code == 200:
    data = resp.json()
    token = data.get('access_token', '')
    print('Token:', token[:20] + '...' if token else 'None')
    club_id = data.get('user', {}).get('clubId', '')
    print('Club ID:', club_id)
    
    # Now try dashboard
    headers = {'Authorization': f'Bearer {token}'}
    dash_res = sess.get('http://127.0.0.1:8000/api/analytics/dashboard', headers=headers)
    print('Dashboard status:', dash_res.status_code)
    if dash_res.status_code == 200:
        dash_data = dash_res.json()
        print('Dashboard data:')
        print(json.dumps(dash_data, indent=2))
    else:
        print('Dashboard error:', dash_res.status_code, dash_res.text)
else:
    print('Login error:', resp.status_code, resp.text)