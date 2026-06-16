from __future__ import annotations

import json
import math
from typing import Any


EARTH_RADIUS_M = 6371008.8
DEFAULT_SAMPLE_STEP_M = 500.0


def coverage_ratio_for_scene(
    points: list[tuple[float, float]] | tuple[tuple[float, float], ...],
    footprint: dict[str, Any] | str | None,
    *,
    buffer_km: float,
    sample_step_m: float = DEFAULT_SAMPLE_STEP_M,
) -> float:
    if not points or not footprint:
        return 0.0

    geometry = _normalize_geometry(footprint)
    if geometry is None:
        return 0.0

    lats = [lat for lat, _ in points]
    lons = [lon for _, lon in points]
    ref_lat = sum(lats) / len(lats)
    ref_lon = sum(lons) / len(lons)
    buffer_m = buffer_km * 1000.0
    circles = [_project(lat, lon, ref_lat, ref_lon) + (buffer_m,) for lat, lon in points]
    polygons = _project_geometry(geometry, ref_lat, ref_lon)
    step_m = max(250.0, min(sample_step_m, buffer_m / 4.0))

    minx = min(cx - radius for cx, cy, radius in circles)
    maxx = max(cx + radius for cx, cy, radius in circles)
    miny = min(cy - radius for cx, cy, radius in circles)
    maxy = max(cy + radius for cx, cy, radius in circles)

    total = 0
    covered = 0
    y = miny + (step_m / 2.0)
    while y <= maxy:
        x = minx + (step_m / 2.0)
        while x <= maxx:
            if _point_in_any_circle(x, y, circles):
                total += 1
                if _point_in_geometry(x, y, polygons):
                    covered += 1
            x += step_m
        y += step_m

    return covered / total if total else 0.0


def _normalize_geometry(footprint: dict[str, Any] | str | None) -> dict[str, Any] | None:
    if footprint is None:
        return None
    if isinstance(footprint, str):
        try:
            footprint = json.loads(footprint)
        except json.JSONDecodeError:
            return None
    geom_type = footprint.get("type")
    if geom_type not in {"Polygon", "MultiPolygon"}:
        return None
    return footprint


def _project(lat: float, lon: float, ref_lat: float, ref_lon: float) -> tuple[float, float]:
    x = math.radians(lon - ref_lon) * math.cos(math.radians(ref_lat)) * EARTH_RADIUS_M
    y = math.radians(lat - ref_lat) * EARTH_RADIUS_M
    return x, y


def _project_geometry(geometry: dict[str, Any], ref_lat: float, ref_lon: float) -> list[list[list[tuple[float, float]]]]:
    geom_type = geometry["type"]
    coordinates = geometry["coordinates"]
    polygons = coordinates if geom_type == "MultiPolygon" else [coordinates]
    out: list[list[list[tuple[float, float]]]] = []
    for polygon in polygons:
        out.append(
            [
                [_project(lat=lat, lon=lon, ref_lat=ref_lat, ref_lon=ref_lon) for lon, lat in ring]
                for ring in polygon
            ]
        )
    return out


def _point_in_any_circle(x: float, y: float, circles: list[tuple[float, float, float]]) -> bool:
    for cx, cy, radius in circles:
        if ((x - cx) ** 2) + ((y - cy) ** 2) <= radius**2:
            return True
    return False


def _point_in_geometry(x: float, y: float, polygons: list[list[list[tuple[float, float]]]]) -> bool:
    for polygon in polygons:
        if not polygon:
            continue
        if _point_in_ring(x, y, polygon[0]) and not any(_point_in_ring(x, y, hole) for hole in polygon[1:]):
            return True
    return False


def _point_in_ring(x: float, y: float, ring: list[tuple[float, float]]) -> bool:
    inside = False
    for idx in range(len(ring)):
        x1, y1 = ring[idx]
        x2, y2 = ring[(idx + 1) % len(ring)]
        intersects = ((y1 > y) != (y2 > y)) and (x < ((x2 - x1) * (y - y1) / ((y2 - y1) or 1e-12) + x1))
        if intersects:
            inside = not inside
    return inside
