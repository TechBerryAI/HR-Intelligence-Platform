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
# Match request timeout so SIGTERM during a long parse is not followed by a 30s kill.
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", str(timeout)))
keepalive = 5
capture_output = True
enable_stdio_inheritance = True
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
# Path + status only — omit query string so OAuth codes/tokens cannot appear in access logs.
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(m)s %(U)s %(H)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# .env is loaded by wsgi.py on import


def on_starting(server):
    """Validate config and verify schema at head. Never migrate in the web master."""
    from pathlib import Path

    from dotenv import load_dotenv

    os.environ['HCIP_PROCESS_ROLE'] = 'web'
    load_dotenv(Path(__file__).resolve().parent / '.env')
    from app.core.log_redaction import install_log_redaction
    from app.config.env_validator import EnvValidator

    install_log_redaction()

    if not EnvValidator.print_report():
        raise SystemExit(1)
    from app.database.alembic_runner import prepare_schema_for_web_process

    prepare_schema_for_web_process()
    os.environ['HCIP_MIGRATIONS_DONE'] = '1'
    os.environ.setdefault('MIGRATIONS_ALREADY_APPLIED', 'true')


def worker_exit(server, worker):
    """Release outbox leases on worker recycle / SIGTERM (do not rely on atexit alone)."""
    try:
        from app.domains.integrations.worker.outbox import stop_outbox_drain

        stop_outbox_drain(timeout=5.0)
    except Exception:
        server.log.warning("worker_exit: outbox drain stop failed", exc_info=True)
