"""
SQL Script Loader

Loads and executes raw SQL scripts from the scripts/ folder.
Uses parameterized queries to prevent SQL injection.
"""

from pathlib import Path
from functools import lru_cache
from sqlalchemy import text

# Path to the scripts directory
SCRIPTS_DIR = Path(__file__).parent / "scripts"


@lru_cache(maxsize=50)
def load_sql(name: str) -> str:
    """
    Load a SQL script by name (without .sql extension).
    Results are cached for performance.
    
    Args:
        name: Script name without .sql extension (e.g., "buy_ticket")
        
    Returns:
        The SQL script content as a string
        
    Raises:
        FileNotFoundError: If the script doesn't exist
    """
    path = SCRIPTS_DIR / f"{name}.sql"
    if not path.exists():
        raise FileNotFoundError(f"SQL script not found: {path}")
    return path.read_text()


def execute_sql(conn, name: str, params: dict = None):
    """
    Execute a named SQL script with safe parameterized queries.
    
    Args:
        conn: SQLAlchemy connection object
        name: Script name without .sql extension
        params: Dictionary of parameters to bind (prevents SQL injection)
        
    Returns:
        SQLAlchemy CursorResult object
        
    Example:
        result = execute_sql(conn, "buy_ticket", {"item_id": "Item A"})
        row = result.fetchone()
    """
    sql = text(load_sql(name))
    return conn.execute(sql, params or {})


def execute_sql_script(conn, name: str):
    """
    Execute a SQL script that may contain multiple statements.
    Used for DDL scripts like create_tables.sql.
    
    Args:
        conn: SQLAlchemy connection object
        name: Script name without .sql extension
        
    Note:
        This splits on semicolons and executes each statement separately.
        Parameters are not supported for multi-statement scripts.
    """
    sql_content = load_sql(name)
    
    # Split by semicolon and execute each non-empty statement
    statements = [s.strip() for s in sql_content.split(';') if s.strip()]
    
    for statement in statements:
        conn.execute(text(statement))
