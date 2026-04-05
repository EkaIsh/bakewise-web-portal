from __future__ import annotations

from flask import Flask

from .orders import orders_bp
from .products import products_bp
from .storefront import storefront_bp


def register_blueprints(app: Flask) -> None:
    """Attach API blueprints to the main Flask application."""
    app.register_blueprint(storefront_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(orders_bp)
