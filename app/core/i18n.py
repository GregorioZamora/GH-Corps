import json
from pathlib import Path
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.services.cart import cart_count

DEFAULT_LANG = "es"


def load_translations(lang: str) -> dict:
    path = Path(__file__).parent.parent / "locales" / f"{lang}.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    path = Path(__file__).parent.parent / "locales" / f"{DEFAULT_LANG}.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class I18nMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        lang = request.cookies.get("lang", DEFAULT_LANG)
        if lang not in ("es", "en", "fr"):
            lang = DEFAULT_LANG
        request.state.lang = lang
        request.state.translations = load_translations(lang)
        request.state.cart_count = cart_count(request)
        response = await call_next(request)
        return response
