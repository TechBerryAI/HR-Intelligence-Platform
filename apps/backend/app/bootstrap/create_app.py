"""Flask application factory."""
from __future__ import annotations

import os
import socket
import sys

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(_BACKEND_DIR, '.env'))

from app.bootstrap.extensions import mail  # noqa: E402
from app.config.env_validator import EnvValidator  # noqa: E402


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

    from app.domains.identity.models import init_models  # noqa: E402

    app = Flask(__name__)
    app.config['JWT_SECRET'] = os.getenv(
        'JWT_SECRET',
        'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoiZXhhbXBsZSJ9.lGrIa8yMwsB_ZSrgoniyr5FF34e9tE7TJboLqTfvifE',
    )
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
                "allow_headers": ["Content-Type", "Authorization", "Accept", "X-Requested-With"],
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
    init_models()

    from app.database.connection.db import init_db  # noqa: E402
    from app.domains.administration.api.admin import admin_bp  # noqa: E402
    from app.domains.administration.api.head_hr import head_hr_bp  # noqa: E402
    from app.domains.candidate.api.routes import candidate_bp  # noqa: E402
    from app.domains.employee.api.feedback import feedback_bp  # noqa: E402
    from app.domains.identity.api.hr_auth import auth_bp  # noqa: E402
    from app.domains.identity.sessions.routes import sessions_bp  # noqa: E402
    from app.domains.recruitment.api.applications import applications_bp  # noqa: E402
    from app.domains.recruitment.api.jobs import jobs_bp  # noqa: E402
    from app.domains.recruitment.api.parsing import parsing_bp  # noqa: E402
    from app.domains.support.api.routes import support_bp  # noqa: E402

    print("[DB] Initializing database at startup...")
    _db_host = os.getenv('POSTGRES_HOST', os.getenv('PGHOST', 'localhost'))
    _db_port = os.getenv('POSTGRES_PORT', os.getenv('PGPORT', '5432'))
    _db_name = os.getenv('POSTGRES_DB', os.getenv('PGDATABASE', 'postgres'))
    print(f"[DB] Target: {_db_host}:{_db_port}/{_db_name}")
    try:
        init_db()
        print("[DB] Database initialized successfully")
    except Exception as e:
        print(f"[DB ERROR] Failed to initialize database ({_db_host}:{_db_port}/{_db_name}): {e}")
        import traceback
        traceback.print_exc()

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
                "/health", "/api", "/api/jobs", "/api/candidate",
                "/api/applications", "/api/sessions", "/api/admin",
            ],
        })

    @app.route('/health', methods=['GET'])
    def health():
        bulk_parser = "not_configured"
        bulk_url = os.getenv('BULK_PARSER_URL', '').rstrip('/')
        if bulk_url:
            try:
                import requests
                r = requests.get(f"{bulk_url}/health", timeout=2)
                bulk_parser = "ok" if r.ok else "unreachable"
            except Exception:
                bulk_parser = "unreachable"
        return jsonify({
            "status": "ok",
            "message": "HR Intelligence API is running",
            "bulk_parser": bulk_parser,
        })

    @app.route('/api/test-cors', methods=['GET', 'OPTIONS'])
    def test_cors():
        return jsonify({
            "status": "ok",
            "message": "CORS test successful",
            "origin": request.headers.get('Origin'),
            "allowed_origins": cors_origins,
        })

    app.register_blueprint(auth_bp, url_prefix='/api')
    app.register_blueprint(jobs_bp, url_prefix='/api/jobs')
    app.register_blueprint(candidate_bp, url_prefix='/api/candidate')
    app.register_blueprint(applications_bp, url_prefix='/api/applications')
    app.register_blueprint(sessions_bp, url_prefix='/api/sessions')
    app.register_blueprint(parsing_bp, url_prefix='/api')
    app.register_blueprint(support_bp, url_prefix='/api/support')
    app.register_blueprint(feedback_bp, url_prefix='/api/feedback')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(head_hr_bp, url_prefix='/api/head-hr')

    return app
