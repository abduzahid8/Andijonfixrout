"""Admin endpoints: stats (spec §3.3), report list, repair action."""
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Report, User
from ..schemas import AdminFlagUpdate, StatusUpdate
from ..spatial import nearest_street
from ..utils import isoformat_z

router = APIRouter(prefix="/admin", tags=["admin"])

ACTIVE_STATUSES = ["active", "in_review"]


def _count(db: Session, *conditions) -> int:
    stmt = select(func.count()).select_from(Report)
    if conditions:
        stmt = stmt.where(*conditions)
    return db.scalar(stmt) or 0


@router.get("/stats")
def admin_stats(db: Session = Depends(get_db)):
    total = _count(db, Report.status.in_(ACTIVE_STATUSES))
    high = _count(db, Report.status == "active", Report.severity == "high")
    repaired = _count(db, Report.status == "repaired")
    in_review = _count(db, Report.status == "in_review")

    rows = db.execute(
        select(Report.latitude, Report.longitude).where(
            Report.status.in_(ACTIVE_STATUSES)
        )
    ).all()
    street_counter: Counter[str] = Counter()
    for lat, lng in rows:
        street_counter[nearest_street(float(lat), float(lng))] += 1
    critical = [
        {"street_name": name, "defect_count": n}
        for name, n in street_counter.most_common(5)
    ]

    return {
        "total_defects": total,
        "high_risk_potholes": high,
        "repaired_count": repaired,
        "in_review_count": in_review,
        "critical_zones": critical,
    }


@router.get("/reports")
def admin_reports(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
):
    stmt = select(Report).order_by(Report.created_at.desc()).offset(offset).limit(limit)
    if status:
        stmt = stmt.where(Report.status == status)
    rows = db.execute(stmt).scalars().all()
    return {
        "total": _count(db),
        "reports": [
            {
                "id": r.id,
                "lat": r.latitude,
                "lng": r.longitude,
                "severity": r.severity,
                "defect_type": r.defect_type,
                "image_url": r.image_url,
                "status": r.status,
                "pit_category": r.pit_category,
                "repair_priority": r.repair_priority,
                "diameter_cm": r.diameter_cm,
                "depth_cm": r.depth_cm,
                "confidence_score": r.confidence_score,
                "user_id": r.user_id,
                "created_at": isoformat_z(r.created_at),
            }
            for r in rows
        ],
    }


@router.patch("/reports/{report_id}")
def update_report_status(
    report_id: str, payload: StatusUpdate, db: Session = Depends(get_db)
):
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    if payload.status not in ("active", "in_review", "repaired"):
        raise HTTPException(status_code=422, detail="Invalid status.")
    report.status = payload.status
    db.commit()
    return {"id": report.id, "status": report.status}


@router.patch("/users/{telegram_id}")
def set_user_admin(
    telegram_id: int, payload: AdminFlagUpdate, db: Session = Depends(get_db)
):
    """Grant or revoke admin rights (used by CLI and future admin UI)."""
    user = db.get(User, telegram_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    user.is_admin = payload.is_admin
    db.commit()
    return {"id": user.id, "is_admin": user.is_admin}
