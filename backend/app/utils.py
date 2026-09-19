"""Shared pure helpers (no FastAPI / DB imports)."""
from datetime import datetime


def isoformat_z(value: datetime | None) -> str | None:
    """ISO-8601 with trailing Z instead of +00:00 (None-safe)."""
    return value.isoformat().replace("+00:00", "Z") if value else None
