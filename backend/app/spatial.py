"""Spatial helpers: distances, street labelling, grid clustering.

MVP-grade stand-ins for Geohash/PostGIS (any upgrade stays in this module):
- `nearest_street` powers the admin `critical_zones` ranking.
- `cluster_sizes` annotates map points so clients can emphasise crowded
  cells without recomputing the grid themselves.
"""
import math

# Anchor coordinates for recognisable Tashkent streets (hackathon venue area).
STREET_ANCHORS: list[tuple[str, float, float]] = [
    ("Amir Temur Avenue", 41.311081, 69.279562),
    ("Navoi Street", 41.319000, 69.240000),
    ("Mustakillik Avenue", 41.317000, 69.284000),
    ("Shota Rustaveli Street", 41.299000, 69.275000),
    ("Small Ring Road", 41.330000, 69.260000),
]

GRID_DEG = 0.0015  # ~150 m cells


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest_street(lat: float, lng: float) -> str:
    best, best_d = "Unknown Street", float("inf")
    for name, slat, slng in STREET_ANCHORS:
        d = haversine_m(lat, lng, slat, slng)
        if d < best_d:
            best, best_d = name, d
    # If far from every anchor, fall back to a geo cell label.
    if best_d > 4000:
        return f"Zone {round(lat, 3)}, {round(lng, 3)}"
    return best


def grid_key(lat: float, lng: float) -> tuple[float, float]:
    return (round(lat / GRID_DEG) * GRID_DEG, round(lng / GRID_DEG) * GRID_DEG)


def cluster_sizes(points: list[tuple[float, float]]) -> dict[tuple[float, float], int]:
    """Count points per grid cell, keyed by `grid_key`."""
    counts: dict[tuple[float, float], int] = {}
    for lat, lng in points:
        key = grid_key(lat, lng)
        counts[key] = counts.get(key, 0) + 1
    return counts
