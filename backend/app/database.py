"""SQLAlchemy engine / session / Base."""
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from .config import settings

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

Base = declarative_base()


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _table_cols(conn, table: str) -> set[str]:
    rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def ensure_migrations() -> None:
    """Lightweight in-place migrations (no Alembic in MVP).

    Adds columns that older databases lack and backfills pit grading
    from severity. Safe to run on every boot (backfills are idempotent).
    """
    with engine.begin() as conn:
        if "is_admin" not in _table_cols(conn, "users"):
            conn.exec_driver_sql("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0")
        report_cols = _table_cols(conn, "reports")
        if "pit_category" not in report_cols:
            conn.exec_driver_sql(
                "ALTER TABLE reports ADD COLUMN pit_category VARCHAR(16) DEFAULT 'medium'"
            )
        if "diameter_cm" not in report_cols:
            conn.exec_driver_sql("ALTER TABLE reports ADD COLUMN diameter_cm FLOAT")
        if "depth_cm" not in report_cols:
            conn.exec_driver_sql("ALTER TABLE reports ADD COLUMN depth_cm FLOAT")
        if "repair_priority" not in report_cols:
            conn.exec_driver_sql(
                "ALTER TABLE reports ADD COLUMN repair_priority VARCHAR(16)"
                " DEFAULT 'scheduled'"
            )
        if "confirmations" not in report_cols:
            conn.exec_driver_sql(
                "ALTER TABLE reports ADD COLUMN confirmations INTEGER DEFAULT 0"
            )
        conn.exec_driver_sql(
            "UPDATE reports SET pit_category='large' "
            "WHERE severity='high' AND pit_category='medium'"
        )
        conn.exec_driver_sql(
            "UPDATE reports SET repair_priority='urgent' "
            "WHERE severity='high' AND repair_priority='scheduled'"
        )
        conn.exec_driver_sql(
            "UPDATE reports SET repair_priority='emergency' "
            "WHERE severity='high' AND pit_category IN ('large', 'severe')"
        )
