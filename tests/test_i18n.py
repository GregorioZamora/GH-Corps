"""Verify i18n renders correctly across languages."""
import asyncio
import sys
import os
import json

PROJECT_DIR = os.environ.get("GH_CORPS_DIR", ".")
sys.path.insert(0, PROJECT_DIR)

from httpx import AsyncClient, ASGITransport
from main import app

BASE = "http://test"
LOCALES_DIR = os.path.join(PROJECT_DIR, "app", "locales")


def load(key):
    with open(os.path.join(LOCALES_DIR, f"{key}.json"), "r", encoding="utf-8") as f:
        return json.load(f)


async def run():
    from app.core.database import init_db, async_session as setup_session
    from app.services.seed import seed_all

    await init_db()
    async with setup_session() as sdb:
        await seed_all(sdb)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE, follow_redirects=True) as c:
        print("== Spanish (default) ==")
        es = load("es")
        r = await c.get("/")
        assert es["home"]["hero_title"] in r.text, "ES hero missing"
        assert es["nav"]["login"] in r.text, "ES nav login missing"
        r = await c.get("/shop")
        assert es["shop"]["title"] in r.text, "ES shop title missing"
        r = await c.get("/auth/login")
        assert "google_client_id" not in es  # sanity
        from app.core.config import settings
        if not settings.GOOGLE_CLIENT_ID:
            assert "accounts.google.com" not in r.text, "Google button should be hidden without client_id"
        print("  OK  ES")

        print("== English ==")
        en = load("en")
        await c.get("/language/en")
        r = await c.get("/")
        assert en["home"]["hero_title"] in r.text, "EN hero missing"
        assert en["nav"]["login"] in r.text, "EN nav login missing"
        r = await c.get("/shop")
        assert en["shop"]["title"] in r.text, "EN shop title missing"
        print("  OK  EN")

        print("== French ==")
        fr = load("fr")
        await c.get("/language/fr")
        r = await c.get("/")
        assert fr["home"]["hero_title"] in r.text, "FR hero missing"
        assert fr["nav"]["login"] in r.text, "FR nav login missing"
        r = await c.get("/shop")
        assert fr["shop"]["title"] in r.text, "FR shop title missing"
        print("  OK  FR")

        print("== Invalid lang falls back to ES ==")
        await c.get("/language/xx")
        r = await c.get("/")
        assert es["home"]["hero_title"] in r.text, "fallback ES missing"
        print("  OK  fallback")

        print("== Locale key parity (es vs en vs fr) ==")
        def flatten(d, prefix=""):
            keys = set()
            for k, v in d.items():
                full = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    keys |= flatten(v, full)
                else:
                    keys.add(full)
            return keys

        key_es = flatten(es)
        key_en = flatten(en)
        key_fr = flatten(fr)
        assert key_en == key_es, f"EN keys missing/extra: {key_en ^ key_es}"
        assert key_fr == key_es, f"FR keys missing/extra: {key_fr ^ key_es}"
        print(f"  3 locale files share {len(key_es)} keys")
        print("  OK  parity")

    print("ALL I18N CHECKS PASSED")


asyncio.run(run())