# Legacy Ledger Refactoring Notes

## Vulnerabilities Found & Fixed

### 1. SQL Injection (Critical)
**Issue**: The original code used f-strings to construct SQL queries (`f"SELECT ... '{query}'"`), allowing attackers to execute arbitrary SQL commands.
**Fix**: Implemented **Parameterized Queries**.
Queries now use the `?` placeholder (e.g., `execute("... WHERE username = ?", (q,))`). This ensures the database treats input strictly as data, neutralizing injection attacks.

### 2. Data Integrity
**Issue**: 
- Updates were not atomic (potential partial writes).
- No check for sufficient funds (could result in negative balance).
**Fix**: 
- **Atomic Transactions**: Leveraged SQLite's transaction support with explicit `commit()` and `rollback()` on error.
- **Validation**: Added logic to verify `balance >= amount` before deducting.

## Performance Solution

### Hybrid Async Architecture
**Constraint**: Must use standard `sqlite3` (blocking).
**Requirement**: API must remain responsive despite 3s delay.

**Solution**:
1.  **FastAPI + Asyncio**: The web server handles requests asynchronously.
2.  **Non-Blocking Delay**: Replaced `time.sleep` with `await asyncio.sleep`. This yields control to the event loop, allowing thousands of requests to be processed while waiting for the "banking core."
3.  **Thread Pool for Database**: Since `sqlite3` is blocking, I wrapped all database operations in `loop.run_in_executor`. This offloads the file I/O to a thread pool, preventing it from blocking the main async event loop.
4.  **WAL Mode**: Enabled `PRAGMA journal_mode=WAL` to allow readers (Search) and writers (Transaction) to operate concurrently without locking the entire file.
5.  **Indexing**: Added an index on `username` to ensure O(1) lookup times.

## How to Run

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Run Server**:
    ```bash
    python legacy_ledger_refactored.py
    ```
    (Runs on port 5001)

3.  **Run Tests**:
    ```bash
    python test_app.py
    ```
