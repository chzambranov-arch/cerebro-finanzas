import requests, time

time.sleep(2)

r = requests.post('http://localhost:8004/api/v1/auth/login', data={'username': 'christian.zv@cerebro.com', 'password': 'cerebro_pass'})
token = r.json().get('access_token')
headers = {'Authorization': f'Bearer {token}'}

# Get folders
folders = requests.get('http://localhost:8004/api/v1/expenses/folders', headers=headers).json()
folder_id = folders[0]['id'] if folders else None
print(f"Using folder_id={folder_id}")

# Create test item
r1 = requests.post('http://localhost:8004/api/v1/expenses/items',
    headers={**headers, 'Content-Type': 'application/json'},
    json={'folder_id': folder_id, 'name': 'ItemTest', 'budget': 1000, 'type': 'FIJO'})
print(f"CREATE item: {r1.status_code}")
item_id = r1.json().get('id')

# Delete item
r2 = requests.delete(f'http://localhost:8004/api/v1/expenses/items/{item_id}', headers=headers)
print(f"DELETE item {item_id}: {r2.status_code} => {r2.json()}")

# Delete expense (sporadic)
folders2 = requests.get('http://localhost:8004/api/v1/expenses/folders', headers=headers).json()
for f in folders2:
    detail = requests.get(f"http://localhost:8004/api/v1/expenses/folders/{f['id']}", headers=headers).json()
    sporadic = detail.get('sporadic_items', [])
    if sporadic:
        exp_id = sporadic[0]['id']
        r3 = requests.delete(f'http://localhost:8004/api/v1/expenses/expenses/{exp_id}', headers=headers)
        print(f"DELETE expense {exp_id}: {r3.status_code} => {r3.json()}")
        break
else:
    print("No sporadic expenses to test")
