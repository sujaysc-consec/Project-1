import requests
import multiprocessing
import time
from database import get_connection
from sqlalchemy import text
from reset_db import reset_database

import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Configuration
API_URL = os.getenv("API_URL", "http://localhost:8000/buy_ticket")
TOTAL_REQUESTS = int(os.getenv("TOTAL_REQUESTS", 1000))
CONCURRENT_PROCESSES = int(os.getenv("CONCURRENT_PROCESSES", 50))

def attempt_purchase(request_id):
    """
    Worker function to send a purchase request.
    Returns the HTTP status code.
    """
    try:
        response = requests.post(API_URL)
        return response.status_code
    except Exception as e:
        return 500

def run_test():
    print("=== Starting Proof of Correctness Test ===")
    
    # 1. Reset Database to ensure clean state (100 items)
    print("Resetting database...")
    reset_database()
    
    # 2. Spawn concurrent workers
    print(f"Spawning {CONCURRENT_PROCESSES} concurrent processes to fire {TOTAL_REQUESTS} requests...")
    
    start_time = time.time()
    
    with multiprocessing.Pool(processes=CONCURRENT_PROCESSES) as pool:
        # Create a list of 1000 tasks
        results = pool.map(attempt_purchase, range(TOTAL_REQUESTS))
        
    duration = time.time() - start_time
    print(f"Test completed in {duration:.2f} seconds.")
    
    # 3. Analyze HTTP Results
    success_count = results.count(200)
    gone_count = results.count(410)
    error_count = len(results) - success_count - gone_count
    
    print("\n--- HTTP Response Analysis ---")
    print(f"Total Requests: {len(results)}")
    print(f"Successful Buys (200 OK): {success_count} (Expected: 100)")
    print(f"Sold Out Responses (410 GONE): {gone_count}")
    print(f"Errors/Other: {error_count}")

    # 4. Verify Database Consistency
    print("\n--- Database Consistency Check ---")
    
    with get_connection() as conn:
        try:
            # Check Final Stock
            result = conn.execute(text("SELECT count FROM inventory WHERE id = 'Item A'"))
            item_row = result.fetchone()
            final_stock = item_row.count if item_row else -999
            
            # Check Purchase Count
            result = conn.execute(text("SELECT count(*) as cnt FROM purchases"))
            purchase_row = result.fetchone()
            purchase_count = purchase_row.cnt if purchase_row else -999
            
            print(f"Final DB Stock: {final_stock} (Expected: 0)")
            print(f"Total Purchase Records: {purchase_count} (Expected: 100)")
            
            # 5. Final Verdict
            if final_stock == 0 and purchase_count == 100 and success_count == 100:
                print("\n✅ SUCCESS: Strict consistency maintained. Exactly 100 items sold.")
            else:
                print("\n❌ FAILURE: Inconsistency detected!")
                if final_stock < 0:
                    print("CRITICAL: Overselling occurred (Stock < 0)!")
                if final_stock > 0:
                    print("CRITICAL: Underselling occurred (Stock > 0 but test finished)!")
                if success_count != 100:
                    print(f"Mismatch: API reported {success_count} successes, but we expected 100.")
                    
        except Exception as e:
            print(f"Error checking database: {e}")

if __name__ == "__main__":
    # Ensure the server is running before executing this!
    print("NOTE: Make sure 'uvicorn app:app' is running on port 8000 before proceeding.")
    # Simple check to see if server is up
    try:
        requests.get("http://localhost:8000/docs", timeout=1)
    except:
        print("❌ Error: Could not connect to localhost:8000. Please start the server first.")
        exit(1)
        
    run_test()
