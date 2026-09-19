"""API smoke tests — isolated in-memory DB, mock AI verdicts.

Run:  pytest
"""
import io

from app.database import Base, get_db
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=engine)


def _override_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_db
client = TestClient(app)


def _jpeg(color=(70, 70, 70)) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (320, 240), color).save(buf, "JPEG")
    return buf.getvalue()


def _upload(user_id: int, lat: float = 41.3111, lng: float = 69.2796):
    return client.post(
        "/api/v1/reports",
        files={"photo": ("road.jpg", _jpeg(), "image/jpeg")},
        data={
            "latitude": lat,
            "longitude": lng,
            "telegram_user_id": user_id,
            "first_name": "Tester",
        },
    )


def test_health():
    assert client.get("/health").json() == {"status": "ok", "service": "RoadPulse"}


def test_stats_shape():
    body = client.get("/api/v1/admin/stats").json()
    assert {"total_defects", "high_risk_potholes", "repaired_count",
            "critical_zones"} <= set(body)


def test_report_flow_awards_points_and_repairs():
    res = _upload(user_id=501)
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    assert data["verified"] is True and data["points_awarded"] == 10

    user = client.get("/api/v1/users/501").json()
    assert user["points"] == 10

    points = client.get("/api/v1/map/points").json()
    assert points["count"] >= 1
    assert points["points"][0]["cluster_size"] >= 1

    rid = data["report_id"]
    patched = client.patch(f"/api/v1/admin/reports/{rid}", json={"status": "repaired"})
    assert patched.json()["status"] == "repaired"
    assert client.get("/api/v1/admin/stats").json()["repaired_count"] >= 1


def test_invalid_coordinates_rejected():
    assert _upload(user_id=502, lat=999).status_code == 422


def test_unsupported_mime_rejected():
    res = client.post(
        "/api/v1/reports",
        files={"photo": ("note.txt", b"hello", "text/plain")},
        data={"latitude": 41.31, "longitude": 69.27, "telegram_user_id": 502},
    )
    assert res.status_code == 415


def test_user_report_history():
    res = _upload(user_id=504)
    assert res.status_code == 201
    rid = res.json()["data"]["report_id"]
    history = client.get("/api/v1/users/504/reports").json()["reports"]
    assert any(r["id"] == rid and r["points_earned"] == 10 for r in history)


def test_admin_promote_and_flag():
    _upload(user_id=505)
    assert client.get("/api/v1/users/505").json()["is_admin"] is False
    res = client.patch("/api/v1/admin/users/505", json={"is_admin": True})
    assert res.json() == {"id": 505, "is_admin": True}
    assert client.get("/api/v1/users/505").json()["is_admin"] is True


def test_finalize_report_service():
    from app.reports_service import finalize_report

    db = TestingSession()
    try:
        verdict = {
            "is_road": True,
            "has_defect": True,
            "defect_type": "pothole",
            "severity": "high",
            "confidence_score": 0.9,
            "description": "service test",
        }
        out = finalize_report(
            db,
            user_id=506,
            username=None,
            first_name="Svc",
            image_url="/media/uploads/x.jpg",
            latitude=41.3,
            longitude=69.27,
            verdict=verdict,
        )
        assert out["points"] == 10 and out["status"] == "active"
        assert out["report"].severity == "high"
        assert out["pit_category"] == "medium" and out["repair_priority"] == "urgent"
    finally:
        db.close()


def test_pit_grading_and_priority():
    from app.ai_service import repair_priority_for

    assert repair_priority_for("high", "severe") == "emergency"
    assert repair_priority_for("high", "small") == "urgent"
    assert repair_priority_for("medium", "medium") == "scheduled"
    assert repair_priority_for("low", "small") == "routine"
    assert repair_priority_for("low", "none") == "routine"

    res = _upload(user_id=507)
    assert res.status_code == 201
    data = res.json()["data"]
    assert data["pit_category"] == "medium"
    assert data["repair_priority"] == "scheduled"
    assert data["diameter_cm"] == 30.0 and data["depth_cm"] == 4.0
