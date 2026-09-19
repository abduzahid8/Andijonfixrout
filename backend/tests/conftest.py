"""Make `backend/` importable so tests use `from app...` like the app itself."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_media_dir(tmp_path, monkeypatch):
    """Keep test uploads out of the real media folder."""
    monkeypatch.setattr(settings, "MEDIA_DIR", str(tmp_path / "uploads"))
