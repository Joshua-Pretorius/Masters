#!/usr/bin/env python3
"""
Build a Sentinel scene directory for an Ocean Scan export.

The workflow is:
1. Group observations by the source shapefile name stored in `extra._sourceId`.
2. Build one WGS84 bbox for all observations in each source scene.
3. Find every intersecting Sentinel-2 L2A item around that scene timestamp.
4. For each S2 item, find the nearest Sentinel-1 item before and after it.

Outputs are written into a directory containing:
- `source_scenes.geojson`: one feature per Ocean Scan source scene bbox
- `s2_scene_directory.csv`: flat table, one row per linked S2 item
- `s2_scene_directory.json`: nested JSON grouped by source scene
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from shapely.geometry import box, mapping, shape
from shapely.ops import unary_union
from urllib3.util.retry import Retry


LOG = logging.getLogger("build_sentinel_scene_directory")

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
DEFAULT_S2_COLLECTION = "sentinel-2-l2a"
DEFAULT_S1_COLLECTIONS = ["sentinel-1-grd", "sentinel-1-rtc"]
DEFAULT_S2_WINDOW_HOURS = 18
DEFAULT_S1_WINDOW_DAYS = 20
DEFAULT_LIMIT = 200
REQUEST_TIMEOUT = 120

S1_COLLECTION_PRIORITY = {
    "sentinel-1-grd": 0,
    "sentinel-1-rtc": 1,
}


@dataclass
class SourceScene:
    name: str
    timestamp: str
    observation_count: int
    bbox: tuple[float, float, float, float]
    geometry: dict[str, Any]
    observation_ids: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a directory of Sentinel-2 scenes linked to an Ocean Scan "
            "campaign and the nearest Sentinel-1 scenes before and after."
        )
    )
    parser.add_argument(
        "input_json",
        type=Path,
        help="Path to the Ocean Scan campaign JSON export.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("scene_directory"),
        help="Directory where the catalogue files will be written.",
    )
    parser.add_argument(
        "--s2-collection",
        default=DEFAULT_S2_COLLECTION,
        help=f"Sentinel-2 collection name. Default: {DEFAULT_S2_COLLECTION}",
    )
    parser.add_argument(
        "--s1-collections",
        nargs="+",
        default=DEFAULT_S1_COLLECTIONS,
        help=(
            "Sentinel-1 collections searched for nearest before/after scenes. "
            f"Default: {' '.join(DEFAULT_S1_COLLECTIONS)}"
        ),
    )
    parser.add_argument(
        "--s2-window-hours",
        type=int,
        default=DEFAULT_S2_WINDOW_HOURS,
        help=(
            "Search window around the source-scene timestamp for matching "
            f"Sentinel-2 scenes. Default: {DEFAULT_S2_WINDOW_HOURS}."
        ),
    )
    parser.add_argument(
        "--s1-window-days",
        type=int,
        default=DEFAULT_S1_WINDOW_DAYS,
        help=(
            "Search window around each Sentinel-2 acquisition when looking for "
            f"nearest Sentinel-1 before/after items. Default: {DEFAULT_S1_WINDOW_DAYS}."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=(
            "Maximum number of items requested from each STAC search. "
            f"Default: {DEFAULT_LIMIT}."
        ),
    )
    parser.add_argument(
        "--source-scene",
        action="append",
        default=[],
        help="Only process the named source scene(s), e.g. biscay_20180419.shp.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Console log level.",
    )
    return parser.parse_args()


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=6,
        backoff_factor=0.8,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = requests.adapters.HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def parse_timestamp(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def iso_z(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    value = value.astimezone(timezone.utc).replace(microsecond=0)
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def sanitize_stem(name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem)
    return stem.strip("_") or "scene"


def bbox_geometry(bounds: tuple[float, float, float, float]) -> dict[str, Any]:
    return mapping(box(*bounds))


def choose_scene_name(observation: dict[str, Any]) -> str:
    source_id = str(observation.get("extra", {}).get("_sourceId") or "").strip()
    if source_id:
        return Path(source_id.split("/", 1)[0]).name
    obs_id = str(observation.get("id") or "unknown")
    return f"unknown_{obs_id}"


def group_source_scenes(observations: list[dict[str, Any]]) -> list[SourceScene]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for observation in observations:
        grouped[choose_scene_name(observation)].append(observation)

    source_scenes: list[SourceScene] = []
    for name, group in sorted(grouped.items()):
        geometries = [shape(ob["geometry"]) for ob in group if ob.get("geometry")]
        if not geometries:
            LOG.warning("Skipping %s because it has no geometries.", name)
            continue

        merged = unary_union(geometries)
        timestamps = sorted(
            {
                str(ob.get("timestamp"))
                for ob in group
                if ob.get("timestamp")
            }
        )
        if not timestamps:
            LOG.warning("Skipping %s because it has no timestamps.", name)
            continue
        if len(timestamps) > 1:
            LOG.warning(
                "%s has %s timestamps; using the earliest one.",
                name,
                len(timestamps),
            )
        timestamp = timestamps[0]
        bounds = tuple(float(v) for v in merged.bounds)
        source_scenes.append(
            SourceScene(
                name=name,
                timestamp=timestamp,
                observation_count=len(group),
                bbox=bounds,
                geometry=bbox_geometry(bounds),
                observation_ids=[str(ob.get("id")) for ob in group if ob.get("id")],
            )
        )
    return source_scenes


def stac_search(
    session: requests.Session,
    collections: list[str],
    intersects: dict[str, Any] | None,
    datetime_range: str | None,
    limit: int,
    extra_query: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    payload: dict[str, Any] = {
        "collections": collections,
        "limit": limit,
    }
    if intersects is not None:
        payload["intersects"] = intersects
    if datetime_range is not None:
        payload["datetime"] = datetime_range
    if extra_query:
        payload.update(extra_query)

    response = session.post(
        f"{STAC_URL}/search",
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    body = response.json()
    features = body.get("features", []) or []

    matched = body.get("context", {}).get("matched")
    if matched and matched > len(features):
        LOG.warning(
            "STAC search returned %s/%s features for collections=%s. Increase --limit if needed.",
            len(features),
            matched,
            ",".join(collections),
        )
    return features


def sort_s2_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(item: dict[str, Any]) -> tuple[Any, ...]:
        properties = item.get("properties", {})
        return (
            properties.get("datetime") or "",
            properties.get("s2:mgrs_tile") or "",
            item.get("id") or "",
        )

    return sorted(items, key=key)


def s1_sort_key(item: dict[str, Any], s2_dt: datetime) -> tuple[float, int, str]:
    item_dt = parse_timestamp(item["properties"]["datetime"])
    delta_seconds = abs((item_dt - s2_dt).total_seconds())
    priority = S1_COLLECTION_PRIORITY.get(item.get("collection", ""), 99)
    return (delta_seconds, priority, str(item.get("id") or ""))


def nearest_s1_before_after(
    session: requests.Session,
    geometry: dict[str, Any],
    s2_dt: datetime,
    collections: list[str],
    window_days: int,
    limit: int,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    start = iso_z(s2_dt - timedelta(days=window_days))
    end = iso_z(s2_dt + timedelta(days=window_days))
    items = stac_search(
        session=session,
        collections=collections,
        intersects=geometry,
        datetime_range=f"{start}/{end}",
        limit=limit,
    )

    before = [
        item
        for item in items
        if parse_timestamp(item["properties"]["datetime"]) < s2_dt
    ]
    after = [
        item
        for item in items
        if parse_timestamp(item["properties"]["datetime"]) > s2_dt
    ]

    before_match = min(before, key=lambda item: s1_sort_key(item, s2_dt), default=None)
    after_match = min(after, key=lambda item: s1_sort_key(item, s2_dt), default=None)
    return before_match, after_match


def delta_hours(item: dict[str, Any] | None, anchor: datetime) -> float | None:
    if item is None:
        return None
    item_dt = parse_timestamp(item["properties"]["datetime"])
    return round((item_dt - anchor).total_seconds() / 3600.0, 3)


def scene_feature(source_scene: SourceScene) -> dict[str, Any]:
    minx, miny, maxx, maxy = source_scene.bbox
    return {
        "type": "Feature",
        "geometry": source_scene.geometry,
        "properties": {
            "source_scene_name": source_scene.name,
            "source_scene_stem": sanitize_stem(source_scene.name),
            "source_scene_timestamp": source_scene.timestamp,
            "source_scene_date": source_scene.timestamp[:10],
            "observation_count": source_scene.observation_count,
            "min_lon": minx,
            "min_lat": miny,
            "max_lon": maxx,
            "max_lat": maxy,
        },
    }


def write_geojson(path: Path, features: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "type": "FeatureCollection",
        "features": features,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s: %(message)s",
    )

    campaign = json.loads(args.input_json.read_text(encoding="utf-8"))
    observations = campaign.get("observations", [])
    if not isinstance(observations, list):
        raise ValueError("Expected `observations` to be a list in the Ocean Scan JSON.")

    source_scenes = group_source_scenes(observations)
    if args.source_scene:
        wanted = set(args.source_scene)
        source_scenes = [scene for scene in source_scenes if scene.name in wanted]

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    write_geojson(
        output_dir / "source_scenes.geojson",
        [scene_feature(scene) for scene in source_scenes],
    )

    session = build_session()

    csv_rows: list[dict[str, Any]] = []
    grouped_json: list[dict[str, Any]] = []

    for index, source_scene in enumerate(source_scenes, start=1):
        LOG.info(
            "[%s/%s] Resolving S2/S1 matches for %s",
            index,
            len(source_scenes),
            source_scene.name,
        )
        source_dt = parse_timestamp(source_scene.timestamp)
        s2_start = iso_z(source_dt - timedelta(hours=args.s2_window_hours))
        s2_end = iso_z(source_dt + timedelta(hours=args.s2_window_hours))

        s2_items = sort_s2_items(
            stac_search(
                session=session,
                collections=[args.s2_collection],
                intersects=source_scene.geometry,
                datetime_range=f"{s2_start}/{s2_end}",
                limit=args.limit,
            )
        )

        scene_entry: dict[str, Any] = {
            "source_scene_name": source_scene.name,
            "source_scene_stem": sanitize_stem(source_scene.name),
            "source_scene_timestamp": source_scene.timestamp,
            "source_scene_date": source_scene.timestamp[:10],
            "observation_count": source_scene.observation_count,
            "observation_ids": source_scene.observation_ids,
            "bbox_wgs84": {
                "min_lon": source_scene.bbox[0],
                "min_lat": source_scene.bbox[1],
                "max_lon": source_scene.bbox[2],
                "max_lat": source_scene.bbox[3],
            },
            "s2_scenes": [],
        }

        if not s2_items:
            csv_rows.append(
                {
                    "source_scene_name": source_scene.name,
                    "source_scene_stem": sanitize_stem(source_scene.name),
                    "source_scene_timestamp": source_scene.timestamp,
                    "source_scene_date": source_scene.timestamp[:10],
                    "source_scene_observation_count": source_scene.observation_count,
                    "scene_min_lon": source_scene.bbox[0],
                    "scene_min_lat": source_scene.bbox[1],
                    "scene_max_lon": source_scene.bbox[2],
                    "scene_max_lat": source_scene.bbox[3],
                    "s2_item_id": "",
                    "s2_collection": "",
                    "s2_datetime": "",
                    "s2_mgrs_tile": "",
                    "s2_platform": "",
                    "s2_cloud_cover": "",
                    "s1_before_id": "",
                    "s1_before_collection": "",
                    "s1_before_datetime": "",
                    "s1_before_delta_hours": "",
                    "s1_after_id": "",
                    "s1_after_collection": "",
                    "s1_after_datetime": "",
                    "s1_after_delta_hours": "",
                    "match_status": "no_s2_match",
                }
            )
            grouped_json.append(scene_entry)
            continue

        for s2_item in s2_items:
            s2_properties = s2_item.get("properties", {})
            s2_dt = parse_timestamp(s2_properties["datetime"])
            s1_before, s1_after = nearest_s1_before_after(
                session=session,
                geometry=s2_item.get("geometry") or source_scene.geometry,
                s2_dt=s2_dt,
                collections=args.s1_collections,
                window_days=args.s1_window_days,
                limit=args.limit,
            )

            before_props = s1_before.get("properties", {}) if s1_before else {}
            after_props = s1_after.get("properties", {}) if s1_after else {}

            row = {
                "source_scene_name": source_scene.name,
                "source_scene_stem": sanitize_stem(source_scene.name),
                "source_scene_timestamp": source_scene.timestamp,
                "source_scene_date": source_scene.timestamp[:10],
                "source_scene_observation_count": source_scene.observation_count,
                "scene_min_lon": source_scene.bbox[0],
                "scene_min_lat": source_scene.bbox[1],
                "scene_max_lon": source_scene.bbox[2],
                "scene_max_lat": source_scene.bbox[3],
                "s2_item_id": s2_item.get("id", ""),
                "s2_collection": s2_item.get("collection", args.s2_collection),
                "s2_datetime": s2_properties.get("datetime", ""),
                "s2_mgrs_tile": s2_properties.get("s2:mgrs_tile", ""),
                "s2_platform": s2_properties.get("platform", ""),
                "s2_cloud_cover": s2_properties.get("eo:cloud_cover", ""),
                "s1_before_id": s1_before.get("id", "") if s1_before else "",
                "s1_before_collection": s1_before.get("collection", "") if s1_before else "",
                "s1_before_datetime": before_props.get("datetime", ""),
                "s1_before_delta_hours": delta_hours(s1_before, s2_dt),
                "s1_after_id": s1_after.get("id", "") if s1_after else "",
                "s1_after_collection": s1_after.get("collection", "") if s1_after else "",
                "s1_after_datetime": after_props.get("datetime", ""),
                "s1_after_delta_hours": delta_hours(s1_after, s2_dt),
                "match_status": "matched",
            }
            csv_rows.append(row)

            scene_entry["s2_scenes"].append(
                {
                    "s2_item_id": row["s2_item_id"],
                    "s2_collection": row["s2_collection"],
                    "s2_datetime": row["s2_datetime"],
                    "s2_mgrs_tile": row["s2_mgrs_tile"],
                    "s2_platform": row["s2_platform"],
                    "s2_cloud_cover": row["s2_cloud_cover"],
                    "s1_before": {
                        "item_id": row["s1_before_id"],
                        "collection": row["s1_before_collection"],
                        "datetime": row["s1_before_datetime"],
                        "delta_hours": row["s1_before_delta_hours"],
                    },
                    "s1_after": {
                        "item_id": row["s1_after_id"],
                        "collection": row["s1_after_collection"],
                        "datetime": row["s1_after_datetime"],
                        "delta_hours": row["s1_after_delta_hours"],
                    },
                }
            )

        grouped_json.append(scene_entry)

    write_csv(output_dir / "s2_scene_directory.csv", csv_rows)
    (output_dir / "s2_scene_directory.json").write_text(
        json.dumps(grouped_json, indent=2),
        encoding="utf-8",
    )

    LOG.info("Wrote %s source scenes to %s", len(source_scenes), output_dir)


if __name__ == "__main__":
    main()
