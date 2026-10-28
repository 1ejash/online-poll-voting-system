import os
import secrets
from datetime import timedelta

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class Config:
    """Runtime configuration. Set production secrets in environment variables."""
    SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)

    MYSQL_HOST = os.getenv("MYSQLHOST", "localhost")
    MYSQL_PORT = int(os.getenv("MYSQLPORT", "3306"))
    MYSQL_USER = os.getenv("MYSQLUSER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQLPASSWORD", "")
    MYSQL_DB = os.getenv("MYSQLDATABASE", "online_poll_db")

    DB_ENGINE = os.getenv("DB_ENGINE", "mysql").lower()
    SQLITE_PATH = os.getenv("SQLITE_PATH", os.path.join(os.path.dirname(__file__), "online_poll.sqlite3"))

    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "357512431894-9p5rgsve8khrtitknkl1ghlg8c4bu99r.apps.googleusercontent.com")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "")

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("FLASK_ENV", "").lower() == "production" or bool(os.getenv("RAILWAY_ENVIRONMENT"))
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    MIN_POLL_OPTIONS = 2
    MAX_POLL_OPTIONS = 6
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

                                                      
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "")
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    PASSWORD_RESET_MAX_AGE = int(os.getenv("PASSWORD_RESET_MAX_AGE", "1800"))


class TestConfig(Config):
    TESTING = True
    DB_ENGINE = "sqlite"
    SQLITE_PATH = ":memory:"
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-only-secret-key"
    GOOGLE_CLIENT_ID = "test-client-id"
    GOOGLE_CLIENT_SECRET = "test-client-secret"
    GOOGLE_REDIRECT_URI = "http://localhost:5000/auth/google/callback"
    ADMIN_EMAIL = "admin@gmail.com"
    ADMIN_PASSWORD = "Admin@123"
