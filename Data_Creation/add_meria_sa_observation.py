#!/usr/bin/env python3
"""Add one MERIA South Africa observation to the local S1 input CSVs.

This is intentionally a local preparation tool.  It queries Copernicus Data
Space for Sentinel-1 SLC candidates, but the generated CSVs are later copied
to the server and consumed by the Docker pipeline.
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent
OUT_DIR = ROOT_DIR / "meria_sa_plastic_s1_slc"
MATCH_CSV = OUT_DIR / "MERIA_SA_plastic_nearest_S1_SLC_before_after.csv"
POINTS_CSV = OUT_DIR / "MERIA_SA_plastic_points.csv"

# Import the established Copernicus query and coverage logic.
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
import build_meria_sa_s1_slc_matches as resolver  # noqa: E402


MATCH_FIELDS = [
    "obs_id",
    "area",
    "date",
    "planet_acquired",
    "points",
    "point_coordinates",
    "before_name",
    "before_start",
    "before_delta_h",
    "before_coverage_ratio",
    "before_candidate_count",
    "before_rejection_reason",
    "before_download_group_key",
    "after_name",
    "after_start",
    "after_delta_h",
    "after_coverage_ratio",
    "after_candidate_count",
    "after_rejection_reason",
    "after_download_group_key",
    "aoi_buffer_km",
    "coverage_threshold",
    "notes",
]
POINT_FIELDS = ["obs_id", "obs_date", "area", "pt_id", "lat", "lon", "dms", "notes"]


def parse_point(value: str) -> tuple[float, float]:
    try:
        lat_text, lon_text = value.split(",", 1)
        lat = float(lat_text.strip())
        lon = float(lon_text.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("points must use LAT,LON, for example -29.8258,31.2519") from exc
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise argparse.ArgumentTypeError(f"point is outside valid latitude/longitude bounds: {value}")
    return lat, lon


def parse_date(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from exc


def bbox_for_points(points: list[tuple[float, float]], pad_deg: float = 0.03) -> tuple[float, float, float, float]:
    lats = [lat for lat, _ in points]
    lons = [lon for _, lon in points]
    return min(lons) - pad_deg, min(lats) - pad_deg, max(lons) + pad_deg, max(lats) + pad_deg


def query_direction(
    points: list[tuple[float, float]],
    observation_day: datetime,
    direction: str,
    *,
    window_days: int,
    buffer_km: float,
    coverage_threshold: float,
) -> dict[str, Any]:
    # With only a date supplied, treat the observation as the full UTC day.
    if direction == "before":
        window_start = observation_day - timedelta(days=window_days)
        window_end = observation_day
        order = "desc"
    elif direction == "after":
        window_start = observation_day + timedelta(days=1)
        window_end = observation_day + timedelta(days=window_days + 1)
        order = "asc"
    else:
        raise ValueError(direction)

    polygon = resolver.bbox_to_polygon(bbox_for_points(points))
    filter_expr = (
        "Collection/Name eq 'SENTINEL-1' and "
        f"OData.CSC.Intersects(area=geography'SRID=4326;{polygon}') and "
        f"ContentDate/Start gt {resolver.to_utc_z(window_start)} and "
        f"ContentDate/Start lt {resolver.to_utc_z(window_end)} and "
        "contains(Name,'_SLC_')"
    )
    products = resolver.request_json(resolver.build_odata_url(filter_expr, top=100, order=order)).get("value", [])
    if coverage_threshold <= 0:
        result = select_best_partial(products, direction, points, buffer_km)
    else:
        result = resolver.select_candidate(
            products,
            direction,
            points,
            buffer_km=buffer_km,
            coverage_threshold=coverage_threshold,
        )
    result["candidate_count"] = result.get("candidate_count", len(products))
    result["window_start"] = window_start
    result["window_end"] = window_end
    result["buffer_km"] = buffer_km
    result["coverage_threshold"] = coverage_threshold
    return result


def select_best_partial(
    products: list[dict[str, Any]],
    direction: str,
    points: list[tuple[float, float]],
    buffer_km: float,
) -> dict[str, Any]:
    candidates: list[tuple[dict[str, Any], float]] = []
    for product in resolver.candidate_products(products):
        coverage = resolver.aoi.coverage_ratio_for_scene(points, product.get("GeoFootprint"), buffer_km=buffer_km)
        if coverage > 0:
            candidates.append((product, coverage))
    if direction == "before":
        candidates.sort(key=lambda item: (-item[1], item[0]["ContentDate"]["Start"]), reverse=False)
        # For equal coverage, prefer the latest acquisition before the date.
        if len(candidates) > 1:
            best_coverage = candidates[0][1]
            equal = [item for item in candidates if abs(item[1] - best_coverage) < 1e-9]
            candidates = [max(equal, key=lambda item: item[0]["ContentDate"]["Start"])] + [
                item for item in candidates if item not in equal
            ]
    else:
        candidates.sort(key=lambda item: (-item[1], item[0]["ContentDate"]["Start"]))
    if not candidates:
        return {"name": None, "start": None, "footprint": None, "coverage_ratio": "-", "candidate_count": 0, "rejection_reason": "no scene intersects AOI"}
    product, coverage = candidates[0]
    return {
        "name": product["Name"],
        "start": product["ContentDate"]["Start"],
        "footprint": product.get("GeoFootprint"),
        "end": product["ContentDate"].get("End"),
        "coverage_ratio": f"{coverage:.3f}",
        "candidate_count": len(candidates),
        "rejection_reason": "-" if coverage >= resolver.COVERAGE_THRESHOLD else "partial scene selected for union coverage",
    }


def format_start(value: str | None) -> str:
    if not value:
        return "-"
    return resolver.parse_utc(value).strftime("%Y-%m-%d %H:%M:%S UTC")


def delta_hours(value: str | None, anchor: datetime) -> str:
    if not value:
        return "-"
    delta = (resolver.parse_utc(value) - anchor).total_seconds() / 3600.0
    return f"{delta:+.2f}"


def granule_key(value: str | None) -> str:
    return value.removesuffix(".SAFE") if value else "-"


def geometry_polygons(geometry: dict[str, Any]) -> list[list[list[list[float]]]]:
    if geometry.get("type") == "Polygon":
        return [geometry["coordinates"]]
    if geometry.get("type") == "MultiPolygon":
        return geometry["coordinates"]
    return []


def union_coverage(points: list[tuple[float, float]], results: list[dict[str, Any]], buffer_km: float) -> float:
    footprints = [result.get("footprint") for result in results if result.get("footprint")]
    if not footprints:
        return 0.0
    polygons: list[list[list[list[float]]]] = []
    for footprint in footprints:
        polygons.extend(geometry_polygons(footprint))
    geometry: dict[str, Any]
    if len(polygons) == 1:
        geometry = {"type": "Polygon", "coordinates": polygons[0]}
    else:
        geometry = {"type": "MultiPolygon", "coordinates": polygons}
    return resolver.aoi.coverage_ratio_for_scene(points, geometry, buffer_km=buffer_km)


def build_match_row(
    *,
    obs_id: str,
    area: str,
    date_text: str,
    points: list[tuple[float, float]],
    before: dict[str, Any],
    after: dict[str, Any],
    notes: str,
    buffer_km: float,
    coverage_threshold: float,
) -> dict[str, str]:
    return {
        "obs_id": obs_id,
        "area": area,
        "date": date_text,
        "planet_acquired": f"{date_text} UTC day",
        "points": str(len(points)),
        "point_coordinates": "; ".join(f"{lat:.8f},{lon:.8f}" for lat, lon in points),
        "before_name": before.get("name") or "-",
        "before_start": format_start(before.get("start")),
        "before_delta_h": delta_hours(before.get("start"), before["window_end"]),
        "before_coverage_ratio": str(before.get("coverage_ratio") or "-"),
        "before_candidate_count": str(before.get("candidate_count", 0)),
        "before_rejection_reason": str(before.get("rejection_reason") or "-"),
        "before_download_group_key": granule_key(before.get("name")),
        "after_name": after.get("name") or "-",
        "after_start": format_start(after.get("start")),
        "after_delta_h": delta_hours(after.get("start"), after["window_start"]),
        "after_coverage_ratio": str(after.get("coverage_ratio") or "-"),
        "after_candidate_count": str(after.get("candidate_count", 0)),
        "after_rejection_reason": str(after.get("rejection_reason") or "-"),
        "after_download_group_key": granule_key(after.get("name")),
        "aoi_buffer_km": f"{buffer_km:.1f}",
        "coverage_threshold": f"{coverage_threshold:.2f}",
        "notes": notes,
    }


def load_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def update_csvs(
    *,
    match_row: dict[str, str],
    points: list[tuple[float, float]],
    area: str,
    notes: str,
    replace: bool,
    match_csv: Path,
    points_csv: Path,
) -> None:
    match_rows = load_rows(match_csv)
    point_rows = load_rows(points_csv)
    obs_id = match_row["obs_id"]
    existing = any(row.get("obs_id") == obs_id for row in match_rows)
    if existing and not replace:
        raise RuntimeError(f"{obs_id} already exists; use --replace to update it")

    match_rows = [row for row in match_rows if row.get("obs_id") != obs_id]
    point_rows = [row for row in point_rows if row.get("obs_id") != obs_id]
    match_rows.append(match_row)
    for idx, (lat, lon) in enumerate(points, start=1):
        point_rows.append(
            {
                "obs_id": obs_id,
                "obs_date": match_row["date"],
                "area": area,
                "pt_id": f"{obs_id}_P{idx:02d}",
                "lat": f"{lat:.12f}",
                "lon": f"{lon:.12f}",
                "dms": "",
                "notes": notes,
            }
        )
    write_rows(match_csv, MATCH_FIELDS, match_rows)
    write_rows(points_csv, POINT_FIELDS, point_rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Add one MERIA SA observation and resolve before/after Sentinel-1 SLC scenes.")
    parser.add_argument("--obs-id", "--name", dest="obs_id", required=True, help="Observation name, e.g. MERIA_SA_009")
    parser.add_argument("--date", required=True, type=parse_date, help="Observation date in YYYY-MM-DD format")
    parser.add_argument("--point", action="append", required=True, type=parse_point, help="Point as LAT,LON; repeat for multiple points")
    parser.add_argument("--area", default="", help="Optional area name")
    parser.add_argument("--notes", default="", help="Optional observation notes")
    parser.add_argument("--window-days", type=int, default=30)
    parser.add_argument("--buffer-km", type=float, default=5.0)
    parser.add_argument("--coverage-threshold", type=float, default=0.75)
    parser.add_argument(
        "--allow-partial-pair",
        action="store_true",
        help="Allow before/after scenes below the individual threshold when their union reaches it.",
    )
    parser.add_argument("--replace", action="store_true", help="Replace an existing observation with this ID")
    parser.add_argument("--match-csv", type=Path, default=MATCH_CSV)
    parser.add_argument("--points-csv", type=Path, default=POINTS_CSV)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.window_days <= 0:
        raise SystemExit("--window-days must be positive")
    if not 0 < args.coverage_threshold <= 1:
        raise SystemExit("--coverage-threshold must be between 0 and 1")

    before = query_direction(
        args.point,
        args.date,
        "before",
        window_days=args.window_days,
        buffer_km=args.buffer_km,
        coverage_threshold=0.0 if args.allow_partial_pair else args.coverage_threshold,
    )
    after = query_direction(
        args.point,
        args.date,
        "after",
        window_days=args.window_days,
        buffer_km=args.buffer_km,
        coverage_threshold=0.0 if args.allow_partial_pair else args.coverage_threshold,
    )
    if not before.get("name") or not after.get("name"):
        raise SystemExit(
            "No acceptable before/after pair found; CSVs were not changed. "
            f"before={before.get('name') or '-'} after={after.get('name') or '-'}"
        )
    pair_union = union_coverage(args.point, [before, after], args.buffer_km)
    if pair_union < args.coverage_threshold:
        raise SystemExit(
            "The selected pair does not cover the requested AOI: "
            f"union coverage={pair_union:.3f}, required={args.coverage_threshold:.3f}. CSVs were not changed."
        )

    row = build_match_row(
        obs_id=args.obs_id,
        area=args.area,
        date_text=args.date.strftime("%Y-%m-%d"),
        points=args.point,
        before=before,
        after=after,
        notes=(args.notes + (" " if args.notes else "") + f"pair_union_coverage={pair_union:.3f}"),
        buffer_km=args.buffer_km,
        coverage_threshold=args.coverage_threshold,
    )
    update_csvs(
        match_row=row,
        points=args.point,
        area=args.area,
        notes=args.notes,
        replace=args.replace,
        match_csv=args.match_csv,
        points_csv=args.points_csv,
    )
    print(f"Added {args.obs_id} to {args.match_csv}")
    print(f"Added {len(args.point)} points to {args.points_csv}")
    print(f"before: {row['before_name']} ({row['before_coverage_ratio']} coverage)")
    print(f"after:  {row['after_name']} ({row['after_coverage_ratio']} coverage)")
    print(f"pair union coverage: {pair_union:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
