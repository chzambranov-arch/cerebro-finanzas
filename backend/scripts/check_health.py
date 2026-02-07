import requests
import sys

try:
    print("Checking server URL: http://localhost:8000/docs")
    r = requests.get("http://localhost:8000/docs", timeout=2)
    print(f"Status Code: {r.status_code}")
    if r.status_code == 200:
        print("Server is UP and reachable.")
    else:
        print("Server returned unexpected status.")
except Exception as e:
    print(f"Server unreachable: {e}")
