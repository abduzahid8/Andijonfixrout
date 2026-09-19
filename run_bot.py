"""Start the RoadPulse Telegram bot (long polling).

Usage:
    python run_bot.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from app.bot import main  # noqa: E402

if __name__ == "__main__":
    main()
