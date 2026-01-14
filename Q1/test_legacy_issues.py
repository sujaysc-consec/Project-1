import requests
import time
import threading
import sys

BASE_URL = "http://127.0.0.1:5000"

def test_sql_injection():
    print("\n--- Testing SQL Injection on /search ---")
    # Attempting to fetch all users by injecting ' OR '1'='1
    payload = "' OR '1'='1"
    url = f"{BASE_URL}/search?q={payload}"
    print(f"Requesting: {url}")
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            print(f"VULNERABILITY CONFIRMED: Found {len(data)} users instead of 0 or 1.")
            for user in data:
                print(f"  - {user['username']} (ID: {user['id']}, Role: {user['role']})")
        else:
            print(f"Search failed with status {response.status_code}")
    except Exception as e:
        print(f"Error during SQL injection test: {e}")

def make_transaction_request(user_id, amount, label):
    start_time = time.time()
    print(f"[{label}] Starting transaction for user {user_id}...")
    try:
        response = requests.post(f"{BASE_URL}/transaction", json={"user_id": user_id, "amount": amount})
        duration = time.time() - start_time
        print(f"[{label}] Finished in {duration:.2f} seconds. Status: {response.status_code}")
    except Exception as e:
        print(f"[{label}] Error: {e}")

def test_blocking_behavior():
    print("\n--- Testing Blocking Behavior on /transaction ---")
    print("Sending two requests simultaneously. If blocking, they will finish sequentially (Total ~6s).")
    
    t1 = threading.Thread(target=make_transaction_request, args=(1, 5.0, "Req 1"))
    t2 = threading.Thread(target=make_transaction_request, args=(2, 10.0, "Req 2"))
    
    start_time = time.time()
    t1.start()
    time.sleep(0.5) # Small gap to ensure order
    t2.start()
    
    t1.join()
    t2.join()
    
    total_duration = time.time() - start_time
    print(f"\nTotal time for both requests: {total_duration:.2f} seconds.")
    if total_duration >= 6.0:
        print("PERFORMANCE ISSUE CONFIRMED: The server is blocking and processing requests sequentially.")
    else:
        print("The server processed requests in parallel (Unexpected for legacy_ledger.py).")

if __name__ == "__main__":
    print("Wait for the Flask server to be ready before running this script.")
    test_sql_injection()
    test_blocking_behavior()
