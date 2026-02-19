import requests, time

# Wait for uvicorn to reload
time.sleep(3)

r = requests.post('http://localhost:8004/api/v1/auth/login', data={'username': 'christian.zv@cerebro.com', 'password': 'cerebro_pass'})
token = r.json().get('access_token')
headers = {'Authorization': f'Bearer {token}'}

# Create a test item first
r_folders = requests.get('http://localhost:8004/api/v1/expenses/folders', headers=headers)
folders = r_folders.json()
print("Folders:", [(f['id'], f['name']) for f in folders])

if folders:
    folder_id = folders[0]['id']
    # Create item
    r_create = requests.post('http://localhost:8004/api/v1/expenses/items', headers={**headers, 'Content-Type': 'application/json'},
        json={'folder_id': folder_id, 'name': 'Test Item', 'budget': 5000, 'type': 'FIJO'})
    print(f"Create item: {r_create.status_code} {r_create.text[:100]}")
    
    if r_create.status_code == 200:
        item_id = r_create.json().get('id')
        print(f"Created item id: {item_id}")
        
        # Now delete it
        r_del = requests.delete(f'http://localhost:8004/api/v1/expenses/items/{item_id}', headers=headers)
        print(f"DELETE item {item_id}: status={r_del.status_code}")
        try:
            print(f"body: {r_del.json()}")
        except:
            print(f"raw: {r_del.text[:200]}")

# Also test expense delete
print("\nTesting expense delete...")
r_exp = requests.get('http://localhost:8004/api/v1/expenses/folders', headers=headers)
data = r_exp.json()
for f in data:
    detail = requests.get(f"http://localhost:8004/api/v1/expenses/folders/{f['id']}", headers=headers)
    d = detail.json()
    sporadic = d.get('sporadic_items', [])
    if sporadic:
        exp_id = sporadic[0]['id']
        print(f"Found sporadic expense id={exp_id}")
        r_del_exp = requests.delete(f'http://localhost:8004/api/v1/expenses/expenses/{exp_id}', headers=headers)
        print(f"DELETE expense {exp_id}: status={r_del_exp.status_code}")
        try:
            print(f"body: {r_del_exp.json()}")
        except:
            print(f"raw: {r_del_exp.text[:200]}")
        break
