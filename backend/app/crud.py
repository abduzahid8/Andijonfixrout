"""Database helpers shared by routers (keeps endpoints thin)."""
import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .models import Report, User
from .spatial import haversine_m


def apply_env_admin(user: User) -> bool:
    """Promote users listed in ADMIN_IDS. Returns True when changed."""
    if not user.is_admin and user.id in settings.admin_id_set:
        user.is_admin = True
        return True
    return False


def get_or_create_user(
    db: Session,
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
) -> User:
    user = db.get(User, telegram_id)
    if user is None:
        user = User(id=telegram_id, username=username, first_name=first_name or "Road")
        db.add(user)
        db.flush()
        apply_env_admin(user)
        return user
    if username and user.username != username:
        user.username = username
    if first_name and user.first_name != first_name:
        user.first_name = first_name
    apply_env_admin(user)
    return user


def award_points(user: User, points: int) -> None:
    if points > 0:
        user.points += points


def find_nearby_report(
    db: Session, lat: float, lng: float, radius_m: float
) -> Report | None:
    """Nearest active/in_review report within radius_m, else None.

    Cheap two-step check (degree bbox prefilter, then exact haversine)
    so re-reports of the same pit become confirmations, not duplicates.
    """
    lat_tol = radius_m / 111320.0
    lng_tol = radius_m / (111320.0 * max(0.2, math.cos(math.radians(lat))))
    candidates = (
        db.execute(
            select(Report)
            .where(
                Report.status.in_(["active", "in_review"]),
                Report.latitude.between(lat - lat_tol, lat + lat_tol),
                Report.longitude.between(lng - lng_tol, lng + lng_tol),
            )
            .limit(50)
        )
        .scalars()
        .all()
    )
    best: Report | None = None
    best_d = radius_m
    for row in candidates:
        dist = haversine_m(lat, lng, row.latitude, row.longitude)
        if dist <= best_d:
            best, best_d = row, dist
    return best
