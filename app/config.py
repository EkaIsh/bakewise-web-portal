from __future__ import annotations

import os


def _get_env(*names: str, default: str = "") -> str:
    """Return the first non-empty environment variable from the given names."""
    for name in names:
        value = os.getenv(name)
        if value not in (None, ""):
            return value
    return default


def _get_int_from_env(*names: str, default: int) -> int:
    """Read the first available integer environment variable with fallback."""
    for name in names:
        value = os.getenv(name)
        if value in (None, ""):
            continue
        try:
            return int(value)
        except ValueError:
            continue
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

    # Customer-facing templates
    STORE_NAME = os.getenv("BAKEWISE_STORE_NAME", "BakeWise Bakery")
    SOURCE_LABEL = os.getenv("BAKEWISE_SOURCE_LABEL", "BakeWise Customer Website")
    DEBUG = _get_bool("FLASK_DEBUG", False)
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = _get_int_from_env("PORT", default=5000)

    # Supports both your custom BakeWise env vars and Railway-style MySQL env vars
    BAKEWISE_DB_HOST = _get_env("BAKEWISE_DB_HOST", "MYSQLHOST", default="127.0.0.1")
    BAKEWISE_DB_PORT = _get_int_from_env("BAKEWISE_DB_PORT", "MYSQLPORT", default=3306)
    BAKEWISE_DB_USER = _get_env("BAKEWISE_DB_USER", "MYSQLUSER", default="root")
    BAKEWISE_DB_PASSWORD = _get_env("BAKEWISE_DB_PASSWORD", "MYSQLPASSWORD", default="")
    BAKEWISE_DB_NAME = _get_env("BAKEWISE_DB_NAME", "MYSQLDATABASE", default="bakewise")
    BAKEWISE_DB_TIMEOUT = _get_int_from_env("BAKEWISE_DB_TIMEOUT", default=10)

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
