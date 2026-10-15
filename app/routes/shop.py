from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from datetime import datetime
from sqlalchemy import select, func, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user, get_optional_user
from app.core.templating import get_templates
from app.models.product import Product
from app.models.order import Order
from app.models.review import Review
from app.models.user import User
from app.models.cart_item import CartItem
from app.services.i18n_helper import t
from app.services.mailer import notify_admin, notify_user
from app.services.notifications import notify_admins
from app.services.pagination import paginate
from app.services.cart import (
    get_cart,
    add_to_cart,
    remove_from_cart,
    clear_cart,
    set_cart,
    persist_cart,
    load_user_cart,
    clear_persisted_cart,
)

router = APIRouter(tags=["shop"])
templates = get_templates()


@router.get("/")
async def home(request: Request, db: AsyncSession = Depends(get_db), current_user=Depends(get_optional_user)):
    product_count = await db.scalar(select(func.count(Product.id)))
    reviews = await _load_reviews(db)
    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "current_user": current_user,
            "product_count": product_count or 0,
            "reviews": reviews,
            "review_count": len(reviews),
            "avg_rating": round(
                sum(r["rating"] for r in reviews) / len(reviews), 1
            ) if reviews else 0,
        },
    )


async def _load_reviews(db: AsyncSession):
    rows = (
        await db.execute(
            select(Review, User)
            .join(User, Review.user_id == User.id)
            .order_by(Review.created_at.desc())
        )
    ).all()
    return [
        {
            "rating": review.rating,
            "comment": review.comment,
            "name": user.full_name,
            "created_at": review.created_at,
        }
        for review, user in rows
    ]


@router.get("/shop")
async def shop(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
    category: str = "",
    software: str = "",
    search: str = "",
    sort: str = "newest",
    page: int = 1,
):
    query = select(Product).where(Product.is_available == True)
    if category:
        query = query.where(Product.category == category)
    if software:
        query = query.where(Product.software == software)
    if search:
        query = query.where(or_(Product.name.ilike(f"%{search}%"), Product.description.ilike(f"%{search}%")))

    sort_map = {
        "newest": Product.created_at.desc(),
        "oldest": Product.created_at.asc(),
        "price_asc": Product.price.asc(),
        "price_desc": Product.price.desc(),
        "name_asc": Product.name.asc(),
    }
    order_by = sort_map.get(sort, Product.created_at.desc())

    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    pager = paginate(total, page, settings.ITEMS_PER_PAGE)

    result = await db.execute(
        query.order_by(order_by).offset(pager["offset"]).limit(pager["per_page"])
    )
    products = result.scalars().all()

    software_vals = (await db.execute(select(Product.software).where(Product.is_available == True).distinct())).scalars().all()

    extra = []
    for key, val in (("category", category), ("software", software), ("search", search), ("sort", sort)):
        if val:
            extra.append(f"{key}={val}")
    extra_qs = ("&" + "&".join(extra)) if extra else ""

    return templates.TemplateResponse(
        "shop/shop.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "current_user": current_user,
            "products": products,
            "selected_category": category,
            "selected_software": software,
            "search": search,
            "sort": sort,
            "software_list": [s for s in software_vals if s],
            "pager": pager,
            "base_url": "/shop",
            "extra_qs": extra_qs,
        },
    )


@router.get("/product/{product_id}")
async def product_detail(
    product_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    return templates.TemplateResponse(
        "shop/product_detail.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "current_user": current_user,
            "product": product,
        },
    )


@router.post("/review")
async def add_review(
    request: Request,
    rating: int = Form(...),
    comment: str = Form(""),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.role == "admin":
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    rating = max(1, min(5, rating))
    existing = await db.execute(select(Review).where(Review.user_id == current_user.id))
    review = existing.scalar_one_or_none()
    if review is None:
        review = Review(user_id=current_user.id, rating=rating, comment=comment.strip() or None)
        db.add(review)
    else:
        review.rating = rating
        review.comment = comment.strip() or None
        review.created_at = datetime.utcnow()
    await db.commit()

    return RedirectResponse(url="/#reviews", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/shop/buy/{product_id}")
async def buy_product(
    product_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    if current_user is None:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

    if current_user.role == "admin":
        return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)

    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product is None or not product.is_available:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not available")

    order = Order(
        user_id=current_user.id,
        product_id=product.id,
        quantity=1,
        total_price=product.price,
        status="pendiente",
    )
    db.add(order)
    await notify_admins(db, f"Nuevo pedido #{order.id}", f"{current_user.full_name} - {product.name}", "/admin/orders")
    await db.commit()

    notify_admin(
        f"Nuevo pedido #{order.id}",
        f"<p>{current_user.full_name} ({current_user.email}) ha realizado un pedido:</p>"
        f"<p><strong>{product.name}</strong> - {product.price}€</p>",
    )
    notify_user(
        current_user.email,
        current_user.full_name,
        "Pedido confirmado",
        f"<p>Hola <strong>{current_user.full_name}</strong>,</p>"
        f"<p>Hemos recibido tu pedido de <strong>{product.name}</strong> por {product.price}€.</p>"
        f"<p>Te avisaremos cuando esté disponible para descargar.</p>",
    )

    return RedirectResponse(url="/account/orders", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/shop/cart/add/{product_id}")
async def cart_add(
    product_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.role == "admin":
        return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)

    product = await db.get(Product, product_id)
    if product is None or not product.is_available:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not available")

    item_cart = get_cart(request)
    item_cart[str(product_id)] = min(99, item_cart.get(str(product_id), 0) + 1)
    response = RedirectResponse(
        url=request.headers.get("referer", "/shop"),
        status_code=status.HTTP_303_SEE_OTHER,
    )
    add_to_cart(request, product_id, 1, response)
    await persist_cart(db, current_user.id, item_cart)
    return response


@router.post("/shop/cart/update")
async def cart_update(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    form = await request.form()
    if current_user.role == "admin":
        return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)

    items = {}
    for key, value in form.items():
        if key.startswith("qty_"):
            try:
                pid = int(key.split("_", 1)[1])
            except ValueError:
                continue
            try:
                qty = max(1, min(99, int(value)))
            except (TypeError, ValueError):
                continue
            items[pid] = qty

    response = RedirectResponse(url="/cart", status_code=status.HTTP_303_SEE_OTHER)
    if items:
        set_cart(request, items, response)
        await persist_cart(db, current_user.id, items)
    return response


@router.post("/shop/cart/remove/{product_id}")
async def cart_remove(
    product_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    item_cart = get_cart(request)
    item_cart.pop(str(product_id), None)
    response = RedirectResponse(url="/cart", status_code=status.HTTP_303_SEE_OTHER)
    remove_from_cart(request, product_id, response)
    await persist_cart(db, current_user.id, item_cart)
    return response


@router.get("/cart")
async def cart_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    cart = get_cart(request)
    healed = False
    if not cart and current_user.role != "admin":
        saved = await load_user_cart(db, current_user.id)
        if saved:
            cart = saved
            healed = True
    product_ids = [int(pid) for pid in cart.keys()]
    products = {}
    if product_ids:
        result = await db.execute(select(Product).where(Product.id.in_(product_ids)))
        products = {p.id: p for p in result.scalars().all()}

    lines = []
    total = 0.0
    for pid, qty in cart.items():
        product = products.get(int(pid))
        if product is None or not product.is_available:
            continue
        subtotal = round(product.price * qty, 2)
        total += subtotal
        lines.append({"product": product, "qty": qty, "subtotal": subtotal})

    total = round(total, 2)
    response = templates.TemplateResponse(
        "shop/cart.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "current_user": current_user,
            "lines": lines,
            "total": total,
            "cart_count": sum(cart.values()),
        },
    )
    if healed:
        set_cart(request, cart, response)
    return response


@router.post("/cart/checkout")
async def cart_checkout(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    if current_user is None:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)
    if current_user.role == "admin":
        return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)

    cart = get_cart(request)
    product_ids = [int(pid) for pid in cart.keys()]
    if not product_ids:
        return RedirectResponse(url="/cart", status_code=status.HTTP_303_SEE_OTHER)

    result = await db.execute(select(Product).where(Product.id.in_(product_ids)))
    products = {p.id: p for p in result.scalars().all()}

    total_price = 0.0
    created = []
    for pid, qty in cart.items():
        product = products.get(int(pid))
        if product is None or not product.is_available:
            continue
        order = Order(
            user_id=current_user.id,
            product_id=product.id,
            quantity=qty,
            total_price=round(product.price * qty, 2),
            status="pendiente",
        )
        db.add(order)
        total_price += product.price * qty
        created.append((product, qty))

    if not created:
        return RedirectResponse(url="/cart", status_code=status.HTTP_303_SEE_OTHER)

    await notify_admins(
        db,
        f"Nuevo pedido del carrito ({len(created)} productos)",
        current_user.full_name,
        "/admin/orders",
    )
    await db.commit()

    items_html = "".join(
        f"<li><strong>{p.name}</strong> x{q} - {round(p.price * q, 2)}€</li>"
        for p, q in created
    )
    notify_admin(
        f"Nuevo pedido del carrito ({len(created)} productos)",
        f"<p>{current_user.full_name} ({current_user.email}) ha realizado un pedido:</p>"
        f"<ul>{items_html}</ul>"
        f"<p><strong>Total: {round(total_price, 2)}€</strong></p>",
    )
    notify_user(
        current_user.email,
        current_user.full_name,
        "Pedido confirmado",
        f"<p>Hola <strong>{current_user.full_name}</strong>,</p>"
        f"<p>Hemos recibido tu pedido:</p><ul>{items_html}</ul>"
        f"<p><strong>Total: {round(total_price, 2)}€</strong>.</p>"
        f"<p>Te avisaremos cuando esté disponible para descargar.</p>",
    )

    response = RedirectResponse(url="/account/orders?from_cart=1", status_code=status.HTTP_303_SEE_OTHER)
    clear_cart(response)
    await clear_persisted_cart(db, current_user.id)
    return response