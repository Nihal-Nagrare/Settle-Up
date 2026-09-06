"""
Settle Up - Flask Backend Application Package
Application factory, SQLAlchemy database initialization, scoped CORS, blueprint registration, and static handlers.
"""

import os
from pathlib import Path
from flask import Flask, send_from_directory, jsonify, request
from werkzeug.exceptions import HTTPException
from .config import get_config, Config
from .models import db
from .db_service import init_database

try:
    from flask_cors import CORS
    HAS_FLASK_CORS = True
except ImportError:
    HAS_FLASK_CORS = False

STATIC_DIR = Path(__file__).resolve().parent.parent


def create_app(config_class=None):
    """Application factory for Settle Up Flask backend."""
    app = Flask(__name__, static_folder=None)

    # Load configuration
    if config_class is None:
        config_class = get_config()
    elif isinstance(config_class, str):
        from .config import config_by_name, DevelopmentConfig
        config_class = config_by_name.get(config_class.lower(), DevelopmentConfig)
    config_obj = config_class() if isinstance(config_class, type) else config_class
    app.config.from_object(config_obj)

    # Initialize SQLAlchemy database
    db.init_app(app)
    init_database(app)

    # Register CLI command for explicit database initialization in production
    @app.cli.command("init-db")
    def init_db_command():
        """Initialize database tables and run non-destructive migrations."""
        init_database(app)
        print("Database initialized successfully.")

    # Apply Werkzeug ProxyFix for reverse proxies (handles HTTPS X-Forwarded-Proto and client IPs)
    if app.config.get('USE_PROXY_FIX'):
        try:
            from werkzeug.middleware.proxy_fix import ProxyFix
            app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
        except ImportError:
            pass

    cors_origins = app.config.get('CORS_ORIGINS', '*')

    # Configure Flask-CORS if available
    if HAS_FLASK_CORS:
        # Note: W3C forbids wildcard with credentials. If wildcard, omit credentials.
        supports_credentials = (cors_origins != '*')
        CORS(
            app,
            resources={r"/api/*": {"origins": cors_origins}},
            supports_credentials=supports_credentials,
            methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["Content-Type", "Authorization", "X-Auth-Token", "X-Member-Id"]
        )

    # Attach comprehensive HTTP security headers and CORS to responses
    @app.after_request
    def apply_security_and_cors_headers(response):
        # 1. Standard HTTP Security Headers (Defense-in-Depth)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # Content-Security-Policy (allows Google fonts, inline styles/scripts for SPA, and remote cloud proof images)
        if not response.headers.get('Content-Security-Policy'):
            csp = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com data:; "
                "img-src 'self' data: blob: https:; "
                "connect-src 'self'; "
                "frame-ancestors 'self';"
            )
            response.headers['Content-Security-Policy'] = csp

        # 2. CORS Headers for API routes
        if request.path.startswith('/api/'):
            if 'Access-Control-Allow-Origin' not in response.headers:
                response.headers['Access-Control-Allow-Origin'] = cors_origins
            if 'Access-Control-Allow-Methods' not in response.headers:
                response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            if 'Access-Control-Allow-Headers' not in response.headers:
                response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Auth-Token, X-Member-Id'
        return response

    # Register API Blueprint
    from .routes import api_bp
    app.register_blueprint(api_bp)

    # JSON Error Handlers for API endpoints
    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        if request.path.startswith('/api/'):
            return jsonify({'error': error.description, 'status': error.code}), error.code
        if error.code == 404:
            return send_from_directory(str(STATIC_DIR), 'index.html')
        return error

    @app.errorhandler(404)
    def not_found_handler(error):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Endpoint not found', 'status': 404}), 404
        # Fallback for frontend SPA navigation
        return send_from_directory(str(STATIC_DIR), 'index.html')

    @app.errorhandler(405)
    def method_not_allowed_handler(error):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Method not allowed', 'status': 405}), 405
        return jsonify({'error': 'Method not allowed'}), 405

    @app.errorhandler(429)
    def rate_limit_handler(error):
        return jsonify({'error': 'Too many requests. Please slow down.', 'status': 429}), 429

    @app.errorhandler(500)
    def internal_error_handler(error):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Internal server error', 'status': 500}), 500
        return jsonify({'error': 'Internal server error'}), 500

    @app.errorhandler(Exception)
    def unhandled_exception_handler(error):
        if isinstance(error, HTTPException):
            return handle_http_exception(error)
        if request.path.startswith('/api/'):
            app.logger.error("Unhandled API exception: %s", error, exc_info=True)
            return jsonify({'error': 'Internal server error', 'status': 500}), 500
        raise error

    # Initialize secure proof storage directory
    from . import proof_storage
    proof_storage.get_upload_dir(app)

    # Static frontend routes
    @app.route('/')
    @app.route('/join-room/<room_id>')
    def serve_index(room_id=None):
        return send_from_directory(str(STATIC_DIR), 'index.html')

    @app.route('/src/<path:filename>')
    def serve_src(filename):
        return send_from_directory(str(STATIC_DIR / 'src'), filename)

    @app.route('/join-room/src/<path:filename>')
    def serve_join_room_src(filename):
        return send_from_directory(str(STATIC_DIR / 'src'), filename)

    @app.route('/<path:filename>')
    def serve_static(filename):
        clean_name = filename.replace('\\', '/').lstrip('/')
        clean_lower = clean_name.lower()

        # Strict security filter: block sensitive private directories, databases, configs, code, logs, and hidden files
        forbidden_prefixes = ('uploads', 'backend', '.', 'venv', 'node_modules', 'brain', '__pycache__', 'scratch')
        forbidden_suffixes = ('.db', '.sqlite', '.sqlite3', '.py', '.pyc', '.env', '.log', '.jsonl', '.sh', '.bat', '.ps1', '.pem', '.key', '.bak', '.tar', '.gz', '.zip')

        if (
            any(clean_lower.startswith(prefix) for prefix in forbidden_prefixes) or
            any(clean_lower.endswith(suffix) for suffix in forbidden_suffixes) or
            'test_' in clean_lower or
            clean_lower.startswith('requirements')
        ):
            return jsonify({'error': 'Forbidden: Static access to private system files is blocked', 'status': 403}), 403

        # Path traversal boundary verification
        try:
            target_path = (STATIC_DIR / clean_name).resolve()
            if not str(target_path).startswith(str(STATIC_DIR.resolve())):
                return jsonify({'error': 'Forbidden: Path traversal attempt detected', 'status': 403}), 403

            if target_path.exists() and target_path.is_file():
                return send_from_directory(str(STATIC_DIR), clean_name)
        except Exception:
            pass

        return send_from_directory(str(STATIC_DIR), 'index.html')

    return app
