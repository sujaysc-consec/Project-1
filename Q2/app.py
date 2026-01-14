import asyncio
import json
import logging
import os
import signal
from datetime import datetime
from typing import Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from pydantic_settings import BaseSettings
import redis.asyncio as redis
import asyncpg


# =============================================================================
# CONFIGURATION (Externalized via Environment Variables)
# =============================================================================
class Settings(BaseSettings):
    redis_url: str
    database_url: str
    stream_key: str
    consumer_group: str
    consumer_name: str
    batch_size: int
    block_ms: int

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# =============================================================================
# MODELS (Pydantic V2)
# =============================================================================
class Event(BaseModel):
    user_id: int
    timestamp: str
    metadata: dict[str, Any]


# =============================================================================
# GLOBAL STATE
# =============================================================================
redis_client: redis.Redis = None  # type: ignore[assignment]
db_pool: asyncpg.Pool = None  # type: ignore[assignment]
shutdown_event: asyncio.Event = asyncio.Event()


# =============================================================================
# DATABASE INITIALIZATION
# =============================================================================
async def init_db() -> None:
    """Initialize the database connection pool and create table if needed."""
    global db_pool
    retries = 5
    while retries > 0:
        try:
            db_pool = await asyncpg.create_pool(settings.database_url)
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS events (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        timestamp TIMESTAMPTZ NOT NULL,
                        metadata JSONB NOT NULL
                    );
                """)
            logger.info("Database initialized and table verified.")
            return
        except Exception as e:
            logger.warning(f"DB Connection failed, retrying in 2s... ({e})")
            retries -= 1
            await asyncio.sleep(2)
    raise RuntimeError("Could not connect to Database after retries.")


# =============================================================================
# REDIS STREAM INITIALIZATION
# =============================================================================
async def init_stream() -> None:
    """Create the consumer group for the stream if it doesn't exist."""
    try:
        # MKSTREAM creates the stream if it doesn't exist
        await redis_client.xgroup_create(
            settings.stream_key,
            settings.consumer_group,
            id="0",
            mkstream=True
        )
        logger.info(f"Consumer group '{settings.consumer_group}' created.")
    except redis.ResponseError as e:
        if "BUSYGROUP" in str(e):
            # Group already exists, which is fine
            logger.info(f"Consumer group '{settings.consumer_group}' already exists.")
        else:
            raise


# =============================================================================
# BATCH PROCESSING (Reliable Queue with XACK)
# =============================================================================
async def flush_batch(messages: list[tuple[bytes, dict[bytes, bytes]]]) -> list[bytes]:
    """
    Inserts a batch of events into PostgreSQL.
    Returns the list of message IDs that were successfully processed.
    Uses parameterized queries for SQL injection safety.
    """
    if not messages:
        return []

    successful_ids: list[bytes] = []
    parsed_events: list[tuple[int, datetime, str]] = []
    id_to_data_map: dict[bytes, tuple] = {}

    for msg_id, data in messages:
        try:
            payload = json.loads(data[b"payload"])
            # Parse ISO timestamp robustly (handles Z, +00:00, etc.)
            ts_str = payload["timestamp"]
            if ts_str.endswith("Z"):
                ts_str = ts_str[:-1] + "+00:00"
            ts = datetime.fromisoformat(ts_str)

            event_tuple = (
                payload["user_id"],
                ts,
                json.dumps(payload["metadata"])  # JSONB as string
            )
            parsed_events.append(event_tuple)
            id_to_data_map[msg_id] = event_tuple
        except Exception as e:
            logger.error(f"Failed to parse event {msg_id}: {e}")
            # Mark as successful to ACK and prevent reprocessing of bad data
            successful_ids.append(msg_id)
            continue

    if not parsed_events:
        return successful_ids

    try:
        async with db_pool.acquire() as conn:
            # Parameterized batch insert - safe from SQL injection
            await conn.executemany(
                """
                INSERT INTO events (user_id, timestamp, metadata)
                VALUES ($1, $2::timestamptz, $3::jsonb)
                """,
                parsed_events
            )
        # All inserts succeeded, mark all message IDs as successful
        successful_ids.extend(id_to_data_map.keys())
        logger.info(f"Flushed {len(parsed_events)} events to DB.")
    except Exception as e:
        logger.error(f"DB Write Failed: {e}. Messages will be retried.")
        # Don't add to successful_ids - they will be redelivered by Redis

    return successful_ids


# =============================================================================
# BACKGROUND WORKER (Redis Streams Consumer)
# =============================================================================
async def worker() -> None:
    """
    Background worker using Redis Streams for reliable message processing.
    - XREADGROUP fetches messages and assigns them to this consumer
    - Messages remain in Pending Entries List (PEL) until XACK'd
    - Pending messages are retried by reading from the PEL (stream ID "0")
    """
    logger.info("Worker started.")

    await drain_pending_messages()

    while not shutdown_event.is_set():
        try:
            pending = await redis_client.xreadgroup(
                groupname=settings.consumer_group,
                consumername=settings.consumer_name,
                streams={settings.stream_key: "0"},
                count=settings.batch_size
            )

            if pending and pending[0][1]:
                stream_messages = pending[0][1]
                successful_ids = await flush_batch(stream_messages)
                if successful_ids:
                    await redis_client.xack(
                        settings.stream_key,
                        settings.consumer_group,
                        *successful_ids
                    )
                if len(successful_ids) < len(stream_messages):
                    await asyncio.sleep(0.5)
                continue

            # Read batch from stream (blocks for block_ms if no messages)
            # ">" means only new messages not yet delivered to any consumer
            messages = await redis_client.xreadgroup(
                groupname=settings.consumer_group,
                consumername=settings.consumer_name,
                streams={settings.stream_key: ">"},
                count=settings.batch_size,
                block=settings.block_ms
            )

            if messages:
                # messages format: [[stream_name, [(id, data), ...]]]
                stream_messages = messages[0][1]  # Get the list of (id, data) tuples

                # Process the batch
                successful_ids = await flush_batch(stream_messages)

                # ACK only successfully processed messages
                if successful_ids:
                    await redis_client.xack(
                        settings.stream_key,
                        settings.consumer_group,
                        *successful_ids
                    )
                    logger.debug(f"ACK'd {len(successful_ids)} messages.")

        except asyncio.CancelledError:
            logger.info("Worker received cancellation signal.")
            break
        except Exception as e:
            logger.error(f"Unexpected worker error: {e}")
            await asyncio.sleep(1)

    # Graceful shutdown: process remaining pending messages
    await drain_pending_messages()
    logger.info("Worker shutdown complete.")


async def drain_pending_messages() -> None:
    """
    Attempt to process messages that were claimed but not ACK'd for this consumer.
    """
    logger.info("Draining pending messages...")
    try:
        # Read pending messages for this consumer (messages we claimed but didn't ACK)
        pending = await redis_client.xreadgroup(
            groupname=settings.consumer_group,
            consumername=settings.consumer_name,
            streams={settings.stream_key: "0"},  # "0" = read pending messages
            count=settings.batch_size
        )

        if pending and pending[0][1]:
            stream_messages = pending[0][1]
            logger.info(f"Processing {len(stream_messages)} pending messages...")
            successful_ids = await flush_batch(stream_messages)
            if successful_ids:
                await redis_client.xack(
                    settings.stream_key,
                    settings.consumer_group,
                    *successful_ids
                )
                logger.info(f"Drained and ACK'd {len(successful_ids)} pending messages.")
    except Exception as e:
        logger.error(f"Error draining pending messages: {e}")


# =============================================================================
# APPLICATION LIFESPAN
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    global redis_client

    # Startup
    redis_client = redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=False
    )
    await init_db()
    await init_stream()

    # Start worker task
    worker_task = asyncio.create_task(worker())

    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda: asyncio.create_task(graceful_shutdown(worker_task))
        )

    yield

    # Shutdown
    shutdown_event.set()
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass

    await redis_client.aclose()
    if db_pool:
        await db_pool.close()


async def graceful_shutdown(worker_task: asyncio.Task) -> None:
    """Signal the worker to drain and stop gracefully."""
    logger.info("Graceful shutdown initiated...")
    shutdown_event.set()


# =============================================================================
# FASTAPI APPLICATION
# =============================================================================
app = FastAPI(lifespan=lifespan)


@app.post("/event", status_code=status.HTTP_202_ACCEPTED)
async def ingest_event(event: Event):
    """
    Ingest an event into the Redis Stream.
    Returns immediately with 202 Accepted.
    Data is persisted to PostgreSQL asynchronously by the background worker.
    """
    try:
        # Pydantic V2: model_dump_json() returns a JSON string
        payload = event.model_dump_json()
        # XADD to Redis Stream - message stays until explicitly ACK'd
        await redis_client.xadd(
            settings.stream_key,
            {"payload": payload}
        )
        return {"status": "accepted"}
    except Exception as e:
        logger.error(f"Redis write failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service Unavailable"
        )


@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration."""
    return {"status": "healthy"}
