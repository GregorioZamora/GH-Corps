"""Shopping cart stored in a signed cookie.

The cookie only holds product ids and quantities. Prices are always read
from the database at checkout, so tampering with the cookie cannot change
what the customer pays.
"""
import json
from datetime import timedelta
from fastapi import Request, Response

from app.core.security import create_access_token, decode_token


CART_COOKIE = "cart"
CART_MAX = 30  # max distinct products


def _sign(data: dict) -> str:
    return create_access_token(
        {"purpose": "cart", "items": data},
        expires_delta=timedelta(days=30),
    )


def _decode(cookie_value) -> dict:
    """Return {product_id_str: quantity}."""
    if not cookie_value:
        return {}
    payload = decode_token(cookie_value)
    if payload is None or payload.get("purpose") != "cart":
        return {}
    items = payload.get("items")
    if not isinstance(items, dict):
        return {}
    cleaned = {}
    for k, v in items.items():
        try:
            pid = str(int(k))
        except (TypeError, ValueError):
            continue
        if isinstance(v, int) and 0 < v <= 99:
            cleaned[pid] = v
    return cleaned


def get_cart(request: Request) -> dict:
    return _decode(request.cookies.get(CART_COOKIE))


def cart_count(request: Request) -> int:
    return sum(get_cart(request).values())


def add_to_cart(request: Request, product_id: int, quantity: int = 1, response: Response = None) -> int:
    items = get_cart(request)
    items[str(product_id)] = min(99, items.get(str(product_id), 0) + max(1, quantity))
    _set_cart_cookie(response, items)
    return sum(items.values())


def remove_from_cart(request: Request, product_id: int, response: Response = None) -> int:
    items = get_cart(request)
    items.pop(str(product_id), None)
    _set_cart_cookie(response, items)
    return sum(items.values())


def clear_cart(response: Response) -> None:
    response.delete_cookie(CART_COOKIE)


def set_cart(request: Request, items: dict, response: Response) -> int:
    _set_cart_cookie(response, {str(k): v for k, v in items.items()})
    return sum(items.values())


def _set_cart_cookie(response: Response, items: dict) -> None:
    if not items:
        response.delete_cookie(CART_COOKIE)
        return
    response.set_cookie(
        key=CART_COOKIE,
        value=_sign(items),
        httponly=True,
        max_age=60 * 60 * 24 * 30,  # 30 days
        samesite="lax",
    )


async def persist_cart(db, user_id: int, items: dict) -> None:
    """Mirror the cookie cart into the DB so it survives devices/logins."""
    from sqlalchemy import delete as _delete, select as _select

    from app.models.cart_item import CartItem

    await db.execute(_delete(CartItem).where(CartItem.user_id == user_id))
    for pid, qty in items.items():
        try:
            pid_int, qty_int = int(pid), int(qty)
        except (TypeError, ValueError):
            continue
        if pid_int <= 0 or qty_int <= 0:
            continue
        db.add(CartItem(user_id=user_id, product_id=pid_int, quantity=min(99, qty_int)))
    await db.commit()


async def clear_persisted_cart(db, user_id: int) -> None:
    from sqlalchemy import delete as _delete

    from app.models.cart_item import CartItem

    await db.execute(_delete(CartItem).where(CartItem.user_id == user_id))
    await db.commit()


async def load_user_cart(db, user_id: int) -> dict:
    """Return {product_id_str: quantity} saved for this user."""
    from sqlalchemy import select as _select

    from app.models.cart_item import CartItem

    rows = (await db.execute(_select(CartItem).where(CartItem.user_id == user_id))).scalars().all()
    return {str(item.product_id): item.quantity for item in rows}