"""POST /api/v1/reports — upload pipeline (spec §3.1 + §4)."""
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..ai_service import analyze_image
from ..auth import get_limiter, validate_telegram_init_data
from ..config import settings
from ..database import get_db
from ..reports_service import finalize_report
from ..storage import save_upload

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", status_code=201)
async def create_report(
    photo: UploadFile = File(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    telegram_user_id: int = Form(...),
    username: str | None = Form(None),
    first_name: str | None = Form(None),
    x_telegram_init_data: str | None = Header(None),
    db: Session = Depends(get_db),
):
    if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
        raise HTTPException(status_code=422, detail="Invalid coordinates.")
    if not validate_telegram_init_data(
        x_telegram_init_data or "", settings.TELEGRAM_BOT_TOKEN
    ):
        raise HTTPException(status_code=401, detail="Invalid Telegram signature.")

    mime = (photo.content_type or "").lower()
    if mime not in settings.allowed_mime_set:
        raise HTTPException(
            status_code=415, detail=f"Unsupported image type: {mime or 'unknown'}."
        )

    limiter = get_limiter(settings.RATE_LIMIT_REPORTS, settings.RATE_LIMIT_WINDOW_SEC)
    limiter.check(f"user:{telegram_user_id}")

    raw = await photo.read()
    if not raw:
        raise HTTPException(status_code=422, detail="Empty image file.")
    if len(raw) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image too large.")

    # ---- AI FIRST (before touching disk/db) ----
    verdict = await analyze_image(raw, mime or "image/jpeg")
    if not verdict["is_road"] or not verdict["has_defect"]:
        return JSONResponse(
            status_code=422,
            content={
                "status": "rejected",
                "reason": "The AI did not detect a road defect in the image.",
                "ai_verdict": {
                    "is_road": verdict["is_road"],
                    "has_defect": verdict["has_defect"],
                    "confidence_score": verdict["confidence_score"],
                },
            },
        )

    # ---- persist + score through the shared service (same as bot flow) ----
    image_url = save_upload(raw, mime)
    out = finalize_report(
        db,
        user_id=telegram_user_id,
        username=username,
        first_name=first_name,
        image_url=image_url,
        latitude=latitude,
        longitude=longitude,
        verdict=verdict,
    )
    report, verified, points = out["report"], out["verified"], out["points"]

    return {
        "status": "success",
        "data": {
            "report_id": report.id,
            "verified": verified,
            "severity": report.severity,
            "defect_type": report.defect_type,
            "pit_category": out["pit_category"],
            "repair_priority": out["repair_priority"],
            "diameter_cm": report.diameter_cm,
            "depth_cm": report.depth_cm,
            "points_awarded": points,
            "duplicate": out.get("duplicate", False),
            "duplicate_of": out.get("duplicate_of"),
            "message": (
                "Already on the map — thanks for confirming!"
                if out.get("duplicate")
                else (
                    "Pothole successfully recorded and added to the map."
                    if verified
                    else "Report saved for manual review (low AI confidence)."
                )
            ),
        },
    }
