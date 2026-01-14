"""
Database Configuration

Provides the SQLAlchemy engine for raw SQL execution.
Uses connection pooling for efficient database access.
Tuned for high-concurrency flash sale scenarios.
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from contextlib import contextmanager

# Load .env file from the current directory or parent directory
load_dotenv()  # looks in current directory
load_dotenv("../.env")  # looks in parent directory

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError('DATABASE_URL is not set.')

# Pool configuration from environment (with sensible defaults for flash sales)
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", 10))
MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", 20))
POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", 5))  # seconds to wait for connection
POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", 300))  # recycle connections after 5 min

# Create engine with tuned connection pooling
engine = create_engine(
    DATABASE_URL,
    pool_size=POOL_SIZE,           # Persistent connections in pool
    max_overflow=MAX_OVERFLOW,      # Extra connections allowed under load
    pool_timeout=POOL_TIMEOUT,      # Max wait time for a connection from pool
    pool_recycle=POOL_RECYCLE,      # Recycle connections to avoid stale connections
    pool_pre_ping=True,             # Verify connection health before use
)


@contextmanager
def get_connection():
    """
    Context manager for getting a database connection.
    Automatically handles commit/rollback and connection cleanup.
    
    Usage:
        with get_connection() as conn:
            result = conn.execute(text("SELECT * FROM inventory"))
    """
    with engine.connect() as conn:
        yield conn


@contextmanager
def get_transaction():
    """
    Context manager for database transactions.
    Auto-commits on success, auto-rollbacks on exception.
    
    Usage:
        with get_transaction() as conn:
            conn.execute(text("UPDATE inventory SET count = count - 1"))
            conn.execute(text("INSERT INTO purchases ..."))
            # Commits automatically if no exception
    """
    with engine.begin() as conn:
        yield conn
