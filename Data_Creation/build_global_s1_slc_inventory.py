#!/usr/bin/env python3
"""Build the global optical-reference to Sentinel-1 IW SLC processing list.

The source inventory combines MARIDA, NASA Marine Debris PlanetScope patches,
Ghana drift observations, the four Greek Sentinel-2 acquisitions, and the
Jamila/Ocean Scan floating-debris export.  Optical imagery is reference data:
where an exact acquisition time is unavailable (notably Jamila), the recorded
nominal observation timestamp is used and explicitly marked as nominal.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

import fiona
import numpy as np
import rasterio
import requests
import yaml
from requests.adapters import HTTPAdapter
from rasterio.features import shapes as raster_shapes
from urllib3.util.retry import Retry
from rasterio.warp import transform as transform_coordinates, transform_bounds
from shapely.geometry import GeometryCollection, box, mapping, shape
from shapely.ops import transform, unary_union


UTC = timezone.utc
EARTH_RADIUS_M = 6_371_008.8
REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = Path(__file__).resolve().parent / "global_s1_slc_inventory"
MARIDA_PATCHES_ROOT = REPO_ROOT / "MARIDA" / "MARIDA" / "patches"
GHANA_POINTS_PATH = REPO_ROOT / "Ghana_Drift" / "ghana_drift_points.shp"
JAMILA_OBSERVATIONS_PATH = (
    REPO_ROOT / "Jamila_Floating_Debris" / "ocean-scan-floating-debris-1e84cd1d-b132-4aa1-9e4e-675e83b42050.json"
)
CATALOG_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
BUFFER_KM = 30.0
SEARCH_HOURS = 72.0
SET_SPAN_HOURS = 12.0
COVERAGE_THRESHOLD = 0.999
MARIDA_MARINE_DEBRIS_CLASS = 1
MARIDA_CONFIDENCE = {1: "high", 2: "moderate", 3: "low"}


def observation_id(source_dataset: str, source_group_id: str) -> str:
    prefix = re.sub(r"[^a-z0-9]+", "_", source_dataset.lower()).strip("_")
    suffix = re.sub(r"[^A-Za-z0-9._-]+", "_", source_group_id).strip("_")
    return f"{prefix}_{suffix}"


@dataclass(frozen=True)
class OpticalGroup:
    source_dataset: str
    source_group_id: str
    reference_time: datetime
    timestamp_source: str
    geometry: Any
    feature_count: int
    area: str

    @property
    def obs_id(self) -> str:
        return observation_id(self.source_dataset, self.source_group_id)


@dataclass(frozen=True)
class S1Scene:
    name: str
    start: datetime
    footprint: Any

    @property
    def granule(self) -> str:
        return self.name.removesuffix(".SAFE")


def parse_utc(value: str) -> datetime:
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def iso_z(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def local_buffer_wgs84(geometry: Any, distance_km: float) -> Any:
    """Buffer WGS84 geometry in a local equirectangular metre plane."""
    center = geometry.centroid
    ref_lon, ref_lat = center.x, center.y
    cos_lat = max(1e-6, math.cos(math.radians(ref_lat)))

    def forward(x: float, y: float, z: float | None = None) -> tuple[float, float]:
        return (
            math.radians(x - ref_lon) * cos_lat * EARTH_RADIUS_M,
            math.radians(y - ref_lat) * EARTH_RADIUS_M,
        )

    def inverse(x: float, y: float, z: float | None = None) -> tuple[float, float]:
        return (
            ref_lon + math.degrees(x / (cos_lat * EARTH_RADIUS_M)),
            ref_lat + math.degrees(y / EARTH_RADIUS_M),
        )

    return transform(inverse, transform(forward, geometry).buffer(distance_km * 1000.0))


def project_local(geometry: Any, ref_lon: float, ref_lat: float) -> Any:
    cos_lat = max(1e-6, math.cos(math.radians(ref_lat)))

    def forward(x: float, y: float, z: float | None = None) -> tuple[float, float]:
        return (
            math.radians(x - ref_lon) * cos_lat * EARTH_RADIUS_M,
            math.radians(y - ref_lat) * EARTH_RADIUS_M,
        )

    return transform(forward, geometry)


def raster_footprint(path: Path) -> Any:
    with rasterio.open(path) as dataset:
        bounds = dataset.bounds
        if dataset.crs is None:
            raise RuntimeError(f"Raster has no CRS: {path}")
        west, south, east, north = transform_bounds(dataset.crs, "EPSG:4326", *bounds, densify_pts=21)
    return box(west, south, east, north)


def union_raster_footprints(paths: Iterable[Path]) -> Any:
    geometries = [raster_footprint(path) for path in paths]
    if not geometries:
        raise RuntimeError("Cannot build an AOI from an empty raster list")
    return unary_union(geometries)


def parse_marida_folder(name: str) -> tuple[str, datetime]:
    match = re.fullmatch(r"S2_(\d{1,2})-(\d{1,2})-(\d{2})_([0-9A-Z]{5})", name)
    if not match:
        raise ValueError(f"Unrecognised MARIDA patch folder: {name}")
    day, month, year, tile = match.groups()
    return tile, datetime(2000 + int(year), int(month), int(day), 12, tzinfo=UTC)


def load_marida_groups() -> list[OpticalGroup]:
    exact_times: dict[str, datetime] = {}
    lookup = REPO_ROOT / "MARIDA" / "Planet_reacquisition_marida_all_scenes.csv"
    with lookup.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            exact_times[row["key"]] = parse_utc(row["s2_acquired_utc"])

    groups: list[OpticalGroup] = []
    for folder in sorted(path for path in MARIDA_PATCHES_ROOT.iterdir() if path.is_dir()):
        tile, nominal = parse_marida_folder(folder.name)
        key = f"{tile}/{nominal.date().isoformat()}"
        images = sorted(
            path for path in folder.glob("*.tif")
            if not path.stem.endswith(("_cl", "_conf"))
        )
        groups.append(OpticalGroup(
            "MARIDA", key, exact_times.get(key, nominal),
            "catalogue" if key in exact_times else "nominal_date_noon",
            union_raster_footprints(images), len(images), tile,
        ))
    return groups


def load_nasa_planet_groups() -> list[OpticalGroup]:
    source = REPO_ROOT / "PlanetData" / "marine_debris" / "nasa-marine-debris" / "source"
    grouped: dict[str, list[Path]] = defaultdict(list)
    for path in source.glob("*.tif"):
        match = re.match(r"(\d{8}_\d{6}_[A-Za-z0-9]+)_", path.name)
        if match:
            grouped[match.group(1)].append(path)
    groups = []
    for group_id, paths in sorted(grouped.items()):
        timestamp = datetime.strptime(group_id[:15], "%Y%m%d_%H%M%S").replace(tzinfo=UTC)
        groups.append(OpticalGroup(
            "NASA_PlanetScope", group_id, timestamp, "filename_exact",
            union_raster_footprints(paths), len(paths), "NASA Marine Debris",
        ))
    return groups


def load_ghana_groups() -> list[OpticalGroup]:
    shp_path = GHANA_POINTS_PATH
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    metadata: dict[str, dict[str, str]] = {}
    with fiona.open(shp_path) as source:
        for feature in source:
            props = dict(feature["properties"])
            obs_id = str(props["obs_id"])
            grouped[obs_id].append(feature["geometry"])
            metadata[obs_id] = {key: str(value or "") for key, value in props.items()}

    summary: dict[str, dict[str, str]] = {}
    summary_path = REPO_ROOT / "Ghana_Drift" / "ghana_drift_planet_summary.csv"
    with summary_path.open("r", encoding="utf-8-sig", newline="") as handle:
        summary = {row["obs_id"]: row for row in csv.DictReader(handle)}

    groups = []
    for obs_id, geometries in sorted(grouped.items()):
        row = summary.get(obs_id, {})
        date_text = metadata[obs_id].get("obs_date", "").replace("/", "-")
        exact = (row.get("planet_acquired_start") or "").strip()
        timestamp = parse_utc(exact) if exact else parse_utc(f"{date_text}T10:00:00Z")
        groups.append(OpticalGroup(
            "Ghana_Drift", obs_id, timestamp,
            "planet_metadata" if exact else "nominal_10utc",
            unary_union([shape(item) for item in geometries]), len(geometries), "Ghana",
        ))
    return groups


def load_greece_groups() -> list[OpticalGroup]:
    raw_root = REPO_ROOT / "sar_ml_pipeline_legacy" / "data" / "raw" / "Greece"
    products = sorted(raw_root.rglob("S2*_MSIL*.SAFE.zip"))
    crop = REPO_ROOT / "sar_ml_pipeline_legacy" / "data" / "processed" / "Greece" / "PLP2021" / "Optical" / "OPTICAL_20210701" / "B01.tif"
    geometry = raster_footprint(crop)
    groups = []
    for product in products:
        match = re.search(r"_(\d{8}T\d{6})_", product.name)
        if not match:
            continue
        timestamp = datetime.strptime(match.group(1), "%Y%m%dT%H%M%S").replace(tzinfo=UTC)
        group_id = product.name.removesuffix(".SAFE.zip")
        groups.append(OpticalGroup(
            "Greece_Sentinel2", group_id, timestamp, "product_name_exact",
            geometry, 1, "Greece PLP",
        ))
    return groups


def jamila_scene_name(observation: dict[str, Any]) -> str:
    source_id = str(observation.get("extra", {}).get("_sourceId") or "").strip()
    return Path(source_id.split("/", 1)[0]).name if source_id else f"unknown_{observation.get('id', 'observation')}"


def load_jamila_groups() -> list[OpticalGroup]:
    payload = json.loads(JAMILA_OBSERVATIONS_PATH.read_text(encoding="utf-8"))
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for observation in payload.get("observations", []):
        grouped[jamila_scene_name(observation)].append(observation)

    groups = []
    for name, observations in sorted(grouped.items()):
        geometries = [shape(item["geometry"]) for item in observations if item.get("geometry")]
        timestamps = sorted(parse_utc(str(item["timestamp"])) for item in observations if item.get("timestamp"))
        if not geometries or not timestamps:
            continue
        groups.append(OpticalGroup(
            "Jamila_Floating_Debris", Path(name).stem, timestamps[0], "nominal",
            unary_union(geometries), len(observations), Path(name).stem,
        ))
    return groups


def load_all_groups() -> list[OpticalGroup]:
    return load_marida_groups() + load_nasa_planet_groups() + load_ghana_groups() + load_greece_groups() + load_jamila_groups()


def bbox_wkt(geometry: Any) -> str:
    west, south, east, north = geometry.bounds
    return f"POLYGON(({west} {south},{west} {north},{east} {north},{east} {south},{west} {south}))"


def query_s1_scenes(session: requests.Session, aoi: Any, reference: datetime) -> list[S1Scene]:
    start = reference - timedelta(hours=SEARCH_HOURS)
    end = reference + timedelta(hours=SEARCH_HOURS)
    filter_expr = (
        "Collection/Name eq 'SENTINEL-1' and "
        f"OData.CSC.Intersects(area=geography'SRID=4326;{bbox_wkt(aoi)}') and "
        f"ContentDate/Start ge {iso_z(start)} and ContentDate/Start le {iso_z(end)} and "
        "contains(Name,'_IW_SLC_')"
    )
    encoded_filter = quote(filter_expr, safe="()/,;'$=")
    url = f"{CATALOG_URL}?$top=1000&$orderby=ContentDate/Start%20asc&$filter={encoded_filter}"
    response = session.get(url, timeout=120)
    response.raise_for_status()
    products = response.json().get("value", [])
    scenes = []
    for product in products:
        name = str(product.get("Name") or "")
        if "_IW_SLC__1SDV_" not in name:
            continue
        footprint = product.get("GeoFootprint")
        if isinstance(footprint, str):
            footprint = json.loads(footprint)
        if not footprint:
            continue
        scenes.append(S1Scene(name, parse_utc(product["ContentDate"]["Start"]), shape(footprint)))
    return scenes


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=6,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def coverage_ratio(aoi: Any, footprints: Iterable[Any]) -> float:
    if aoi.is_empty or aoi.area <= 0:
        return 0.0
    center = aoi.centroid
    projected_aoi = project_local(aoi, center.x, center.y)
    projected_footprints = [project_local(item, center.x, center.y) for item in footprints]
    merged = unary_union(projected_footprints)
    return max(0.0, min(1.0, projected_aoi.intersection(merged).area / projected_aoi.area))


def greedy_cover(aoi: Any, scenes: list[S1Scene]) -> tuple[list[S1Scene], float]:
    selected: list[S1Scene] = []
    covered = GeometryCollection()
    remaining = list(scenes)
    while remaining:
        current_ratio = coverage_ratio(aoi, [covered]) if selected else 0.0
        best = max(remaining, key=lambda scene: coverage_ratio(aoi, [covered, scene.footprint]))
        new_covered = covered.union(best.footprint)
        new_ratio = coverage_ratio(aoi, [new_covered])
        if new_ratio <= current_ratio + 1e-12:
            break
        selected.append(best)
        covered = new_covered
        remaining.remove(best)
        if new_ratio >= COVERAGE_THRESHOLD:
            return selected, new_ratio
    return selected, coverage_ratio(aoi, [covered]) if selected else 0.0


def select_scene_set(aoi: Any, scenes: list[S1Scene], reference: datetime, role: str) -> tuple[list[S1Scene], float]:
    if role == "before":
        eligible = sorted((scene for scene in scenes if scene.start <= reference), key=lambda scene: scene.start, reverse=True)
    else:
        eligible = sorted((scene for scene in scenes if scene.start >= reference), key=lambda scene: scene.start)

    best: tuple[list[S1Scene], float] = ([], 0.0)
    for anchor in eligible:
        if role == "before":
            window = [
                scene for scene in eligible
                if anchor.start - timedelta(hours=SET_SPAN_HOURS) <= scene.start <= anchor.start
            ]
        else:
            window = [
                scene for scene in eligible
                if anchor.start <= scene.start <= anchor.start + timedelta(hours=SET_SPAN_HOURS)
            ]
        selected, ratio = greedy_cover(aoi, window)
        if ratio > best[1]:
            best = selected, ratio
        if ratio >= COVERAGE_THRESHOLD:
            return sorted(selected, key=lambda scene: scene.start), ratio
    return best


def group_row(group: OpticalGroup, buffered: Any) -> dict[str, Any]:
    west, south, east, north = buffered.bounds
    return {
        "obs_id": group.obs_id,
        "source_dataset": group.source_dataset,
        "source_group_id": group.source_group_id,
        "area": group.area,
        "reference_time": iso_z(group.reference_time),
        "timestamp_source": group.timestamp_source,
        "feature_count": group.feature_count,
        "aoi_buffer_km": BUFFER_KM,
        "aoi_west": west, "aoi_south": south, "aoi_east": east, "aoi_north": north,
    }


def bounds_ring(geometry: Any) -> list[tuple[float, float]]:
    west, south, east, north = geometry.bounds
    return [(west, south), (west, north), (east, north), (east, south), (west, south)]


def reference_point_row(
    *,
    obs_id: str,
    point_id: str,
    lat: float,
    lon: float,
    reference_kind: str,
    seed_eligible: bool,
    source_feature_id: str,
    confidence: str = "",
    notes: str = "",
) -> dict[str, Any]:
    return {
        "obs_id": obs_id,
        "point_id": point_id,
        "lat": lat,
        "lon": lon,
        "reference_kind": reference_kind,
        "seed_eligible": str(seed_eligible).lower(),
        "source_feature_id": source_feature_id,
        "confidence": confidence,
        "notes": notes,
    }


def aoi_reference_rows(group: OpticalGroup, buffered: Any) -> list[dict[str, Any]]:
    return [
        reference_point_row(
            obs_id=group.obs_id,
            point_id=f"{group.obs_id}_AOI_{point_index:04d}",
            lat=lat,
            lon=lon,
            reference_kind="aoi_proxy",
            seed_eligible=False,
            source_feature_id=f"30km_buffer_corner_{point_index}",
            notes="Corner of the 30 km buffered optical AOI; context only, never an OpenDrift seed.",
        )
        for point_index, (lon, lat) in enumerate(bounds_ring(buffered), 1)
    ]


def _representative_seed(geometry: Any) -> Any:
    if geometry.geom_type in {"LineString", "MultiLineString"} and geometry.length > 0:
        return geometry.interpolate(0.5, normalized=True)
    if geometry.geom_type == "Point":
        return geometry
    return geometry.representative_point()


def marida_seed_rows(
    allowed_obs_ids: set[str],
    *,
    patches_root: Path = MARIDA_PATCHES_ROOT,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seed_counts: dict[str, int] = defaultdict(int)
    for folder in sorted(path for path in patches_root.iterdir() if path.is_dir()):
        tile, nominal = parse_marida_folder(folder.name)
        obs_id = observation_id("MARIDA", f"{tile}/{nominal.date().isoformat()}")
        if obs_id not in allowed_obs_ids:
            continue
        for class_path in sorted(folder.glob("*_cl.tif")):
            confidence_path = class_path.with_name(class_path.name.replace("_cl.tif", "_conf.tif"))
            with rasterio.open(class_path) as class_source:
                classes = class_source.read(1)
                debris = classes == MARIDA_MARINE_DEBRIS_CLASS
                if not debris.any():
                    continue
                confidence_values = None
                if confidence_path.exists():
                    with rasterio.open(confidence_path) as confidence_source:
                        confidence_values = confidence_source.read(1)
                for component_index, (geometry_mapping, value) in enumerate(
                    raster_shapes(
                        debris.astype(np.uint8),
                        mask=debris,
                        transform=class_source.transform,
                        connectivity=8,
                    ),
                    1,
                ):
                    if int(value) != 1:
                        continue
                    component = shape(geometry_mapping)
                    projected_point = _representative_seed(component)
                    longitudes, latitudes = transform_coordinates(
                        class_source.crs,
                        "EPSG:4326",
                        [projected_point.x],
                        [projected_point.y],
                    )
                    confidence_code = 0
                    if confidence_values is not None:
                        pixel_row, pixel_col = class_source.index(projected_point.x, projected_point.y)
                        if 0 <= pixel_row < confidence_values.shape[0] and 0 <= pixel_col < confidence_values.shape[1]:
                            confidence_code = int(confidence_values[pixel_row, pixel_col])
                    confidence = MARIDA_CONFIDENCE.get(confidence_code, "unknown")
                    seed_counts[obs_id] += 1
                    rows.append(
                        reference_point_row(
                            obs_id=obs_id,
                            point_id=f"{obs_id}_MARIDA_MD_{seed_counts[obs_id]:04d}",
                            lat=latitudes[0],
                            lon=longitudes[0],
                            reference_kind="marida_debris_mask",
                            seed_eligible=True,
                            source_feature_id=f"{class_path.name}#component-{component_index:04d}",
                            confidence=confidence,
                            notes=(
                                "Representative point inside a connected MARIDA Marine Debris (class DN=1) "
                                f"mask component; annotator confidence={confidence} (DN={confidence_code})."
                            ),
                        )
                    )
    return rows


def jamila_seed_rows(
    allowed_obs_ids: set[str],
    *,
    observations_path: Path = JAMILA_OBSERVATIONS_PATH,
) -> list[dict[str, Any]]:
    payload = json.loads(observations_path.read_text(encoding="utf-8"))
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for observation in payload.get("observations", []):
        if observation.get("isAbsence") or not observation.get("geometry"):
            continue
        grouped[jamila_scene_name(observation)].append(observation)

    rows: list[dict[str, Any]] = []
    for scene_name, observations in sorted(grouped.items()):
        obs_id = observation_id("Jamila_Floating_Debris", Path(scene_name).stem)
        if obs_id not in allowed_obs_ids:
            continue
        ordered = sorted(observations, key=lambda item: str(item.get("id") or ""))
        for index, observation in enumerate(ordered, 1):
            geometry = shape(observation["geometry"])
            if geometry.is_empty:
                continue
            point = _representative_seed(geometry)
            source_feature_id = str(observation.get("id") or f"feature-{index:04d}")
            rows.append(
                reference_point_row(
                    obs_id=obs_id,
                    point_id=f"{obs_id}_JAMILA_{index:04d}",
                    lat=point.y,
                    lon=point.x,
                    reference_kind="jamila_debris_geometry",
                    seed_eligible=True,
                    source_feature_id=source_feature_id,
                    confidence="source_label",
                    notes=(
                        f"Midpoint/representative point of non-absence Jamila geometry {source_feature_id}; "
                        "the recorded timestamp is nominal and contributes temporal uncertainty."
                    ),
                )
            )
    return rows


def ghana_seed_rows(
    allowed_obs_ids: set[str],
    *,
    points_path: Path = GHANA_POINTS_PATH,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with fiona.open(points_path) as source:
        for index, feature in enumerate(source, 1):
            properties = dict(feature["properties"])
            source_obs_id = str(properties["obs_id"])
            obs_id = observation_id("Ghana_Drift", source_obs_id)
            if obs_id not in allowed_obs_ids:
                continue
            geometry = shape(feature["geometry"])
            point = _representative_seed(geometry)
            point_id = str(properties.get("pt_id") or f"P{index:04d}")
            rows.append(
                reference_point_row(
                    obs_id=obs_id,
                    point_id=f"{obs_id}_{point_id}",
                    lat=point.y,
                    lon=point.x,
                    reference_kind="ghana_observed_point",
                    seed_eligible=True,
                    source_feature_id=point_id,
                    confidence="source_label",
                    notes=str(properties.get("note") or "Supplied Ghana drift observation point."),
                )
            )
    return rows


def source_seed_rows(groups: list[OpticalGroup]) -> list[dict[str, Any]]:
    allowed = {group.obs_id for group in groups}
    rows = marida_seed_rows(allowed)
    rows.extend(jamila_seed_rows(allowed))
    rows.extend(ghana_seed_rows(allowed))
    return sorted(rows, key=lambda row: (row["obs_id"], row["point_id"]))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fieldnames or (list(rows[0]) if rows else [])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(groups: list[OpticalGroup], *, query_catalogue: bool) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    group_rows: list[dict[str, Any]] = []
    point_rows: list[dict[str, Any]] = []
    target_rows: list[dict[str, Any]] = []
    selection_rows: list[dict[str, Any]] = []
    geojson_features = []
    buffered_by_obs: dict[str, Any] = {}
    session = build_session()
    cache_path = OUT_DIR / "copernicus_s1_slc_cache.json"
    cache: dict[str, list[dict[str, Any]]] = {}
    if query_catalogue and cache_path.exists():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))

    for index, group in enumerate(groups, 1):
        buffered = local_buffer_wgs84(group.geometry, BUFFER_KM)
        buffered_by_obs[group.obs_id] = buffered
        group_rows.append(group_row(group, buffered))
        geojson_features.append({"type": "Feature", "geometry": mapping(buffered), "properties": group_row(group, buffered)})
        point_rows.extend(aoi_reference_rows(group, buffered))
        if not query_catalogue:
            continue
        cached = cache.get(group.obs_id)
        if cached is None:
            for attempt in range(1, 7):
                try:
                    scenes = query_s1_scenes(session, buffered, group.reference_time)
                    break
                except requests.RequestException:
                    if attempt == 6:
                        raise
                    wait_seconds = 15 * attempt
                    print(
                        f"Catalogue throttled for {group.source_group_id}; retrying in {wait_seconds}s "
                        f"(attempt {attempt}/6)",
                        flush=True,
                    )
                    time.sleep(wait_seconds)
            cache[group.obs_id] = [
                {"name": scene.name, "start": iso_z(scene.start), "footprint": mapping(scene.footprint)}
                for scene in scenes
            ]
            cache_path.write_text(json.dumps(cache, indent=2), encoding="utf-8")
        else:
            scenes = [S1Scene(item["name"], parse_utc(item["start"]), shape(item["footprint"])) for item in cached]
        for role in ("before", "after"):
            selected, set_ratio = select_scene_set(buffered, scenes, group.reference_time, role)
            selection_rows.append({
                "obs_id": group.obs_id, "source_dataset": group.source_dataset,
                "source_group_id": group.source_group_id, "role": role,
                "candidate_count": len([scene for scene in scenes if scene.start <= group.reference_time]) if role == "before" else len([scene for scene in scenes if scene.start >= group.reference_time]),
                "selected_count": len(selected), "coverage_set_ratio": round(set_ratio, 6),
                "coverage_complete": set_ratio >= COVERAGE_THRESHOLD,
                "reason": "selected" if set_ratio >= COVERAGE_THRESHOLD else "no <=12h scene set reached 99.9% coverage",
            })
            for rank, scene in enumerate(selected, 1):
                target_rows.append({
                    "target_id": f"{group.obs_id}:{role}:{rank:02d}",
                    "obs_id": group.obs_id, "source_dataset": group.source_dataset,
                    "source_group_id": group.source_group_id, "area": group.area,
                    "date": group.reference_time.date().isoformat(), "reference_time": iso_z(group.reference_time),
                    "timestamp_source": group.timestamp_source, "role": role, "selection_rank": rank,
                    "granule_name": scene.name, "acquisition_start": iso_z(scene.start),
                    "delta_h": round((scene.start - group.reference_time).total_seconds() / 3600.0, 3),
                    "scene_coverage_ratio": round(coverage_ratio(buffered, [scene.footprint]), 6),
                    "coverage_set_ratio": round(set_ratio, 6), "coverage_complete": set_ratio >= COVERAGE_THRESHOLD,
                    "download_group_key": scene.granule, "aoi_buffer_km": BUFFER_KM,
                })
        print(f"[{index}/{len(groups)}] {group.source_dataset}: {group.source_group_id} ({len(scenes)} candidates)", flush=True)
        time.sleep(0.25 if cached is None else 0.01)

    point_rows.extend(source_seed_rows(groups))
    write_csv(OUT_DIR / "optical_groups.csv", group_rows)
    write_csv(OUT_DIR / "global_s1_slc_points.csv", point_rows)
    if query_catalogue:
        write_csv(OUT_DIR / "global_s1_slc_associations.csv", target_rows)
        write_csv(OUT_DIR / "global_s1_slc_selection_summary.csv", selection_rows)

        complete_associations = [row for row in target_rows if row["coverage_complete"]]
        by_granule: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in complete_associations:
            by_granule[row["granule_name"]].append(row)
        processing_rows: list[dict[str, Any]] = []
        processing_points: list[dict[str, Any]] = []
        unique_targets: list[str] = []
        for granule_name, associations in sorted(by_granule.items()):
            granule = granule_name.removesuffix(".SAFE")
            obs_id = f"S1_{granule}"
            target_id = f"{obs_id}:scene"
            unique_targets.append(target_id)
            first = associations[0]
            processing_rows.append({
                "target_id": target_id, "obs_id": obs_id, "source_dataset": "deduplicated_global_s1",
                "source_group_id": granule, "area": "Global_S1", "date": first["acquisition_start"][:10],
                "reference_time": first["acquisition_start"], "timestamp_source": "s1_catalogue",
                "role": "scene", "selection_rank": 1, "granule_name": granule_name,
                "acquisition_start": first["acquisition_start"], "delta_h": 0,
                "scene_coverage_ratio": 1, "coverage_set_ratio": 1, "coverage_complete": True,
                "download_group_key": granule, "aoi_buffer_km": BUFFER_KM,
                "association_count": len(associations),
            })
            associated_aoi = unary_union([buffered_by_obs[row["obs_id"]] for row in associations])
            boundary = bounds_ring(associated_aoi)
            for point_index, (lon, lat) in enumerate(boundary, 1):
                processing_points.append({
                    "obs_id": obs_id, "point_id": f"{obs_id}_P{point_index:04d}", "lat": lat, "lon": lon,
                })
        write_csv(OUT_DIR / "global_s1_slc_processing_targets.csv", processing_rows)
        write_csv(OUT_DIR / "global_s1_slc_processing_points.csv", processing_points)
        manifest = {
            "schema_version": 1, "run_id": "global-optical-reference-s1-slc-v1", "dataset_mode": "global",
            "targets": unique_targets,
            "inputs": {
                "match_csv": "/data/raw/global_s1_slc_processing_targets.csv", "points_csv": "/data/raw/global_s1_slc_processing_points.csv",
                "raw_slc_root": "/data/raw/slc", "shapefiles_root": "/data/shapefiles",
            },
            "outputs": {
                "processed_root": "/data/processed", "patches_root": "/data/patches", "stacks_root": "/data/stacks",
                "logs_root": "/data/logs", "manifests_root": "/data/manifests",
            },
            "stages": {"slc_process": {"enabled": True, "overwrite": False, "gpt": "/usr/local/snap/bin/gpt", "pad_deg": 0},
                       "patch_extract": {"enabled": False, "overwrite": False},
                       "patch_stack": {"enabled": False, "overwrite": False}},
            "processing": {"resolution_policy": "snap-native", "output_mode": "scene", "subset_mode": "full-swath",
                           "subswaths": ["IW1", "IW2", "IW3"], "workers": 1, "cache_gb": 32, "patch_size": 256},
        }
        (OUT_DIR / "global_s1_slc_job.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    (OUT_DIR / "optical_groups.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": geojson_features}, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory-only", action="store_true", help="Build optical AOIs without querying Sentinel-1.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    groups = load_all_groups()
    print(f"Loaded {len(groups)} optical reference groups")
    write_outputs(groups, query_catalogue=not args.inventory_only)


if __name__ == "__main__":
    main()
