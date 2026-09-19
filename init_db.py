"""Initialise the database and populate it with mock_data.json.

Usage:
    python init_db.py [--reset]

--reset drops all tables first. Without flags the script is idempotent:
it only seeds when the reports table is empty.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))

from app.database import Base, SessionLocal, engine, ensure_migrations  # noqa: E402
from app.models import User  # noqa: E402
from app.seed import seed_database  # noqa: E402


def make_admin(telegram_id: int) -> None:
    db = SessionLocal()
    try:
        user = db.get(User, telegram_id)
        if user is None:
            user = User(id=telegram_id, first_name="Admin")
            db.add(user)
        user.is_admin = True
        db.commit()
        print(f"User {telegram_id} is now admin (points={user.points}).")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Init RoadPulse DB + seed mock data.")
    parser.add_argument("--reset", action="store_true", help="Drop all tables before seeding.")
    parser.add_argument("--make-admin", type=int, default=None, metavar="TELEGRAM_ID",
                        help="Grant admin rights to a Telegram user ID and exit.")
    args = parser.parse_args()

    if args.reset:
        print("Dropping all tables...")
        Base.metadata.drop_all(bind=engine)

    Base.metadata.create_all(bind=engine)
    ensure_migrations()
    print("Tables ready.")

    if args.make_admin is not None:
        make_admin(args.make_admin)
        return

    db = SessionLocal()
    try:
        added = seed_database(db, reset=args.reset)
        if added:
            print(f"Seeded {added} mock reports (Amir Temur cluster included).")
        else:
            print("DB already seeded — skipping.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
