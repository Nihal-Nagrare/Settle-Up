import os
import secrets
import logging
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.pool import NullPool

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

    # Database Configuration
    _raw_db_url = os.getenv('DATABASE_URL')
    if _raw_db_url and _raw_db_url.strip():
        # Normalize legacy postgres:// scheme to postgresql:// for modern SQLAlchemy
        if _raw_db_url.startswith("postgres://"):
            _raw_db_url = _raw_db_url.replace("postgres://", "postgresql://", 1)
        SQLALCHEMY_DATABASE_URI = _raw_db_url
    else:
        default_db_path = str(BASE_DIR / 'settleup.db').replace('\\', '/')
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{default_db_path}"

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False

    # Engine connection pooling options (crucial for PostgreSQL & serverless reconnection)
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

    # Database Auto-Initialization flag (can be disabled in production serverless)
    AUTO_INIT_DB = os.getenv('AUTO_INIT_DB', 'True').lower() in ('true', '1', 't')

    # Payment Proof Storage Configuration
    STORAGE_PROVIDER = os.getenv('STORAGE_PROVIDER', 'local').lower()
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
    SQLALCHEMY_ENGINE_OPTIONS = {}
    UPLOAD_FOLDER = str(BASE_DIR / 'uploads' / 'test_proofs')


class ProductionConfig(Config):
    """Production configuration with strict secret key enforcement, PostgreSQL database, and cloud object storage."""
    DEBUG = False
    TESTING = False
    USE_PROXY_FIX = os.getenv('USE_PROXY_FIX', 'True').lower() in ('true', '1', 't')
    SECRET_KEY = os.getenv('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = None  # Never silently default to SQLite in production

    # Serverless connection pooling: NullPool prevents connection leaks across lambda containers
    SQLALCHEMY_ENGINE_OPTIONS = {
        'poolclass': NullPool,
        'pool_pre_ping': True,
    }

    def __init__(self):
        super().__init__()
        # 1. Enforce strict SECRET_KEY
        secret = os.getenv('SECRET_KEY')
        if not secret or not secret.strip() or secret == DEFAULT_SECRET_KEY:
            raise RuntimeError(
                "CRITICAL CONFIGURATION ERROR: 'SECRET_KEY' environment variable must be explicitly configured in production. "
                "Refusing to start with missing or default fallback secret key. "
                "Please generate a secure key (e.g., `python -c 'import secrets; print(secrets.token_hex(32))'`) and set SECRET_KEY in your environment."
            )
        self.SECRET_KEY = secret.strip()

        # 2. Enforce strict PostgreSQL DATABASE_URL (fail fast on SQLite or missing)
        db_url = os.getenv('DATABASE_URL')
        if not db_url or not db_url.strip():
            raise RuntimeError(
                "CRITICAL CONFIGURATION ERROR: 'DATABASE_URL' environment variable must be configured in production mode. "
                "SQLite is not supported in production on Vercel. Please set DATABASE_URL to a valid PostgreSQL connection string "
                "(e.g., postgresql://user:password@host:5432/dbname?sslmode=require)."
            )
        db_url_clean = db_url.strip()
        if db_url_clean.startswith("postgres://"):
            db_url_clean = db_url_clean.replace("postgres://", "postgresql://", 1)

        if not (db_url_clean.startswith("postgresql://") or db_url_clean.startswith("postgresql+")):
            raise RuntimeError(
                f"CRITICAL CONFIGURATION ERROR: Production database must be PostgreSQL. "
                f"'DATABASE_URL' must start with 'postgresql://' or 'postgres://'. "
                f"SQLite or non-PostgreSQL databases are not permitted in production."
            )
        self.SQLALCHEMY_DATABASE_URI = db_url_clean

        # 3. Enforce persistent STORAGE_PROVIDER (fail fast on local or missing)
        provider = (os.getenv('STORAGE_PROVIDER') or '').strip().lower()
        valid_providers = {'s3', 'cloudinary', 'vercel_blob'}
        if not provider or provider == 'local' or provider not in valid_providers:
            raise RuntimeError(
                "CRITICAL CONFIGURATION ERROR: A persistent 'STORAGE_PROVIDER' ('s3', 'cloudinary', or 'vercel_blob') "
                "must be configured in production mode. Local filesystem storage is ephemeral on Vercel serverless. "
                "Please configure STORAGE_PROVIDER and the corresponding cloud credentials in your environment variables."
            )
        self.STORAGE_PROVIDER = provider


config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def get_config():
    """Retrieve active configuration based on FLASK_ENV or Vercel environment."""
    env = os.getenv('FLASK_ENV', '').strip().lower()
    if not env:
        # Automatically detect Vercel production/preview serverless deployment
        if os.getenv('VERCEL') == '1' or os.getenv('VERCEL_ENV') in ('production', 'preview'):
            env = 'production'
        else:
            env = 'development'
    return config_by_name.get(env, DevelopmentConfig)
