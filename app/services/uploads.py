import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.core.config import settings


def _validate_upload(upload: UploadFile, kind: str) -> None:
    """Validate size, extension and (for images) MIME type of an upload."""
    original = (upload.filename or "").strip()
    if not original:
        raise HTTPException(status_code=400, detail="Archivo vacío")

    ext = Path(original).suffix.lower()
    allowed_ext = (
        settings.ALLOWED_IMAGE_EXTENSIONS if kind == "image" else settings.ALLOWED_FILE_EXTENSIONS
    )
    if ext not in allowed_ext:
        raise HTTPException(status_code=400, detail=f"Extensión no permitida: {ext}")

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    upload.file.seek(0, 2)
    size = upload.file.tell()
    upload.file.seek(0)
    if size > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"Archivo demasiado grande (máx. {settings.MAX_UPLOAD_SIZE_MB}MB)",
        )

    if kind == "image":
        upload.file.seek(0)
        head = upload.file.read(512)
        upload.file.seek(0)
        mime = _sniff_mime(head) or ""
        if mime not in settings.ALLOWED_IMAGE_MIMES:
            raise HTTPException(status_code=400, detail="El archivo no es una imagen válida")


def _sniff_mime(head: bytes) -> str | None:
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if b"<svg" in head:
        return "image/svg+xml"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return None


def save_upload(upload: UploadFile, prefix: str, extra_id: int | str = "", kind: str = "file") -> str | None:
    """Store an uploaded file under settings.UPLOAD_DIR.

    Returns the absolute path string or None when no file/sentinel is present.
    Raises HTTPException(400) when the upload does not pass validation.
    """
    if not upload:
        return None

    upload.file.seek(0)
    original = (upload.filename or "").strip()
    if not original:
        return None

    _validate_upload(upload, kind)

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(original).suffix
    filename = f"{prefix}_{extra_id}_{uuid.uuid4().hex[:8]}{ext}" if extra_id else f"{prefix}_{uuid.uuid4().hex[:8]}{ext}"
    dest = upload_dir / filename
    upload.file.seek(0)
    dest.write_bytes(upload.file.read())
    return str(dest)


def save_uploads(uploads, prefix: str, extra_id: int | str = "", kind: str = "file") -> list:
    """Store a list of uploaded files and return the list of saved paths."""
    saved = []
    for upload in uploads or []:
        path = save_upload(upload, prefix, extra_id, kind=kind)
        if path:
            saved.append(path)
    return saved


def remove_upload(path: str | None) -> None:
    if not path:
        return
    try:
        p = Path(path)
        if p.is_file():
            p.unlink()
    except OSError:
        pass