"""RoadPulse FastAPI entrypoint."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import BASE_DIR, settings
from .database import Base, SessionLocal, engine, ensure_migrations
from .routers import admin, map, reports, users
from .seed import seed_database

log = logging.getLogger("roadpulse")
logging.basicConfig(level=logging.INFO)


def startup_seed() -> int:
    """Seed an empty DB from mock data. Never lets seed errors stop boot."""
    db = SessionLocal()
    try:
        return seed_database(db)
    except Exception as exc:
        log.warning("Mock seeding skipped: %s", exc)
        db.rollback()
        return 0
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_migrations()
    Path(settings.MEDIA_DIR).mkdir(parents=True, exist_ok=True)
    seeded = startup_seed()
    log.info("RoadPulse ready. mock_seeded=%d db=%s", seeded, settings.DATABASE_URL)
    yield


app = FastAPI(title=settings.APP_NAME, version="1.0.0-MVP", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(reports.router, prefix=settings.API_PREFIX)
app.include_router(map.router, prefix=settings.API_PREFIX)
app.include_router(admin.router, prefix=settings.API_PREFIX)
app.include_router(users.router, prefix=settings.API_PREFIX)


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.APP_NAME}


# ---- static assets ----
app.mount("/media", StaticFiles(directory=str(BASE_DIR / "media")), name="media")

CLIENT_DIR = BASE_DIR / "client"
DASHBOARD_DIR = BASE_DIR / "dashboard"
if CLIENT_DIR.exists():
    app.mount("/client", StaticFiles(directory=str(CLIENT_DIR), html=True), name="client")
if DASHBOARD_DIR.exists():
    app.mount(
        "/dashboard", StaticFiles(directory=str(DASHBOARD_DIR), html=True), name="dashboard"
    )


@app.get("/", include_in_schema=False)
def root():
    index = CLIENT_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"service": settings.APP_NAME, "docs": "/docs"}
