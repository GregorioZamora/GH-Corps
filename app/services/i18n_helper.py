from fastapi import Request


def _resolve(translations: dict, key: str, **kwargs) -> str:
    """Resolve a dotted key (e.g. 'home.hero_title') against a nested dict."""
    current = translations
    for part in key.split("."):
        if not isinstance(current, dict):
            return key
        current = current.get(part)
        if current is None:
            return key
    if isinstance(current, dict):
        return key
    value = current
    return value.format(**kwargs) if kwargs else value


def t(request: Request, key: str, **kwargs) -> str:
    """Translate a key using the request's loaded translations."""
    translations = getattr(request.state, "translations", {})
    return _resolve(translations, key, **kwargs)


def tf(lang: str, key: str, **kwargs) -> str:
    """Translate using an explicit lang string (used in services)."""
    from app.core.i18n import load_translations

    return _resolve(load_translations(lang), key, **kwargs)