"""Database helpers shared by routers (keeps endpoints thin)."""
from sqlalchemy.orm import Session

from .config import settings
from .models import User


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
