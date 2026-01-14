from database import engine
from sql_loader import execute_sql_script, execute_sql

def reset_database():
    print("Resetting database...")
    
    try:
        # Get a connection
        with engine.begin() as conn:
            # 1. Drop existing tables
            print("Dropping tables...")
            execute_sql_script(conn, "drop_tables")
            
            # 2. Create new tables
            print("Creating tables...")
            execute_sql_script(conn, "create_tables")
            
            # 3. Seed inventory
            print("Seeding inventory...")
            # 'Item A' with 100 items
            execute_sql(conn, "seed_inventory", {"item_id": "Item A", "count": 100})
            
            print("Database reset complete. 'Item A' initialized with 100 stock.")
            
    except Exception as e:
        print(f"Error resetting database: {e}")
        # Transaction rolls back automatically on error

if __name__ == "__main__":
    reset_database()
