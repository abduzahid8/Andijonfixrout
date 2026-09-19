"""SQLAlchemy models — mirrors spec section 2."""
import uuid
from datetime import UTC, datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Telegram user id
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str] = mapped_column(String(64), nullable=False, default="Road")
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)

    reports: Mapped[list["Report"]] = relationship("Report", back_populates="user")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    image_url: Mapped[str] = mapped_column(String(255), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    has_defect: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # pothole | crack | manhole | other (AI may return uneven_surface/none -> normalised)
    defect_type: Mapped[str] = mapped_column(String(32), nullable=False, default="pothole")
    # low | medium | high
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    # small | medium | large | severe | none ("none" for non-pit defects)
    pit_category: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    diameter_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    depth_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    # routine | scheduled | urgent | emergency
    repair_priority: Mapped[str] = mapped_column(
        String(16), nullable=False, default="scheduled"
    )
    # How many other users confirmed this same pit.
    confirmations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # active | in_review | repaired
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, index=True
    )

    user: Mapped["User"] = relationship("User", back_populates="reports")
