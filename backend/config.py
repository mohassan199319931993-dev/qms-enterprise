"""
QMS Enterprise — Configuration
Railway-compatible: reads DATABASE_URL, PORT, etc. from environment
"""
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


def _fix_db_url(url: str) -> str:
    """Railway / Heroku provide postgres:// but SQLAlchemy 2.x needs postgresql://"""
    if url and url.startswith('postgres://'):
        return url.replace('postgres://', 'postgresql://', 1)
    return url


class Config:
    # Flask
    SECRET_KEY  = os.environ.get('SECRET_KEY', 'change-this-secret-key-in-production')
    DEBUG       = False
    TESTING     = False

    # Database — auto-fix postgres:// → postgresql://
    SQLALCHEMY_DATABASE_URI = _fix_db_url(
        os.environ.get('DATABASE_URL', 'postgresql://qms_user:qms_pass@localhost:5432/qms_db')
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping':  True,
        'pool_recycle':   300,
        'pool_size':      5,
        'max_overflow':   10,
    }

    # JWT
    JWT_SECRET_KEY             = os.environ.get('JWT_SECRET_KEY', 'change-this-jwt-secret')
    JWT_ACCESS_TOKEN_EXPIRES   = timedelta(minutes=60)   # longer for prod UX
    JWT_REFRESH_TOKEN_EXPIRES  = timedelta(days=30)

    # CORS — accept all in base config; tighten in production via env var
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')

    # Email
    MAIL_SERVER         = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT           = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS        = True
    MAIL_USERNAME       = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD       = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@qms.com')

    # Frontend URL (used in reset-password emails)
    FRONTEND_URL = os.environ.get('FRONTEND_URL', '')

    # Auth
    PASSWORD_RESET_EXPIRES_HOURS = 2
    MAX_LOGIN_ATTEMPTS           = 5
    LOCKOUT_DURATION_MINUTES     = 15

    # AI models storage
    MODEL_DIR = os.environ.get('MODEL_DIR', '/tmp/ai_models')


class DevelopmentConfig(Config):
    DEBUG = True
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)


class ProductionConfig(Config):
    DEBUG = False
    # Railway injects DATABASE_URL — already handled above
    PREFERRED_URL_SCHEME = 'https'


class TestingConfig(Config):
    TESTING     = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)


config = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'testing':     TestingConfig,
    'default':     ProductionConfig,   # Railway default
}
