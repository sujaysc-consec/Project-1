import sqlite3
import asyncio
from typing import List, Optional, Any
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
import concurrent.futures


DB_NAME = 'ledger.db'

# We will use a ThreadPoolExecutor for blocking DB operations
# SQLite handles concurrent reads well in WAL mode, but writes lock.
# A single-threaded writer is often safer/faster for SQLite than concurrent writers fighting for lock.
# However, for this assessment, a default pool is fine.
db_executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)

# --- Database Setup (Do not modify this setup logic) ---
def init_db():
    conn = sqlite3.connect('ledger.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY, username TEXT, balance REAL, role TEXT)''')
    
    # Seeding some dummy data
    users = [
        (1, 'alice', 100.0, 'user'),
        (2, 'bob', 50.0, 'user'),
        (3, 'admin', 9999.0, 'admin'),
        (4, 'charlie', 10.0, 'user')
    ]
    
    c.executemany("INSERT OR IGNORE INTO users (id, username, balance, role) VALUES (?, ?, ?, ?)", users)
    conn.commit()
    conn.close()

init_db()
# -------------------------------------------------------

# --- Application Setup ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    db_executor.shutdown()

app = FastAPI(title="Ledger API", lifespan=lifespan)

# --- Pydantic Models ---
class UserResponse(BaseModel):
    id: int
    username: str
    role: str

class TransactionRequest(BaseModel):
    user_id: int = Field(..., gt=0, description="The ID of the user")
    amount: float = Field(..., gt=0, description="Amount to deduct")

class TransactionResponse(BaseModel):
    status: str
    deducted: float

# --- DB Helpers (The "Bridge" to Async) ---

def run_query_sync(query: str, params: tuple = ()) -> List[dict]:
    """Blocking function to run a read query."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        results = cursor.fetchall()
        # Convert Row objects to dicts so they can be passed back safely
        return [dict(row) for row in results]
    finally:
        conn.close()

def run_transaction_sync(user_id: int, amount: float) -> float:
    """Blocking function to execute the transaction logic atomically."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        # Start transaction (implicit in standard python sqlite3 for DML)
        # 1. Check Balance
        cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        
        if not row:
            raise ValueError("User not found")
            
        current_balance = row['balance']
        
        if current_balance < amount:
            raise ValueError("Insufficient funds")
        
        # 2. Update Balance
        cursor.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (amount, user_id))
        
        conn.commit()
        return current_balance - amount
        
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# --- Routes ---

@app.get('/search', response_model=List[UserResponse])
async def search_users(q: str = Query(..., min_length=1, description="Username to search for")):
    """
    Search for a user by username.
    Offloads blocking SQLite call to a thread pool.
    """
    loop = asyncio.get_running_loop()
    try:
        # Run the synchronous function in the executor
        results = await loop.run_in_executor(db_executor, run_query_sync, "SELECT id, username, role FROM users WHERE username = ?", (q,))
        
        users = [
            UserResponse(id=r['id'], username=r['username'], role=r['role']) 
            for r in results
        ]
        return users
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/transaction', response_model=TransactionResponse)
async def process_transaction(transaction: TransactionRequest):
    """
    Deducts money from a user's balance.
    Mixes Async (sleep) with Threaded (sqlite) execution.
    """
    
    # 1. Non-blocking delay (Simulate Banking Core)
    await asyncio.sleep(3)
    
    # 2. Blocking DB Transaction (Run in Thread)
    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(
            db_executor, 
            run_transaction_sync, 
            transaction.user_id, 
            transaction.amount
        )
        
        return TransactionResponse(
            status="processed", 
            deducted=transaction.amount
        )
        
    except ValueError as e:
        # Map our custom errors to HTTP status codes
        msg = str(e)
        if "User not found" in msg:
            raise HTTPException(status_code=404, detail=msg)
        elif "Insufficient funds" in msg:
            raise HTTPException(status_code=400, detail=msg)
        else:
            raise HTTPException(status_code=500, detail=msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001)
