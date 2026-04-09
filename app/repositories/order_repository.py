from __future__ import annotations

from ..extensions import mysql


def _serialize_temporal(value):
    """Return a JSON-safe date/datetime string from either DB objects or plain strings."""
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def insert_order(order_data: dict) -> int:
    """
    Insert the order header into BakeWise.

    Assumptions:
    - Website orders are stored in the `transactions` table
    - The table supports these columns:
      cashier_name, date, payment_method, service_mode, order_source,
      customer_number, pickup_date_from, pickup_date_to,
      online_order_status, total, amount_paid, is_voided
    - If your BakeWise schema uses different names, edit this SQL first
    """
    cursor = mysql.get_cursor(dictionary=False)
    cursor.execute(
        """
        INSERT INTO transactions (
            cashier_name,
            date,
            payment_method,
            service_mode,
            order_source,
            customer_number,
            pickup_date_from,
            pickup_date_to,
            online_order_status,
            total,
            amount_paid,
            is_voided
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            order_data["source_label"],
            order_data["created_at"],
            order_data["payment_method"],
            order_data["service_mode"],
            order_data["order_source"],
            order_data["customer_number"],
            order_data["pickup_date_from"],
            order_data["pickup_date_to"],
            order_data["online_order_status"],
            order_data["total"],
            order_data["amount_paid"],
            0,
        ),
    )
    return int(cursor.lastrowid)


def insert_order_items(order_id: int, items: list[dict]) -> None:
    """
    Insert order line items into BakeWise.

    Assumptions:
    - Order lines live in `transaction_items`
    - The line table has columns:
      transaction_id, product_id, product_name, quantity, subtotal
    """
    cursor = mysql.get_cursor(dictionary=False)

    for item in items:
        cursor.execute(
            """
            INSERT INTO transaction_items (
                transaction_id,
                product_id,
                product_name,
                quantity,
                subtotal
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                order_id,
                item["product_id"],
                item["product_name"],
                item["quantity"],
                item["subtotal"],
            ),
        )


def fetch_order_by_id(order_id: int) -> dict | None:
    """
    Read one website order and its items.

    Assumptions:
    - The main order is stored in `transactions`
    - The related items are stored in `transaction_items`
    - `transaction_items.transaction_id` points to `transactions.transaction_id`
    """
    cursor = mysql.get_cursor()
    cursor.execute(
        """
        SELECT
            transaction_id,
            payment_method,
            service_mode,
            order_source,
            customer_number,
            pickup_date_from,
            pickup_date_to,
            online_order_status,
            total,
            amount_paid,
            date
        FROM transactions
        WHERE transaction_id = %s
        LIMIT 1
        """,
        (order_id,),
    )
    order_row = cursor.fetchone()
    if order_row is None:
        return None

    cursor.execute(
        """
        SELECT
            product_id,
            product_name,
            quantity,
            subtotal
        FROM transaction_items
        WHERE transaction_id = %s
        ORDER BY product_id ASC
        """,
        (order_id,),
    )
    items = [
        {
            "product_id": int(item["product_id"]),
            "product_name": item["product_name"],
            "quantity": int(item["quantity"]),
            "subtotal": float(item["subtotal"]),
        }
        for item in cursor.fetchall()
    ]

    return {
        "order_id": int(order_row["transaction_id"]),
        "customer_number": order_row.get("customer_number"),
        "payment_method": order_row.get("payment_method"),
        "service_mode": order_row.get("service_mode"),
        "order_source": order_row.get("order_source"),
        "pickup_date_from": _serialize_temporal(order_row.get("pickup_date_from")),
        "pickup_date_to": _serialize_temporal(order_row.get("pickup_date_to")),
        "online_order_status": order_row.get("online_order_status"),
        "total": float(order_row.get("total") or 0),
        "amount_paid": float(order_row.get("amount_paid") or 0),
        "created_at": _serialize_temporal(order_row.get("date")),
        "items": items,
    }
