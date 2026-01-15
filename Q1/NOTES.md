# Legacy Ledger Refactoring Notes

## Vulnerabilities Found & Fixed

### 1. SQL Injection (Critical)
**Issue**: The original code used f-strings to construct SQL queries (`f"SELECT ... '{query}'"`), allowing attackers to execute arbitrary SQL commands.
**Fix**: Implemented **Parameterized Queries**.
Queries now use the `?` placeholder (e.g., `execute("... WHERE username = ?", (q,))`). This ensures the database treats input strictly as data, neutralizing injection attacks.

### 2. Data Integrity
**Issue**:
- Transaction updates were built via string interpolation and did not enforce any guardrails (easy to corrupt data or deduct unintended amounts).

**Fix**:
- **Parameterized UPDATE**: Uses `UPDATE users SET balance = balance - ? WHERE id = ? AND balance >= ?` to prevent SQL injection and ensure the update happens as a single atomic statement.
- **Commit/Rollback**: Commits on success and rolls back on any exception to avoid leaving the DB in a bad state.
- **Serialized Writes**: Runs all write transactions through a single-worker thread pool to avoid concurrent write contention in SQLite.

## Performance Solution

### Hybrid Async Architecture
**Constraint**: Must use standard `sqlite3` (blocking).
**Requirement**: API must remain responsive despite 3s delay.

**Solution**:
1.  **FastAPI + Asyncio**: The server uses an async event loop to keep request handling responsive.
2.  **Non-Blocking Delay**: Replaced `time.sleep(3)` with `await asyncio.sleep(3)`, so one slow transaction doesn’t block other requests.
3.  **Thread Pool for Database**: Because `sqlite3` is blocking, DB work runs in `loop.run_in_executor`.
4.  **Separate Pools**: Reads use a small thread pool; writes use a single-worker thread pool to keep updates safe and avoid SQLite write-lock contention.

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

    Note: `test_app.py` is configured to call `http://127.0.0.1:5001`.

3.  **Run Tests**:
    ```bash
    python test_app.py
    ```
