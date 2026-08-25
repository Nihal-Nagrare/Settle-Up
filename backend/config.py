import os
import secrets
import logging
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables from .env file if present
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

DEFAULT_SECRET_KEY = 'settleup-default-secret-key-2026'


class Config:
    """Base configuration."""
    SECRET_KEY = os.getenv('SECRET_KEY', DEFAULT_SECRET_KEY)
    HOST = os.getenv('HOST', '127.0.0.1')
    PORT = int(os.getenv('PORT', 5000))
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    TESTING = False
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*')
    
    # Proxy Fix (Reverse Proxy Headers Support for HTTPS and client IP)
    USE_PROXY_FIX = os.getenv('USE_PROXY_FIX', 'False').lower() in ('true', '1', 't')

    # SQLite / Database Configuration
    default_db_path = str(BASE_DIR / 'settleup.db').replace('\\', '/')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', f"sqlite:///{default_db_path}")
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        # Fix legacy Heroku postgres:// URLs to postgresql://
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False

    # Payment Proof Storage Configuration
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', str(BASE_DIR / 'uploads' / 'proofs'))
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB max request size
    ALLOWED_PROOF_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
    ALLOWED_PROOF_MIMETYPES = {'image/jpeg', 'image/png', 'image/webp'}


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True


class TestingConfig(Config):
    """Testing configuration with in-memory SQLite database and isolated upload folder."""
    TESTING = True
    DEBUG = False
    CORS_ORIGINS = '*'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = str(BASE_DIR / 'uploads' / 'test_proofs')


class ProductionConfig(Config):
    """Production configuration with strict secret key and reverse proxy security."""
    DEBUG = False
    TESTING = False
    USE_PROXY_FIX = os.getenv('USE_PROXY_FIX', 'True').lower() in ('true', '1', 't')

    def __init__(self):
        super().__init__()
        # In production, if SECRET_KEY is missing or using default, generate a secure random one
        if not os.getenv('SECRET_KEY') or self.SECRET_KEY == DEFAULT_SECRET_KEY:
            self.SECRET_KEY = secrets.token_hex(32)
            logger.warning(
                "SECURITY WARNING: SECRET_KEY not configured in environment! "
                "Generated temporary random runtime key for session protection."
            )


config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def get_config():
    """Retrieve active configuration based on FLASK_ENV."""
    env = os.getenv('FLASK_ENV', 'development').lower()
    return config_by_name.get(env, DevelopmentConfig)
