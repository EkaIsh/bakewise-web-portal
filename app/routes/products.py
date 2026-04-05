from __future__ import annotations

from flask import Blueprint, jsonify

from ..services.product_service import get_all_products, get_product_by_id


# All product-related API routes live under /api/products.
products_bp = Blueprint("products", __name__, url_prefix="/api/products")


def _success_response(message: str, data: dict, status_code: int = 200, meta: dict | None = None):
    """Return a consistent success payload for product endpoints."""
    payload = {
        "success": True,
        "message": message,
        "data": data,
    }
    if meta is not None:
        payload["meta"] = meta
    return jsonify(payload), status_code


def _error_response(message: str, status_code: int, details: str | None = None):
    """Return a consistent error payload for product endpoints."""
    payload = {
        "success": False,
        "message": message,
    }
    if details:
        payload["details"] = details
    return jsonify(payload), status_code


@products_bp.get("")
def list_products():
    """Return all products from the service and repository layers."""
    try:
        products = get_all_products()
    except Exception as exc:  # noqa: BLE001 - keep local debugging simple
        return _error_response("Could not load products.", 500, str(exc))

    message = "Products loaded successfully."
    if not products:
        message = "No products found."

    return _success_response(
        message,
        {"products": products},
        meta={"count": len(products)},
    )


@products_bp.get("/<int:product_id>")
def get_product(product_id: int):
    """Return one product by ID."""
    try:
        product = get_product_by_id(product_id)
    except Exception as exc:  # noqa: BLE001 - keep local debugging simple
        return _error_response("Could not load product.", 500, str(exc))

    if product is None:
        return _error_response("Product not found.", 404)

    return _success_response("Product loaded successfully.", {"product": product})
