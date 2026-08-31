import requests
import json

sess = requests.Session()

# Login
resp = sess.post('http://127.0.0.1:8000/api/auth/login', json={
    'email': 'sophie.lin@sst.example.com',
    'password': 'demo123'
})
print('Login status:', resp.status_code)
if resp.status_code == 200:
    data = resp.json()
    token = data.get('access_token', '')
    
    # Dashboard
    headers = {'Authorization': f'Bearer {token}'}
    dash_res = sess.get('http://127.0.0.1:8000/api/analytics/dashboard', headers=headers)
    print('Dashboard status:', dash_res.status_code)
    if dash_res.status_code == 200:
        dash_data = dash_res.json()
        athletes = dash_data['widgets']['team_overview']['athletes']
        print(f'Team overview athletes ({len(athletes)}):')
        for a in athletes:
            print(f"  {a['name']}: figure={a['avg_figure_score']}, routine={a['avg_routine_score']}, trend={a['improvement_trend']}")
    else:
        print('Dashboard error:', dash_res.status_code, dash_res.text)
else:
    print('Login error:', resp.status_code, resp.text)