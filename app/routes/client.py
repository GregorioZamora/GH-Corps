from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path
from datetime import datetime
import re

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user, get_password_hash, verify_password
from app.core.templating import get_templates
from app.models.order import Order
from app.models.message import Message
from app.models.message_attachment import MessageAttachment
from app.models.product import Product
from app.models.user import User
from app.models.review import Review
from app.models.commission import Commission, CommissionMessage
from app.services.i18n_helper import t
from app.services.mailer import notify_admin, notify_user
from app.services.notifications import notify_user as notify_user_app, notify_admins
from app.services.uploads import save_upload, save_uploads
from app.services.pagination import paginate

router = APIRouter(prefix="/account", tags=["client"])
templates = get_templates()

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


@router.get("/orders/{order_id}/download")
async def download_order_file(
    order_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if order is None or order.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if order.status not in ("pagado", "completado", "enviado"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="File not available yet")

    product = await db.get(Product, order.product_id)
    if product is None or not product.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not available")

    file_path = Path(product.file_path)
    if not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    return FileResponse(
        path=file_path,
        filename=product.file_path.split("/")[-1].split("\\")[-1],
        media_type="application/octet-stream",
    )


@router.get("/profile")
async def profile_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return templates.TemplateResponse(
        "client/profile.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "current_user": current_user,
        },
    )


@router.post("/profile")
async def update_profile(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    gender: str = Form(""),
    account_type: str = Form(""),
    phone: str = Form(""),
    address: str = Form(""),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    full_name = full_name.strip()
    email = email.strip().lower()

    new_email = email != current_user.email
    if new_email:
        existing = await db.execute(select(User).where(User.email == email, User.id != current_user.id))
        if existing.scalar_one_or_none() is not None:
            return templates.TemplateResponse(
                "client/profile.html",
                {
                    "request": request,
                    "lang": request.state.lang,
                    "_t": lambda k, **kw: t(request, k, **kw),
                    "current_user": current_user,
                    "error": t(request, "auth.email_taken"),
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    current_user.full_name = full_name
    current_user.email = email
    current_user.gender = gender or None
    current_user.account_type = account_type or None
    current_user.phone = phone or None
    current_user.address = address or None
    await db.commit()

    return RedirectResponse(url="/account/profile?updated=1", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/password")
async def password_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return templates.TemplateResponse(
        "client/password.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "current_user": current_user,
            "has_password": current_user.hashed_password is not None,
        },
    )


@router.post("/password")
async def change_password(
    request: Request,
    current_password: str = Form(""),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    error = None
    if current_user.hashed_password:
        if not verify_password(current_password, current_user.hashed_password):
            error = t(request, "client.password_wrong")
    elif len(new_password) < 6:
        error = t(request, "client.password_short")
    if error is None and len(new_password) < 6:
        error = t(request, "client.password_short")
    if error is None and new_password != confirm_password:
        error = t(request, "client.password_mismatch")

    if error:
        return templates.TemplateResponse(
            "client/password.html",
            {
                "request": request,
                "lang": request.state.lang,
                "_t": lambda k, **kw: t(request, k, **kw),
                "current_user": current_user,
                "has_password": current_user.hashed_password is not None,
                "error": error,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    current_user.hashed_password = get_password_hash(new_password)
    await db.commit()

    notify_user(
        current_user.email,
        current_user.full_name,
        "Contraseña actualizada",
        f"<p>Hola <strong>{current_user.full_name}</strong>,</p>"
        "<p>Tu contraseña se ha cambiado correctamente. Si no fuiste tú, contacta con soporte.</p>",
    )

    return RedirectResponse(url="/account/password?changed=1", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/review")
async def my_review_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    review = await db.scalar(select(Review).where(Review.user_id == current_user.id))
    return templates.TemplateResponse(
        "client/review.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "current_user": current_user,
            "review": review,
        },
    )


@router.post("/review/delete")
async def delete_my_review(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    review = await db.scalar(select(Review).where(Review.user_id == current_user.id))
    if review is not None:
        await db.delete(review)
        await db.commit()
    return RedirectResponse(url="/account/review?deleted=1", status_code=status.HTTP_303_SEE_OTHER)


@router.get("")
async def account_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return templates.TemplateResponse(
        "client/dashboard.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "current_user": current_user,
        },
    )


@router.get("/orders")
async def my_orders(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = 1,
):
    if current_user.role == "admin":
        return RedirectResponse(url="/admin/orders", status_code=status.HTTP_303_SEE_OTHER)

    query = select(Order).where(Order.user_id == current_user.id)
    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    pager = paginate(total, page, settings.ITEMS_PER_PAGE)

    result = await db.execute(
        query.order_by(Order.created_at.desc()).offset(pager["offset"]).limit(pager["per_page"])
    )
    orders = result.scalars().all()

    product_ids = {o.product_id for o in orders}
    products_result = await db.execute(select(Product).where(Product.id.in_(product_ids)))
    products = {p.id: p for p in products_result.scalars().all()} if product_ids else {}

    return templates.TemplateResponse(
        "client/orders.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "current_user": current_user,
            "orders": orders,
            "products": products,
            "pager": pager,
            "base_url": "/account/orders",
            "extra_qs": "",
        },
    )


@router.get("/messages")
async def my_messages(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = 1,
):
    originals_query = select(Message).options(selectinload(Message.attachments)).where(
        Message.user_id == current_user.id,
        Message.reply_to_id.is_(None),
    )
    total = await db.scalar(select(func.count()).select_from(originals_query.subquery())) or 0
    pager = paginate(total, page, settings.ITEMS_PER_PAGE)

    result = await db.execute(
        originals_query.order_by(Message.created_at.desc())
        .offset(pager["offset"])
        .limit(pager["per_page"])
    )
    originals = result.scalars().all()
    original_ids = [m.id for m in originals]

    replies = []
    if original_ids:
        replies_result = await db.execute(
            select(Message)
            .options(selectinload(Message.attachments))
            .where(Message.reply_to_id.in_(original_ids))
            .order_by(Message.created_at.asc())
        )
        replies = replies_result.scalars().all()
    replies_by_thread = {}
    for r in replies:
        replies_by_thread.setdefault(r.reply_to_id, []).append(r)

    threads = [
        {"original": m, "replies": replies_by_thread.get(m.id, [])}
        for m in originals
    ]

    return templates.TemplateResponse(
        "client/messages.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "current_user": current_user,
            "threads": threads,
            "pager": pager,
            "base_url": "/account/messages",
            "extra_qs": "",
        },
    )


@router.post("/messages")
async def send_message(
    request: Request,
    subject: str = Form(...),
    content: str = Form(...),
    files: list[UploadFile] = File(default=[]),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    message = Message(
        user_id=current_user.id,
        sender_name=current_user.full_name,
        sender_email=current_user.email,
        subject=subject.strip(),
        content=content.strip(),
    )
    db.add(message)
    await db.flush()
    for path in save_uploads(files, "msg", message.id, kind="image"):
        db.add(
            MessageAttachment(
                message_id=message.id,
                filename=path.split("\\")[-1].split("/")[-1],
                path=path,
            )
        )
    await notify_admins(db, f"Nuevo mensaje: {subject.strip()}", content.strip(), "/admin/messages")
    await db.commit()

    return RedirectResponse(url="/account/messages?sent=1", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/commissions")
async def my_commissions(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = 1,
):
    if current_user.role == "admin":
        return RedirectResponse(url="/admin/commissions", status_code=status.HTTP_303_SEE_OTHER)

    query = select(Commission).where(Commission.user_id == current_user.id)
    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    pager = paginate(total, page, settings.ITEMS_PER_PAGE)

    result = await db.execute(
        query.order_by(Commission.updated_at.desc()).offset(pager["offset"]).limit(pager["per_page"])
    )
    commissions = result.scalars().all()

    return templates.TemplateResponse(
        "client/commissions.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "current_user": current_user,
            "commissions": commissions,
            "pager": pager,
            "base_url": "/account/commissions",
            "extra_qs": "",
        },
    )


@router.get("/commissions/new")
async def new_commission_page(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    if current_user.role == "admin":
        return RedirectResponse(url="/admin/commissions", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        "client/commission_form.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "current_user": current_user,
        },
    )


@router.post("/commissions")
async def create_commission(
    request: Request,
    contact_name: str = Form(""),
    contact_email: str = Form(""),
    title: str = Form(...),
    description: str = Form(""),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == "admin":
        return RedirectResponse(url="/admin/commissions", status_code=status.HTTP_303_SEE_OTHER)

    contact_name = contact_name.strip()
    contact_email = contact_email.strip().lower()

    error = None
    if not contact_name:
        error = t(request, "commission.contact_name_required")
    elif not contact_email:
        error = t(request, "commission.contact_email_required")
    elif not EMAIL_REGEX.match(contact_email):
        error = t(request, "commission.contact_email_invalid")

    if error:
        return templates.TemplateResponse(
            "client/commission_form.html",
            {
                "request": request,
                "lang": request.state.lang,
                "_t": lambda k, **kw: t(request, k, **kw),
                "current_user": current_user,
                "error": error,
                "contact_name": contact_name,
                "contact_email": contact_email,
                "title": title,
                "description": description,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    commission = Commission(
        user_id=current_user.id,
        title=title.strip(),
        description=description.strip(),
        client_name=contact_name,
        client_email=contact_email,
        status="en_proceso",
    )
    db.add(commission)
    await db.flush()

    db.add(
        CommissionMessage(
            commission_id=commission.id,
            sender_id=current_user.id,
            content=description.strip(),
        )
    )
    await notify_admins(db, f"Nuevo encargo: {commission.title}", contact_name, "/admin/commissions")
    await db.commit()

    notify_admin(
        f"Nuevo encargo: {commission.title}",
        f"<p>{contact_name} ({contact_email}) ha solicitado un encargo:</p>"
        f"<p><strong>{commission.title}</strong></p><p>{description.strip()}</p>",
    )

    return RedirectResponse(
        url=f"/account/commissions/{commission.id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/commissions/{commission_id}")
async def commission_detail(
    commission_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Commission).where(Commission.id == commission_id))
    commission = result.scalar_one_or_none()
    if commission is None or commission.user_id != current_user.id:
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

    return templates.TemplateResponse(
        "client/commission_detail.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "current_user": current_user,
            "commission": commission,
            "thread": thread,
            "senders": senders,
        },
    )


@router.post("/commissions/{commission_id}/messages")
async def client_commission_reply(
    commission_id: int,
    request: Request,
    content: str = Form(""),
    attachment: UploadFile = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Commission).where(Commission.id == commission_id))
    commission = result.scalar_one_or_none()
    if commission is None or commission.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    msg = CommissionMessage(
        commission_id=commission_id,
        sender_id=current_user.id,
        content=content.strip() or None,
        attachment_path=save_upload(attachment, "commission", commission_id, kind="file"),
    )
    db.add(msg)
    commission.updated_at = datetime.utcnow()
    await notify_admins(db, f"Nuevo mensaje en encargo: {commission.title}", current_user.full_name, "/admin/commissions")
    await db.commit()

    notify_admin(
        f"Nuevo mensaje en encargo: {commission.title}",
        f"<p>{current_user.full_name} ha actualizado el encargo '<strong>{commission.title}</strong>'.</p>",
    )

    return RedirectResponse(
        url=f"/account/commissions/{commission_id}", status_code=status.HTTP_303_SEE_OTHER
    )