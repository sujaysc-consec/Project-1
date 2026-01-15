import sqlite3
import asyncio
from typing import List, Optional, Any
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import concurrent.futures


read_executor = concurrent.futures.ThreadPoolExecutor(max_workers=8)
write_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

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


# --- DB Helpers (The "Bridge" to Async) ---

def run_query_sync(query: str, params: tuple = ()) -> List[dict]:
    conn = sqlite3.connect('ledger.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        results = cursor.fetchall()
        return [dict(row) for row in results]
    finally:
        conn.close()

def run_transaction_sync(user_id: int, amount: float) -> float:
    conn = sqlite3.connect('ledger.db')
    conn.row_factory = sqlite3.Row
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

@app.get('/search')
async def search_users(q: str | None = Query(default=None)):
    """
    Search for a user by username.
    Compatible with legacy behavior:
    - Missing q -> 400 {"error": "Missing query parameter"}
    - Errors -> 500 {"error": "..."}
    """
    if not q:
        return JSONResponse(status_code=400, content={"error": "Missing query parameter"})

    loop = asyncio.get_running_loop()
    try:
        results = await loop.run_in_executor(
            read_executor,
            run_query_sync,
            "SELECT id, username, role FROM users WHERE username = ?",
            (q,),
        )
        return [{"id": r["id"], "username": r["username"], "role": r["role"]} for r in results]
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post('/transaction')
async def process_transaction(request: Request):
    """
    Deducts money from a user's balance.
    Compatible with legacy behavior:
    - Invalid input -> 400 {"error": "Invalid input"}
    - Errors -> 500 {"error": "..."}
    """
    try:
        data = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid input"})

    if not isinstance(data, dict):
        return JSONResponse(status_code=400, content={"error": "Invalid input"})

    user_id = data.get("user_id")
    amount = data.get("amount")

    if not user_id or not amount:
        return JSONResponse(status_code=400, content={"error": "Invalid input"})

    await asyncio.sleep(3)

    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(write_executor, run_transaction_sync, int(user_id), float(amount))
        return {"status": "processed", "deducted": amount}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001)
