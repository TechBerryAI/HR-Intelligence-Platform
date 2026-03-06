import os
import sys
import socket
import threading
from flask import Flask, jsonify, request, make_response
from flask_cors import CORS
from dotenv import load_dotenv

# Load .env from backend directory so mail/db config is found regardless of CWD
_backend_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_backend_dir, '.env'))

# Validate environment variables before proceeding
from env_validator import EnvValidator
is_valid, errors, warnings = EnvValidator.validate()
if not is_valid:
    EnvValidator.print_report()
    print("💡 TIP: Copy backend/.env.example to backend/.env and configure it.\n")
    sys.exit(1)
elif warnings:
    # Print warnings but continue
    EnvValidator.print_report()

from extensions import mail
from models import init_models


def _build_allowed_origins():
    env_origins = os.getenv('FRONTEND_URLS') or os.getenv('FRONTEND_URL')
    if env_origins:
        return [origin.strip() for origin in env_origins.split(',') if origin.strip()]
    origins = ['http://localhost:5173', 'http://127.0.0.1:5173']
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
        if local_ip and local_ip != '127.0.0.1':
            origins.append(f'http://{local_ip}:5173')
    except OSError:
        pass
    return origins


app = Flask(__name__)
app.config['JWT_SECRET'] = os.getenv('JWT_SECRET', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoiZXhhbXBsZSJ9.lGrIa8yMwsB_ZSrgoniyr5FF34e9tE7TJboLqTfvifE')
# Mail configuration
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', '587'))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL', 'false').lower() == 'true'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
_raw_sender = (os.getenv('MAIL_DEFAULT_SENDER') or '').strip() or app.config.get('MAIL_USERNAME')
app.config['MAIL_DEFAULT_SENDER'] = (_raw_sender.strip('"').strip("'") if _raw_sender else None) or app.config.get('MAIL_USERNAME')
app.config['MAIL_SUPPRESS_SEND'] = os.getenv('MAIL_SUPPRESS_SEND', 'false').lower() == 'true'
# Timeout for SMTP send (seconds); Flask-Mail has no built-in timeout
app.config['MAIL_TIMEOUT'] = int(os.getenv('MAIL_TIMEOUT', '25'))
# Optional: retries for transient SMTP failures
app.config['MAIL_SEND_RETRIES'] = int(os.getenv('MAIL_SEND_RETRIES', '3'))

# Validate mail config at startup when sending is enabled (catch MAIL_USERNAME=display name)
if not app.config['MAIL_SUPPRESS_SEND'] and app.config.get('MAIL_USERNAME'):
    un = app.config['MAIL_USERNAME'].strip()
    if '@' not in un or '.' not in un.split('@')[-1]:
        print("[MAIL] WARNING: MAIL_USERNAME should be the full email address (e.g. user@gmail.com), not a label. Current value may cause SMTP auth to fail.")
# Disable strict slashes to prevent redirects that break CORS preflight
app.url_map.strict_slashes = False

cors_origins = _build_allowed_origins()
print(f"[CORS] Allowed origins: {cors_origins}")

# CORS: use the explicit origin list so Flask-CORS reflects the actual Origin header.
# browsers block credentialed requests (credentials: 'include') when the server
# responds with Access-Control-Allow-Origin: * — a specific list is required.
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
    }
)

mail.init_app(app)
# Log mail status at startup so we can see if .env was loaded when run from different CWD
if app.config.get('MAIL_SUPPRESS_SEND') or not app.config.get('MAIL_USERNAME') or not app.config.get('MAIL_PASSWORD'):
    print("[MAIL] Suppressed or missing creds — emails will NOT be sent. Check backend/.env and MAIL_USERNAME/MAIL_PASSWORD.")
else:
    print("[MAIL] Configured — sending enabled (server=%s, user=%s)" % (app.config['MAIL_SERVER'], app.config['MAIL_USERNAME']))
init_models()

from db import init_db  # noqa: E402
from auth import auth_bp  # noqa: E402
from jobs import jobs_bp  # noqa: E402
from candidate import candidate_bp  # noqa: E402
from applications import applications_bp  # noqa: E402
from sessions_routes import sessions_bp  # noqa: E402
from routes.simple_candidate_auth import simple_candidate_auth_bp  # noqa: E402
from parsing_routes import parsing_bp  # noqa: E402
from support import support_bp  # noqa: E402
from modules.admin.routes import admin_bp  # noqa: E402

# Database initialization - DO IT AT STARTUP, NOT LAZY
# Lazy loading was causing 10+ second delays on first API call
print("[DB] Initializing database at startup...")
try:
    init_db()
    print("[DB] Database initialized successfully")
except Exception as e:
    err_msg = str(e)
    print(f"[DB ERROR] Failed to initialize database: {e}")
    import traceback
    traceback.print_exc()

# Optional: log if bulk parser URL is set but unreachable (admin bulk upload will use in-process when available)
_bulk_url = (os.getenv('BULK_PARSER_URL') or '').strip().rstrip('/') or None
if _bulk_url:
    try:
        import requests
        r = requests.get(f"{_bulk_url}/health", timeout=2)
        if not r.ok:
            print(f"[BULK PARSER] {_bulk_url} returned {r.status_code}; admin bulk upload may use in-process parsing.")
    except Exception:
        print(f"[BULK PARSER] {_bulk_url} not reachable; admin bulk upload will use in-process parsing when available.")

@app.route('/', methods=['GET'])
def root():
    return jsonify({
        "status": "ok",
        "message": "Job Portal API root. See /health for status.",
        "endpoints": ["/health", "/api", "/api/jobs", "/api/candidate", "/api/applications", "/api/sessions", "/api/admin"]
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
        "message": "Job Portal API is running",
        "bulk_parser": bulk_parser,
    })

@app.route('/api/test-cors', methods=['GET', 'OPTIONS'])
def test_cors():
    """Test endpoint to verify CORS is working"""
    return jsonify({
        "status": "ok",
        "message": "CORS test successful",
        "origin": request.headers.get('Origin'),
        "allowed_origins": cors_origins
    })

app.register_blueprint(auth_bp, url_prefix='/api')
app.register_blueprint(jobs_bp, url_prefix='/api/jobs')
app.register_blueprint(simple_candidate_auth_bp, url_prefix='/api/candidate')
app.register_blueprint(candidate_bp, url_prefix='/api/candidate')
app.register_blueprint(applications_bp, url_prefix='/api/applications')
app.register_blueprint(sessions_bp, url_prefix='/api/sessions')
app.register_blueprint(parsing_bp, url_prefix='/api')
app.register_blueprint(support_bp, url_prefix='/api/support')
# Admin-only: bulk resume parsing (proxy to Bulk-Resume-Parser), job matches (ATS results)
app.register_blueprint(admin_bp, url_prefix='/api/admin')

if __name__ == '__main__':
    port = int(os.getenv('PORT', '3000'))
    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    
    # Disable reloader when running as a job to avoid restart issues
    use_reloader = debug_mode and os.getenv('FLASK_USE_RELOADER', 'false').lower() == 'true'
    
    print(f"[SERVER] Starting Flask server on port {port}...")
    print(f"[SERVER] Debug mode: {debug_mode}, Reloader: {use_reloader}")
    
    app.run(
        host='0.0.0.0', 
        port=port, 
        debug=debug_mode,
        use_reloader=use_reloader,
        threaded=True
    )
