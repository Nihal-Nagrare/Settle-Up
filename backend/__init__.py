"""
Settle Up - Flask Backend Application Package
Application factory, SQLAlchemy database initialization, scoped CORS, blueprint registration, and static handlers.
"""

import os
from pathlib import Path
from flask import Flask, send_from_directory, jsonify, request
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
    app.config.from_object(config_class)

    # Initialize SQLAlchemy database
    db.init_app(app)
    init_database(app)

    cors_origins = app.config.get('CORS_ORIGINS', '*')

    # Configure Flask-CORS if available
    if HAS_FLASK_CORS:
        CORS(
            app,
            resources={r"/api/*": {"origins": cors_origins}},
            supports_credentials=True,
            methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["Content-Type", "Authorization"]
        )

    # Ensure API routes always have CORS headers attached
    @app.after_request
    def apply_cors_headers(response):
        if request.path.startswith('/api/'):
            if 'Access-Control-Allow-Origin' not in response.headers:
                response.headers['Access-Control-Allow-Origin'] = cors_origins
            if 'Access-Control-Allow-Methods' not in response.headers:
                response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            if 'Access-Control-Allow-Headers' not in response.headers:
                response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return response

    # Register API Blueprint
    from .routes import api_bp
    app.register_blueprint(api_bp)

    # JSON Error Handlers for API endpoints
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

    @app.errorhandler(500)
    def internal_error_handler(error):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Internal server error', 'status': 500}), 500
        return jsonify({'error': 'Internal server error'}), 500

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
        file_path = STATIC_DIR / filename
        if file_path.exists() and file_path.is_file():
            return send_from_directory(str(STATIC_DIR), filename)
        return send_from_directory(str(STATIC_DIR), 'index.html')

    return app
