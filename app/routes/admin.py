import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select, func, or_, update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import require_role
from app.core.templating import get_templates
from app.models.user import User
from app.models.product import Product, ProductImage
from app.models.order import Order
from app.models.message import Message
from app.models.message_attachment import MessageAttachment
from app.models.commission import Commission, CommissionMessage
from app.models.review import Review
from app.services.i18n_helper import t
from app.services.mailer import notify_admin, notify_user
from app.services.notifications import notify_user as notify_user_app, notify_admins
from app.services.uploads import save_upload, remove_upload, save_uploads
from app.services.pagination import paginate

router = APIRouter(prefix="/admin", tags=["admin"])
templates = get_templates()

admin_required = require_role("admin")


def save_product_file(file: UploadFile, product_id: int) -> str:
    """Store an uploaded product file and return its filesystem path."""
    return save_upload(file, "product", product_id, kind="file")


def save_product_image(file: UploadFile, product_id: int) -> str:
    """Store a product preview image. Returns path or '' when empty."""
    path = save_upload(file, "product_img", product_id, kind="image")
    return path or ""


def remove_uploaded_file(file_path: str | None) -> None:
    """Delete an uploaded product file from disk, ignoring missing files."""
    remove_upload(file_path)


@router.get("")
async def admin_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    total_orders = await db.scalar(select(func.count(Order.id))) or 0
    total_customers = await db.scalar(select(func.count(User.id)).where(User.role == "client")) or 0
    total_revenue = await db.scalar(
        select(func.coalesce(func.sum(Order.total_price), 0)).where(Order.status != "cancelado")
    ) or 0
    unread_messages = await db.scalar(select(func.count(Message.id)).where(Message.is_read == False)) or 0
    total_products = await db.scalar(select(func.count(Product.id))) or 0
    total_commissions = await db.scalar(select(func.count(Commission.id))) or 0
    total_reviews = await db.scalar(select(func.count(Review.id))) or 0

    recent_orders = (await db.execute(select(Order).order_by(Order.created_at.desc()).limit(5))).scalars().all()
    recent_messages = (await db.execute(select(Message).order_by(Message.created_at.desc()).limit(5))).scalars().all()
    recent_commissions = (await db.execute(select(Commission).order_by(Commission.updated_at.desc()).limit(5))).scalars().all()

    commission_unread_rows = (
        await db.execute(
            select(CommissionMessage.commission_id, func.count(CommissionMessage.id))
            .where(CommissionMessage.is_read == False)
            .where(CommissionMessage.commission_id.in_([c.id for c in recent_commissions]))
            .group_by(CommissionMessage.commission_id)
        )
    ).all() if recent_commissions else []
    recent_unread_commissions = {row[0]: row[1] for row in commission_unread_rows}

    month_rows = (
        await db.execute(
            select(
                func.strftime("%Y-%m", Order.created_at).label("month"),
                func.count(Order.id).label("orders"),
                func.coalesce(func.sum(Order.total_price), 0).label("revenue"),
            )
            .where(Order.status != "cancelado")
            .group_by("month")
            .order_by("month")
        )
    ).all()
    month_map = {row.month: {"orders": row.orders, "revenue": row.revenue} for row in month_rows}
    now = datetime.now()
    monthly_sales = []
    for i in range(5, -1, -1):
        year, month = now.year, now.month - i
        while month <= 0:
            month += 12
            year -= 1
        label = f"{year:04d}-{month:02d}"
        data = month_map.get(label, {"orders": 0, "revenue": 0})
        monthly_sales.append({"label": label, "orders": data["orders"], "revenue": data["revenue"]})

    max_monthly_orders = max((m["orders"] for m in monthly_sales), default=0)

    top_rows = (
        await db.execute(
            select(
                Product.name.label("name"),
                func.count(Order.id).label("sold"),
                func.coalesce(func.sum(Order.total_price), 0).label("revenue"),
            )
            .join(Order, Order.product_id == Product.id)
            .group_by(Product.id, Product.name)
            .order_by(func.count(Order.id).desc(), func.sum(Order.total_price).desc())
            .limit(5)
        )
    ).all()
    top_products = [
        {"name": row.name, "sold": row.sold, "revenue": row.revenue}
        for row in top_rows
    ]

    products_result = await db.execute(select(Product))
    products = {p.id: p for p in products_result.scalars().all()}
    users_result = await db.execute(select(User))
    users = {u.id: u for u in users_result.scalars().all()}

    return templates.TemplateResponse(
        "admin/dashboard.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "current_user": current_user,
            "total_orders": total_orders,
            "total_customers": total_customers,
            "total_revenue": total_revenue,
            "unread_messages": unread_messages,
            "total_products": total_products,
            "total_commissions": total_commissions,
            "total_reviews": total_reviews,
            "monthly_sales": monthly_sales,
            "max_monthly_orders": max_monthly_orders,
            "top_products": top_products,
            "recent_orders": recent_orders,
            "recent_messages": recent_messages,
            "recent_commissions": recent_commissions,
            "recent_unread_commissions": recent_unread_commissions,
            "products": products,
            "users": users,
        },
    )


@router.get("/orders")
async def admin_orders(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_required),
    status_filter: str = "",
    page: int = 1,
):
    query = select(Order)
    if status_filter:
        query = query.where(Order.status == status_filter)

    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    pager = paginate(total, page, settings.ITEMS_PER_PAGE)

    result = await db.execute(
        query.order_by(Order.created_at.desc()).offset(pager["offset"]).limit(pager["per_page"])
    )
    orders = result.scalars().all()

    product_ids = {o.product_id for o in orders}
    user_ids = {o.user_id for o in orders}
    products_result = await db.execute(select(Product).where(Product.id.in_(product_ids)))
    products = {p.id: p for p in products_result.scalars().all()} if product_ids else {}
    users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users = {u.id: u for u in users_result.scalars().all()} if user_ids else {}

    return templates.TemplateResponse(
        "admin/orders.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "current_user": current_user,
            "orders": orders,
            "products": products,
            "users": users,
            "status_filter": status_filter,
            "pager": pager,
            "base_url": "/admin/orders",
            "extra_qs": f"&status_filter={status_filter}" if status_filter else "",
        },
    )


@router.get("/orders/{order_id}")
async def admin_order_detail(
    order_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    order = await db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    user = await db.get(User, order.user_id) if order.user_id else None
    product = await db.get(Product, order.product_id) if order.product_id else None

    return templates.TemplateResponse(
        "admin/order_detail.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "current_user": current_user,
            "order": order,
            "customer": user,
            "product": product,
        },
    )


@router.post("/orders/{order_id}/status")
async def update_order_status(
    order_id: int,
    request: Request,
    status_value: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    order.status = status_value
    await db.commit()

    user = await db.get(User, order.user_id)
    product = await db.get(Product, order.product_id)
    if user:
        notify_user_app(
            db,
            user.id,
            f"Pedido #{order.id} {status_value}",
            f"Tu pedido de {product.name if product else ''} ha pasado a {status_value}",
            "/account/orders",
        )
        await db.commit()
    if user and status_value in ("enviado", "completado"):
        notify_user(
            user.email,
            user.full_name,
            f"Tu pedido #{order.id} está {status_value}",
            f"<p>Hola <strong>{user.full_name}</strong>,</p>"
            f"<p>Tu pedido de <strong>{product.name if product else ''}</strong> (nº {order.id}) "
            f"ha pasado a estado <strong>{status_value}</strong>.</p>"
            f"<p>Ya puedes <strong>descargar el plano</strong> desde tu panel de cliente.</p>",
        )

    return RedirectResponse(url="/admin/orders", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/customers")
async def admin_customers(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_required),
    search: str = "",
    page: int = 1,
):
    query = select(User).where(User.role == "client")
    if search:
        like = f"%{search}%"
        query = query.where(
            (User.full_name.ilike(like)) | (User.email.ilike(like)) | (User.phone.ilike(like))
        )

    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    pager = paginate(total, page, settings.ITEMS_PER_PAGE)

    result = await db.execute(
        query.order_by(User.created_at.desc()).offset(pager["offset"]).limit(pager["per_page"])
    )
    customers = result.scalars().all()

    return templates.TemplateResponse(
        "admin/customers.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "current_user": current_user,
            "customers": customers,
            "search": search,
            "pager": pager,
            "base_url": "/admin/customers",
            "extra_qs": f"&search={search}" if search else "",
        },
    )


@router.get("/messages")
async def admin_messages(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_required),
    status_filter: str = "",
    q: str = "",
    since: str = "",
    page: int = 1,
):
    query = select(Message).where(Message.reply_to_id.is_(None))
    if status_filter:
        if status_filter == "unread":
            query = query.where(Message.is_read == False)
        elif status_filter == "read":
            query = query.where(Message.is_read == True)
    if since.isdigit():
        threshold = datetime.now() - timedelta(days=int(since))
        query = query.where(Message.created_at >= threshold)
    search = q.strip()
    if search:
        pattern = f"%{search.lower()}%"
        query = query.where(
            or_(
                func.lower(Message.subject).like(pattern),
                func.lower(Message.sender_name).like(pattern),
                func.lower(Message.sender_email).like(pattern),
            )
        )

    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    pager = paginate(total, page, settings.ITEMS_PER_PAGE)

    result = await db.execute(
        query.order_by(Message.created_at.desc()).offset(pager["offset"]).limit(pager["per_page"])
    )
    messages = result.scalars().all()
    att_counts: dict[int, int] = {}
    if messages:
        counts = (
            await db.execute(
                select(MessageAttachment.message_id, func.count(MessageAttachment.id))
                .where(MessageAttachment.message_id.in_([m.id for m in messages]))
                .group_by(MessageAttachment.message_id)
            )
        ).all()
        att_counts = {mid: cnt for mid, cnt in counts}

    extra_parts = []
    if status_filter:
        extra_parts.append(f"status_filter={status_filter}")
    if search:
        extra_parts.append(f"q={search.replace(' ', '+')}")
    if since.isdigit():
        extra_parts.append(f"since={since}")
    extra_qs = f"&{'&'.join(extra_parts)}" if extra_parts else ""

    return templates.TemplateResponse(
        "admin/messages.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "current_user": current_user,
            "messages": messages,
            "att_counts": att_counts,
            "support_agents": settings.SUPPORT_AGENTS,
            "status_filter": status_filter,
            "q": search,
            "since": since if since.isdigit() else "",
            "pager": pager,
            "base_url": "/admin/messages",
            "extra_qs": extra_qs,
        },
    )


@router.post("/messages/{message_id}/read")
async def mark_message_read(
    message_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    message.is_read = True
    await db.commit()
    return RedirectResponse(url="/admin/messages", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/messages/{message_id}/delete")
async def delete_message(
    message_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    attachments = (
        await db.execute(select(MessageAttachment).where(MessageAttachment.message_id == message.id))
    ).scalars().all()
    for att in attachments:
        remove_upload(att.path)

    await db.delete(message)
    await db.commit()
    return RedirectResponse(url="/admin/messages", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/messages/{message_id}")
async def message_detail(
    message_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    result = await db.execute(
        select(Message).options(selectinload(Message.attachments)).where(Message.id == message_id)
    )
    message = result.scalar_one_or_none()
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    original = message
    if message.reply_to_id:
        original_result = await db.execute(
            select(Message).options(selectinload(Message.attachments)).where(Message.id == message.reply_to_id)
        )
        original = original_result.scalar_one_or_none()
        if original is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    replies_result = await db.execute(
        select(Message)
        .options(selectinload(Message.attachments))
        .where(Message.reply_to_id == original.id)
        .order_by(Message.created_at.asc())
    )
    thread = [original] + list(replies_result.scalars().all())

    if not original.is_read:
        original.is_read = True
        await db.commit()

    return templates.TemplateResponse(
        "admin/message_detail.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "current_user": current_user,
            "message": original,
            "thread": thread,
            "support_agents": settings.SUPPORT_AGENTS,
            "company_email": settings.COMPANY_EMAIL,
        },
    )


@router.post("/messages/{message_id}/reply")
async def reply_message(
    message_id: int,
    request: Request,
    reply_content: str = Form(...),
    agent: str = Form(""),
    files: list[UploadFile] = File(default=[]),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    original_id = message.reply_to_id or message.id
    agent_name = agent.strip()
    if agent_name not in settings.SUPPORT_AGENTS:
        agent_name = settings.SUPPORT_AGENTS[0] if settings.SUPPORT_AGENTS else settings.COMPANY_NAME

    original = await db.get(Message, original_id)
    root_subject = original.subject if original else message.subject

    message.is_read = True
    reply = Message(
        user_id=None,
        reply_to_id=original_id,
        sender_name=agent_name,
        sender_email=settings.COMPANY_EMAIL,
        subject=f"RE: {root_subject}",
        content=reply_content.strip(),
        is_read=True,
    )
    db.add(reply)
    await db.flush()
    for path in save_uploads(files, "msg", reply.id, kind="image"):
        db.add(
            MessageAttachment(
                message_id=reply.id,
                filename=path.split("\\")[-1].split("/")[-1],
                path=path,
            )
        )
    if message.user_id:
        notify_user_app(
            db,
            message.user_id,
            f"Re: {message.subject}",
            f"{agent_name} ({settings.COMPANY_NAME}) te ha respondido.",
            "/account/messages",
        )
    await db.commit()

    notify_user(
        message.sender_email,
        message.sender_name,
        f"Re: {message.subject}",
        f"<p>Hola <strong>{message.sender_name}</strong>,</p>"
        f"<p><strong>{agent_name}</strong> de <strong>{settings.COMPANY_NAME}</strong> "
        f"ha respondido a tu mensaje:</p>"
        f"<blockquote style='border-left:3px solid #ccc;padding-left:12px;margin-left:0'>{reply_content.strip()}</blockquote>"
        f"<p>Puedes revisar el historial en tu panel de cliente.</p>",
    )

    return RedirectResponse(
        url=f"/admin/messages/{original_id}?sent=1", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/products")
async def admin_products(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_required),
    search: str = "",
    page: int = 1,
):
    query = select(Product)
    if search:
        like = f"%{search}%"
        query = query.where((Product.name.ilike(like)) | (Product.description.ilike(like)))

    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    pager = paginate(total, page, settings.ITEMS_PER_PAGE)

    result = await db.execute(
        query.order_by(Product.created_at.desc()).offset(pager["offset"]).limit(pager["per_page"])
    )
    products = result.scalars().all()

    return templates.TemplateResponse(
        "admin/products.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "current_user": current_user,
            "products": products,
            "search": search,
            "pager": pager,
            "base_url": "/admin/products",
            "extra_qs": f"&search={search}" if search else "",
        },
    )


@router.get("/products/new")
async def new_product_page(
    request: Request,
    current_user: User = Depends(admin_required),
):
    return templates.TemplateResponse(
        "admin/product_form.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "current_user": current_user,
            "action": "create",
            "product": None,
            "categories": ["solidworks", "autocad", "otros"],
        },
    )


@router.get("/products/{product_id}/edit")
async def edit_product_page(
    product_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return templates.TemplateResponse(
        "admin/product_form.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "current_user": current_user,
            "action": f"edit/{product_id}",
            "product": product,
            "categories": ["solidworks", "autocad", "otros"],
        },
    )


@router.post("/products/create")
async def create_product(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    price: float = Form(...),
    category: str = Form("planos"),
    software: str = Form(""),
    file: UploadFile = File(None),
    image: UploadFile = File(None),
    gallery_images: List[UploadFile] = File([]),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    product = Product(
        name=name.strip(),
        description=description.strip(),
        price=price,
        category=category,
        software=software.strip(),
        is_available=True,
    )
    db.add(product)
    await db.flush()

    if file and file.filename:
        product.file_path = save_product_file(file, product.id)
    if image and image.filename:
        product.image_path = save_product_image(image, product.id)
    for gfile in gallery_images or []:
        if gfile and gfile.filename:
            gpath = save_product_image(gfile, product.id)
            if gpath:
                db.add(ProductImage(product_id=product.id, image_path=gpath))

    await db.commit()

    return RedirectResponse(url="/admin/products", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/products/{product_id}/update")
async def update_product(
    product_id: int,
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    price: float = Form(...),
    category: str = Form("planos"),
    software: str = Form(""),
    is_available: bool = Form(False),
    file: UploadFile = File(None),
    image: UploadFile = File(None),
    remove_file: bool = Form(False),
    remove_image: bool = Form(False),
    gallery_images: List[UploadFile] = File([]),
    remove_gallery: List[int] = Form([]),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    product.name = name.strip()
    product.description = description.strip()
    product.price = price
    product.category = category
    product.software = software.strip()
    product.is_available = is_available

    if remove_file:
        remove_uploaded_file(product.file_path)
        product.file_path = None
    elif file and file.filename:
        remove_uploaded_file(product.file_path)
        product.file_path = save_product_file(file, product.id)

    if remove_image:
        remove_uploaded_file(product.image_path)
        product.image_path = None
    elif image and image.filename:
        remove_uploaded_file(product.image_path)
        product.image_path = save_product_image(image, product.id) or None

    if remove_gallery:
        target = (
            await db.execute(
                select(ProductImage).where(
                    ProductImage.product_id == product_id, ProductImage.id.in_(remove_gallery)
                )
            )
        ).scalars().all()
        for gi in target:
            remove_uploaded_file(gi.image_path)
            await db.delete(gi)

    for gfile in gallery_images or []:
        if gfile and gfile.filename:
            gpath = save_product_image(gfile, product.id)
            if gpath:
                db.add(ProductImage(product_id=product.id, image_path=gpath))

    await db.commit()

    return RedirectResponse(url="/admin/products", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/products/{product_id}/delete")
async def delete_product(
    product_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    remove_uploaded_file(product.file_path)
    remove_uploaded_file(product.image_path)
    gallery_images = (
        await db.execute(select(ProductImage).where(ProductImage.product_id == product_id))
    ).scalars().all()
    for gi in gallery_images:
        remove_uploaded_file(gi.image_path)

    await db.delete(product)
    await db.commit()

    return RedirectResponse(url="/admin/products", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/commissions")
async def admin_commissions(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_required),
    status_filter: str = "",
    q: str = "",
    since: str = "",
    page: int = 1,
):
    query = select(Commission)
    if status_filter:
        query = query.where(Commission.status == status_filter)
    if since.isdigit():
        threshold = datetime.now() - timedelta(days=int(since))
        query = query.where(Commission.created_at >= threshold)
    search = q.strip()
    if search:
        pattern = f"%{search.lower()}%"
        query = query.where(
            or_(
                func.lower(Commission.title).like(pattern),
                func.lower(Commission.client_name).like(pattern),
                func.lower(Commission.client_email).like(pattern),
                Commission.user_id.in_(
                    select(User.id).where(
                        or_(
                            func.lower(User.full_name).like(pattern),
                            func.lower(User.email).like(pattern),
                        )
                    )
                ),
            )
        )

    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    pager = paginate(total, page, settings.ITEMS_PER_PAGE)

    result = await db.execute(
        query.order_by(Commission.updated_at.desc()).offset(pager["offset"]).limit(pager["per_page"])
    )
    commissions = result.scalars().all()

    user_ids = {c.user_id for c in commissions if c.user_id}
    users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users = {u.id: u for u in users_result.scalars().all()} if user_ids else {}

    unread_rows = (
        await db.execute(
            select(CommissionMessage.commission_id, func.count(CommissionMessage.id))
            .where(CommissionMessage.is_read == False)
            .where(CommissionMessage.commission_id.in_([c.id for c in commissions]))
            .group_by(CommissionMessage.commission_id)
        )
    ).all() if commissions else []
    unread_counts = {row[0]: row[1] for row in unread_rows}

    extra_parts = []
    if status_filter:
        extra_parts.append(f"status_filter={status_filter}")
    if search:
        extra_parts.append(f"q={search.replace(' ', '+')}")
    if since.isdigit():
        extra_parts.append(f"since={since}")
    extra_qs = f"&{'&'.join(extra_parts)}" if extra_parts else ""

    return templates.TemplateResponse(
        "admin/commissions.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "current_user": current_user,
            "commissions": commissions,
            "users": users,
            "unread_counts": unread_counts,
            "status_filter": status_filter,
            "q": search,
            "since": since if since.isdigit() else "",
            "pager": pager,
            "base_url": "/admin/commissions",
            "extra_qs": extra_qs,
        },
    )


@router.get("/commissions/{commission_id}")
async def admin_commission_detail(
    commission_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    result = await db.execute(select(Commission).where(Commission.id == commission_id))
    commission = result.scalar_one_or_none()
    if commission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    messages_result = await db.execute(
        select(CommissionMessage)
        .where(CommissionMessage.commission_id == commission_id)
        .order_by(CommissionMessage.created_at.asc())
    )
    thread = messages_result.scalars().all()

    sender_ids = {m.sender_id for m in thread if m.sender_id}
    senders_result = await db.execute(select(User).where(User.id.in_(sender_ids)))
    senders = {u.id: u for u in senders_result.scalars().all()} if sender_ids else {}

    if commission.user_id:
        owner = await db.get(User, commission.user_id)
    else:
        owner = None

    await db.execute(
        update(CommissionMessage)
        .where(
            CommissionMessage.commission_id == commission_id,
            CommissionMessage.is_read == False,
        )
        .values(is_read=True)
    )
    await db.commit()

    return templates.TemplateResponse(
        "admin/commission_detail.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "current_user": current_user,
            "commission": commission,
            "thread": thread,
            "senders": senders,
            "owner": owner,
        },
    )


@router.post("/commissions/{commission_id}/status")
async def admin_update_commission_status(
    commission_id: int,
    request: Request,
    new_status: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    result = await db.execute(select(Commission).where(Commission.id == commission_id))
    commission = result.scalar_one_or_none()
    if commission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    old_status = commission.status
    commission.status = new_status
    commission.updated_at = datetime.now()
    if commission.user_id:
        notify_user_app(
            db,
            commission.user_id,
            f"Encargo '{commission.title}' actualizado",
            f"Estado: {old_status} → {new_status}",
            f"/account/commissions/{commission_id}",
        )
    await db.commit()

    if commission.user_id:
        user = await db.get(User, commission.user_id)
        if user:
            notify_user(
                user.email,
                user.full_name,
                f"Encargo '{commission.title}' actualizado",
                f"<p>Hola <strong>{user.full_name}</strong>,</p>"
                f"<p>Tu encargo '<strong>{commission.title}</strong>' ha pasado de "
                f"<strong>{old_status}</strong> a <strong>{new_status}</strong>.</p>",
            )

    return RedirectResponse(
        url=f"/admin/commissions/{commission_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/commissions/{commission_id}/messages")
async def admin_commission_reply(
    commission_id: int,
    request: Request,
    content: str = Form(""),
    attachment: UploadFile = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    result = await db.execute(select(Commission).where(Commission.id == commission_id))
    commission = result.scalar_one_or_none()
    if commission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    msg = CommissionMessage(
        commission_id=commission_id,
        sender_id=current_user.id,
        content=content.strip() or None,
        attachment_path=save_upload(attachment, "commission", commission_id, kind="file"),
        is_read=True,
    )
    db.add(msg)
    commission.updated_at = datetime.now()
    if commission.user_id:
        notify_user_app(
            db,
            commission.user_id,
            f"Nuevo avance en tu encargo '{commission.title}'",
            "El equipo ha actualizado tu encargo.",
            f"/account/commissions/{commission_id}",
        )
    await db.commit()

    if commission.user_id:
        user = await db.get(User, commission.user_id)
        if user:
            notify_user(
                user.email,
                user.full_name,
                f"Nuevo avance en tu encargo '{commission.title}'",
                f"<p>Hola <strong>{user.full_name}</strong>,</p>"
                f"<p>El equipo ha actualizado tu encargo '<strong>{commission.title}</strong>'"
                + (f" con un nuevo prototipo adjunto." if msg.attachment_path else f":<br>{content.strip()}") + "</p>",
            )

    return RedirectResponse(
        url=f"/admin/commissions/{commission_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/reviews")
async def admin_reviews(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_required),
    page: int = 1,
):
    total = await db.scalar(select(func.count()).select_from(Review)) or 0
    pager = paginate(total, page, settings.ITEMS_PER_PAGE)

    rows = (
        await db.execute(
            select(Review, User)
            .join(User, Review.user_id == User.id)
            .order_by(Review.created_at.desc())
            .offset(pager["offset"])
            .limit(pager["per_page"])
        )
    ).all()

    return templates.TemplateResponse(
        "admin/reviews.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "current_user": current_user,
            "reviews": [{"review": review, "user": user} for review, user in rows],
            "pager": pager,
            "base_url": "/admin/reviews",
            "extra_qs": "",
        },
    )


@router.post("/reviews/{review_id}/delete")
async def admin_review_delete(
    review_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    review = await db.get(Review, review_id)
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await db.delete(review)
    await db.commit()
    return RedirectResponse(url="/admin/reviews", status_code=status.HTTP_303_SEE_OTHER)
