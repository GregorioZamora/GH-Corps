import os
import secrets
from dotenv import load_dotenv
from pathlib import Path

_BASE_DIR = Path(__file__).parent.parent
load_dotenv(_BASE_DIR / ".env")


def _load_secret_key() -> str:
    """Use the configured SECRET_KEY, or persist a generated one.

    A fixed default (or a clearly dev placeholder) is dangerous, so when
    nothing secure is provided we generate a random key once and store it
    in a local .secret_key file. This keeps sessions/tokens valid across
    restarts without requiring the user to configure anything.
    """
    value = os.getenv("SECRET_KEY", "")
    insecure = (
        not value
        or "change-this" in value
        or "change-in-production" in value
        or value == "dev-secret-key-gh-corps-change-in-production"
        or len(value) < 32
    )

    if not insecure:
        return value

    key_file = _BASE_DIR / ".secret_key"
    try:
        if key_file.is_file():
            stored = key_file.read_text(encoding="utf-8").strip()
            if stored:
                return stored
        generated = secrets.token_urlsafe(48)
        key_file.write_text(generated, encoding="utf-8")
        return generated
    except OSError:
        return secrets.token_urlsafe(48)


class Settings:
    PROJECT_NAME: str = os.getenv("APP_NAME", "GH Diseños")
    PROJECT_URL: str = os.getenv("APP_URL", "http://localhost:8000")
    COMPANY_NAME: str = os.getenv("COMPANY_NAME", "GH Diseños")
    COMPANY_EMAIL: str = os.getenv("COMPANY_EMAIL", "infoghdisenos@gmail.com")
    SUPPORT_AGENTS: list = [
        a.strip() for a in os.getenv("SUPPORT_AGENTS", "Gregorio, Henri").split(",") if a.strip()
    ]
    SECRET_KEY: str = _load_secret_key()
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./gh_corps.db")
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
    UPLOAD_DIR: str = str(_BASE_DIR / "uploads")
    LOCALES_DIR: str = str(_BASE_DIR / "locales")
    SUPPORTED_LANGUAGES: list = ["es", "en", "fr"]
    DEFAULT_LANGUAGE: str = "es"
    MAIL_ENABLED: bool = os.getenv("MAIL_ENABLED", "false").lower() in ("1", "true", "yes", "on")
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    MAIL_FROM: str = os.getenv("MAIL_FROM", "GH Diseños <no-reply@localhost>")
    MAIL_FROM_NAME: str = os.getenv("MAIL_FROM_NAME", "GH Diseños")
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "infoghdisenos@gmail.com")
    ITEMS_PER_PAGE: int = int(os.getenv("ITEMS_PER_PAGE", "10"))

    # Upload security
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))
    ALLOWED_IMAGE_EXTENSIONS: set = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}
    ALLOWED_FILE_EXTENSIONS: set = {
        ".pdf", ".zip", ".rar", ".7z", ".dwg", ".dxf", ".sldprt", ".sldasm",
        ".step", ".stp", ".iges", ".igs", ".stl", ".obj", ".catpart", ".catproduct",
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".txt", ".jpg", ".jpeg", ".png",
        ".webp", ".svg",
    }
    ALLOWED_IMAGE_MIMES: set = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml"}

    # Rate limiting (in-memory)
    RATE_LIMIT_MAX: int = int(os.getenv("RATE_LIMIT_MAX", "30"))
    RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "300"))


settings = Settings()