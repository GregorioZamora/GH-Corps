from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_optional_user
from app.core.templating import get_templates
from app.models.message import Message
from app.models.message_attachment import MessageAttachment
from app.models.product import Product
from app.models.commission import Commission, CommissionMessage
from app.services.i18n_helper import t
from app.services.mailer import notify_admin
from app.services.notifications import notify_admins
from app.services.uploads import save_uploads

router = APIRouter(tags=["pages"])
templates = get_templates()


@router.get("/about")
async def about(request: Request, current_user=Depends(get_optional_user)):
    return templates.TemplateResponse(
        "about.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "current_user": current_user,
        },
    )


@router.get("/contact")
async def contact_page(request: Request, current_user=Depends(get_optional_user)):
    return templates.TemplateResponse(
        "contact.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "current_user": current_user,
            "user": current_user,
        },
    )


@router.post("/contact")
async def contact_submit(
    request: Request,
    subject: str = Form(...),
    message: str = Form(...),
    kind: str = Form("message"),
    name: str = Form(""),
    email: str = Form(""),
    files: list[UploadFile] = File(default=[]),
    current_user=Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user is None:
        kind = "message"
        name = name.strip()
        email = email.strip()
        if not name or "@" not in email or "." not in email.split("@")[-1]:
            return RedirectResponse(url="/contact?error=1", status_code=status.HTTP_303_SEE_OTHER)
        sender_name, sender_email, user_id = name, email, None
    elif current_user.role == "admin":
        sender_name, sender_email, user_id = current_user.full_name, current_user.email, current_user.id
    else:
        sender_name, sender_email, user_id = current_user.full_name, current_user.email, current_user.id

    if kind == "commission" and current_user is not None and current_user.role != "admin":
        commission = Commission(
            user_id=current_user.id,
            client_name=current_user.full_name,
            client_email=current_user.email,
            title=subject.strip(),
            description=message.strip(),
            status="en_proceso",
        )
        db.add(commission)
        await db.flush()
        db.add(
            CommissionMessage(
                commission_id=commission.id,
                sender_id=current_user.id,
                content=message.strip(),
            )
        )
        await notify_admins(db, f"Nuevo encargo solicitado: {subject.strip()}", current_user.full_name, "/admin/commissions")
        await db.commit()
        notify_admin(
            f"Nuevo encargo solicitado: {subject.strip()}",
            f"<p>{current_user.full_name} ({current_user.email}) ha solicitado un encargo:</p>"
            f"<p><strong>{subject.strip()}</strong></p><p>{message.strip()}</p>",
        )
        return RedirectResponse(url="/contact?sent_commission=1", status_code=status.HTTP_303_SEE_OTHER)

    db_message = Message(
        user_id=user_id,
        sender_name=sender_name,
        sender_email=sender_email,
        subject=subject.strip(),
        content=message.strip(),
    )
    db.add(db_message)
    await db.flush()
    for path in save_uploads(files, "msg", db_message.id, kind="image"):
        db.add(
            MessageAttachment(
                message_id=db_message.id,
                filename=path.split("\\")[-1].split("/")[-1],
                path=path,
            )
        )
    await notify_admins(db, f"Nuevo mensaje: {subject.strip()}", sender_name, "/admin/messages")
    await db.commit()

    notify_admin(
        f"Nuevo mensaje: {subject.strip()}",
        f"<p>Nuevo mensaje de <strong>{sender_name}</strong> ({sender_email}):</p>"
        f"<p>{message.strip()}</p>"
        "<p>Responde desde el panel de administración.</p>",
    )

    return RedirectResponse(url="/contact?sent=1", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/language/{lang}")
async def set_language(lang: str):
    if lang not in ("es", "en", "fr"):
        lang = "es"
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="lang", value=lang, max_age=31536000)
    return response


@router.get("/robots.txt", include_in_schema=False)
async def robots_txt():
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        f"Sitemap: {settings.PROJECT_URL.rstrip('/')}/sitemap.xml\n"
    )
    return Response(content=body, media_type="text/plain")


@router.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml(db: AsyncSession = Depends(get_db)):
    base = settings.PROJECT_URL.rstrip("/")
    urls = ["/", "/shop", "/about", "/contact", "/legal/aviso-legal", "/legal/privacidad", "/legal/cookies"]
    products = (
        await db.execute(select(Product).where(Product.is_available == True))
    ).scalars().all()
    items = "".join(
        f"<url><loc>{base}{path}</loc><changefreq>weekly</changefreq></url>" for path in urls
    )
    product_items = "".join(
        f"<url><loc>{base}/product/{p.id}</loc><changefreq>monthly</changefreq></url>"
        for p in products
    )
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{items}{product_items}\n"
        "</urlset>\n"
    )
    return Response(content=body, media_type="application/xml")


@router.get("/legal/aviso-legal")
async def legal_terms(request: Request, current_user=Depends(get_optional_user)):
    return templates.TemplateResponse(
        "legal/aviso_legal.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "current_user": current_user,
        },
    )


@router.get("/legal/privacidad")
async def legal_privacy(request: Request, current_user=Depends(get_optional_user)):
    return templates.TemplateResponse(
        "legal/privacidad.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "current_user": current_user,
        },
    )


@router.get("/legal/cookies")
async def legal_cookies(request: Request, current_user=Depends(get_optional_user)):
    return templates.TemplateResponse(
        "legal/cookies.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "current_user": current_user,
        },
    )