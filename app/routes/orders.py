from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..services.order_service import create_order as create_order_service
from ..services.order_service import get_order_by_id


# All order-related API routes live under /api/orders.
orders_bp = Blueprint("orders", __name__, url_prefix="/api/orders")


def _success_response(message: str, data: dict, status_code: int = 200):
    """Return a consistent success payload for order endpoints."""
    return (
        jsonify(
            {
                "success": True,
                "message": message,
                "data": data,
            }
        ),
        status_code,
    )


def _error_response(message: str, status_code: int, errors: list[str] | None = None, details: str | None = None):
    """Return a consistent error payload for order endpoints."""
    payload = {
        "success": False,
        "message": message,
    }
    if errors:
        payload["errors"] = errors
    if details:
        payload["details"] = details
    return jsonify(payload), status_code


def _validate_order_payload(payload: object) -> list[str]:
    """Check the basic request shape before calling the service layer."""
    errors: list[str] = []

    if not isinstance(payload, dict):
        return ["Request body must be a JSON object."]

    payment_method = payload.get("payment_method")
    if not isinstance(payment_method, str) or not payment_method.strip():
        errors.append("payment_method is required.")

    items = payload.get("items")
    if not isinstance(items, list) or not items:
        errors.append("items must be a non-empty array.")
        return errors

    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            errors.append(f"items[{index - 1}] must be an object.")
            continue

        if "product_id" not in item:
            errors.append(f"items[{index - 1}].product_id is required.")
        if "quantity" not in item:
            errors.append(f"items[{index - 1}].quantity is required.")

    return errors


@orders_bp.post("")
def create_order():
    """Validate and create one order."""
    payload = request.get_json(silent=True)
    validation_errors = _validate_order_payload(payload)
    if validation_errors:
        return _error_response("Invalid order payload.", 400, errors=validation_errors)

    try:
        order = create_order_service(payload)
    except ValueError as exc:
        return _error_response(str(exc), 400)
    except Exception as exc:  # noqa: BLE001 - keep local debugging simple
        return _error_response("Could not create order.", 500, details=str(exc))

    return _success_response("Order created successfully.", {"order": order}, 201)


@orders_bp.get("/<int:order_id>")
def get_order(order_id: int):
    """Return one order by ID."""
    try:
        order = get_order_by_id(order_id)
    except Exception as exc:  # noqa: BLE001 - keep local debugging simple
        return _error_response("Could not load order.", 500, details=str(exc))

    if order is None:
        return _error_response("Order not found.", 404)

    return _success_response("Order loaded successfully.", {"order": order})
