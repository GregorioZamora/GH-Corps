from fastapi.templating import Jinja2Templates
from app.core.config import settings


def get_templates() -> Jinja2Templates:
    """Return a Jinja2Templates instance with shared globals registered.

    Settings globals are registered once so every template can access
    ``settings`` (company name, contact email, etc.) directly.
    """
    templates = Jinja2Templates(directory="app/templates")

    def register_globals()->None:
        templates.env.globals["settings"] = settings

    # Ensure globals are registered only once per environment instance.
    if "settings" not in templates.env.globals:
        register_globals()

    return templates
