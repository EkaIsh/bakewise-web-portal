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


def _products_has_category_column() -> bool:
    """Check if the BakeWise products table includes a category column."""
    cursor = mysql.get_cursor()
    cursor.execute("SHOW COLUMNS FROM products")
    columns = {row["Field"] for row in cursor.fetchall()}
    return "category" in columns


def fetch_all_products() -> list[dict]:
    """
    Read all products for the storefront.

    Works whether the products table has a `category` column or not.
    """
    cursor = mysql.get_cursor()

    category_select = (
        "p.category AS category"
        if _products_has_category_column()
        else "'Uncategorized' AS category"
    )

    query = f"""
        SELECT
            p.product_id,
            p.name,
            {category_select},
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
    cursor.execute(query)
    return [_serialize_product(row) for row in cursor.fetchall()]


def fetch_product_by_id(product_id: int) -> dict | None:
    """
    Read one product by ID.

    Works whether the products table has a `category` column or not.
    """
    cursor = mysql.get_cursor()

    category_select = (
        "p.category AS category"
        if _products_has_category_column()
        else "'Uncategorized' AS category"
    )

    query = f"""
        SELECT
            p.product_id,
            p.name,
            {category_select},
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
    """
    cursor.execute(query, (product_id,))
    row = cursor.fetchone()

    if row is None:
        return None

    return _serialize_product(row)
