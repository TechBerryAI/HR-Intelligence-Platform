import os
import socket
from flask import Flask, jsonify, request, make_response
from flask_cors import CORS
from dotenv import load_dotenv

from extensions import mail
from models import init_models

load_dotenv()


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
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', app.config.get('MAIL_USERNAME'))
app.config['MAIL_SUPPRESS_SEND'] = os.getenv('MAIL_SUPPRESS_SEND', 'false').lower() == 'true'
# Disable strict slashes to prevent redirects that break CORS preflight
app.url_map.strict_slashes = False

cors_origins = _build_allowed_origins()
print(f"[CORS] Allowed origins: {cors_origins}")

# CORS Preflight Handler - Allow OPTIONS requests
@app.before_request
def handle_cors_preflight():
    """Handle CORS preflight requests - permissive for development"""
    origin = request.headers.get('Origin')
    
    # Handle OPTIONS preflight requests
    if request.method == 'OPTIONS':
        print(f"[CORS] OPTIONS preflight: {request.path} from {origin or 'same-origin'}")
        
        # Create response for OPTIONS
        response = make_response()
        response.status_code = 200
        
        # If origin is present and in allowed list, set it
        if origin and origin in cors_origins:
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Credentials'] = 'true'
            print(f"[CORS] Preflight allowed for {origin}")
        # If origin present but not in list, still allow but don't set credentials
        elif origin:
            response.headers['Access-Control-Allow-Origin'] = origin
            print(f"[CORS] Preflight allowed for {origin} (without credentials)")
        # If no origin (same-origin request), allow without CORS headers
        else:
            print(f"[CORS] Preflight allowed for same-origin request")
        
        # Set other CORS headers for all OPTIONS requests
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, Accept, X-Requested-With'
        response.headers['Access-Control-Max-Age'] = '3600'
        
        return response

# Configure Flask-CORS as backup layer
# Note: Manual handlers above take precedence, this provides fallback
cors = CORS(
    app,
    resources={
        r"/*": {
            "origins": "*",  # Allow all origins (credentials controlled by manual handler)
            "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
            "allow_headers": ["Content-Type", "Authorization", "Accept", "X-Requested-With"],
            "expose_headers": ["Content-Type", "Authorization"],
            "max_age": 3600,
        }
    },
    supports_credentials=False,  # Credentials only for whitelisted origins (handled manually)
    automatic_options=False,  # We handle OPTIONS manually in before_request
)

# Add CORS headers to responses
@app.after_request
def add_cors_headers(response):
    """Add CORS headers to API responses"""
    origin = request.headers.get('Origin')
    
    # For API routes, set CORS headers
    if request.path.startswith('/api') or request.path.startswith('/health'):
        if origin:
            # Allow whitelisted origins with credentials
            if origin in cors_origins:
                response.headers['Access-Control-Allow-Origin'] = origin
                response.headers['Access-Control-Allow-Credentials'] = 'true'
                print(f"[CORS] Headers added to {request.method} {request.path} for {origin} (trusted)")
            # Allow other origins without credentials (for development flexibility)
            else:
                response.headers['Access-Control-Allow-Origin'] = origin
                print(f"[CORS] Headers added to {request.method} {request.path} for {origin} (untrusted)")
            
            # Set other CORS headers for all origins
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, Accept, X-Requested-With'
            response.headers['Access-Control-Expose-Headers'] = 'Content-Type, Authorization'
            response.headers['Access-Control-Max-Age'] = '3600'
        # Same-origin requests don't need CORS headers
        else:
            print(f"[CORS] Same-origin request to {request.method} {request.path}")
    
    return response

mail.init_app(app)
init_models()

from db import init_db  # noqa: E402
from auth import auth_bp  # noqa: E402
from jobs import jobs_bp  # noqa: E402
from candidate import candidate_bp  # noqa: E402
from applications import applications_bp  # noqa: E402
from sessions_routes import sessions_bp  # noqa: E402
from routes.candidate_auth import candidate_auth_bp  # noqa: E402
from parsing_routes import parsing_bp  # noqa: E402

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
app.register_blueprint(candidate_auth_bp, url_prefix='/api/candidate')
app.register_blueprint(candidate_bp, url_prefix='/api/candidate')
app.register_blueprint(applications_bp, url_prefix='/api/applications')
app.register_blueprint(sessions_bp, url_prefix='/api/sessions')
app.register_blueprint(parsing_bp, url_prefix='/api')

if __name__ == '__main__':
    init_db()
    port = int(os.getenv('PORT', '3000'))
    app.run(host='0.0.0.0', port=port, debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true')
