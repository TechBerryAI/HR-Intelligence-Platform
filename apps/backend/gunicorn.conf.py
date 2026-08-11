# Gunicorn config for production on Ubuntu/Linux
# Run from backend dir: gunicorn -c gunicorn.conf.py wsgi:app

import os

bind = os.getenv("GUNICORN_BIND", "127.0.0.1:3000")
workers = int(os.getenv("GUNICORN_WORKERS", "4"))
worker_class = "gthread"
threads = 2
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
# Exceed AI parse default_timeout_seconds (300) so long resume/JD parses are not killed mid-request.
timeout = int(os.getenv("GUNICORN_TIMEOUT", "320"))
keepalive = 5
capture_output = True
enable_stdio_inheritance = True
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")

# .env is loaded by wsgi.py on import
