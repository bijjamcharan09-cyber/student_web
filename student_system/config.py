import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    """Base configuration class."""
    JSON_SORT_KEYS = False

    # Session cookie baseline security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # MySQL Database Settings
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", 4000))
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "student_management_db")
    DB_CHARSET = "utf8mb4"
    DB_SSL_CA = os.getenv("DB_SSL_CA", "")

    DB_SSL = {
    "ca": str(BASE_DIR / DB_SSL_CA)
    } if DB_SSL_CA else {}

    # Connection pool / timeout settings
    DB_CONNECT_TIMEOUT = 10
    DB_READ_TIMEOUT = 30
    DB_WRITE_TIMEOUT = 30


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    TESTING = False
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-student-management-system-local-only")
    SESSION_COOKIE_SECURE = False


class TestingConfig(Config):
    """Testing configuration."""
    DEBUG = False
    TESTING = True
    SECRET_KEY = "test-secret-key-for-automated-tests-only"
    DB_NAME = os.getenv("TEST_DB_NAME", "test_student_management_db")
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True

    @property
    def SECRET_KEY(self):
        val = os.getenv("SECRET_KEY")
        if not val or val in ("dev-secret-key-student-management-system", "dev-secret-key-student-management-system-local-only"):
            raise RuntimeError(
                "CRITICAL SECURITY CONFIGURATION ERROR: "
                "A strong, unique SECRET_KEY environment variable must be set in production environments."
            )
        return val


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig(),
    "default": DevelopmentConfig,
}
