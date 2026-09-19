"""Gemini 1.5 Flash vision wrapper with safe mock fallback.

Spec section 4: the image must be analysed BEFORE it is persisted.
Response is always a strict JSON object:
  {is_road, has_defect, defect_type, severity, pit_category,
   diameter_cm, depth_cm, confidence_score, description}
"""
import base64
import json
import logging
import re

from .config import settings

log = logging.getLogger("roadpulse.ai")

SYSTEM_PROMPT = """You are an advanced Computer Vision model specialized
in urban road surface quality analysis.

Examine the input image and return a strictly formatted JSON response.
Do not include markdown wraps or backticks.

Validation Rules:

1. "is_road": true if the image clearly depicts asphalt, concrete highway,
   or a car lane. false if it shows indoor environments, humans, vehicle
   interiors, trees, sky, or irrelevant objects.

2. "has_defect": true if potholes, significant cracks, missing asphalt
   sections, or dangerous sunken manholes are visible.

3. "defect_type": choose strictly from
   ["pothole", "crack", "manhole", "uneven_surface", "none"].

4. "severity":
   - "high": deep pothole capable of causing tire/suspension damage.
   - "medium": noticeable hole/crack requiring speed reduction.
   - "low": minor asphalt deformation or hairline cracks.
   - "none": if no defect is found.

5. "pit_category": how bad the pit itself is (potholes only;
   "none" for cracks/manholes without a pit, or when there is no defect):
   - "small": shallow cosmetic pit, roughly < 15 cm wide.
   - "medium": clear pit roughly 15-40 cm wide, a few cm deep.
   - "large": wide/deep pit roughly > 40 cm wide or > 7 cm deep.
   - "severe": crater-like destruction, merged pits, exposed road base.
   - "none": no pit visible.

6. "diameter_cm" / "depth_cm": best-effort visual estimates of the main
   pit in centimetres (numbers). null when there is no pit or the size
   cannot be judged.

7. "confidence_score": float value between 0.0 and 1.0.

Expected Schema:

{
  "is_road": boolean,
  "has_defect": boolean,
  "defect_type": string,
  "severity": string,
  "pit_category": string,
  "diameter_cm": number or null,
  "depth_cm": number or null,
  "confidence_score": float,
  "description": string
}

Return ONLY the JSON object."""

ALLOWED_DEFECTS = {"pothole", "crack", "manhole", "uneven_surface", "none"}
ALLOWED_SEVERITY = {"low", "medium", "high", "none"}
PIT_CATEGORIES = {"small", "medium", "large", "severe", "none"}


def _opt_cm(value) -> float | None:
    """Coerce a visual size estimate to cm, or None when unusable."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0 or number > 1000:
        return None
    return round(number, 1)


def repair_priority_for(severity: str, pit_category: str) -> str:
    """Deterministic repair urgency: routine < scheduled < urgent < emergency."""
    if severity == "high" and pit_category in ("large", "severe"):
        return "emergency"
    if severity == "high" or pit_category in ("large", "severe"):
        return "urgent"
    if severity == "medium" or pit_category == "medium":
        return "scheduled"
    return "routine"


def _mock_verdict() -> dict:
    """Deterministic positive verdict so the demo works without a key/quota."""
    return {
        "is_road": True,
        "has_defect": True,
        "defect_type": "pothole",
        "severity": "medium",
        "pit_category": "medium",
        "diameter_cm": 30.0,
        "depth_cm": 4.0,
        "confidence_score": 0.87,
        "description": "Mock AI verdict (no GEMINI_API_KEY configured): assumed pothole.",
    }


def normalise_verdict(raw: dict) -> dict:
    """Clamp / coerce a raw model dict into the expected schema."""
    verdict = {
        "is_road": bool(raw.get("is_road", False)),
        "has_defect": bool(raw.get("has_defect", False)),
        "defect_type": str(raw.get("defect_type", "none") or "none").lower(),
        "severity": str(raw.get("severity", "none") or "none").lower(),
        "pit_category": str(raw.get("pit_category", "none") or "none").lower(),
        "diameter_cm": _opt_cm(raw.get("diameter_cm")),
        "depth_cm": _opt_cm(raw.get("depth_cm")),
        "confidence_score": float(raw.get("confidence_score", 0.0) or 0.0),
        "description": str(raw.get("description", "") or "")[:500],
    }
    if verdict["defect_type"] not in ALLOWED_DEFECTS:
        verdict["defect_type"] = "other" if verdict["has_defect"] else "none"
    if verdict["severity"] not in ALLOWED_SEVERITY:
        verdict["severity"] = "medium" if verdict["has_defect"] else "none"
    if verdict["defect_type"] != "pothole" or not verdict["has_defect"]:
        verdict["pit_category"] = "none"
        verdict["diameter_cm"] = None
        verdict["depth_cm"] = None
    elif verdict["pit_category"] not in PIT_CATEGORIES - {"none"}:
        verdict["pit_category"] = "medium"
    verdict["confidence_score"] = min(1.0, max(0.0, verdict["confidence_score"]))
    return verdict


def to_storage_defect(defect_type: str, has_defect: bool) -> str:
    """Map AI vocabulary to DB enum: pothole | crack | manhole | other."""
    if not has_defect or defect_type == "none":
        return "other"
    if defect_type in ("pothole", "crack", "manhole"):
        return defect_type
    return "other"  # uneven_surface -> other


def to_storage_severity(severity: str, has_defect: bool) -> str:
    if not has_defect or severity == "none":
        return "low"
    return severity if severity in ("low", "medium", "high") else "medium"


def _extract_json(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?|```", "", text).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object in model output: {text[:200]!r}")
    return json.loads(cleaned[start : end + 1])


async def analyze_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    """Analyse one image. Falls back to mock verdict when appropriate."""
    if settings.MOCK_AI or not settings.GEMINI_API_KEY:
        return _mock_verdict()

    try:
        import google.generativeai as genai  # lazy import: optional dep at runtime

        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(
            settings.GEMINI_MODEL,
            generation_config={"response_mime_type": "application/json"},
            system_instruction=SYSTEM_PROMPT,
        )
        b64 = base64.b64encode(image_bytes).decode("ascii")
        resp = await model.generate_content_async(
            [
                {"text": "Analyse this road photo and return ONLY the JSON verdict."},
                {"inline_data": {"mime_type": mime_type, "data": b64}},
            ]
        )
        verdict = normalise_verdict(_extract_json(resp.text))
        return verdict
    except Exception as exc:  # never hard-fail an upload on AI outage
        log.warning("Gemini call failed, using mock verdict: %s", exc)
        fallback = _mock_verdict()
        fallback["description"] = f"AI fallback after error: {exc}"
        return fallback
