from __future__ import annotations

from flask import Blueprint, current_app, jsonify, render_template

from ..repositories.product_repository import fetch_all_products

storefront_bp = Blueprint("storefront", __name__)


def _bakewise(**extra: object) -> dict[str, object]:
    """Build the `bakewise` object for templates (merges with anything extra, e.g. order_id)."""
    payload: dict[str, object] = {
        "store_name": current_app.config["STORE_NAME"],
        "source_label": current_app.config["SOURCE_LABEL"],
    }
    payload.update(extra)
    return payload


# ── Page routes ──────────────────────────────────────────────────────────────

@storefront_bp.get("/")
def home():
    return render_template("home.html", page_name="home")


@storefront_bp.get("/products")
def products_page():
    return render_template("products.html", page_name="products")


@storefront_bp.get("/cart")
def cart_page():
    return render_template("cart.html", page_name="cart")


@storefront_bp.get("/checkout")
def checkout_page():
    return render_template("checkout.html", page_name="checkout")


@storefront_bp.get("/confirmation/<int:order_id>")
def confirmation_page(order_id: int):
    return render_template(
        "confirmation.html",
        page_name="confirmation",
        bakewise=_bakewise(order_id=order_id),
    )


# ── Storefront API ────────────────────────────────────────────────────────────

@storefront_bp.get("/api/storefront")
def api_storefront():
    """Return a storefront summary with featured products for the home page."""
    try:
        all_products = fetch_all_products()
    except Exception:  # noqa: BLE001
        all_products = []

    # Return up to 3 in-stock products as featured items.
    in_stock = [p for p in all_products if p.get("available_quantity", 0) > 0]
    featured = in_stock[:3] if in_stock else all_products[:3]

    return jsonify(
        {
            "store_name": current_app.config["STORE_NAME"],
            "accepting_orders": True,
            "featured_products": featured,
            "total_products": len(all_products),
        }
    )
