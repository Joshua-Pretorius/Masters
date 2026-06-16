#!/usr/bin/env python3
from __future__ import annotations

import csv
import itertools
import json
import math
import re
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape


UTC = timezone.utc
EARTH_RADIUS_KM = 6371.0088
CATALOG_BASE = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import slc_match_aoi as aoi

OUT_DIR = ROOT_DIR / "meria_global_s1_slc"
CACHE_PATH = OUT_DIR / "copernicus_s1_slc_cache.json"
DOCX_PATH = OUT_DIR / "MERIA_global_plastic_nearest_S1_SLC_before_after.docx"
CSV_PATH = OUT_DIR / "MERIA_global_plastic_nearest_S1_SLC_before_after.csv"
POINTS_CSV_PATH = OUT_DIR / "MERIA_global_plastic_points.csv"
PLANET_LOOKUP_PATH = ROOT_DIR / "meria_planet_acquisitions.json"
GHANA_POINTS_PATH = ROOT_DIR.parent / "Ghana_Drift" / "ghana_drift_points.shp"
GHANA_OGRINFO_PATH = Path(r"C:\Program Files\PostgreSQL\17\bin\ogrinfo.exe")
AOI_BUFFER_KM = 5.0
COVERAGE_THRESHOLD = 0.75


@dataclass(frozen=True)
class PointRecord:
    pt_id: str
    lat: float
    lon: float


@dataclass(frozen=True)
class Observation:
    obs_id: str
    area: str
    region: str
    date: str
    center_lat: float
    center_lon: float
    location_label: str
    notes: str = ""
    explicit_points: tuple[str, ...] = ()
    point_records: tuple[PointRecord, ...] = ()
    point_source: str = ""
    match_strategy: str = "coverage"
    planet_acquired_start: str | None = None
    planet_acquired_end: str | None = None
    aoi_buffer_km: float = AOI_BUFFER_KM
    coverage_threshold: float = COVERAGE_THRESHOLD


BASE_OBSERVATIONS = [
    Observation(
        obs_id="cabcd011-9d82-4124-9f9c-120bdc406cf3",
        area="Palma de Mallorca",
        region="Spain",
        date="2018-10-12",
        center_lat=39.603,
        center_lon=3.468,
        location_label="39.603N 3.468E",
        notes="Patches visible along the whole Palma de Mallorca coast from 2018-10-11 onwards.",
        explicit_points=(
            "39.66174 N 3.46868 E",
            "39.57672 N 3.42316 E",
            "39.63309 N 3.54552 E",
            "39.62612 N 3.37886 E",
        ),
    ),
    Observation(
        obs_id="05e7c3bc-2eac-4c4b-ba8a-6bf8aa4c0789",
        area="Palma de Mallorca",
        region="Spain",
        date="2018-10-12",
        center_lat=39.607,
        center_lon=3.469,
        location_label="39.607N 3.469E",
        notes="",
    ),
    Observation(
        obs_id="9e17ce98-9eeb-40f6-989e-894dc2be72ea",
        area="Bay Islands of Honduras",
        region="Honduras",
        date="2017-10-12",
        center_lat=16.017,
        center_lon=-86.692,
        location_label="16.017N 86.692W",
        notes=(
            "Same debris visible again in the following year. Additional Planet debris examples were noted "
            "during 2018-10-10 to 2018-10-13 near 16.17511 N 86.64093 W; 16.26083 N 86.66296 W; "
            "16.16267 N 86.39596 W; 16.08530 N 86.87297 W."
        ),
    ),
    Observation(
        obs_id="33a32832-fc41-4fdd-8c91-a41844fc1709",
        area="Bay Islands of Honduras",
        region="Honduras",
        date="2017-10-17",
        center_lat=16.025,
        center_lon=-86.392,
        location_label="16.025N 86.392W",
        notes=(
            "Found something at 15.95362 N 86.77741 W in a 2017-10-15 Planet image, and also at "
            "16 deg 20 min 13 sec N 88 deg 26 min 19 sec W. Both were difficult to see in the SAR image."
        ),
    ),
]


def load_ogrinfo_features(path: Path, layer_name: str) -> list[dict[str, Any]]:
    completed = subprocess.run(
        [str(GHANA_OGRINFO_PATH), "-json", "-features", str(path), layer_name],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    return payload["layers"][0]["features"]


def parse_obs_date(value: str) -> str:
    return value.replace("/", "-")


def format_location_label(lat: float, lon: float) -> str:
    lat_hemi = "N" if lat >= 0 else "S"
    lon_hemi = "E" if lon >= 0 else "W"
    return f"{abs(lat):.3f}{lat_hemi} {abs(lon):.3f}{lon_hemi}"


def load_ghana_drift_observations() -> list[Observation]:
    features = load_ogrinfo_features(GHANA_POINTS_PATH, GHANA_POINTS_PATH.stem)
    grouped: dict[str, dict[str, Any]] = {}
    for feature in features:
        properties = feature["properties"]
        obs_id = str(properties["obs_id"])
        entry = grouped.setdefault(
            obs_id,
            {
                "date": parse_obs_date(str(properties["obs_date"])),
                "area": str(properties["area"]),
                "region": "Ghana",
                "notes": str(properties.get("note") or ""),
                "point_records": [],
            },
        )
        entry["point_records"].append(
            PointRecord(
                pt_id=str(properties["pt_id"]),
                lat=float(feature["geometry"]["coordinates"][1]),
                lon=float(feature["geometry"]["coordinates"][0]),
            )
        )

    observations: list[Observation] = []
    for obs_id, entry in sorted(grouped.items(), key=lambda item: (item[1]["date"], item[0])):
        point_records = tuple(sorted(entry["point_records"], key=lambda record: record.pt_id))
        center_lat = sum(point.lat for point in point_records) / len(point_records)
        center_lon = sum(point.lon for point in point_records) / len(point_records)
        observations.append(
            Observation(
                obs_id=obs_id,
                area=entry["area"],
                region=entry["region"],
                date=entry["date"],
                center_lat=center_lat,
                center_lon=center_lon,
                location_label=format_location_label(center_lat, center_lon),
                notes=entry["notes"],
                point_records=point_records,
                point_source="ghana_drift_points",
                match_strategy="contains_all_points",
                planet_acquired_start=f"{entry['date']}T10:00:00Z",
                planet_acquired_end=f"{entry['date']}T10:00:00Z",
                aoi_buffer_km=0.0,
                coverage_threshold=1.0,
            )
        )
    return observations


OBSERVATIONS = BASE_OBSERVATIONS + load_ghana_drift_observations()
OBSERVATIONS_BY_ID = {obs.obs_id: obs for obs in OBSERVATIONS}


def day_bounds(date_text: str) -> tuple[datetime, datetime]:
    start = datetime.strptime(date_text, "%Y-%m-%d").replace(tzinfo=UTC)
    return start, start + timedelta(days=1)


def load_planet_lookup() -> dict[str, dict[str, Any]]:
    payload = json.loads(PLANET_LOOKUP_PATH.read_text(encoding="utf-8"))
    return payload["global"]


def to_utc_z(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def parse_decimal_cardinal(text: str) -> tuple[float, float]:
    parts = re.findall(r"(\d+(?:\.\d+)?)\s*([NSWE])", text)
    if len(parts) != 2:
        raise ValueError(f"Could not parse coordinate: {text}")
    values = []
    for number, hemi in parts:
        value = float(number)
        if hemi in {"S", "W"}:
            value *= -1
        values.append(value)
    return values[0], values[1]


def format_decimal_cardinal(lat: float, lon: float, places: int = 5) -> str:
    lat_hemi = "N" if lat >= 0 else "S"
    lon_hemi = "E" if lon >= 0 else "W"
    return f"{abs(lat):.{places}f} {lat_hemi} {abs(lon):.{places}f} {lon_hemi}"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1_r, lon1_r, lat2_r, lon2_r = map(math.radians, (lat1, lon1, lat2, lon2))
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = math.sin(dlat / 2.0) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def move_km(lat: float, lon: float, bearing_deg: float, distance_km: float) -> tuple[float, float]:
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)
    bearing = math.radians(bearing_deg)
    angular_distance = distance_km / EARTH_RADIUS_KM

    lat2 = math.asin(
        math.sin(lat1) * math.cos(angular_distance)
        + math.cos(lat1) * math.sin(angular_distance) * math.cos(bearing)
    )
    lon2 = lon1 + math.atan2(
        math.sin(bearing) * math.sin(angular_distance) * math.cos(lat1),
        math.cos(angular_distance) - math.sin(lat1) * math.sin(lat2),
    )
    lon2 = (lon2 + math.pi) % (2.0 * math.pi) - math.pi
    return math.degrees(lat2), math.degrees(lon2)


def synthetic_points(obs: Observation, distance_km: float = 100.0) -> tuple[str, ...]:
    center = (obs.center_lat, obs.center_lon)
    north = move_km(obs.center_lat, obs.center_lon, 0.0, distance_km)
    south = move_km(obs.center_lat, obs.center_lon, 180.0, distance_km)
    east = move_km(obs.center_lat, obs.center_lon, 90.0, distance_km)
    west = move_km(obs.center_lat, obs.center_lon, 270.0, distance_km)
    return tuple(format_decimal_cardinal(lat, lon) for lat, lon in (center, north, south, east, west))


def point_records_for_observation(obs: Observation) -> tuple[PointRecord, ...]:
    if obs.point_records:
        return obs.point_records
    if obs.explicit_points:
        return tuple(
            PointRecord(pt_id=f"P{idx:02d}", lat=lat, lon=lon)
            for idx, (lat, lon) in enumerate((parse_decimal_cardinal(point) for point in obs.explicit_points), start=1)
        )
    return tuple(
        PointRecord(pt_id=f"P{idx:02d}", lat=lat, lon=lon)
        for idx, (lat, lon) in enumerate((parse_decimal_cardinal(point) for point in synthetic_points(obs)), start=1)
    )


def observation_points(obs: Observation) -> tuple[str, ...]:
    return tuple(format_decimal_cardinal(record.lat, record.lon) for record in point_records_for_observation(obs))


def bbox_for_observation(obs: Observation, pad_deg: float = 0.03) -> tuple[float, float, float, float]:
    coords = observation_points_latlon(obs)
    lats = [lat for lat, _ in coords]
    lons = [lon for _, lon in coords]
    return (
        min(lons) - pad_deg,
        min(lats) - pad_deg,
        max(lons) + pad_deg,
        max(lats) + pad_deg,
    )


def bbox_to_polygon(bounds: tuple[float, float, float, float]) -> str:
    left, bottom, right, top = bounds
    return (
        "POLYGON(("
        f"{left} {bottom},"
        f"{left} {top},"
        f"{right} {top},"
        f"{right} {bottom},"
        f"{left} {bottom}"
        "))"
    )


def build_odata_url(filter_expr: str, top: int = 100, order: str = "desc") -> str:
    params = {
        "$top": str(top),
        "$orderby": f"ContentDate/Start {order}",
        "$filter": filter_expr,
    }
    query = urlencode(params, quote_via=quote, safe="()',$;/:_-.=")
    return f"{CATALOG_BASE}?{query}"


def request_json(url: str, retries: int = 4) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            req = Request(url, headers={"User-Agent": "Codex MERIA Global S1 SLC Resolver"})
            with urlopen(req, timeout=90) as resp:
                return json.load(resp)
        except HTTPError as exc:
            last_error = exc
            if exc.code not in {429, 500, 502, 503, 504} or attempt == retries - 1:
                raise
        except URLError as exc:
            last_error = exc
            if attempt == retries - 1:
                raise
        time.sleep(1.5 * (attempt + 1))
    if last_error is not None:
        raise last_error
    raise RuntimeError("Catalog request failed.")


def load_cache() -> dict[str, Any]:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict[str, Any]) -> None:
    CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")


def s1_identity_key(name: str) -> str:
    match = re.match(r"^(.*)_[0-9A-F]{4}(?:_COG)?\.SAFE$", name)
    return match.group(1) if match else name


def observation_points_latlon(obs: Observation) -> list[tuple[float, float]]:
    return [(record.lat, record.lon) for record in point_records_for_observation(obs)]


def candidate_products(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for product in products:
        grouped.setdefault(s1_identity_key(product["Name"]), []).append(product)
    deduped = [
        sorted(items, key=lambda p: (1 if p["Name"].endswith("_COG.SAFE") else 0, p["Name"]))[0]
        for items in grouped.values()
    ]
    return sorted(deduped, key=lambda p: parse_utc(p["ContentDate"]["Start"]))


def cached_payload_is_usable(payload: dict[str, Any] | None) -> bool:
    if payload is None:
        return True
    required = {"candidate_count", "coverage_ratio", "rejection_reason"}
    return required.issubset(payload)


def select_candidate(products: list[dict[str, Any]], direction: str, points: list[tuple[float, float]]) -> dict[str, Any]:
    ordered = candidate_products(products)
    if direction == "before":
        ordered = list(reversed(ordered))
    for product in ordered:
        coverage = aoi.coverage_ratio_for_scene(points, product.get("GeoFootprint"), buffer_km=AOI_BUFFER_KM)
        if coverage >= COVERAGE_THRESHOLD:
            return {
                "name": product["Name"],
                "start": product["ContentDate"]["Start"],
                "end": product["ContentDate"].get("End"),
                "id": product.get("Id"),
                "coverage_ratio": f"{coverage:.3f}",
                "candidate_count": len(ordered),
                "rejection_reason": "-",
            }
    rejection_reason = "-" if not ordered else f"no candidate met {COVERAGE_THRESHOLD:.2f} coverage threshold"
    return {
        "name": None,
        "start": None,
        "end": None,
        "id": None,
        "coverage_ratio": "-",
        "candidate_count": len(ordered),
        "rejection_reason": rejection_reason,
    }


def cached_selection_list_is_usable(payload: Any) -> bool:
    if not isinstance(payload, list):
        return False
    required = {"candidate_count", "coverage_ratio", "rejection_reason", "selected_point_ids"}
    return all(required.issubset(item) for item in payload)


def point_in_ring(x: float, y: float, ring: list[list[float]]) -> bool:
    inside = False
    for idx in range(len(ring)):
        x1, y1 = ring[idx]
        x2, y2 = ring[(idx + 1) % len(ring)]
        intersects = ((y1 > y) != (y2 > y)) and (x < ((x2 - x1) * (y - y1) / ((y2 - y1) or 1e-12) + x1))
        if intersects:
            inside = not inside
    return inside


def polygons_for_geometry(geometry: dict[str, Any] | None) -> list[list[list[list[float]]]]:
    if not geometry:
        return []
    geom_type = geometry.get("type")
    if geom_type == "Polygon":
        return [geometry["coordinates"]]
    if geom_type == "MultiPolygon":
        return geometry["coordinates"]
    return []


def point_in_geometry(lat: float, lon: float, geometry: dict[str, Any] | None) -> bool:
    x = lon
    y = lat
    for polygon in polygons_for_geometry(geometry):
        outer = polygon[0]
        holes = polygon[1:]
        if point_in_ring(x, y, outer) and not any(point_in_ring(x, y, hole) for hole in holes):
            return True
    return False


def covered_point_ids(point_records: tuple[PointRecord, ...], geometry: dict[str, Any] | None) -> list[str]:
    return [record.pt_id for record in point_records if point_in_geometry(record.lat, record.lon, geometry)]


def product_payload_for_points(
    product: dict[str, Any],
    selected_point_ids: list[str],
    total_points: int,
    candidate_count: int,
) -> dict[str, Any]:
    return {
        "name": product["Name"],
        "start": product["ContentDate"]["Start"],
        "end": product["ContentDate"].get("End"),
        "id": product.get("Id"),
        "coverage_ratio": f"{(len(selected_point_ids) / total_points):.3f}" if total_points else "-",
        "candidate_count": candidate_count,
        "rejection_reason": "-",
        "selected_point_ids": selected_point_ids,
    }


def select_point_cover_products(
    products: list[dict[str, Any]],
    direction: str,
    point_records: tuple[PointRecord, ...],
) -> list[dict[str, Any]]:
    ordered = candidate_products(products)
    if direction == "before":
        ordered = list(reversed(ordered))
    total_points = len(point_records)
    coverage_rows: list[tuple[dict[str, Any], list[str]]] = []
    for product in ordered:
        selected_ids = covered_point_ids(point_records, product.get("GeoFootprint"))
        coverage_rows.append((product, selected_ids))
        if len(selected_ids) == total_points:
            return [product_payload_for_points(product, selected_ids, total_points, len(ordered))]

    for combo_size in range(2, min(4, len(coverage_rows)) + 1):
        for combo in itertools.combinations(coverage_rows, combo_size):
            union = set().union(*(set(selected_ids) for _, selected_ids in combo))
            if len(union) == total_points:
                return [
                    product_payload_for_points(product, selected_ids, total_points, len(ordered))
                    for product, selected_ids in combo
                ]
    return []


def planet_window(obs: Observation, planet_lookup: dict[str, dict[str, Any]]) -> tuple[datetime, datetime]:
    if obs.obs_id in planet_lookup:
        entry = planet_lookup[obs.obs_id]
        return parse_utc(entry["planet_acquired_start"]), parse_utc(entry["planet_acquired_end"])
    if obs.planet_acquired_start and obs.planet_acquired_end:
        return parse_utc(obs.planet_acquired_start), parse_utc(obs.planet_acquired_end)
    raise KeyError(f"No Planet acquisition lookup found for {obs.obs_id}")


def query_s1_slc(
    obs: Observation,
    direction: str,
    cache: dict[str, Any],
    planet_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    planet_start, planet_end = planet_window(obs, planet_lookup)
    if direction == "before":
        window_start = planet_start - timedelta(days=30)
        window_end = planet_start
        order = "desc"
    elif direction == "after":
        window_start = planet_end
        window_end = planet_end + timedelta(days=30)
        order = "asc"
    else:
        raise ValueError(direction)

    key = f"{obs.obs_id}:{direction}:{to_utc_z(window_start)}:{to_utc_z(window_end)}"
    if key in cache and cached_payload_is_usable(cache[key]):
        return cache[key]

    polygon = bbox_to_polygon(bbox_for_observation(obs))
    flt = (
        "Collection/Name eq 'SENTINEL-1' and "
        f"OData.CSC.Intersects(area=geography'SRID=4326;{polygon}') and "
        f"ContentDate/Start gt {to_utc_z(window_start)} and "
        f"ContentDate/Start lt {to_utc_z(window_end)} and "
        "contains(Name,'_SLC_')"
    )
    url = build_odata_url(flt, top=100, order=order)
    products = request_json(url).get("value", [])
    payload = select_candidate(products, direction, observation_points_latlon(obs))
    cache[key] = payload
    save_cache(cache)
    return payload


def query_s1_slc_containing_points(
    obs: Observation,
    direction: str,
    cache: dict[str, Any],
    planet_lookup: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    planet_start, planet_end = planet_window(obs, planet_lookup)
    if direction == "before":
        window_start = planet_start - timedelta(days=30)
        window_end = planet_start
        order = "desc"
    elif direction == "after":
        window_start = planet_end
        window_end = planet_end + timedelta(days=30)
        order = "asc"
    else:
        raise ValueError(direction)

    key = f"{obs.obs_id}:{direction}:contains_all_points:{to_utc_z(window_start)}:{to_utc_z(window_end)}"
    if key in cache and cached_selection_list_is_usable(cache[key]):
        return cache[key]

    polygon = bbox_to_polygon(bbox_for_observation(obs, pad_deg=0.0))
    filter_expr = (
        "Collection/Name eq 'SENTINEL-1' and "
        f"OData.CSC.Intersects(area=geography'SRID=4326;{polygon}') and "
        f"ContentDate/Start gt {to_utc_z(window_start)} and "
        f"ContentDate/Start lt {to_utc_z(window_end)} and "
        "contains(Name,'_SLC_')"
    )
    url = build_odata_url(filter_expr, top=100, order=order)
    products = request_json(url).get("value", [])
    payload = select_point_cover_products(products, direction, point_records_for_observation(obs))
    cache[key] = payload
    save_cache(cache)
    return payload


def format_dt(value: str | None) -> str:
    if not value:
        return "-"
    return parse_utc(value).strftime("%Y-%m-%d %H:%M:%S UTC")


def format_planet_acquired(obs: Observation, planet_lookup: dict[str, dict[str, Any]]) -> str:
    planet_start, planet_end = planet_window(obs, planet_lookup)
    start_text = planet_start.strftime("%Y-%m-%d %H:%M:%S UTC")
    end_text = planet_end.strftime("%Y-%m-%d %H:%M:%S UTC")
    return start_text if planet_start == planet_end else f"{start_text} to {end_text}"


def delta_from_planet_window(
    obs: Observation,
    product: dict[str, Any] | None,
    planet_lookup: dict[str, dict[str, Any]],
) -> str:
    if not product or not product.get("start"):
        return "-"
    planet_start, planet_end = planet_window(obs, planet_lookup)
    product_start = parse_utc(product["start"])
    lower_h = (product_start - planet_end).total_seconds() / 3600.0
    upper_h = (product_start - planet_start).total_seconds() / 3600.0
    if math.isclose(lower_h, upper_h, rel_tol=0.0, abs_tol=1e-9):
        return f"{lower_h:+.2f}"
    return f"{lower_h:+.2f} to {upper_h:+.2f}"


def point_coordinates(obs: Observation) -> str:
    return "; ".join(observation_points(obs))


def product_value(product: dict[str, Any] | None, key: str, default: str = "-") -> str:
    if not product:
        return default
    value = product.get(key)
    if value in {None, ""}:
        return default
    return str(value)


def point_source_for_observation(obs: Observation) -> str:
    if obs.point_source:
        return obs.point_source
    if obs.explicit_points:
        return "explicit"
    return "synthetic_center_plus_100km_cardinals"


def subset_payload_for_observation(product: dict[str, Any], point_count: int) -> dict[str, Any]:
    payload = dict(product)
    payload["coverage_ratio"] = f"{1.0 if point_count else 0.0:.3f}"
    return payload


def split_observation_by_scene_cover(
    obs: Observation,
    before_matches: list[dict[str, Any]],
    after_matches: list[dict[str, Any]],
) -> list[tuple[Observation, dict[str, Any] | None, dict[str, Any] | None]]:
    if len(before_matches) <= 1 and len(after_matches) <= 1:
        return [(obs, before_matches[0] if before_matches else None, after_matches[0] if after_matches else None)]

    points = point_records_for_observation(obs)
    before_lookup = {
        payload["name"]: set(payload.get("selected_point_ids") or [])
        for payload in before_matches
        if payload.get("name")
    }
    after_lookup = {
        payload["name"]: set(payload.get("selected_point_ids") or [])
        for payload in after_matches
        if payload.get("name")
    }
    clusters: dict[tuple[str, str], list[PointRecord]] = {}
    before_payloads = {payload["name"]: payload for payload in before_matches if payload.get("name")}
    after_payloads = {payload["name"]: payload for payload in after_matches if payload.get("name")}
    for point in points:
        before_name = next((name for name, selected in before_lookup.items() if point.pt_id in selected), None)
        after_name = next((name for name, selected in after_lookup.items() if point.pt_id in selected), None)
        if before_name is None and before_matches:
            before_name = before_matches[0].get("name")
        if after_name is None and after_matches:
            after_name = after_matches[0].get("name")
        if before_name is None or after_name is None:
            continue
        clusters.setdefault((before_name, after_name), []).append(point)

    parts: list[tuple[Observation, dict[str, Any] | None, dict[str, Any] | None]] = []
    ordered_clusters = sorted(clusters.items(), key=lambda item: points.index(item[1][0]))
    for idx, ((before_name, after_name), cluster_points) in enumerate(ordered_clusters):
        point_ids = ", ".join(point.pt_id for point in cluster_points)
        child_obs = Observation(
            obs_id=f"{obs.obs_id}_{chr(65 + idx)}",
            area=obs.area,
            region=obs.region,
            date=obs.date,
            center_lat=sum(point.lat for point in cluster_points) / len(cluster_points),
            center_lon=sum(point.lon for point in cluster_points) / len(cluster_points),
            location_label=obs.location_label,
            notes=(
                f"{obs.notes} Split from {obs.obs_id} because no single Sentinel-1 scene covered every point. "
                f"This subset uses {point_ids}."
            ).strip(),
            point_records=tuple(cluster_points),
            point_source=f"{point_source_for_observation(obs)}_split",
            match_strategy=obs.match_strategy,
            planet_acquired_start=obs.planet_acquired_start,
            planet_acquired_end=obs.planet_acquired_end,
            aoi_buffer_km=obs.aoi_buffer_km,
            coverage_threshold=obs.coverage_threshold,
        )
        before_payload = subset_payload_for_observation(before_payloads[before_name], len(cluster_points))
        after_payload = subset_payload_for_observation(after_payloads[after_name], len(cluster_points))
        parts.append((child_obs, before_payload, after_payload))
    return parts or [(obs, before_matches[0] if before_matches else None, after_matches[0] if after_matches else None)]


def resolved_observation_rows(
    obs: Observation,
    cache: dict[str, Any],
    planet_lookup: dict[str, dict[str, Any]],
) -> list[tuple[Observation, dict[str, Any] | None, dict[str, Any] | None]]:
    if obs.match_strategy == "contains_all_points":
        before_matches = query_s1_slc_containing_points(obs, "before", cache, planet_lookup)
        after_matches = query_s1_slc_containing_points(obs, "after", cache, planet_lookup)
        return split_observation_by_scene_cover(obs, before_matches, after_matches)
    before = query_s1_slc(obs, "before", cache, planet_lookup)
    after = query_s1_slc(obs, "after", cache, planet_lookup)
    return [(obs, before, after)]


def write_points_csv(observations: list[Observation]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with POINTS_CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["obs_id", "obs_date", "area", "region", "pt_id", "lat", "lon", "dms", "notes", "point_source"],
        )
        writer.writeheader()
        for obs in observations:
            for point in point_records_for_observation(obs):
                writer.writerow(
                    {
                        "obs_id": obs.obs_id,
                        "obs_date": obs.date,
                        "area": obs.area,
                        "region": obs.region,
                        "pt_id": f"{obs.obs_id}_{point.pt_id}",
                        "lat": point.lat,
                        "lon": point.lon,
                        "dms": format_decimal_cardinal(point.lat, point.lon),
                        "notes": obs.notes,
                        "point_source": point_source_for_observation(obs),
                    }
                )


def xml_space_attr(text: str) -> str:
    return ' xml:space="preserve"' if text[:1].isspace() or text[-1:].isspace() else ""


def run(text: str, *, bold: bool = False, size: int = 18) -> str:
    props = ["<w:rPr>"]
    if bold:
        props.append("<w:b/>")
    props.append(f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>')
    props.append("</w:rPr>")
    return f"<w:r>{''.join(props)}<w:t{xml_space_attr(text)}>{escape(text)}</w:t></w:r>"


def paragraph(text: str, *, bold: bool = False, size: int = 20) -> str:
    return "<w:p>" + run(text, bold=bold, size=size) + "</w:p>"


def cell(text: str, width: int, *, bold: bool = False, shade: str | None = None) -> str:
    shade_xml = f'<w:shd w:val="clear" w:color="auto" w:fill="{shade}"/>' if shade else ""
    return (
        f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/><w:vAlign w:val="top"/>{shade_xml}</w:tcPr>'
        f"{paragraph(text or '-', bold=bold, size=16)}</w:tc>"
    )


def table(rows: list[list[str]]) -> str:
    widths = [780, 1100, 820, 1450, 520, 2000, 1700, 900, 1700, 900, 850, 850, 850, 850, 2000]
    grid = "<w:tblGrid>" + "".join(f'<w:gridCol w:w="{w}"/>' for w in widths) + "</w:tblGrid>"
    props = """
<w:tblPr>
  <w:tblW w:w="0" w:type="auto"/>
  <w:tblLayout w:type="fixed"/>
  <w:tblBorders>
    <w:top w:val="single" w:sz="6" w:space="0" w:color="808080"/>
    <w:left w:val="single" w:sz="6" w:space="0" w:color="808080"/>
    <w:bottom w:val="single" w:sz="6" w:space="0" w:color="808080"/>
    <w:right w:val="single" w:sz="6" w:space="0" w:color="808080"/>
    <w:insideH w:val="single" w:sz="4" w:space="0" w:color="A6A6A6"/>
    <w:insideV w:val="single" w:sz="4" w:space="0" w:color="A6A6A6"/>
  </w:tblBorders>
</w:tblPr>
""".strip()
    out_rows = []
    for ridx, row in enumerate(rows):
        out_rows.append(
            "<w:tr>"
            + "".join(cell(value, widths[cidx], bold=ridx == 0, shade="DCE6F1" if ridx == 0 else None) for cidx, value in enumerate(row))
            + "</w:tr>"
        )
    return "<w:tbl>" + props + grid + "".join(out_rows) + "</w:tbl>"


def build_docx(rows: list[dict[str, str]]) -> None:
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    table_rows = [[
        "Obs ID",
        "Area",
        "Planet date",
        "Planet acquired",
        "Points",
        "Point coordinates",
        "S1 SLC before product",
        "Before cov",
        "Before acquired",
        "S1 SLC after product",
        "After cov",
        "After acquired",
        "Before h",
        "After h",
        "Observation notes",
    ]]
    for row in rows:
        table_rows.append([
            row["obs_id"],
            row["area"],
            row["date"],
            row["planet_acquired"],
            row["points"],
            row["point_coordinates"],
            row["before_name"],
            row["before_coverage_ratio"],
            row["before_start"],
            row["after_name"],
            row["after_coverage_ratio"],
            row["after_start"],
            row["before_delta_h"],
            row["after_delta_h"],
            row["notes"],
        ])

    body = [
        paragraph("MERIA International Plastic Observations: Nearest Sentinel-1 SLC Acquisitions", bold=True, size=28),
        paragraph(f"Generated {generated}. Source: Data_Creation/MERIA_IDS_OF_INTERESTS.docx.", size=18),
        paragraph(
            "Planet acquisition times come from the local MERIA Planet download summary where available, with the unresolved Honduras observation filled from a direct Planet API lookup. Legacy global observations still use the buffered 5 km seed-point coverage rule, while the Ghana drift rows use the supplied point shapefile directly and require Sentinel-1 scenes to contain every listed point. Where no single Ghana scene contained the full point set, the observation was split into multiple rows so each row keeps one before scene, one after scene, and a point subset fully contained by both scenes.",
            size=18,
        ),
        table(table_rows),
        """
<w:sectPr>
  <w:pgSz w:w="16840" w:h="11900" w:orient="landscape"/>
  <w:pgMar w:top="500" w:right="500" w:bottom="500" w:left="500" w:header="500" w:footer="500" w:gutter="0"/>
</w:sectPr>
""".strip(),
    ]
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
        + "".join(body)
        + "</w:body></w:document>"
    )
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""
    with zipfile.ZipFile(DOCX_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document_xml)


def build_row(
    obs: Observation,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    planet_lookup: dict[str, dict[str, Any]],
) -> dict[str, str]:
    return {
        "obs_id": obs.obs_id,
        "area": obs.area,
        "date": obs.date,
        "planet_acquired": format_planet_acquired(obs, planet_lookup),
        "points": str(len(observation_points(obs))),
        "point_coordinates": point_coordinates(obs),
        "before_name": product_value(before, "name"),
        "before_start": format_dt(before["start"] if before else None),
        "before_delta_h": delta_from_planet_window(obs, before, planet_lookup),
        "before_coverage_ratio": product_value(before, "coverage_ratio"),
        "before_candidate_count": product_value(before, "candidate_count"),
        "before_rejection_reason": product_value(before, "rejection_reason"),
        "before_download_group_key": product_value(before, "name").removesuffix(".SAFE") if product_value(before, "name") != "-" else "-",
        "after_name": product_value(after, "name"),
        "after_start": format_dt(after["start"] if after else None),
        "after_delta_h": delta_from_planet_window(obs, after, planet_lookup),
        "after_coverage_ratio": product_value(after, "coverage_ratio"),
        "after_candidate_count": product_value(after, "candidate_count"),
        "after_rejection_reason": product_value(after, "rejection_reason"),
        "after_download_group_key": product_value(after, "name").removesuffix(".SAFE") if product_value(after, "name") != "-" else "-",
        "aoi_buffer_km": f"{obs.aoi_buffer_km:.1f}",
        "coverage_threshold": f"{obs.coverage_threshold:.2f}",
        "notes": obs.notes,
    }


def build_rows(
    cache: dict[str, Any],
    planet_lookup: dict[str, dict[str, Any]],
) -> tuple[list[Observation], list[dict[str, str]]]:
    resolved_observations: list[Observation] = []
    rows: list[dict[str, str]] = []
    for obs in OBSERVATIONS:
        for resolved_obs, before, after in resolved_observation_rows(obs, cache, planet_lookup):
            resolved_observations.append(resolved_obs)
            rows.append(build_row(resolved_obs, before, after, planet_lookup))
    return resolved_observations, rows


def write_outputs(rows: list[dict[str, str]]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    build_docx(rows)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cache = load_cache()
    planet_lookup = load_planet_lookup()
    final_observations, rows = build_rows(cache, planet_lookup)
    write_points_csv(final_observations)
    write_outputs(rows)
    print(f"Wrote {CSV_PATH}")
    print(f"Wrote {DOCX_PATH}")
    print(f"Wrote {POINTS_CSV_PATH}")


if __name__ == "__main__":
    main()
