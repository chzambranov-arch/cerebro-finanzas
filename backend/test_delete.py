import requests

r = requests.post('http://localhost:8004/api/v1/auth/login', data={'username': 'christian.zv@cerebro.com', 'password': 'cerebro_pass'})
token = r.json().get('access_token')
headers = {'Authorization': f'Bearer {token}'}

# Get folders
r2 = requests.get('http://localhost:8004/api/v1/expenses/folders', headers=headers)
data = r2.json()
for f in data:
    print(f"Folder: {f['id']} {f['name']}")
    for item in f.get('items', []):
        print(f"  Item: {item['id']} {item['name']}")

# Try deleting item id=2
print()
r3 = requests.delete('http://localhost:8004/api/v1/expenses/items/2', headers=headers)
print(f"DELETE item 2: status={r3.status_code} body={r3.text}")

# Try deleting expense id=1
r4 = requests.delete('http://localhost:8004/api/v1/expenses/expenses/1', headers=headers)
print(f"DELETE expense 1: status={r4.status_code} body={r4.text}")
