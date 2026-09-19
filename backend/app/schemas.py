"""Pydantic v2 response/request schemas."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DefectType = Literal["pothole", "crack", "manhole", "other"]
Severity = Literal["low", "medium", "high"]
ReportStatus = Literal["active", "in_review", "repaired"]


class ReportCreateResponse(BaseModel):
    report_id: str
    verified: bool
    severity: Severity
    defect_type: DefectType
    pit_category: str = "medium"
    repair_priority: str = "scheduled"
    diameter_cm: float | None = None
    depth_cm: float | None = None
    points_awarded: int
    status: ReportStatus
    message: str


class ReportEnvelope(BaseModel):
    status: Literal["success"] = "success"
    data: ReportCreateResponse


class RejectedEnvelope(BaseModel):
    status: Literal["rejected"] = "rejected"
    reason: str
    ai_verdict: dict


class MapPoint(BaseModel):
    id: str
    lat: float
    lng: float
    severity: str
    defect_type: str
    image_url: str
    status: str
    cluster_size: int = 1
    pit_category: str = "medium"
    repair_priority: str = "scheduled"
    diameter_cm: float | None = None
    depth_cm: float | None = None
    created_at: datetime


class MapPointsResponse(BaseModel):
    count: int
    points: list[MapPoint]


class CriticalZone(BaseModel):
    street_name: str
    defect_count: int


class AdminStatsResponse(BaseModel):
    total_defects: int
    high_risk_potholes: int
    repaired_count: int
    in_review_count: int = 0
    critical_zones: list[CriticalZone]


class AdminReportRow(MapPoint):
    pass


class UserOut(BaseModel):
    id: int
    username: str | None = None
    first_name: str
    points: int
    is_admin: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class StatusUpdate(BaseModel):
    status: ReportStatus = Field(description="Target status, e.g. repaired")


class AdminFlagUpdate(BaseModel):
    is_admin: bool = Field(description="Grant (true) or revoke (false) admin rights")
