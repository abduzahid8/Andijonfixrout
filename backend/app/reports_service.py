"""Shared report finalisation: verdict -> status / points / DB row.

Single source of truth used by both the REST upload endpoint and the
Telegram bot photo flow, so the two entry points can never drift apart.
"""
from sqlalchemy.orm import Session

from .ai_service import repair_priority_for, to_storage_defect, to_storage_severity
from .config import settings
from .crud import award_points, get_or_create_user
from .models import Report


def finalize_report(
    db: Session,
    *,
    user_id: int,
    username: str | None,
    first_name: str | None,
    image_url: str,
    latitude: float,
    longitude: float,
    verdict: dict,
) -> dict:
    """Persist a verified report. Returns report, user, verified, points, status."""
    confidence = float(verdict["confidence_score"])
    status = "in_review" if confidence < settings.CONFIDENCE_THRESHOLD else "active"
    verified = status == "active"
    points = settings.POINTS_PER_REPORT if verified else 0

    user = get_or_create_user(db, user_id, username, first_name)
    award_points(user, points)

    storage_defect = to_storage_defect(verdict.get("defect_type", "none"), True)
    if storage_defect == "pothole":
        pit_category = str(verdict.get("pit_category", "medium") or "medium").lower()
        if pit_category not in ("small", "medium", "large", "severe"):
            pit_category = "medium"
    else:
        pit_category = "none"
    severity = to_storage_severity(verdict.get("severity", "none"), True)
    repair_priority = repair_priority_for(severity, pit_category)

    report = Report(
        user_id=user.id,
        image_url=image_url,
        latitude=latitude,
        longitude=longitude,
        has_defect=True,
        defect_type=storage_defect,
        severity=severity,
        pit_category=pit_category,
        diameter_cm=verdict.get("diameter_cm"),
        depth_cm=verdict.get("depth_cm"),
        repair_priority=repair_priority,
        confidence_score=confidence,
        status=status,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return {
        "report": report,
        "user": user,
        "verified": verified,
        "points": points,
        "status": status,
        "pit_category": pit_category,
        "repair_priority": repair_priority,
    }
