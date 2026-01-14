import asyncio
import asyncpg
import logging
import os
import time
from datetime import datetime, timezone

# Configuration - use environment variable or default
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@127.0.0.1:5439/firehose")

# Logging config
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def hold_lock(duration: int) -> None:
    """Task 1: Acquires an exclusive lock and holds it."""
    logger.info("Task 1: Connecting to database...")
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        logger.info(f"Task 1: Acquiring ACCESS EXCLUSIVE lock on 'events' table for {duration} seconds...")
        async with conn.transaction():
            # This lock mode conflicts with ROW EXCLUSIVE (used by INSERT)
            await conn.execute("LOCK TABLE events IN ACCESS EXCLUSIVE MODE;")
            logger.info("Task 1: Table locked! Database is effectively 'down' for other connections.")
            
            for i in range(duration):
                logger.info(f"Task 1: Outage active... {duration - i}s remaining")
                await asyncio.sleep(1)
                
        logger.info("Task 1: Transaction committed. Lock released.")
    except Exception as e:
        logger.error(f"Task 1 Error: {e}")
    finally:
        await conn.close()


async def try_insert() -> None:
    """Task 2: Attempts to insert a record, which should be blocked by Task 1."""
    # Wait a bit to ensure Task 1 has acquired the lock
    await asyncio.sleep(2)
    
    logger.info("Task 2: Attempting to insert a record (this should block)...")
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        start_time = time.time()
        # This will hang until the lock from Task 1 is released
        # Using TIMESTAMPTZ to match the new schema
        await conn.execute("""
            INSERT INTO events (user_id, timestamp, metadata) 
            VALUES (999, $1::timestamptz, $2::jsonb)
        """, datetime.now(timezone.utc), '{"test": "blocked_insert"}')
        
        duration = time.time() - start_time
        logger.info(f"Task 2: Insert successful! It was blocked for {duration:.2f} seconds.")
    except Exception as e:
        logger.error(f"Task 2 Error: {e}")
    finally:
        await conn.close()


async def simulate_outage(duration: int = 10) -> None:
    """
    Coordinates the lock task and the insertion attempt task.
    
    This demonstrates that:
    1. The database becomes unavailable for writes during the lock
    2. The application (and Redis buffer) continues accepting requests
    3. Once the lock is released, pending writes complete successfully
    """
    logger.info("=" * 60)
    logger.info("STARTING DATABASE OUTAGE SIMULATION")
    logger.info("=" * 60)
    logger.info(f"This will lock the 'events' table for {duration} seconds.")
    logger.info("During this time:")
    logger.info("  - The API should continue accepting requests (returning 202)")
    logger.info("  - Events will queue in Redis Stream")
    logger.info("  - Worker will retry until DB recovers")
    logger.info("=" * 60)
    
    await asyncio.gather(
        hold_lock(duration),
        try_insert()
    )
    
    logger.info("=" * 60)
    logger.info("SIMULATION COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Simulate database outage")
    parser.add_argument(
        "--duration",
        type=int,
        default=10,
        help="Duration of simulated outage in seconds (default: 10)"
    )
    args = parser.parse_args()
    
    asyncio.run(simulate_outage(args.duration))
