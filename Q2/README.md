# Q2 — Firehose Collector

A high-throughput ingestion service that accepts events at `POST /event` and returns `202 Accepted` immediately, buffering events in Redis Streams and persisting them to PostgreSQL asynchronously in batches.

## Project Files

- `app.py`: FastAPI service with Redis Streams buffering and a background worker.
- `architecture.md`: Architecture description (buffering, batching, reliability).
- `load_test.py`: Locust load test for concurrent request generation.
- `simulate_outage.py`: Script that simulates a PostgreSQL outage via table locks.
- `docker-compose.yml`: Redis + PostgreSQL containers for local dev.
- `requirements.txt`: Python dependencies.

## Setup

Create a virtual environment and install dependencies:

```bash
python3 -m venv venv
./venv/bin/python -m pip install -r requirements.txt
```

Start Redis + PostgreSQL:

```bash
docker compose up -d
```

## Configuration

Create a `.env` file in this folder:

```env
REDIS_URL=redis://127.0.0.1:6379
DATABASE_URL=postgresql://user:password@127.0.0.1:5439/firehose
STREAM_KEY=event_stream
CONSUMER_GROUP=event_processors
CONSUMER_NAME=worker-1
BATCH_SIZE=100
BLOCK_MS=1000
```

## Run

```bash
./venv/bin/uvicorn app:app --host 0.0.0.0 --port 8002
```

## Verify

Health check:

```bash
curl http://127.0.0.1:8002/health
```

Send an event (expects `202`):

```bash
curl -X POST http://127.0.0.1:8002/event \
  -H 'Content-Type: application/json' \
  -d '{"user_id":1,"timestamp":"2026-01-14T00:00:00Z","metadata":{"k":"v"}}'
```

Simulate a DB outage (while the API is running):

```bash
./venv/bin/python simulate_outage.py --duration 5
```

## Load Test

```bash
./venv/bin/locust -f load_test.py --host http://127.0.0.1:8002
```

