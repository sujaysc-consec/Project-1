# Flash Sale System

A high-concurrency e-commerce backend prototype designed to handle flash sales without overselling. Built with FastAPI and Raw SQL (PostgreSQL), ensuring strict data consistency through row-level locking.

## Features

- **Concurrency Safe**: Uses `SELECT ... FOR UPDATE` to prevent race conditions.
- **Raw SQL Implementation**: High-performance SQL queries separated into `.sql` scripts.
- **SQL Injection Safe**: Uses parameterized queries (`sqlalchemy.text` binding).
- **Atomic Transactions**: Purchase and inventory updates happen in a single atomic transaction.
- **Verification Suite**: Includes a `proof_of_correctness.py` script to simulate high load.

## Tech Stack

- **Language**: Python 3.14+
- **Framework**: FastAPI
- **Database**: PostgreSQL (Raw SQL via SQLAlchemy Core)
- **Driver**: `psycopg2-binary`
- **Testing**: `multiprocessing` for concurrent load testing
- **Serving**: Uvicorn (dev), Gunicorn + Uvicorn workers (multi-process)

## Project Structure

```
flash_sale_system/
├── app.py                  # API Endpoints (FastAPI)
├── database.py             # Database connection & transaction management
├── gunicorn.conf.py        # Gunicorn configuration (Uvicorn workers)
├── sql_loader.py           # Helper to load/execute .sql scripts safely
├── proof_of_correctness.py # Load testing & verification script
├── reset_db.py             # Database reset & seeding utility
└── scripts/                # Raw SQL Queries
    ├── create_tables.sql
    ├── drop_tables.sql
    ├── seed_inventory.sql
    ├── get_item_for_update.sql
    └── buy_ticket.sql
```

## Setup & Installation

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   *(Includes `fastapi`, `uvicorn`, `gunicorn`, `sqlalchemy`, `psycopg2-binary`, `requests`, `python-dotenv`.)*

2. **Environment Configuration**:
   Create a `.env` file in the root directory:
   ```env
    DATABASE_URL=postgresql://user:password@localhost:5432/dbname
    API_URL=http://localhost:8000/buy_ticket
    TOTAL_REQUESTS=1000
    CONCURRENT_PROCESSES=50

     # Optional tuning
     WEB_CONCURRENCY=4
     DB_POOL_SIZE=10
     DB_MAX_OVERFLOW=20
     DB_POOL_TIMEOUT=5
     DB_RETRY_BUDGET_SECONDS=2.0
   ```

3. **Initialize Database**:
   ```bash
   python flash_sale_system/reset_db.py
   ```

## Usage

### Start the Server
Dev (single process, auto-reload):
```bash
uvicorn flash_sale_system.app:app --reload --host 0.0.0.0 --port 8000
```

Prod-like (multi-process, Gunicorn + Uvicorn workers):
```bash
cd flash_sale_system
gunicorn -c gunicorn.conf.py app:app
```

### Run Verification Test
Simulates 1000 concurrent requests to buy 100 items.
```bash
python flash_sale_system/proof_of_correctness.py
```
Expected Output:
> SUCCESS: Strict consistency maintained. Exactly 100 items sold.

