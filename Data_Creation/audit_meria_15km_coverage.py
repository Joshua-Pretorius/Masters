#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import itertools
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import build_meria_global_s1_slc_matches as global_matches
import build_meria_sa_s1_slc_matches as sa_matches
import slc_match_aoi as aoi


BUFFER_KM = 15.0
REMOTE_TOP_N = 12
MAX_COMBO_SIZE = 4
EPSILON = 1e-9


@dataclass(frozen=True)
class GroupKey:
    dataset: str
    obs_id: str
    area: str
    role: str


@dataclass
class SceneRecord:
    dataset: str
    obs_id: str
    area: str
    role: str
    product_name: str
    download_group_key: str
    scene_id: str
    status: str
    downloaded: bool
    fully_processed: bool
    coverage_15km: float
    footprint: dict[str, Any] | None
    source: str
    scene_dir: Path | None
    zip_path: Path | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=Path(r"D:\Masters\meria_15km_coverage_summary.csv"),
    )
    parser.add_argument(
        "--products-out",
        type=Path,
        default=Path(r"D:\Masters\meria_15km_coverage_products.csv"),
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip live Copernicus candidate queries and report local-scene deficits only.",
    )
    return parser.parse_args()


def load_point_groups(path: Path, dataset: str) -> dict[GroupKey, list[tuple[float, float]]]:
    groups: dict[GroupKey, list[tuple[float, float]]] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            key_before = GroupKey(dataset=dataset, obs_id=row["obs_id"], area=row["area"], role="before")
            key_after = GroupKey(dataset=dataset, obs_id=row["obs_id"], area=row["area"], role="after")
            point = (float(row["lat"]), float(row["lon"]))
            groups.setdefault(key_before, []).append(point)
            groups.setdefault(key_after, []).append(point)
    return groups


def local_dataset_roots() -> dict[str, Path]:
    root = Path(__file__).resolve().parent
    return {
        "meria_sa": root / "meria_sa_plastic_s1_slc" / "processed_slc",
        "meria_global": root / "meria_global_s1_slc" / "processed_slc",
    }


def observation_maps() -> dict[str, dict[str, Any]]:
    return {
        "meria_sa": {obs.obs_id: obs for obs in sa_matches.OBSERVATIONS},
        "meria_global": global_matches.OBSERVATIONS_BY_ID,
    }


def planet_lookups() -> dict[str, dict[str, dict[str, Any]]]:
    return {
        "meria_sa": sa_matches.load_planet_lookup(),
        "meria_global": global_matches.load_planet_lookup(),
    }


def module_for_dataset(dataset: str):
    if dataset == "meria_sa":
        return sa_matches
    if dataset == "meria_global":
        return global_matches
    raise KeyError(dataset)


def observation_for_group(
    dataset: str,
    obs_id: str,
    points: list[tuple[float, float]],
    obs_maps: dict[str, dict[str, Any]],
) -> Any:
    dataset_obs = obs_maps[dataset]
    if obs_id in dataset_obs:
        return dataset_obs[obs_id]
    if dataset == "meria_global":
        base_id = re.sub(r"_[A-Z]+$", "", obs_id)
        if base_id in dataset_obs:
            base_obs = dataset_obs[base_id]
            point_records = tuple(
                global_matches.PointRecord(pt_id=f"P{idx:02d}", lat=lat, lon=lon)
                for idx, (lat, lon) in enumerate(points, start=1)
            )
            return global_matches.Observation(
                obs_id=obs_id,
                area=base_obs.area,
                region=base_obs.region,
                date=base_obs.date,
                center_lat=sum(lat for lat, _ in points) / len(points),
                center_lon=sum(lon for _, lon in points) / len(points),
                location_label=base_obs.location_label,
                notes=base_obs.notes,
                explicit_points=(),
                point_records=point_records,
                point_source=f"{base_obs.point_source or 'synthetic'}_split",
                match_strategy=base_obs.match_strategy,
                planet_acquired_start=base_obs.planet_acquired_start,
                planet_acquired_end=base_obs.planet_acquired_end,
                aoi_buffer_km=base_obs.aoi_buffer_km,
                coverage_threshold=base_obs.coverage_threshold,
            )
    raise KeyError(obs_id)


def file_outputs_complete(payload: dict[str, Any]) -> bool:
    outputs = payload.get("outputs") or {}
    existing_paths = [Path(value) for value in outputs.values() if value]
    if existing_paths and all(path.exists() for path in existing_paths):
        return True
    subswaths = payload.get("subswath_outputs") or {}
    sub_paths = [
        Path(value)
        for entry in subswaths.values()
        for value in (entry or {}).values()
        if value
    ]
    return bool(sub_paths) and all(path.exists() for path in sub_paths)


def geometry_from_bounds(bounds: list[float] | tuple[float, float, float, float] | None) -> dict[str, Any] | None:
    if not bounds or len(bounds) != 4:
        return None
    minx, miny, maxx, maxy = bounds
    return {
        "type": "Polygon",
        "coordinates": [[
            [minx, miny],
            [minx, maxy],
            [maxx, maxy],
            [maxx, miny],
            [minx, miny],
        ]],
    }


def parse_manifest_safe_footprint(zip_path: Path) -> dict[str, Any] | None:
    if not zip_path.exists():
        return None
    try:
        with zipfile.ZipFile(zip_path) as archive:
            manifest_name = next((name for name in archive.namelist() if name.endswith("manifest.safe")), None)
            if manifest_name is None:
                return None
            with archive.open(manifest_name) as handle:
                xml_bytes = handle.read()
    except (OSError, zipfile.BadZipFile, StopIteration):
        return None

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None

    namespace = "{http://www.opengis.net/gml}"
    polygons: list[list[list[float]]] = []
    for node in root.iter():
        if node.tag == f"{namespace}coordinates" and node.text:
            ring: list[list[float]] = []
            for pair in node.text.strip().split():
                parts = pair.split(",")
                if len(parts) < 2:
                    continue
                lat = float(parts[0])
                lon = float(parts[1])
                ring.append([lon, lat])
            if ring and ring[0] != ring[-1]:
                ring.append(ring[0])
            if len(ring) >= 4:
                polygons.append(ring)

    if not polygons:
        return None
    if len(polygons) == 1:
        return {"type": "Polygon", "coordinates": [polygons[0]]}
    return {"type": "MultiPolygon", "coordinates": [[[ring]] for ring in polygons]}


def local_scene_records(point_groups: dict[GroupKey, list[tuple[float, float]]]) -> dict[GroupKey, list[SceneRecord]]:
    grouped: dict[GroupKey, list[SceneRecord]] = {}
    for dataset, processed_root in local_dataset_roots().items():
        for manifest_path in processed_root.rglob("*_slc_manifest.json"):
            payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
            key = GroupKey(
                dataset=dataset,
                obs_id=payload["observation_id"],
                area=payload["area"],
                role=payload["role"],
            )
            points = point_groups.get(key)
            if not points:
                continue
            slc = payload.get("slc") or {}
            granule = slc.get("granule")
            if not granule:
                continue
            zip_path = Path(slc["zip"]) if slc.get("zip") else None
            footprint = None
            if zip_path is not None:
                footprint = parse_manifest_safe_footprint(zip_path)
            if footprint is None:
                processing = payload.get("processing") or {}
                footprint = geometry_from_bounds(processing.get("final_grid", {}).get("bounds"))
                if footprint is None:
                    for grid in processing.get("subswath_grids") or []:
                        footprint = geometry_from_bounds(grid.get("bounds"))
                        if footprint is not None:
                            break
                if footprint is None:
                    footprint = geometry_from_bounds(processing.get("aoi_bounds_wgs84"))
            scene_dir = manifest_path.parent
            status = str(payload.get("status") or "")
            downloaded = bool(zip_path and zip_path.exists())
            fully_processed = status == "processed" and file_outputs_complete(payload)
            record = SceneRecord(
                dataset=dataset,
                obs_id=key.obs_id,
                area=key.area,
                role=key.role,
                product_name=f"{granule}.SAFE",
                download_group_key=str(payload.get("download_group_key") or granule),
                scene_id=str(payload.get("scene_id") or scene_dir.name),
                status=status,
                downloaded=downloaded,
                fully_processed=fully_processed,
                coverage_15km=aoi.coverage_ratio_for_scene(points, footprint, buffer_km=BUFFER_KM),
                footprint=footprint,
                source="local",
                scene_dir=scene_dir,
                zip_path=zip_path,
            )
            grouped.setdefault(key, []).append(record)
    return grouped


def best_combo(records: list[SceneRecord], points: list[tuple[float, float]]) -> tuple[float, list[SceneRecord]]:
    best_ratio = 0.0
    best_records: list[SceneRecord] = []
    if not records:
        return best_ratio, best_records
    for combo_size in range(1, min(MAX_COMBO_SIZE, len(records)) + 1):
        for combo in itertools.combinations(records, combo_size):
            ratio = union_coverage(points, [record.footprint for record in combo])
            if ratio > best_ratio + EPSILON:
                best_ratio = ratio
                best_records = list(combo)
    return best_ratio, best_records


def union_coverage(points: list[tuple[float, float]], footprints: list[dict[str, Any] | None]) -> float:
    valid = [footprint for footprint in footprints if footprint]
    if not valid:
        return 0.0
    merged = valid[0]
    for footprint in valid[1:]:
        merged = merge_geometries(merged, footprint)
    return aoi.coverage_ratio_for_scene(points, merged, buffer_km=BUFFER_KM)


def merge_geometries(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    polygons = geometry_polygons(left) + geometry_polygons(right)
    if len(polygons) == 1:
        return {"type": "Polygon", "coordinates": polygons[0]}
    return {"type": "MultiPolygon", "coordinates": polygons}


def geometry_polygons(geometry: dict[str, Any]) -> list[list[list[list[float]]]]:
    geom_type = geometry.get("type")
    if geom_type == "Polygon":
        return [geometry["coordinates"]]
    if geom_type == "MultiPolygon":
        return geometry["coordinates"]
    return []


def fetch_candidate_products(dataset: str, obs: Any, role: str) -> list[dict[str, Any]]:
    module = module_for_dataset(dataset)
    lookup = planet_lookups()[dataset]
    planet_start, planet_end = module.planet_window(obs, lookup)
    if role == "before":
        window_start = planet_start - module.timedelta(days=30)
        window_end = planet_start
        order = "desc"
    else:
        window_start = planet_end
        window_end = planet_end + module.timedelta(days=30)
        order = "asc"
    polygon = module.bbox_to_polygon(module.bbox_for_observation(obs))
    flt = (
        "Collection/Name eq 'SENTINEL-1' and "
        f"OData.CSC.Intersects(area=geography'SRID=4326;{polygon}') and "
        f"ContentDate/Start gt {module.to_utc_z(window_start)} and "
        f"ContentDate/Start lt {module.to_utc_z(window_end)} and "
        "contains(Name,'_SLC_')"
    )
    url = module.build_odata_url(flt, top=100, order=order)
    return module.candidate_products(module.request_json(url).get("value", []))


def remote_scene_records(
    key: GroupKey,
    points: list[tuple[float, float]],
    obs: Any,
    existing_names: set[str],
) -> list[SceneRecord]:
    candidates = fetch_candidate_products(key.dataset, obs, key.role)
    rows: list[SceneRecord] = []
    for product in candidates:
        name = product["Name"]
        if name in existing_names:
            continue
        footprint = product.get("GeoFootprint")
        coverage = aoi.coverage_ratio_for_scene(points, footprint, buffer_km=BUFFER_KM)
        rows.append(
            SceneRecord(
                dataset=key.dataset,
                obs_id=key.obs_id,
                area=key.area,
                role=key.role,
                product_name=name,
                download_group_key=name.removesuffix(".SAFE"),
                scene_id=name.removesuffix(".SAFE"),
                status="not_local",
                downloaded=False,
                fully_processed=False,
                coverage_15km=coverage,
                footprint=footprint,
                source="catalogue",
                scene_dir=None,
                zip_path=None,
            )
        )
    rows = [row for row in rows if row.coverage_15km > 0.0]
    rows.sort(key=lambda row: row.coverage_15km, reverse=True)
    return rows[:REMOTE_TOP_N]


def choose_recommended_combo(
    key: GroupKey,
    points: list[tuple[float, float]],
    local_records: list[SceneRecord],
    remote_records: list[SceneRecord],
) -> tuple[float, list[SceneRecord]]:
    current_ratio, current_combo = best_combo(local_records, points)
    if not current_combo and remote_records:
        seed = remote_records[0]
        current_combo = [seed]
        current_ratio = union_coverage(points, [seed.footprint])

    chosen = {record.product_name for record in current_combo}
    pool = [record for record in (local_records + remote_records) if record.product_name not in chosen]
    while len(current_combo) < MAX_COMBO_SIZE and current_ratio + EPSILON < 1.0:
        best_candidate: SceneRecord | None = None
        best_ratio = current_ratio
        for candidate in pool:
            combo = current_combo + [candidate]
            ratio = union_coverage(points, [record.footprint for record in combo])
            if ratio > best_ratio + EPSILON:
                best_candidate = candidate
                best_ratio = ratio
                continue
            if abs(ratio - best_ratio) <= EPSILON and best_candidate is not None:
                current_score = (
                    0 if candidate.downloaded else 1,
                    0 if candidate.fully_processed else 1,
                    -candidate.coverage_15km,
                )
                best_score = (
                    0 if best_candidate.downloaded else 1,
                    0 if best_candidate.fully_processed else 1,
                    -best_candidate.coverage_15km,
                )
                if current_score < best_score:
                    best_candidate = candidate
        if best_candidate is None:
            break
        current_combo.append(best_candidate)
        current_ratio = best_ratio
        chosen.add(best_candidate.product_name)
        pool = [record for record in pool if record.product_name != best_candidate.product_name]
    return current_ratio, current_combo


def recommended_action(record: SceneRecord) -> str:
    if not record.downloaded:
        return "download"
    if not record.fully_processed:
        return "process"
    return "done"


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    roots = Path(__file__).resolve().parent
    point_groups: dict[GroupKey, list[tuple[float, float]]] = {}
    point_groups.update(load_point_groups(roots / "meria_sa_plastic_s1_slc" / "MERIA_SA_plastic_points.csv", "meria_sa"))
    point_groups.update(load_point_groups(roots / "meria_global_s1_slc" / "MERIA_global_plastic_points.csv", "meria_global"))
    local_by_group = local_scene_records(point_groups)
    obs_maps = observation_maps()

    summary_rows: list[dict[str, Any]] = []
    product_rows: list[dict[str, Any]] = []

    for key in sorted(point_groups, key=lambda item: (item.dataset, item.area, item.obs_id, item.role)):
        points = point_groups[key]
        local_records = sorted(local_by_group.get(key, []), key=lambda row: row.product_name)
        local_best_ratio, local_best_records = best_combo(local_records, points)
        if local_best_ratio + EPSILON >= 1.0:
            continue

        remote_records: list[SceneRecord] = []
        recommended_ratio = local_best_ratio
        recommended_records = list(local_best_records)
        query_status = "offline"

        if not args.offline:
            print(f"querying {key.dataset} {key.obs_id} {key.role}", flush=True)
            obs = observation_for_group(key.dataset, key.obs_id, points, obs_maps)
            existing_names = {record.product_name for record in local_records}
            remote_records = remote_scene_records(key, points, obs, existing_names)
            recommended_ratio, recommended_records = choose_recommended_combo(
                key,
                points,
                local_records,
                remote_records,
            )
            query_status = "queried"

        summary_rows.append(
            {
                "dataset": key.dataset,
                "obs_id": key.obs_id,
                "area": key.area,
                "role": key.role,
                "local_best_union_15km": f"{local_best_ratio:.3f}",
                "recommended_union_15km": f"{recommended_ratio:.3f}",
                "recommended_reaches_100pct": "yes" if recommended_ratio + EPSILON >= 1.0 else "no",
                "query_status": query_status,
                "recommended_products": "; ".join(record.product_name for record in recommended_records),
            }
        )

        best_local_names = {record.product_name for record in local_best_records}
        recommended_names = {record.product_name for record in recommended_records}
        row_pool = local_records + remote_records
        for record in row_pool:
            if record.product_name not in recommended_names and record.product_name not in best_local_names:
                continue
            product_rows.append(
                {
                    "dataset": key.dataset,
                    "obs_id": key.obs_id,
                    "area": key.area,
                    "role": key.role,
                    "local_best_union_15km": f"{local_best_ratio:.3f}",
                    "recommended_union_15km": f"{recommended_ratio:.3f}",
                    "product_name": record.product_name,
                    "scene_coverage_15km": f"{record.coverage_15km:.3f}",
                    "downloaded": str(record.downloaded),
                    "fully_processed": str(record.fully_processed),
                    "status": record.status,
                    "source": record.source,
                    "in_local_best_combo": "yes" if record.product_name in best_local_names else "no",
                    "in_recommended_combo": "yes" if record.product_name in recommended_names else "no",
                    "recommended_action": recommended_action(record) if record.product_name in recommended_names else "",
                }
            )

    write_csv(
        args.summary_out,
        summary_rows,
        [
            "dataset",
            "obs_id",
            "area",
            "role",
            "local_best_union_15km",
            "recommended_union_15km",
            "recommended_reaches_100pct",
            "query_status",
            "recommended_products",
        ],
    )
    write_csv(
        args.products_out,
        product_rows,
        [
            "dataset",
            "obs_id",
            "area",
            "role",
            "local_best_union_15km",
            "recommended_union_15km",
            "product_name",
            "scene_coverage_15km",
            "downloaded",
            "fully_processed",
            "status",
            "source",
            "in_local_best_combo",
            "in_recommended_combo",
            "recommended_action",
        ],
    )
    print(f"summary={args.summary_out}")
    print(f"products={args.products_out}")
    print(f"deficit_groups={len(summary_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
