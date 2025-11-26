import os
import socket
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from extensions import mail
from models import init_models

load_dotenv()


def _build_allowed_origins():
    env_origins = os.getenv('FRONTEND_URLS') or os.getenv('FRONTEND_URL')
    if env_origins:
        return [origin.strip() for origin in env_origins.split(',') if origin.strip()]
    origins = {'http://localhost:5173', 'http://127.0.0.1:5173'}
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
        if local_ip:
            origins.add(f'http://{local_ip}:5173')
    except OSError:
        pass
    return sorted(origins)


app = Flask(__name__)
app.config['JWT_SECRET'] = os.getenv('JWT_SECRET', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoiZXhhbXBsZSJ9.lGrIa8yMwsB_ZSrgoniyr5FF34e9tE7TJboLqTfvifE')
# Mail configuration
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', '587'))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL', 'false').lower() == 'true'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', app.config.get('MAIL_USERNAME'))
app.config['MAIL_SUPPRESS_SEND'] = os.getenv('MAIL_SUPPRESS_SEND', 'false').lower() == 'true'
# Disable strict slashes to prevent redirects that break CORS preflight
app.url_map.strict_slashes = False

cors_origins = _build_allowed_origins()
# Fix CORS: Explicitly allow OPTIONS method and handle preflight properly
CORS(
    app,
    resources={
        r"/api/*": {
            "origins": cors_origins,
            "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "supports_credentials": True,
        }
    },
    supports_credentials=True,
    automatic_options=True,
)

mail.init_app(app)
init_models()

from db import init_db  # noqa: E402
from auth import auth_bp  # noqa: E402
from jobs import jobs_bp  # noqa: E402
from candidate import candidate_bp  # noqa: E402
from applications import applications_bp  # noqa: E402
from sessions_routes import sessions_bp  # noqa: E402
from routes.candidate_auth import candidate_auth_bp  # noqa: E402

@app.route('/', methods=['GET'])
def root():
    return jsonify({
        "status": "ok",
        "message": "Job Portal API root. See /health for status.",
        "endpoints": ["/health", "/api", "/api/jobs", "/api/candidate", "/api/applications", "/api/sessions"]
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "message": "Job Portal API is running"})

app.register_blueprint(auth_bp, url_prefix='/api')
app.register_blueprint(jobs_bp, url_prefix='/api/jobs')
app.register_blueprint(candidate_auth_bp, url_prefix='/api/candidate')
app.register_blueprint(candidate_bp, url_prefix='/api/candidate')
app.register_blueprint(applications_bp, url_prefix='/api/applications')
app.register_blueprint(sessions_bp, url_prefix='/api/sessions')

if __name__ == '__main__':
    init_db()
    port = int(os.getenv('PORT', '3000'))
    app.run(host='0.0.0.0', port=port, debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true')
