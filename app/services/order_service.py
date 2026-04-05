from __future__ import annotations

from datetime import date, datetime

from ..extensions import mysql
from ..repositories.order_repository import fetch_order_by_id as fetch_order_record
from ..repositories.order_repository import insert_order
from ..repositories.order_repository import insert_order_items
from ..repositories.product_repository import fetch_product_by_id


ALLOWED_PAYMENT_METHODS = {
    "cash": "Cash",
    "cash on pickup": "Cash",
    "gcash": "GCash",
    "card": "Card",
}


def _parse_optional_date(value: str | None) -> str | None:
    """Accept YYYY-MM-DD input and keep it simple for MySQL inserts."""
    if value in (None, ""):
        return None

    date.fromisoformat(str(value))
    return str(value)


def _normalize_payment_method(value: str) -> str:
    """Convert user input into one of the supported BakeWise payment labels."""
    normalized = str(value).strip().lower()
    if not normalized:
        raise ValueError("payment_method is required.")

    if normalized not in ALLOWED_PAYMENT_METHODS:
        raise ValueError("payment_method must be Cash, GCash, or Card.")

    return ALLOWED_PAYMENT_METHODS[normalized]


def create_order(order_data: dict) -> dict:
    """
    Validate and save one order.

    This is the main business-logic layer for orders:
    - validate the request payload
    - load product details
    - compute totals
    - save the order header and items through the repositories
    """
    if not isinstance(order_data, dict):
        raise ValueError("Order data must be a JSON object.")

    items = order_data.get("items") or []
    if not isinstance(items, list) or not items:
        raise ValueError("At least one order item is required.")

    payment_method = _normalize_payment_method(order_data.get("payment_method", ""))
    pickup_date_from = _parse_optional_date(order_data.get("pickup_date_from"))
    pickup_date_to = _parse_optional_date(order_data.get("pickup_date_to"))

    if pickup_date_from and pickup_date_to and pickup_date_to < pickup_date_from:
        raise ValueError("pickup_date_to cannot be earlier than pickup_date_from.")

    normalized_items: list[dict] = []
    total = 0.0

    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Item #{index} must be an object.")

        try:
            product_id = int(item.get("product_id"))
            quantity = int(item.get("quantity"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Item #{index} must include valid product_id and quantity.") from exc

        if quantity <= 0:
            raise ValueError(f"Item #{index} quantity must be greater than zero.")

        product = fetch_product_by_id(product_id)
        if product is None:
            raise ValueError(f"Product with ID {product_id} was not found.")

        subtotal = round(float(product["price"]) * quantity, 2)
        total = round(total + subtotal, 2)
        normalized_items.append(
            {
                "product_id": product["product_id"],
                "product_name": product["name"],
                "quantity": quantity,
                "subtotal": subtotal,
            }
        )

    order_stamp = datetime.now()
    created_at = order_stamp.replace(microsecond=0)
    customer_number = f"WEB-{order_stamp.strftime('%y%m%d%H%M%S')}{order_stamp.microsecond // 10000:02d}"
    amount_paid = total if payment_method.lower() in {"gcash", "card"} else 0.0

    order_header = {
        "source_label": "BakeWise Website",
        "created_at": created_at,
        "payment_method": payment_method,
        "service_mode": "Online Orders",
        "order_source": "Online Orders",
        "customer_number": customer_number,
        "pickup_date_from": pickup_date_from,
        "pickup_date_to": pickup_date_to,
        "online_order_status": "pending",
        "total": total,
        "amount_paid": amount_paid,
    }

    connection = mysql.get_connection()
    try:
        order_id = insert_order(order_header)
        insert_order_items(order_id, normalized_items)
        connection.commit()
    except Exception:
        connection.rollback()
        raise

    return get_order_by_id(order_id)


def get_order_by_id(order_id: int) -> dict | None:
    """
    Return one saved order from the repository layer.
    """
    return fetch_order_record(order_id)
