import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.exception_handlers import http_exception_handler as fastapi_http_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.database import init_db, async_session
from app.core.i18n import I18nMiddleware
from app.core.templating import get_templates
from app.routes import auth, shop, client, admin, pages, notifications
from app.services.i18n_helper import t
from app.services.seed import seed_all

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

templates = get_templates()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with async_session() as db:
        await seed_all(db)
    yield


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)
app.add_middleware(I18nMiddleware)


async def _render_error(request: Request, status_code: int, title_key: str, hint_key: str):
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "lang": getattr(request.state, "lang", "es"),
            "_t": lambda k, **kw: t(request, k, **kw),
            "current_user": None,
            "is_admin": False,
            "status_code": status_code,
            "error_title": t(request, title_key),
            "error_hint": t(request, hint_key),
        },
        status_code=status_code,
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return await _render_error(request, 404, "error.not_found", "error.not_found_hint")
    return await fastapi_http_exception_handler(request, exc)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logging.getLogger("uvicorn.error").error("Unhandled error on %s %s: %s", request.method, request.url.path, exc)
    return await _render_error(request, 500, "error.server_error", "error.server_error_hint")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

app.include_router(pages.router)
app.include_router(shop.router)
app.include_router(auth.router)
app.include_router(client.router)
app.include_router(admin.router)
app.include_router(notifications.router)