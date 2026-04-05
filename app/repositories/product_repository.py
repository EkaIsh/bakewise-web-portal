from __future__ import annotations

from ..extensions import mysql


def _serialize_product(row: dict) -> dict:
    """Convert one database row into a simple product dictionary."""
    return {
        "product_id": int(row["product_id"]),
        "name": row["name"],
        "category": row.get("category") or "Uncategorized",
        "price": float(row["price"]),
        "available_quantity": int(row.get("available_quantity") or 0),
    }


def fetch_all_products() -> list[dict]:
    """
    Read all products for the storefront.

    Assumptions:
    - BakeWise stores products in a table named `products`
    - The table has columns: product_id, name, category, price
    - Stock can be estimated from `inventory_batches.quantity`
    """
    cursor = mysql.get_cursor()
    cursor.execute(
        """
        SELECT
            p.product_id,
            p.name,
            p.category,
            p.price,
            COALESCE(stock.available_quantity, 0) AS available_quantity
        FROM products AS p
        LEFT JOIN (
            SELECT
                product_id,
                COALESCE(SUM(quantity), 0) AS available_quantity
            FROM inventory_batches
            WHERE quantity > 0
              AND (expiry_date IS NULL OR expiry_date >= CURDATE())
            GROUP BY product_id
        ) AS stock
            ON stock.product_id = p.product_id
        ORDER BY p.product_id ASC
        """
    )
    return [_serialize_product(row) for row in cursor.fetchall()]


def fetch_product_by_id(product_id: int) -> dict | None:
    """
    Read one product by ID.

    Assumptions:
    - `products.product_id` is the primary key used by BakeWise
    - `inventory_batches` can be joined by product_id for stock totals
    """
    cursor = mysql.get_cursor()
    cursor.execute(
        """
        SELECT
            p.product_id,
            p.name,
            p.category,
            p.price,
            COALESCE(stock.available_quantity, 0) AS available_quantity
        FROM products AS p
        LEFT JOIN (
            SELECT
                product_id,
                COALESCE(SUM(quantity), 0) AS available_quantity
            FROM inventory_batches
            WHERE quantity > 0
              AND (expiry_date IS NULL OR expiry_date >= CURDATE())
            GROUP BY product_id
        ) AS stock
            ON stock.product_id = p.product_id
        WHERE p.product_id = %s
        LIMIT 1
        """,
        (product_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None

    return _serialize_product(row)
