import re
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, decode_token, get_password_hash, verify_password
from app.core.templating import get_templates
from app.models.user import User
from app.services.google_oauth import (
    get_google_auth_url,
    exchange_code_for_token,
    get_google_user_info,
)
from app.services.i18n_helper import t
from app.services.mailer import notify_user
from app.services.rate_limiter import rate_limiter, client_key

router = APIRouter(prefix="/auth", tags=["auth"])
templates = get_templates()

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
RESET_EXPIRE_MINUTES = 30
CONFIRM_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


def _redirect_home_with_error(request: Request, template: str, error_key: str, **ctx):
    lang = request.state.lang
    return templates.TemplateResponse(
        template,
        {
            "request": request,
            "lang": lang,
            "_t": lambda k, **kw: t(request, k, **kw),
        }
        | ctx
        | {"error": t(request, error_key)},
        status_code=status.HTTP_400_BAD_REQUEST,
    )


def _set_auth_cookie(response: RedirectResponse, token: str) -> RedirectResponse:
    response.set_cookie(key="access_token", value=token, httponly=True, max_age=604800, samesite="lax")
    return response


@router.get("/login")
async def login_page(request: Request, verify: int = 0, confirmed: int = 0, reset: int = 0):
    return templates.TemplateResponse(
        "auth/login.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "google_client_id": "configured",
            "verify": verify,
            "confirmed": confirmed,
            "reset": reset,
        },
    )


@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    _rl_key = client_key(request)
    if _rl_key is not None and not rate_limiter.is_allowed(_rl_key):
        return _redirect_home_with_error(request, "auth/login.html", "auth.rate_limited", email=email)

    result = await db.execute(select(User).where(User.email == email.strip().lower()))
    user = result.scalar_one_or_none()

    if user is None or not user.hashed_password or not verify_password(password, user.hashed_password):
        return _redirect_home_with_error(request, "auth/login.html", "auth.invalid_credentials", email=email)

    if not user.is_active:
        return _redirect_home_with_error(request, "auth/login.html", "auth.account_disabled", email=email)

    if not user.is_email_confirmed:
        return _redirect_home_with_error(request, "auth/login.html", "auth.email_not_confirmed", email=email)

    token = create_access_token({"sub": str(user.id)})
    redirect_url = "/admin" if user.role == "admin" else "/account"
    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    response = _set_auth_cookie(response, token)

    if user.role != "admin":
        from app.services.cart import get_cart, set_cart, load_user_cart, persist_cart

        session_items = get_cart(request)
        db_items = await load_user_cart(db, user.id)
        merged = dict(db_items)
        for pid, qty in session_items.items():
            merged[pid] = min(99, merged.get(pid, 0) + qty)
        if merged:
            set_cart(request, merged, response)
            await persist_cart(db, user.id, merged)

    return response


@router.get("/register")
async def register_page(request: Request):
    return templates.TemplateResponse(
        "auth/register.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "google_client_id": "configured",
        },
    )


@router.post("/register")
async def register(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    gender: str = Form(...),
    account_type: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    _rl_key = client_key(request)
    if _rl_key is not None and not rate_limiter.is_allowed(_rl_key):
        return _redirect_home_with_error(request, "auth/register.html", "auth.rate_limited", email=email)

    email = email.strip().lower()

    if not EMAIL_REGEX.match(email):
        return _redirect_home_with_error(request, "auth/register.html", "auth.invalid_credentials", email=email)

    if password != confirm_password:
        return _redirect_home_with_error(request, "auth/register.html", "auth.password_mismatch", email=email)

    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none() is not None:
        return _redirect_home_with_error(request, "auth/register.html", "auth.email_taken", email=email)

    user = User(
        email=email,
        full_name=full_name.strip(),
        hashed_password=get_password_hash(password),
        role="client",
        auth_provider="local",
        gender=gender,
        account_type=account_type,
        is_email_confirmed=not settings.MAIL_ENABLED,
    )
    db.add(user)
    await db.flush()

    if settings.MAIL_ENABLED:
        token = create_access_token(
            {"sub": str(user.id), "purpose": "confirm_email"},
            expires_delta=timedelta(minutes=CONFIRM_EXPIRE_MINUTES),
        )
        confirm_url = f"{settings.PROJECT_URL}/auth/confirm-email?token={token}"
        notify_user(
            user.email,
            user.full_name,
            "Confirma tu correo — GH Diseños",
            f"<p>Hola <strong>{user.full_name}</strong>,</p>"
            f"<p>Confirma tu correo electrónico para activar tu cuenta:</p>"
            f"<p><a href='{confirm_url}'>Confirmar correo</a></p>"
            f"<p>Si no te registraste tú, ignora este mensaje.</p>",
        )
        await db.commit()
        return RedirectResponse(url="/auth/login?verify=1", status_code=status.HTTP_303_SEE_OTHER)

    await db.commit()
    token = create_access_token({"sub": str(user.id)})
    response = RedirectResponse(url="/account", status_code=status.HTTP_303_SEE_OTHER)
    return _set_auth_cookie(response, token)


@router.get("/confirm-email")
async def confirm_email(
    request: Request,
    token: str = "",
    db: AsyncSession = Depends(get_db),
):
    payload = decode_token(token)
    if payload is None or payload.get("purpose") != "confirm_email" or payload.get("sub") is None:
        return _redirect_home_with_error(request, "auth/login.html", "auth.invalid_confirm_token")

    user = await db.get(User, int(payload["sub"]))
    if user is None:
        return _redirect_home_with_error(request, "auth/login.html", "auth.invalid_confirm_token")

    user.is_email_confirmed = True
    await db.commit()

    return RedirectResponse(url="/auth/login?confirmed=1", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/google")
async def google_login(request: Request):
    state = secrets.token_urlsafe(16)
    signed_state = create_access_token(
        {"purpose": "oauth_state", "state": state},
        expires_delta=timedelta(minutes=10),
    )
    url = get_google_auth_url(state)
    response = RedirectResponse(url=url)
    response.set_cookie(key="oauth_state", value=signed_state, httponly=True, max_age=600, samesite="lax")
    return response


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    signed_state = request.cookies.get("oauth_state")
    try:
        payload = decode_token(signed_state) if signed_state else None
        if payload is None or payload.get("purpose") != "oauth_state" or payload.get("state") != state:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid OAuth state")

        token_response = await exchange_code_for_token(code)
        user_info = await get_google_user_info(token_response["access_token"])

        google_id = user_info["id"]
        email = user_info["email"].lower()

        result = await db.execute(select(User).where(User.google_id == google_id))
        user = result.scalar_one_or_none()

        if user is None:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            if user is not None:
                user.google_id = google_id
                user.auth_provider = "google"
                user.is_email_confirmed = True
                await db.commit()
        else:
            user.email = email

        if user is None:
            user = User(
                email=email,
                full_name=user_info.get("name", "Usuario Google"),
                role="client",
                auth_provider="google",
                google_id=google_id,
                avatar_url=user_info.get("picture"),
                is_email_confirmed=True,
            )
            db.add(user)
            await db.commit()

        if not user.is_active:
            return _redirect_home_with_error(request, "auth/login.html", "auth.account_disabled")

        token = create_access_token({"sub": str(user.id)})
        redirect_url = "/admin" if user.role == "admin" else "/account"
        response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
        response.delete_cookie(key="oauth_state")
        return _set_auth_cookie(response, token)

    except Exception:
        lang = request.state.lang
        return templates.TemplateResponse(
            "auth/login.html",
            {
                "request": request,
                "lang": lang,
                "_t": lambda k, **kw: t(request, k, **kw),
                "error": t(request, "auth.google_login_failed"),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )


@router.get("/forgot-password")
async def forgot_password_page(request: Request):
    return templates.TemplateResponse(
        "auth/forgot_password.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
        },
    )


@router.post("/forgot-password")
async def forgot_password(
    request: Request,
    email: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    _rl_key = client_key(request)
    if _rl_key is not None and not rate_limiter.is_allowed(_rl_key):
        return _redirect_home_with_error(request, "auth/forgot_password.html", "auth.rate_limited", email=email)

    email = email.strip().lower()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        return RedirectResponse(url="/auth/forgot-password?sent=1", status_code=status.HTTP_303_SEE_OTHER)

    token = create_access_token(
        {"sub": str(user.id), "purpose": "reset"},
        expires_delta=timedelta(minutes=RESET_EXPIRE_MINUTES),
    )
    reset_url = f"{settings.PROJECT_URL}/auth/reset-password?token={token}"

    notify_user(
        user.email,
        user.full_name,
        "Recupera tu contraseña",
        f"<p>Hola <strong>{user.full_name}</strong>,</p>"
        f"<p>Recibimos una solicitud para restablecer tu contraseña.</p>"
        f"<p><a href='{reset_url}'>Haz clic aquí para cambiarla</a> "
        f"(el enlace es válido durante {RESET_EXPIRE_MINUTES} minutos).</p>"
        f"<p>Si no la pediste tú, ignora este correo.</p>",
    )

    return RedirectResponse(url="/auth/forgot-password?sent=1", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/reset-password")
async def reset_password_page(request: Request, token: str = ""):
    return templates.TemplateResponse(
        "auth/reset_password.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "token": token,
        },
    )


@router.post("/reset-password")
async def reset_password(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    _rl_key = client_key(request)
    if _rl_key is not None and not rate_limiter.is_allowed(_rl_key):
        return _redirect_home_with_error(request, "auth/reset_password.html", "auth.rate_limited", token=token)

    payload = decode_token(token)
    if payload is None or payload.get("purpose") != "reset":
        return _redirect_home_with_error(request, "auth/reset_password.html", "auth.invalid_reset_token", token=token)

    user_id = payload.get("sub")
    if user_id is None:
        return _redirect_home_with_error(request, "auth/reset_password.html", "auth.invalid_reset_token", token=token)

    user = await db.get(User, int(user_id))
    if user is None:
        return _redirect_home_with_error(request, "auth/reset_password.html", "auth.invalid_reset_token", token=token)

    if password != confirm_password:
        return _redirect_home_with_error(
            request, "auth/reset_password.html", "auth.password_mismatch", token=token
        )

    user.hashed_password = get_password_hash(password)
    user.is_email_confirmed = True
    await db.commit()

    notify_user(
        user.email,
        user.full_name,
        "Contraseña actualizada",
        f"<p>Hola <strong>{user.full_name}</strong>,</p>"
        f"<p>Tu contraseña se actualizó correctamente.</p>"
        f"<p>Si no fuiste tú, contacta con nosotros lo antes posible.</p>",
    )

    return RedirectResponse(url="/auth/login?reset=1", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key="access_token")
    response.delete_cookie(key="oauth_state")
    return response