"""Flask application factory."""
from __future__ import annotations

import os
import socket
import sys

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask.wrappers import Request as FlaskRequest
from flask_cors import CORS

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(_BACKEND_DIR, '.env'))

from app.bootstrap.extensions import mail  # noqa: E402
from app.config.env_validator import EnvValidator  # noqa: E402


class _AppRequest(FlaskRequest):
    """Werkzeug 3.1 defaults (1000 parts / 500KB) break bulk multipart uploads.

    Flask 3.0.x only wires MAX_CONTENT_LENGTH from config; form limits must be set
    on the Request class (Flask 3.1+ adds MAX_FORM_* config keys).
    """

    max_form_memory_size = int(os.getenv('MAX_FORM_MEMORY_SIZE', str(64 * 1024 * 1024)))
    max_form_parts = int(os.getenv('MAX_FORM_PARTS', '2000'))


def _build_allowed_origins():
    env_origins = os.getenv('FRONTEND_URLS') or os.getenv('FRONTEND_URL')
    if env_origins:
        origins = [origin.strip() for origin in env_origins.split(',') if origin.strip()]
    else:
        origins = ['http://localhost:5173', 'http://127.0.0.1:5173']
        try:
            local_ip = socket.gethostbyname(socket.gethostname())
            if local_ip and local_ip != '127.0.0.1':
                origins.append(f'http://{local_ip}:5173')
        except OSError:
            pass
    if os.getenv('FLASK_DEBUG', 'false').lower() == 'true':
        # Localhost any port + private LAN (for direct API access without editing .env)
        origins.extend(
            [
                r'http://localhost:\d+',
                r'http://127\.0\.0\.1:\d+',
                r'http://192\.168\.\d+\.\d+:\d+',
                r'http://10\.\d+\.\d+\.\d+:\d+',
                r'http://172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+:\d+',
            ]
        )
    return origins


def create_app() -> Flask:
    is_valid, errors, warnings = EnvValidator.validate()
    if not is_valid:
        EnvValidator.print_report()
        print("💡 TIP: Copy apps/backend/.env.example to apps/backend/.env and configure it.\n")
        sys.exit(1)
    elif warnings:
        EnvValidator.print_report()

    try:
        from app.ai.parser.engine.hardware import apply_hardware_env

        apply_hardware_env()
    except Exception as exc:
        print(f"[AI] hardware profile apply skipped: {exc}")

    from app.domains.identity.models import init_models  # noqa: E402

    app = Flask(__name__)
    app.request_class = _AppRequest
    # Bulk resume uploads: raise body size (Flask wires this via Request.max_content_length).
    # Form part/memory limits are on _AppRequest (see class docstring).
    app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', str(512 * 1024 * 1024)))
    from app.core.auth import JWT_SECRET
    app.config['JWT_SECRET'] = JWT_SECRET
    app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', '587'))
    app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
    app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL', 'false').lower() == 'true'
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    _raw_sender = (os.getenv('MAIL_DEFAULT_SENDER') or '').strip() or app.config.get('MAIL_USERNAME')
    app.config['MAIL_DEFAULT_SENDER'] = (
        (_raw_sender.strip('"').strip("'") if _raw_sender else None) or app.config.get('MAIL_USERNAME')
    )
    app.config['MAIL_SUPPRESS_SEND'] = os.getenv('MAIL_SUPPRESS_SEND', 'false').lower() == 'true'
    app.config['MAIL_TIMEOUT'] = int(os.getenv('MAIL_TIMEOUT', '25'))
    app.config['MAIL_SEND_RETRIES'] = int(os.getenv('MAIL_SEND_RETRIES', '3'))
    app.config['DEVELOPER_MODE'] = os.getenv('DEVELOPER_MODE', 'false').lower() in (
        '1', 'true', 'yes', 'on',
    )

    if not app.config['MAIL_SUPPRESS_SEND'] and app.config.get('MAIL_USERNAME'):
        un = app.config['MAIL_USERNAME'].strip()
        if '@' not in un or '.' not in un.split('@')[-1]:
            print(
                "[MAIL] WARNING: MAIL_USERNAME should be the full email address "
                "(e.g. user@gmail.com), not a label. Current value may cause SMTP auth to fail."
            )
    app.url_map.strict_slashes = False

    cors_origins = _build_allowed_origins()
    print(f"[CORS] Allowed origins: {cors_origins}")

    CORS(
        app,
        resources={
            r"/*": {
                "origins": cors_origins,
                "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
                "allow_headers": ["Content-Type", "Authorization", "Accept", "X-Requested-With", "X-Platform-Key"],
                "expose_headers": ["Content-Type", "Authorization"],
                "supports_credentials": True,
                "max_age": 3600,
            }
        },
    )

    mail.init_app(app)
    if (
        app.config.get('MAIL_SUPPRESS_SEND')
        or not app.config.get('MAIL_USERNAME')
        or not app.config.get('MAIL_PASSWORD')
    ):
        print(
            "[MAIL] Suppressed or missing creds — emails will NOT be sent. "
            "Check apps/backend/.env and MAIL_USERNAME/MAIL_PASSWORD."
        )
    else:
        print(
            "[MAIL] Configured — sending enabled (server=%s, user=%s)"
            % (app.config['MAIL_SERVER'], app.config['MAIL_USERNAME'])
        )

    from app.core.log_redaction import install_log_redaction  # noqa: E402
    from app.core.structured_logging import configure_structured_logging  # noqa: E402

    install_log_redaction()
    configure_structured_logging(app)

    @app.after_request
    def _security_headers(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault(
            'Permissions-Policy',
            'camera=(), microphone=(), geolocation=(), payment=()',
        )
        return response

    init_models()

    from app.domains.administration.api.admin import admin_bp  # noqa: E402
    from app.domains.administration.api.developer import developer_bp  # noqa: E402
    from app.domains.administration.api.head_hr import head_hr_bp  # noqa: E402
    from app.domains.administration.api.platform import platform_bp  # noqa: E402
    from app.domains.candidate.api.routes import candidate_bp  # noqa: E402
    from app.domains.employee.api.feedback import feedback_bp  # noqa: E402
    from app.domains.identity.api.companies import companies_bp  # noqa: E402
    from app.domains.identity.api.hr_auth import auth_bp  # noqa: E402
    from app.domains.identity.sessions.routes import sessions_bp  # noqa: E402
    from app.domains.recruitment.api.applications import applications_bp  # noqa: E402
    from app.domains.recruitment.api.jobs import jobs_bp  # noqa: E402
    from app.domains.recruitment.api.parsing import parsing_bp  # noqa: E402
    from app.domains.support.api.routes import support_bp  # noqa: E402
    from app.domains.support.api.media import media_bp  # noqa: E402
    from app.domains.integrations.api.routes import integrations_bp  # noqa: E402
    from app.domains.integrations.api.calendar_oauth_routes import calendar_oauth_bp  # noqa: E402
    from app.domains.recruitment.api.interview_booking import interview_bp  # noqa: E402


    # Developer Mode: correlate @timing events per HTTP request (no-op when disabled)
    @app.before_request
    def _developer_timing_begin():
        try:
            from app.core.developer_mode import is_developer_mode_enabled
            from app.core.request_context import start_request_context
            from app.core.timing_collector import timing_collector

            if not is_developer_mode_enabled():
                return
            # Skip noisy probes and the developer dashboard APIs themselves
            path = request.path or ''
            if path in ('/health', '/ready', '/', '/api/test-cors') or path.startswith('/api/admin/developer'):
                return
            ctx = start_request_context(path=path, method=request.method)
            timing_collector.begin_session(
                request_id=ctx.request_id,
                started_at=ctx.started_at_iso,
                path=ctx.path,
                method=ctx.method,
            )
            request.timing_request_id = ctx.request_id
            request.timing_started_at = ctx.started_at
        except Exception:
            pass

    @app.teardown_request
    def _developer_timing_end(exc):
        try:
            from app.core.developer_mode import is_developer_mode_enabled
            from app.core.request_context import get_timing_context, set_timing_context
            from app.core.timing_collector import timing_collector
            import time as _time

            if not is_developer_mode_enabled():
                return
            rid = getattr(request, 'timing_request_id', None)
            started = getattr(request, 'timing_started_at', None)
            if not rid:
                ctx = get_timing_context()
                rid = ctx.request_id if ctx else None
                started = ctx.started_at if ctx else None
            if rid:
                wall_ms = None
                if started is not None:
                    wall_ms = (_time.perf_counter() - started) * 1000.0
                if exc is not None:
                    timing_collector.mark_error(rid)
                timing_collector.end_session(rid, wall_duration_ms=wall_ms)
            set_timing_context(None)
        except Exception:
            pass

    print("[DB] Initializing database at startup...")
    _db_host = os.getenv('POSTGRES_HOST', os.getenv('PGHOST', 'localhost'))
    _db_port = os.getenv('POSTGRES_PORT', os.getenv('PGPORT', '5432'))
    _db_name = os.getenv('POSTGRES_DB', os.getenv('PGDATABASE', 'postgres'))
    print(f"[DB] Target: {_db_host}:{_db_port}/{_db_name}")
    try:
        from app.database.alembic_runner import prepare_schema_for_web_process

        prepare_schema_for_web_process()
    except Exception as e:
        from app.core.errors import log_unexpected

        log_unexpected(
            'prepare_schema_for_web_process',
            e,
            host=_db_host,
            port=_db_port,
            db=_db_name,
        )
        print(
            "[DB ERROR] STARTUP BLOCKED — production must migrate once then set "
            "MIGRATIONS_ALREADY_APPLIED=true; development may run alembic upgrade head."
        )
        sys.exit(1)

    _bulk_url = (os.getenv('BULK_PARSER_URL') or '').strip().rstrip('/') or None
    if _bulk_url:
        try:
            import requests
            r = requests.get(f"{_bulk_url}/health", timeout=2)
            if not r.ok:
                print(
                    f"[BULK PARSER] {_bulk_url} returned {r.status_code}; "
                    "admin bulk upload may use in-process parsing."
                )
        except Exception:
            print(
                f"[BULK PARSER] {_bulk_url} not reachable; "
                "admin bulk upload will use in-process parsing when available."
            )

    @app.route('/', methods=['GET'])
    def root():
        return jsonify({
            "status": "ok",
            "message": "HR Intelligence API root. See /health for status.",
            "endpoints": [
                "/health", "/ready", "/api", "/api/jobs", "/api/candidate",
                "/api/applications", "/api/sessions", "/api/admin",
                "/api/integrations",
            ],
        })

    def _check_postgres() -> str:
        try:
            from app.database.connection.db import get_conn

            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute('SELECT 1')
                    cur.fetchone()
            return 'ok'
        except Exception:
            return 'error'

    def _check_ollama() -> str:
        base = (
            (os.getenv('OLLAMA_HOST') or os.getenv('OLLAMA_BASE_URL') or '')
            .strip()
            .rstrip('/')
        )
        if not base:
            return 'not_configured'
        try:
            import requests

            r = requests.get(f'{base}/api/tags', timeout=2)
            return 'ok' if r.ok else 'unreachable'
        except Exception:
            return 'unreachable'

    def _check_bulk_parser() -> str:
        bulk_url = (os.getenv('BULK_PARSER_URL') or '').rstrip('/')
        if not bulk_url:
            return 'not_configured'
        try:
            import requests

            r = requests.get(f'{bulk_url}/health', timeout=2)
            return 'ok' if r.ok else 'unreachable'
        except Exception:
            return 'unreachable'

    @app.route('/health', methods=['GET'])
    def health():
        """Liveness: process is up. Reports dependency status; does not fail on Ollama/DB."""
        from app.core.shared_store import redis_status

        checks = {
            'postgres': _check_postgres(),
            'redis': redis_status(),
            'ollama': _check_ollama(),
            'bulk_parser': _check_bulk_parser(),
        }
        return jsonify({
            'status': 'ok',
            'message': 'HR Intelligence API is running',
            'pid': os.getpid(),
            'checks': checks,
            # Back-compat for older probes
            'bulk_parser': checks['bulk_parser'],
        })

    @app.route('/ready', methods=['GET'])
    def ready():
        """Readiness: Postgres (and Redis when REDIS_URL is set) must be reachable."""
        postgres = _check_postgres()
        redis_url = (os.getenv('REDIS_URL') or '').strip()
        redis = None
        ready_ok = postgres == 'ok'
        if redis_url:
            from app.core.shared_store import redis_status

            redis = redis_status()
            ready_ok = ready_ok and redis == 'ok'
        body = {
            'status': 'ready' if ready_ok else 'not_ready',
            'postgres': postgres,
        }
        if redis is not None:
            body['redis'] = redis
        return jsonify(body), (200 if ready_ok else 503)

    if os.getenv('FLASK_DEBUG', 'false').lower() == 'true':
        @app.route('/api/test-cors', methods=['GET', 'OPTIONS'])
        def test_cors():
            return jsonify({
                "status": "ok",
                "message": "CORS test successful",
                "origin": request.headers.get('Origin'),
                "allowed_origins": cors_origins,
            })

    app.register_blueprint(auth_bp, url_prefix='/api')
    app.register_blueprint(companies_bp, url_prefix='/api/companies')
    app.register_blueprint(platform_bp, url_prefix='/api/platform')
    app.register_blueprint(jobs_bp, url_prefix='/api/jobs')
    app.register_blueprint(candidate_bp, url_prefix='/api/candidate')
    app.register_blueprint(applications_bp, url_prefix='/api/applications')
    app.register_blueprint(sessions_bp, url_prefix='/api/sessions')
    app.register_blueprint(parsing_bp, url_prefix='/api')
    app.register_blueprint(support_bp, url_prefix='/api/support')
    app.register_blueprint(media_bp, url_prefix='/api/media')
    app.register_blueprint(feedback_bp, url_prefix='/api/feedback')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(developer_bp, url_prefix='/api/admin/developer')
    app.register_blueprint(head_hr_bp, url_prefix='/api/head-hr')
    app.register_blueprint(integrations_bp, url_prefix='/api/integrations')
    app.register_blueprint(calendar_oauth_bp, url_prefix='/api/integrations')
    app.register_blueprint(interview_bp, url_prefix='/api/interviews')

    try:
        from app.core import media_storage, site_assets
        from app.core.data_home import ensure_data_layout
        layout = ensure_data_layout()
        root = media_storage.get_media_root()
        media_storage.ensure_hero_video()
        hero = site_assets.ensure_hero_video_in_db()
        size = int(hero.get('byte_size') or 0) if hero else 0
        print(
            f"[MEDIA] DATA_HOME={layout['data_home']} "
            f"MEDIA_ROOT={root} hero_db_bytes={size}"
        )
    except Exception as e:
        from app.core.errors import log_unexpected

        log_unexpected('media_init', e)

    try:
        from app.domains.integrations.bootstrap import init_integrations
        init_integrations()
        print("[INTEGRATIONS] Framework initialized")
    except Exception as e:
        from app.core.errors import log_unexpected

        log_unexpected('integrations_init', e)

    if app.config.get('DEVELOPER_MODE'):
        print("[DEVELOPER MODE] Enabled — Admin performance collector active")

    return app
