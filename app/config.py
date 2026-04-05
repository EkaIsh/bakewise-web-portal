from __future__ import annotations

import os


def _get_int(name: str, default: int) -> int:
    """Read an integer environment variable with a safe fallback."""
    value = os.getenv(name)
    if not value:
        return default

    try:
        return int(value)
    except ValueError:
        return default


def _get_bool(name: str, default: bool) -> bool:
    """Read a boolean environment variable like 1/0 or true/false."""
    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    """Base configuration for the BakeWise customer website backend."""

    SECRET_KEY = os.getenv("SECRET_KEY", "bakewise-dev-key")

    # Customer-facing templates (safe defaults; override with env in production).
    STORE_NAME = os.getenv("BAKEWISE_STORE_NAME", "BakeWise Bakery")
    SOURCE_LABEL = os.getenv("BAKEWISE_SOURCE_LABEL", "BakeWise Customer Website")
    DEBUG = _get_bool("FLASK_DEBUG", False)
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = _get_int("PORT", 5000)

    BAKEWISE_DB_HOST = os.getenv("BAKEWISE_DB_HOST", "127.0.0.1")
    BAKEWISE_DB_PORT = _get_int("BAKEWISE_DB_PORT", 3306)
    BAKEWISE_DB_USER = os.getenv("BAKEWISE_DB_USER", "root")
    BAKEWISE_DB_PASSWORD = os.getenv("BAKEWISE_DB_PASSWORD", "")
    BAKEWISE_DB_NAME = os.getenv("BAKEWISE_DB_NAME", "bakewise")
    BAKEWISE_DB_TIMEOUT = _get_int("BAKEWISE_DB_TIMEOUT", 5)

    @classmethod
    def mysql_settings(cls) -> dict[str, object]:
        """Return MySQL settings in the format mysql-connector expects."""
        return {
            "host": cls.BAKEWISE_DB_HOST,
            "port": cls.BAKEWISE_DB_PORT,
            "user": cls.BAKEWISE_DB_USER,
            "password": cls.BAKEWISE_DB_PASSWORD,
            "database": cls.BAKEWISE_DB_NAME,
            "connection_timeout": cls.BAKEWISE_DB_TIMEOUT,
            "autocommit": False,
        }
