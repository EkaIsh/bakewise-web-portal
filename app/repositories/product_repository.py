from __future__ import annotations

from ..extensions import mysql


def _table_exists(table_name: str) -> bool:
    cursor = mysql.get_cursor()
    cursor.execute("SHOW TABLES LIKE %s", (table_name,))
    return cursor.fetchone() is not None


def _get_columns(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()

    cursor = mysql.get_cursor()
    cursor.execute(f"SHOW COLUMNS FROM `{table_name}`")
    return {row["Field"] for row in cursor.fetchall()}


def _pick_first_existing(columns: set[str], *candidates: str) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def _serialize_product(row: dict) -> dict:
    return {
        "product_id": int(row["product_id"]),
        "name": row.get("name") or "Unnamed Product",
        "category": row.get("category") or "Uncategorized",
        "price": float(row.get("price") or 0),
        "available_quantity": int(row.get("available_quantity") or 0),
    }


def _build_product_query(where_clause: str = "", limit_clause: str = "") -> str:
    product_columns = _get_columns("products")
    inventory_columns = _get_columns("inventory_batches")

    if not product_columns:
        raise RuntimeError("Table 'products' does not exist in the connected database.")

    product_id_col = _pick_first_existing(product_columns, "product_id", "id")
    name_col = _pick_first_existing(product_columns, "name", "product_name")
    price_col = _pick_first_existing(product_columns, "price", "selling_price", "unit_price")
    category_col = _pick_first_existing(product_columns, "category")

    if product_id_col is None:
        raise RuntimeError("No usable product ID column found in 'products' table.")

    if name_col is None:
        raise RuntimeError("No usable product name column found in 'products' table.")

    if price_col is None:
        raise RuntimeError("No usable product price column found in 'products' table.")

    category_select = (
        f"p.`{category_col}` AS category"
        if category_col is not None
        else "'Uncategorized' AS category"
    )

    stock_join = ""
    stock_select = "0 AS available_quantity"

    if inventory_columns:
        inventory_product_id_col = _pick_first_existing(inventory_columns, "product_id", "id")
        quantity_col = _pick_first_existing(inventory_columns, "quantity", "stock", "available_quantity")
        expiry_col = _pick_first_existing(inventory_columns, "expiry_date", "expiration_date", "expires_at")

        if inventory_product_id_col and quantity_col:
            expiry_filter = ""
            if expiry_col is not None:
                expiry_filter = f"AND (`{expiry_col}` IS NULL OR `{expiry_col}` >= CURDATE())"

            stock_join = f"""
                LEFT JOIN (
                    SELECT
                        `{inventory_product_id_col}` AS stock_product_id,
                        COALESCE(SUM(`{quantity_col}`), 0) AS available_quantity
                    FROM inventory_batches
                    WHERE `{quantity_col}` > 0
                    {expiry_filter}
                    GROUP BY `{inventory_product_id_col}`
                ) AS stock
                    ON stock.stock_product_id = p.`{product_id_col}`
            """
            stock_select = "COALESCE(stock.available_quantity, 0) AS available_quantity"

    query = f"""
        SELECT
            p.`{product_id_col}` AS product_id,
            p.`{name_col}` AS name,
            {category_select},
            p.`{price_col}` AS price,
            {stock_select}
        FROM products AS p
        {stock_join}
        {where_clause}
        ORDER BY p.`{product_id_col}` ASC
        {limit_clause}
    """
    return query


def fetch_all_products() -> list[dict]:
    cursor = mysql.get_cursor()
    query = _build_product_query()
    cursor.execute(query)
    return [_serialize_product(row) for row in cursor.fetchall()]


def fetch_product_by_id(product_id: int) -> dict | None:
    cursor = mysql.get_cursor()
    query = _build_product_query(where_clause="WHERE p.`product_id` = %s", limit_clause="LIMIT 1")

    try:
        cursor.execute(query, (product_id,))
    except Exception:
        fallback_query = _build_product_query(where_clause="WHERE p.`id` = %s", limit_clause="LIMIT 1")
        cursor.execute(fallback_query, (product_id,))

    row = cursor.fetchone()
    if row is None:
        return None

    return _serialize_product(row)
