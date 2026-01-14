# Q1 — Legacy Ledger Audit (Refactor)

This folder contains the original legacy service and a refactored implementation that addresses:
- SQL injection in the search endpoint
- API responsiveness under slow “banking core” delays
- Atomic balance updates in SQLite

## Project Files

- `legacy_ledger.py`: Original legacy implementation (reference).
- `legacy_ledger_refactored.py`: Refactored FastAPI implementation (main deliverable).
- `ledger.db`: SQLite database created on first run.
- `test_app.py`: Verification script against the refactored service (SQLi + responsiveness checks).
- `NOTES.md`: Brief explanation of fixes and design choices.

## Setup

```bash
python3 -m venv venv
./venv/bin/python -m pip install -r requirements.txt
```

## Run

Starts the refactored API on port `5001`.

```bash
./venv/bin/python legacy_ledger_refactored.py
```

## Verify

In a separate terminal (with the server running):

```bash
./venv/bin/python test_app.py
```

## API

- `GET /search?q=<username>`: Parameterized lookup by exact username.
- `POST /transaction` with JSON `{ "user_id": <int>, "amount": <float> }`: Deducts balance after a simulated delay.

