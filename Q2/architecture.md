# Architecture Description

## Overview
The "Firehose" Collector is designed to handle high-throughput event ingestion (5,000+ RPS) with non-blocking responses and **zero data loss** resilience against database outages.

## Components

### 1. API Layer (FastAPI)
- **Framework:** FastAPI (Python) running with Uvicorn.
- **Endpoint:** `POST /event`
- **Behavior:**
  - Accepts JSON payload.
  - Validates schema using Pydantic V2.
  - **Non-blocking:** Immediately pushes the serialized event to a Redis Stream (`XADD`) and returns `HTTP 202 Accepted`.
  - Does NOT wait for database persistence.

### 2. Buffering Layer (Redis Streams)
- **Technology:** Redis Streams (not simple Lists).
- **Why Streams over Lists?**
  - **Reliable Queue Pattern:** Messages remain in the Pending Entries List (PEL) until explicitly acknowledged (`XACK`).
  - **At-Least-Once Delivery:** A message is only removed from the PEL after a successful DB write and `XACK`.
  - **Consumer Groups:** Enables horizontal scaling with multiple workers.
- **Key / Group / Consumer Name:** Configured via `STREAM_KEY`, `CONSUMER_GROUP`, `CONSUMER_NAME`.

### 3. Storage Layer (PostgreSQL)
- **Database:** PostgreSQL (running in Docker).
- **Schema:** Simple `events` table with JSONB column for arbitrary metadata.
  - `user_id` (BIGINT)
  - `timestamp` (TIMESTAMPTZ) - Timezone-aware timestamps
  - `metadata` (JSONB) - Safely stores unstructured data
- **Security:** All database operations use parameterized queries (`$1`, `$2`, etc.) preventing SQL injection.

### 4. Background Worker (Asyncio + Redis Consumer Group)
- **Mechanism:** A background task launched within the FastAPI application lifespan.
- **Process:**
  1. Reads pending messages from the PEL for this consumer (`XREADGROUP` with stream ID `0`) and retries them first.
  2. Reads new messages (`XREADGROUP` with stream ID `>`).
  3. Parses JSON and performs bulk insert using `asyncpg.executemany()`.
  4. Only after successful DB write, calls `XACK` to remove messages from the PEL.
- **Resilience Strategy:**
  - **Database Outage:** If the DB write fails, messages are NOT acknowledged and remain pending in the PEL.
  - **Retry:** The worker retries PEL messages on subsequent iterations (with a short backoff).
  - **Malformed Payloads:** If a message payload can’t be parsed, it is acknowledged to avoid a poison-pill loop.
  - **Graceful Shutdown:** On SIGTERM/SIGINT, the worker drains pending messages before exiting.

### 5. Configuration (Externalized)
- **Technology:** `pydantic-settings` with environment variable support.
- **Benefits:**
  - No hardcoded credentials in source code.
  - Easy deployment across environments (dev, staging, prod).
  - Supports `.env` files for local development.
- **Variables:**
  - `REDIS_URL` - Redis connection string
  - `DATABASE_URL` - PostgreSQL connection string
  - `STREAM_KEY` - Redis stream name
  - `CONSUMER_GROUP` - Consumer group name
  - `CONSUMER_NAME` - Consumer name within the group
  - `BATCH_SIZE` - Number of events per batch
  - `BLOCK_MS` - Max stream blocking read time (ms)

## Data Flow
```
Client -> [POST /event] -> FastAPI -> Redis Stream (XADD)
                                          |
                                          v
                          [Background Worker (XREADGROUP)]
                                          |
                                          v
                                    PostgreSQL (INSERT)
                                          |
                                          v
                              Redis Stream (XACK - remove from PEL)
```

## Reliability Guarantees

| Failure Scenario | Behavior |
|-----------------|----------|
| Worker crashes after XREADGROUP | Messages remain in PEL; retried when consumer resumes |
| DB outage during INSERT | No XACK sent; messages remain pending and are retried |
| Redis outage | API returns 503, no data accepted |
| Graceful shutdown | Worker drains pending messages before exit |

## Security Measures

1. **SQL Injection Prevention:**
   - All queries use parameterized statements (`$1`, `$2`, `$3`)
   - JSONB data is serialized via `json.dumps()` and cast via `::jsonb`
   - No string concatenation in SQL queries

2. **Configuration Security:**
   - No hardcoded credentials
   - Environment variables for all sensitive data
   - `.env` file support for local development (not committed)

## Performance Characteristics

- **Throughput:** 5,000+ RPS (limited by Redis, not application)
- **Latency:** Sub-millisecond API response (just XADD + return)
- **Batching:** Configurable batch size (default: 100 events)
- **Backpressure:** Redis Streams handle bursts; worker processes at DB speed
