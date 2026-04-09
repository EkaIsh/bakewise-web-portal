import os
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.parse import unquote, urlparse

import mysql.connector


VALID_PAYMENT_METHODS = {
    "cash": "Cash",
    "cash on pickup": "Cash",
    "cod": "Cash",
    "gcash": "GCash",
    "card": "Card",
}

DEFAULT_STORE_NAME = os.getenv("BAKEWISE_STORE_NAME", "BakeWise Bakery")
DEFAULT_SOURCE_LABEL = os.getenv("BAKEWISE_SOURCE_LABEL", "BakeWise Customer Website")
_SCHEMA_READY = False


class StoreError(Exception):
    def __init__(self, status_code, message, details=None):
        super().__init__(message)
        self.status_code = int(status_code)
        self.message = str(message)
        self.details = details or {}


def _env_value(*names, default=None):
    for name in names:
        value = os.getenv(name)
        if value not in (None, ""):
            return value
    return default


def _money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _settings_from_connection_url():
    raw_url = _env_value("BAKEWISE_DB_URL", "MYSQL_URL", "DATABASE_URL")
    if not raw_url:
        return None

    parsed = urlparse(raw_url)
    if parsed.scheme not in {"mysql", "mysql2"}:
        return None

    return {
        "host": parsed.hostname or "127.0.0.1",
        "port": int(parsed.port or 3306),
        "user": unquote(parsed.username or "root"),
        "password": unquote(parsed.password or ""),
        "database": unquote((parsed.path or "").lstrip("/") or "bakewise"),
    }


def get_connection():
    timeout = int(_env_value("BAKEWISE_DB_TIMEOUT", default="3"))
    connection_url_settings = _settings_from_connection_url()
    if connection_url_settings:
        return mysql.connector.connect(**connection_url_settings, connection_timeout=timeout)

    return mysql.connector.connect(
        host=_env_value("BAKEWISE_DB_HOST", "MYSQL_HOST", "MYSQLHOST", default="127.0.0.1"),
        port=int(_env_value("BAKEWISE_DB_PORT", "MYSQL_PORT", "MYSQLPORT", default="3306")),
        user=_env_value("BAKEWISE_DB_USER", "MYSQL_USER", "MYSQLUSER", default="root"),
        password=_env_value("BAKEWISE_DB_PASSWORD", "MYSQL_PASSWORD", "MYSQLPASSWORD", default=""),
        database=_env_value("BAKEWISE_DB_NAME", "MYSQL_DATABASE", "MYSQLDATABASE", default="bakewise"),
        connection_timeout=timeout,
    )


def _column_exists(cursor, table_name, column_name):
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s
        """,
        (table_name, column_name),
    )
    return cursor.fetchone()[0] > 0


def ensure_schema():
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                setting_key VARCHAR(100) PRIMARY KEY,
                setting_value VARCHAR(255) NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP
            )
            """
        )

        if not _column_exists(cursor, "transactions", "total"):
            cursor.execute(
                """
                ALTER TABLE transactions
                ADD COLUMN total DOUBLE NULL AFTER payment_method
                """
            )
            cursor.execute(
                """
                UPDATE transactions
                SET total = amount_paid
                WHERE total IS NULL
                """
            )

        column_updates = {
            "service_mode": "ALTER TABLE transactions ADD COLUMN service_mode VARCHAR(20) NULL AFTER payment_method",
            "order_source": "ALTER TABLE transactions ADD COLUMN order_source VARCHAR(30) NULL AFTER service_mode",
            "customer_number": "ALTER TABLE transactions ADD COLUMN customer_number VARCHAR(20) NULL AFTER order_source",
            "pickup_date_from": "ALTER TABLE transactions ADD COLUMN pickup_date_from DATE NULL AFTER customer_number",
            "pickup_date_to": "ALTER TABLE transactions ADD COLUMN pickup_date_to DATE NULL AFTER pickup_date_from",
            "online_order_status": "ALTER TABLE transactions ADD COLUMN online_order_status VARCHAR(20) NULL AFTER pickup_date_to",
            "accepted_at": "ALTER TABLE transactions ADD COLUMN accepted_at DATETIME NULL AFTER online_order_status",
            "processed_at": "ALTER TABLE transactions ADD COLUMN processed_at DATETIME NULL AFTER accepted_at",
        }
        for column_name, alter_sql in column_updates.items():
            if not _column_exists(cursor, "transactions", column_name):
                cursor.execute(alter_sql)

        cursor.execute(
            """
            INSERT IGNORE INTO app_settings (setting_key, setting_value)
            VALUES ('online_orders_accepting', '1')
            """
        )
        cursor.execute(
            """
            UPDATE transactions
            SET online_order_status = CASE
                WHEN is_voided = 1 THEN 'voided'
                ELSE 'processed'
            END
            WHERE order_source = 'Online Orders'
              AND COALESCE(online_order_status, '') = ''
            """
        )
        conn.commit()
        _SCHEMA_READY = True
    finally:
        conn.close()


def _parse_iso_date(value, field_name):
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value))
    except Exception as exc:
        raise StoreError(400, f"{field_name} must use YYYY-MM-DD format.") from exc


def _normalize_payment_method(value):
    normalized = str(value or "").strip().lower()
    if normalized not in VALID_PAYMENT_METHODS:
        raise StoreError(
            400,
            "Unsupported payment method.",
            {"allowed_payment_methods": ["Cash", "GCash", "Card"]},
        )
    return VALID_PAYMENT_METHODS[normalized]


def _product_query(filters=None):
    base_query = """
        SELECT
            p.product_id,
            p.name,
            p.category,
            p.price,
            p.shelf_life_days,
            COALESCE(stock.available_quantity, 0) AS available_quantity
        FROM products p
        LEFT JOIN (
            SELECT
                product_id,
                COALESCE(SUM(quantity), 0) AS available_quantity
            FROM inventory_batches
            WHERE expiry_date >= CURDATE()
              AND quantity > 0
            GROUP BY product_id
        ) stock ON stock.product_id = p.product_id
    """
    if filters:
        base_query += " WHERE " + " AND ".join(filters)
    base_query += " ORDER BY p.product_id ASC"
    return base_query


def _serialize_product(row):
    category = row.get("category") or "Fresh Bakes"
    return {
        "product_id": int(row["product_id"]),
        "name": row["name"],
        "category": category,
        "price": float(_money(row["price"])),
        "shelf_life_days": int(row.get("shelf_life_days") or 0),
        "available_quantity": int(row.get("available_quantity") or 0),
        # This gives the frontend a visual theme until real photo storage is added.
        "image_theme": category,
    }


def get_products(search=None, category=None, limit=None):
    ensure_schema()
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        filters = []
        params = []
        if search:
            filters.append("(p.name LIKE %s OR p.category LIKE %s OR CAST(p.product_id AS CHAR) LIKE %s)")
            wildcard = f"%{search.strip()}%"
            params.extend([wildcard, wildcard, wildcard])
        if category and category != "All":
            filters.append("p.category = %s")
            params.append(category)

        query = _product_query(filters)
        if limit is not None:
            query += " LIMIT %s"
            params.append(int(limit))

        cursor.execute(query, tuple(params))
        return [_serialize_product(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_product(product_id):
    ensure_schema()
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        query = _product_query(["p.product_id = %s"]) + " LIMIT 1"
        cursor.execute(query, (product_id,))
        row = cursor.fetchone()
        if not row:
            raise StoreError(404, "Product not found.")
        return _serialize_product(row)
    finally:
        conn.close()


def get_categories():
    ensure_schema()
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT DISTINCT category
            FROM products
            WHERE category IS NOT NULL
              AND TRIM(category) <> ''
            ORDER BY category ASC
            """
        )
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def get_storefront(limit=6):
    return {
        "store_name": DEFAULT_STORE_NAME,
        "source_label": DEFAULT_SOURCE_LABEL,
        "accepting_orders": get_online_orders_accepting(),
        "categories": get_categories(),
        "featured_products": get_products(limit=limit),
        "server_time": datetime.now().replace(microsecond=0).isoformat(),
    }


def get_online_orders_accepting():
    ensure_schema()
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT setting_value FROM app_settings WHERE setting_key = %s",
            ("online_orders_accepting",),
        )
        row = cursor.fetchone()
        if not row:
            return True
        return str(row[0]).strip().lower() not in {"0", "false", "off", "no"}
    finally:
        conn.close()


def _peek_next_customer_number(cursor, created_at):
    next_day = created_at + timedelta(days=1)
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM transactions
        WHERE service_mode = %s
          AND order_source = %s
          AND date >= %s
          AND date < %s
        """,
        ("Online Orders", "Online Orders", created_at, next_day),
    )
    count = (cursor.fetchone()[0] or 0) + 1
    return f"ON-{count:03d}"


def _serialize_temporal(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _serialize_order_row(row):
    return {
        "transaction_id": int(row["transaction_id"]),
        "customer_number": row.get("customer_number"),
        "payment_method": row.get("payment_method"),
        "service_mode": row.get("service_mode") or "Online Orders",
        "order_source": row.get("order_source") or "Online Orders",
        "online_order_status": row.get("online_order_status") or "pending",
        "pickup_date_from": _serialize_temporal(row.get("pickup_date_from")),
        "pickup_date_to": _serialize_temporal(row.get("pickup_date_to")),
        "created_at": _serialize_temporal(row.get("date")),
        "total": float(_money(row.get("total") or row.get("amount_paid") or 0)),
        "amount_paid": float(_money(row.get("amount_paid") or 0)),
        "items": [],
    }


def _attach_order_items(cursor, orders):
    if not orders:
        return orders

    order_lookup = {order["transaction_id"]: order for order in orders}
    placeholders = ", ".join(["%s"] * len(order_lookup))
    cursor.execute(
        f"""
        SELECT transaction_id, product_id, product_name, quantity, subtotal
        FROM transaction_items
        WHERE transaction_id IN ({placeholders})
        ORDER BY id ASC
        """,
        tuple(order_lookup.keys()),
    )
    for row in cursor.fetchall():
        order_lookup[int(row["transaction_id"])]["items"].append(
            {
                "product_id": int(row["product_id"]),
                "name": row["product_name"],
                "quantity": int(row["quantity"]),
                "subtotal": float(_money(row["subtotal"])),
            }
        )
    return orders


def get_orders(limit=25):
    ensure_schema()
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT
                transaction_id,
                customer_number,
                payment_method,
                service_mode,
                order_source,
                COALESCE(online_order_status, 'pending') AS online_order_status,
                pickup_date_from,
                pickup_date_to,
                date,
                total,
                amount_paid
            FROM transactions
            WHERE order_source = 'Online Orders'
            ORDER BY transaction_id DESC
            LIMIT %s
            """,
            (int(limit),),
        )
        orders = [_serialize_order_row(row) for row in cursor.fetchall()]
        return _attach_order_items(cursor, orders)
    finally:
        conn.close()


def get_order(order_id):
    ensure_schema()
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT
                transaction_id,
                customer_number,
                payment_method,
                service_mode,
                order_source,
                COALESCE(online_order_status, 'pending') AS online_order_status,
                pickup_date_from,
                pickup_date_to,
                date,
                total,
                amount_paid
            FROM transactions
            WHERE transaction_id = %s
              AND order_source = 'Online Orders'
            LIMIT 1
            """,
            (int(order_id),),
        )
        row = cursor.fetchone()
        if not row:
            raise StoreError(404, "Order not found.")
        order = _serialize_order_row(row)
        _attach_order_items(cursor, [order])
        return order
    finally:
        conn.close()


def create_order(payload):
    ensure_schema()
    if not isinstance(payload, dict):
        raise StoreError(400, "Request body must be a JSON object.")
    if not get_online_orders_accepting():
        raise StoreError(409, "BakeWise is not accepting online orders right now.")

    raw_items = payload.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise StoreError(400, "Provide at least one cart item.")

    requested_quantities = defaultdict(int)
    for index, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            raise StoreError(400, f"Item #{index} must be an object.")
        try:
            product_id = int(item.get("product_id"))
            quantity = int(item.get("quantity"))
        except Exception as exc:
            raise StoreError(400, f"Item #{index} must include valid product_id and quantity.") from exc
        if quantity <= 0:
            raise StoreError(400, f"Item #{index} quantity must be greater than zero.")
        requested_quantities[product_id] += quantity

    pickup_date_from = _parse_iso_date(payload.get("pickup_date_from"), "pickup_date_from")
    pickup_date_to = _parse_iso_date(payload.get("pickup_date_to"), "pickup_date_to")
    if pickup_date_from and pickup_date_to and pickup_date_to < pickup_date_from:
        raise StoreError(400, "pickup_date_to cannot be earlier than pickup_date_from.")

    payment_method = _normalize_payment_method(payload.get("payment_method"))
    source_label = str(payload.get("source_label") or DEFAULT_SOURCE_LABEL).strip() or DEFAULT_SOURCE_LABEL

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        product_ids = list(requested_quantities.keys())
        placeholders = ", ".join(["%s"] * len(product_ids))
        cursor.execute(
            f"""
            SELECT
                p.product_id,
                p.name,
                p.price,
                COALESCE(stock.available_quantity, 0) AS available_quantity
            FROM products p
            LEFT JOIN (
                SELECT
                    product_id,
                    COALESCE(SUM(quantity), 0) AS available_quantity
                FROM inventory_batches
                WHERE expiry_date >= CURDATE()
                  AND quantity > 0
                GROUP BY product_id
            ) stock ON stock.product_id = p.product_id
            WHERE p.product_id IN ({placeholders})
            """,
            tuple(product_ids),
        )
        product_rows = {int(row["product_id"]): row for row in cursor.fetchall()}

        missing_ids = [product_id for product_id in product_ids if product_id not in product_rows]
        if missing_ids:
            raise StoreError(400, "One or more selected products no longer exist.", {"missing_product_ids": missing_ids})

        stock_issues = []
        items_to_save = []
        for product_id, quantity in requested_quantities.items():
            row = product_rows[product_id]
            available_quantity = int(row.get("available_quantity") or 0)
            if quantity > available_quantity:
                stock_issues.append(
                    {
                        "product_id": product_id,
                        "name": row["name"],
                        "requested_quantity": quantity,
                        "available_quantity": available_quantity,
                    }
                )
            subtotal = _money(Decimal(str(row["price"])) * Decimal(quantity))
            items_to_save.append(
                {
                    "product_id": product_id,
                    "name": row["name"],
                    "quantity": quantity,
                    "subtotal": subtotal,
                }
            )

        if stock_issues:
            raise StoreError(409, "Some items do not have enough stock.", {"stock_issues": stock_issues})

        created_at = datetime.now().replace(microsecond=0)
        day_start = datetime.combine(created_at.date(), datetime.min.time())
        customer_number = _peek_next_customer_number(cursor, day_start)
        total = _money(sum(item["subtotal"] for item in items_to_save))
        default_amount_paid = total if payment_method in {"GCash", "Card"} else Decimal("0.00")
        amount_paid = payload.get("amount_paid", default_amount_paid)
        try:
            amount_paid = _money(amount_paid)
        except (InvalidOperation, ValueError) as exc:
            raise StoreError(400, "amount_paid must be numeric.") from exc

        cursor.execute(
            """
            INSERT INTO transactions
                (
                    cashier_name,
                    date,
                    payment_method,
                    service_mode,
                    order_source,
                    customer_number,
                    pickup_date_from,
                    pickup_date_to,
                    online_order_status,
                    accepted_at,
                    processed_at,
                    total,
                    amount_paid,
                    is_voided
                )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                source_label,
                created_at,
                payment_method,
                "Online Orders",
                "Online Orders",
                customer_number,
                pickup_date_from,
                pickup_date_to,
                "pending",
                None,
                None,
                float(total),
                float(amount_paid),
                0,
            ),
        )
        transaction_id = cursor.lastrowid

        for item in items_to_save:
            cursor.execute(
                """
                INSERT INTO transaction_items
                    (transaction_id, product_id, product_name, quantity, subtotal)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    transaction_id,
                    item["product_id"],
                    item["name"],
                    item["quantity"],
                    float(item["subtotal"]),
                ),
            )

        conn.commit()
        return get_order(transaction_id)
    except StoreError:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise StoreError(500, "BakeWise could not save the online order.", {"message": str(exc)}) from exc
    finally:
        conn.close()
