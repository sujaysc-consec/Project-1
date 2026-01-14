import sqlite3
import asyncio
from typing import List, Optional, Any
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
import concurrent.futures


DB_NAME = 'ledger.db'

read_executor = concurrent.futures.ThreadPoolExecutor(max_workers=8)
write_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)


def connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn

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
    read_executor.shutdown()
    write_executor.shutdown()

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
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        results = cursor.fetchall()
        return [dict(row) for row in results]
    finally:
        conn.close()

def run_transaction_sync(user_id: int, amount: float) -> float:
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE users SET balance = balance - ? WHERE id = ? AND balance >= ?",
            (amount, user_id, amount),
        )
        if cursor.rowcount != 1:
            cursor.execute("SELECT 1 FROM users WHERE id = ?", (user_id,))
            if cursor.fetchone() is None:
                raise ValueError("User not found")
            raise ValueError("Insufficient funds")

        cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.commit()
        return float(row["balance"]) if row is not None else 0.0
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
        results = await loop.run_in_executor(
            read_executor,
            run_query_sync,
            "SELECT id, username, role FROM users WHERE username = ?",
            (q,),
        )
        
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
            write_executor,
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
