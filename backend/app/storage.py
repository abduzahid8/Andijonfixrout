"""Upload persistence: validated bytes -> /media/uploads/<uuid>.<ext>."""
import uuid
from pathlib import Path

from .config import settings

EXT_BY_MIME = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def save_upload(data: bytes, mime: str) -> str:
    """Write bytes to the media dir. Returns the public URL path."""
    media_dir = Path(settings.MEDIA_DIR)
    media_dir.mkdir(parents=True, exist_ok=True)
    ext = EXT_BY_MIME.get(mime.lower(), ".jpg")
    name = f"{uuid.uuid4().hex}{ext}"
    (media_dir / name).write_bytes(data)
    return f"/media/uploads/{name}"
