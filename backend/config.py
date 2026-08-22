import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if present
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)


class Config:
    """Base configuration."""
    SECRET_KEY = os.getenv('SECRET_KEY', 'settleup-default-secret-key-2026')
    HOST = os.getenv('HOST', '127.0.0.1')
    PORT = int(os.getenv('PORT', 5000))
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    TESTING = False
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*')
    
    # SQLite Database Configuration
    default_db_path = str(BASE_DIR / 'settleup.db').replace('\\', '/')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', f"sqlite:///{default_db_path}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True


class TestingConfig(Config):
    """Testing configuration with in-memory SQLite database."""
    TESTING = True
    DEBUG = False
    CORS_ORIGINS = '*'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False


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
