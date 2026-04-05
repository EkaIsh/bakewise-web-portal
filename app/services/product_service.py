from __future__ import annotations

from ..repositories.product_repository import fetch_all_products
from ..repositories.product_repository import fetch_product_by_id as fetch_product_record


def get_all_products() -> list[dict]:
    """
    Return all products for the API.

    The service layer stays intentionally thin here because the main job
    is simply to fetch storefront products from the repository layer.
    """
    products = fetch_all_products()
    return products or []


def get_product_by_id(product_id: int) -> dict | None:
    """
    Return one product by its ID.

    The route can turn a None result into a 404 response.
    """
    return fetch_product_record(product_id)
