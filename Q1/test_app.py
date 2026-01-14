import time
import asyncio
import httpx
import sys

BASE_URL = "http://127.0.0.1:5001"

async def test_sql_injection():
    print("\n--- Testing SQL Injection Vulnerability ---")
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        # payload that would dump the table in the legacy version
        payload = "' OR '1'='1"
        response = await client.get(f"/search?q={payload}")
        
        print(f"Payload: {payload}")
        print(f"Status: {response.status_code}")
        
        try:
            data = response.json()
            print(f"Response: {data}")
        except Exception:
            print("Response is not JSON")
            data = []

        if response.status_code == 200:
            if isinstance(data, list):
                if len(data) == 0:
                     print("✅ SQL Injection prevented (No results returned for malicious payload).")
                else:
                    # If it returns all users (id 1, 2, 3, 4), it failed.
                    ids = [u['id'] for u in data]
                    if 1 in ids and 2 in ids and 3 in ids:
                        print("❌ SQL Injection SUCCEEDED (Vulnerability exists).")
                    else:
                         print("✅ SQL Injection prevented (No leaked data).")
            else:
                print(f"❌ Unexpected response format: {type(data)}")
        else:
             print(f"❌ Unexpected status code: {response.status_code}")

async def test_concurrency():
    print("\n--- Testing Concurrency/Performance ---")
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        start_time = time.time()
        
        # Launch a slow transaction
        print("Starting slow transaction (3s delay)...")
        task_transaction = asyncio.create_task(
            client.post("/transaction", json={"user_id": 1, "amount": 5.0})
        )
        
        # Wait a tiny bit to ensure transaction request reached server
        await asyncio.sleep(0.1)
        
        # Launch a fast search
        print("Starting fast search (should be instant)...")
        search_start = time.time()
        response_search = await client.get("/search?q=alice")
        search_duration = time.time() - search_start
        
        print(f"Search finished in {search_duration:.4f} seconds.")
        
        # Wait for transaction to finish
        await task_transaction
        total_duration = time.time() - start_time
        print(f"Transaction finished. Total time: {total_duration:.4f} seconds.")
        
        if search_duration < 1.0:
            print("✅ API is responsive (Search was not blocked by transaction).")
        else:
            print("❌ API is BLOCKED (Search took too long).")

async def main():
    # Ensure server is up (manual check usually, but we assume it's running for this script)
    print("Checking if server is up...")
    try:
        async with httpx.AsyncClient(base_url=BASE_URL) as client:
            await client.get("/search?q=ping")
    except httpx.ConnectError:
        print("❌ Could not connect to server. Please run 'python legacy_ledger_refactored.py' in a separate terminal.")
        return

    await test_sql_injection()
    await test_concurrency()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        # Helper to run the test easily
        asyncio.run(main())
    else:
        asyncio.run(main())
