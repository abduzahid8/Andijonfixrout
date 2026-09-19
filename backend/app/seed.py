"""Shared seeding logic: load mock_data.json points into the database.

Single source of truth used both by `init_db.py` (CLI) and the FastAPI
startup lifespan, so the two can never drift apart.
"""
import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .ai_service import repair_priority_for
from .config import BASE_DIR
from .models import Report, User
from .storage import ensure_demo_photo

DEMO_USER_ID = 999_000_001
FALLBACK_IMAGE = "/media/uploads/mock.jpg"
# Pit grading for legacy mock rows that predate AI pit analysis.
SEVERITY_TO_PIT = {"high": "large", "medium": "medium", "low": "small"}


def parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(UTC)


def load_mock_points(path: Path | None = None) -> list[dict]:
    mock_path = path or (BASE_DIR / "mock_data.json")
    payload = json.loads(mock_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload.get("points", [])
    return payload


def seed_database(db: Session, *, reset: bool = False) -> int:
    """Insert mock points. Returns rows added (0 when already seeded)."""
    if reset:
        db.query(Report).delete()
        db.commit()
    elif db.scalar(select(func.count()).select_from(Report)):
        return 0

    points = load_mock_points()
    ensure_demo_photo("mock.jpg")  # demo rows reference this file
    demo = db.get(User, DEMO_USER_ID)
    if demo is None:
        demo = User(id=DEMO_USER_ID, username="demo_city", first_name="City")
        db.add(demo)
        db.flush()

    for p in points:
        severity = p.get("severity", "medium")
        pit_category = p.get("pit_category") or SEVERITY_TO_PIT.get(severity, "medium")
        db.add(
            Report(
                user_id=demo.id,
                image_url=p.get("image_url", FALLBACK_IMAGE),
                latitude=float(p["lat"]),
                longitude=float(p["lng"]),
                has_defect=True,
                defect_type=p.get("defect_type", "pothole"),
                severity=severity,
                pit_category=pit_category,
                diameter_cm=p.get("diameter_cm"),
                depth_cm=p.get("depth_cm"),
                repair_priority=repair_priority_for(severity, pit_category),
                confidence_score=float(p.get("confidence_score", 0.9)),
                status=p.get("status", "active"),
                created_at=parse_dt(p.get("created_at")),
            )
        )
    demo.points = sum(10 for p in points if p.get("status", "active") == "active")
    db.commit()
    return len(points)
