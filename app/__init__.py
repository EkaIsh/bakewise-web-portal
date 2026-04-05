from __future__ import annotations

import os

from flask import Flask, jsonify, render_template, request

from .config import Config
from .extensions import mysql
from .routes import register_blueprints


def create_app() -> Flask:
    """Create and configure the Flask application."""
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    app = Flask(
        __name__,
        template_folder=os.path.join(root, "templates"),
        static_folder=os.path.join(root, "static"),
    )
    app.config.from_object(Config)
    app.config["MYSQL_SETTINGS"] = Config.mysql_settings()

    register_extensions(app)
    register_template_globals(app)
    register_core_routes(app)
    register_blueprints(app)
    register_error_handlers(app)

    return app


def register_template_globals(app: Flask) -> None:
    """Expose safe storefront settings to all Jinja templates."""

    @app.context_processor
    def inject_bakewise_config() -> dict:
        return {
            "bakewise": {
                "store_name": app.config["STORE_NAME"],
                "source_label": app.config["SOURCE_LABEL"],
            }
        }


def register_extensions(app: Flask) -> None:
    """Attach shared services that the rest of the app can reuse."""
    mysql.init_app(app)


def register_core_routes(app: Flask) -> None:
    """Health check and other non-blueprint routes."""

    @app.get("/health")
    def health():
        payload = {
            "status": "ok",
            "app": "BakeWise customer website backend",
            "database": "connected",
        }
        status_code = 200

        try:
            mysql.ping()
        except Exception as exc:  # noqa: BLE001 - simple local-dev feedback
            payload["status"] = "warning"
            payload["database"] = "unavailable"
            payload["database_error"] = str(exc)
            status_code = 503

        return jsonify(payload), status_code


def register_error_handlers(app: Flask) -> None:
    """HTML-friendly errors for browser requests."""

    @app.errorhandler(404)
    def handle_not_found(_error):  # noqa: ANN001
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "message": "Not found"}), 404
        return render_template("404.html", page_name="not-found"), 404
