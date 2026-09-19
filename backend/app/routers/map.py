"""GET /api/v1/map/points — BBOX-filtered active points (spec §3.2)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Report
from ..spatial import cluster_sizes, grid_key
from ..utils import isoformat_z

router = APIRouter(prefix="/map", tags=["map"])


@router.get("/points")
def map_points(
    min_lat: float | None = Query(None, ge=-90, le=90),
    max_lat: float | None = Query(None, ge=-90, le=90),
    min_lng: float | None = Query(None, ge=-180, le=180),
    max_lng: float | None = Query(None, ge=-180, le=180),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Report)
        .where(Report.status.in_(["active", "in_review"]))
        .order_by(Report.created_at.desc())
        .limit(2000)
    )
    if min_lat is not None:
        stmt = stmt.where(Report.latitude >= min_lat)
    if max_lat is not None:
        stmt = stmt.where(Report.latitude <= max_lat)
    if min_lng is not None:
        stmt = stmt.where(Report.longitude >= min_lng)
    if max_lng is not None:
        stmt = stmt.where(Report.longitude <= max_lng)

    rows = db.execute(stmt).scalars().all()
    sizes = cluster_sizes([(r.latitude, r.longitude) for r in rows])
    points = [
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
            "cluster_size": sizes.get(grid_key(r.latitude, r.longitude), 1),
            "created_at": isoformat_z(r.created_at),
        }
        for r in rows
    ]
    return {"count": len(points), "points": points}
