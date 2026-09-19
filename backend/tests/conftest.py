"""Make `backend/` importable so tests use `from app...` like the app itself."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
