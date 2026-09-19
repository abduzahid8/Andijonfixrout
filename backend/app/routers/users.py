"""User profile, leaderboard, and per-user report history (Mini App data)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..crud import apply_env_admin
from ..database import get_db
from ..models import Report, User
from ..schemas import UserOut
from ..utils import isoformat_z

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/leaderboard")
def leaderboard(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    rows = (
        db.execute(select(User).order_by(User.points.desc(), User.created_at).limit(limit))
        .scalars()
        .all()
    )
    return {
        "leaders": [
            {
                "id": u.id,
                "first_name": u.first_name,
                "username": u.username,
                "points": u.points,
            }
            for u in rows
        ]
    }


@router.get("/{telegram_id}", response_model=UserOut)
def get_user(telegram_id: int, db: Session = Depends(get_db)):
    user = db.get(User, telegram_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if apply_env_admin(user):
        db.commit()
        db.refresh(user)
    return user


@router.get("/{telegram_id}/reports")
def get_user_reports(
    telegram_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    rows = (
        db.execute(
            select(Report)
            .where(Report.user_id == telegram_id)
            .order_by(Report.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return {
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
                "points_earned": settings.POINTS_PER_REPORT if r.status == "active" else 0,
                "created_at": isoformat_z(r.created_at),
            }
            for r in rows
        ]
    }
