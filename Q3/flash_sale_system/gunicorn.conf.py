import os
import multiprocessing

bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")
workers = int(os.getenv("WEB_CONCURRENCY", multiprocessing.cpu_count()))
worker_class = "uvicorn.workers.UvicornWorker"

loglevel = os.getenv("GUNICORN_LOGLEVEL", "info")
accesslog = os.getenv("GUNICORN_ACCESSLOG") or None
errorlog = "-"

timeout = int(os.getenv("GUNICORN_TIMEOUT", "60"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))

max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "100"))

preload_app = False
reuse_port = True
backlog = int(os.getenv("GUNICORN_BACKLOG", "2048"))
