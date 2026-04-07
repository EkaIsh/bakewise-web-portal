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


def _get_schema_info() -> dict:
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

    inventory_product_id_col = None
    quantity_col = None
    expiry_col = None

    if inventory_columns:
        inventory_product_id_col = _pick_first_existing(inventory_columns, "product_id", "id")
        quantity_col = _pick_first_existing(inventory_columns, "quantity", "stock", "available_quantity")
        expiry_col = _pick_first_existing(inventory_columns, "expiry_date", "expiration_date", "expires_at")

    return {
        "product_id_col": product_id_col,
        "name_col": name_col,
        "price_col": price_col,
        "category_col": category_col,
        "inventory_product_id_col": inventory_product_id_col,
        "quantity_col": quantity_col,
        "expiry_col": expiry_col,
    }


def _build_product_query(
    product_id_col: str,
    name_col: str,
    price_col: str,
    category_col: str | None,
    inventory_product_id_col: str | None,
    quantity_col: str | None,
    expiry_col: str | None,
    where_clause: str = "",
    limit_clause: str = "",
) -> str:
    category_select = (
        f"p.`{category_col}` AS category"
        if category_col is not None
        else "'Uncategorized' AS category"
    )

    stock_select = "0 AS available_quantity"
    stock_join = ""

    if inventory_product_id_col and quantity_col:
        expiry_filter = ""
        if expiry_col is not None:
            expiry_filter = f"AND (`{expiry_col}` IS NULL OR `{expiry_col}` >= CURDATE())"

        stock_select = "COALESCE(stock.available_quantity, 0) AS available_quantity"
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

    return f"""
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


def fetch_all_products() -> list[dict]:
    schema = _get_schema_info()
    cursor = mysql.get_cursor()

    query = _build_product_query(
        product_id_col=schema["product_id_col"],
        name_col=schema["name_col"],
        price_col=schema["price_col"],
        category_col=schema["category_col"],
        inventory_product_id_col=schema["inventory_product_id_col"],
        quantity_col=schema["quantity_col"],
        expiry_col=schema["expiry_col"],
    )

    cursor.execute(query)
    return [_serialize_product(row) for row in cursor.fetchall()]


def fetch_product_by_id(product_id: int) -> dict | None:
    schema = _get_schema_info()
    cursor = mysql.get_cursor()

    query = _build_product_query(
        product_id_col=schema["product_id_col"],
        name_col=schema["name_col"],
        price_col=schema["price_col"],
        category_col=schema["category_col"],
        inventory_product_id_col=schema["inventory_product_id_col"],
        quantity_col=schema["quantity_col"],
        expiry_col=schema["expiry_col"],
        where_clause=f"WHERE p.`{schema['product_id_col']}` = %s",
        limit_clause="LIMIT 1",
    )

    cursor.execute(query, (product_id,))
    row = cursor.fetchone()

    if row is None:
        return None

    return _serialize_product(row)
