from __future__ import annotations

from flask import current_app

from ..extensions import mysql


def _serialize_product(row: dict) -> dict:
    """Convert one database row into a simple product dictionary."""
    return {
        "product_id": int(row["product_id"]),
        "name": row.get("name", ""),
        "category": row.get("category", "Uncategorized"),
        "price": float(row.get("price", 0) or 0),
        "available_quantity": int(row.get("available_quantity", 0) or 0),
    }


def fetch_all_products() -> list[dict]:
    """
    Read all products for the storefront.

    Assumptions:
    - products table has: product_id, name, category, price
    - inventory_batches table has: product_id, quantity, expiry_date
    """

    cursor = mysql.get_cursor()

    try:
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
                    SUM(CASE WHEN quantity > 0 THEN quantity ELSE 0 END) AS available_quantity
                FROM inventory_batches
                GROUP BY product_id
            ) AS stock
                ON stock.product_id = p.product_id
            ORDER BY p.product_id ASC
            """
        )
        rows = cursor.fetchall() or []
        return [_serialize_product(row) for row in rows]

    except Exception as e:
        current_app.logger.exception("fetch_all_products failed")
        raise RuntimeError(f"Could not fetch products: {e}") from e

    finally:
        cursor.close()


def fetch_product_by_id(product_id: int) -> dict | None:
    """
    Read a single product for the storefront.

    Assumptions:
    - products table has: product_id, name, category, price
    - inventory_batches table has: product_id, quantity, expiry_date
    """

    cursor = mysql.get_cursor()

    try:
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
                    SUM(CASE WHEN quantity > 0 THEN quantity ELSE 0 END) AS available_quantity
                FROM inventory_batches
                GROUP BY product_id
            ) AS stock
                ON stock.product_id = p.product_id
            WHERE p.product_id = %s
            LIMIT 1
            """,
            (product_id,),
        )

        row = cursor.fetchone()
        if not row:
            return None

        return _serialize_product(row)

    except Exception as e:
        current_app.logger.exception("fetch_product_by_id failed")
        raise RuntimeError(f"Could not fetch product {product_id}: {e}") from e

    finally:
        cursor.close()
