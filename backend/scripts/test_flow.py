import requests
import sys

BASE_URL = "http://localhost:8000"
API_URL = f"{BASE_URL}/api/v1"

def test_flow():
    print("--- STARTING DIAGNOSTIC TEST ---")
    
    # 1. Health Check
    try:
        r = requests.get(f"{BASE_URL}/docs", timeout=2)
        print(f"1. Health Check (Docs): {r.status_code} {'✅' if r.status_code == 200 else '❌'}")
    except Exception as e:
        print(f"1. Health Check Failed: {e}")
        return

    # 2. Login
    print("\n2. Attempting Login...")
    login_data = {
        "username": "christian.zv@cerebro.com",
        "password": "123456" # Default pass set in init_user
    }
    
    try:
        r = requests.post(f"{API_URL}/auth/login", data=login_data)
        print(f"   Status: {r.status_code}")
        
        if r.status_code != 200:
            print(f"   Login Failed: {r.text}")
            return
            
        token = r.json().get("access_token")
        if token:
            print(f"   Token received: {token[:10]}... ✅")
        else:
            print("   No token in response ❌")
            return
            
        # 3. Fetch Dashboard
        print("\n3. Fetching Dashboard Data...")
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{API_URL}/expenses/dashboard", headers=headers)
        
        print(f"   Status: {r.status_code}")
        if r.status_code == 200:
             data = r.json()
             print(f"   Dashboard Data Received: {list(data.keys())} ✅")
             print(f"   Monthly Budget: {data.get('monthly_budget')}")
             print(f"   Available Balance: {data.get('available_balance')}")
        else:
             print(f"   Dashboard Fetch Failed: {r.text} ❌")

    except Exception as e:
        print(f"Login/Dashboard Test Failed: {e}")

if __name__ == "__main__":
    test_flow()
