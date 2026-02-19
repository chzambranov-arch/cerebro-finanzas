import os, time, requests

# Touch finance.py to force uvicorn reload
path = 'app/routers/finance.py'
stat = os.stat(path)
os.utime(path, (stat.st_atime, time.time()))
print('Touched finance.py, waiting for reload...')
time.sleep(4)

r = requests.post('http://localhost:8004/api/v1/auth/login', data={'username': 'christian.zv@cerebro.com', 'password': 'cerebro_pass'})
token = r.json().get('access_token')
headers = {'Authorization': f'Bearer {token}'}

r2 = requests.get('http://localhost:8004/api/v1/expenses/folders', headers=headers)
data = r2.json()
item_id = None
for f in data:
    for item in f.get('items', []):
        item_id = item['id']
        print(f"Found item: {item_id} {item['name']}")
        break
    if item_id:
        break

if item_id:
    r3 = requests.delete(f'http://localhost:8004/api/v1/expenses/items/{item_id}', headers=headers)
    print(f'DELETE status: {r3.status_code}')
    try:
        print(f'body: {r3.json()}')
    except:
        print(f'raw: {r3.text[:300]}')
else:
    print("No items found to delete")
