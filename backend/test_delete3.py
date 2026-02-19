import requests

r = requests.post('http://localhost:8004/api/v1/auth/login', data={'username': 'christian.zv@cerebro.com', 'password': 'cerebro_pass'})
token = r.json().get('access_token')
headers = {'Authorization': f'Bearer {token}'}

# First check what items exist
r2 = requests.get('http://localhost:8004/api/v1/expenses/folders', headers=headers)
data = r2.json()
print("Current state:")
for f in data:
    print(f"  Folder {f['id']}: {f['name']}")
    for item in f.get('items', []):
        print(f"    Item {item['id']}: {item['name']}")

# Try deleting item id=3 (Supermercado)
print("\nTrying DELETE item 3...")
r3 = requests.delete('http://localhost:8004/api/v1/expenses/items/3', headers=headers)
print(f"status: {r3.status_code}")
try:
    print(f"body: {r3.json()}")
except:
    print(f"body (raw): {r3.text[:300]}")
