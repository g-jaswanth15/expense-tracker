import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base configuration shared across all environments."""
    SECRET_KEY         = os.environ.get("SECRET_KEY", "change-me-in-production")
    DB_DIR             = os.path.join(BASE_DIR, "db")
    DB_PATH            = os.path.join(DB_DIR, "expenses.db")
    JSON_SORT_KEYS     = False
    TESTING            = False


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING  = True
    DEBUG    = True
    DB_PATH  = ":memory:"          # isolated in-memory DB for tests


class ProductionConfig(Config):
    DEBUG = False


# Mapping used by the app factory
config_map = {
    "development": DevelopmentConfig,
    "testing":     TestingConfig,
    "production":  ProductionConfig,
    "default":     DevelopmentConfig,
}