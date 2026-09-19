"""Upload persistence: validated bytes -> /media/uploads/<uuid>.<ext>."""
import math
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


def ensure_demo_photo(filename: str = "mock.jpg", width: int = 640, height: int = 480) -> str:
    """Generate a synthetic asphalt/pothole photo for demo seed rows.

    Offline-safe and deterministic; only generates when the file is absent.
    Returns the public URL path.
    """
    import random

    from PIL import Image, ImageDraw  # lazy: keeps import cost off hot paths

    media_dir = Path(settings.MEDIA_DIR)
    media_dir.mkdir(parents=True, exist_ok=True)
    dest = media_dir / filename
    if dest.exists():
        return f"/media/uploads/{filename}"

    rng = random.Random(42)
    img = Image.new("RGB", (width, height), (58, 58, 60))
    pixels = img.load()
    for y in range(height):
        for x in range(width):
            noise = rng.randint(-14, 14)
            pixels[x, y] = (58 + noise, 58 + noise, 60 + noise)
    draw = ImageDraw.Draw(img)
    cx, cy, rx, ry = width // 2, int(height * 0.58), 150, 95
    draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=(18, 18, 20))
    draw.ellipse(
        [cx - rx + 16, cy - ry + 12, cx + rx - 16, cy + ry - 12], fill=(30, 30, 34)
    )
    for _ in range(7):  # cracks radiating from the pit
        angle = rng.uniform(0, 6.283)
        x0 = cx + int(rx * 0.9 * math.cos(angle))
        y0 = cy + int(ry * 0.9 * math.sin(angle))
        x1 = cx + int(rx * 1.9 * math.cos(angle))
        y1 = cy + int(ry * 1.9 * math.sin(angle))
        draw.line([x0, y0, x1, y1], fill=(20, 20, 22), width=3)
    img.save(dest, "JPEG", quality=82)
    return f"/media/uploads/{filename}"
