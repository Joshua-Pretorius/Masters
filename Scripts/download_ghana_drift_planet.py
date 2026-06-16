#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import csv
import json
import logging
import shutil
import subprocess
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen


LOG = logging.getLogger("ghana_drift_planet")
UTC = timezone.utc
PLANET_QUICK_SEARCH_URL = "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250"
PLANET_ORDERS_URL = "https://api.planet.com/compute/ops/orders/v2"
FINAL_ORDER_STATES = {"success", "partial", "failed", "cancelled"}
DEFAULT_PRODUCT_BUNDLE = "analytic_udm2"
DEFAULT_ITEM_TYPE = "PSScene"
DEFAULT_OGRINFO = Path(r"C:\Program Files\PostgreSQL\17\bin\ogrinfo.exe")
DEFAULT_GDAL_BIN_DIR = Path(r"C:\OTB-9.1.1-Win64\bin")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download clipped Planet imagery for each Ghana drift bounds polygon on its observation date."
    )
    parser.add_argument(
        "--bounds-shapefile",
        type=Path,
        default=Path(r"D:\Masters\Ghana_Drift\ghana_drift_bounds.shp"),
        help="Path to the Ghana drift bounds shapefile.",
    )
    parser.add_argument(
        "--api-key-file",
        type=Path,
        default=Path(r"D:\Masters\planet_api.txt"),
        help="Text file containing the Planet API key.",
    )
    parser.add_argument(
        "--download-dir",
        type=Path,
        default=Path(r"D:\Masters\Ghana_Drift"),
        help="Directory where clipped downloads and summaries are written.",
    )
    parser.add_argument(
        "--summary-csv",
        type=Path,
        default=Path(r"D:\Masters\Ghana_Drift\ghana_drift_planet_summary.csv"),
        help="CSV summary output path.",
    )
    parser.add_argument(
        "--summary-json",
        type=Path,
        default=Path(r"D:\Masters\Ghana_Drift\ghana_drift_planet_summary.json"),
        help="JSON summary output path.",
    )
    parser.add_argument(
        "--ogrinfo-path",
        type=Path,
        default=DEFAULT_OGRINFO,
        help="Path to ogrinfo.exe.",
    )
    parser.add_argument(
        "--gdal-bin-dir",
        type=Path,
        default=DEFAULT_GDAL_BIN_DIR,
        help="Directory containing gdalbuildvrt.exe and gdalwarp.exe.",
    )
    parser.add_argument(
        "--item-type",
        default=DEFAULT_ITEM_TYPE,
        help=f"Planet item type to query. Default: {DEFAULT_ITEM_TYPE}",
    )
    parser.add_argument(
        "--product-bundle",
        default=DEFAULT_PRODUCT_BUNDLE,
        help="Planet Orders product bundle string.",
    )
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=20,
        help="Seconds between order-status polls.",
    )
    parser.add_argument(
        "--max-polls",
        type=int,
        default=90,
        help="Maximum number of order-status polls.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download files even if they already exist.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve Planet items and write summaries without submitting orders.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Console log level.",
    )
    parser.add_argument(
        "--obs-id",
        action="append",
        default=[],
        help="Limit processing to one or more specific observation IDs.",
    )
    parser.add_argument(
        "--max-split-parts",
        type=int,
        default=8,
        help="Maximum number of equal strips to split a bounds polygon into after oversized or over-quota failures.",
    )
    return parser.parse_args()


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def read_api_key(path: Path) -> str:
    api_key = path.read_text(encoding="utf-8").strip()
    if not api_key:
        raise RuntimeError(f"No Planet API key found in {path}")
    return api_key


def authorization_header(api_key: str) -> str:
    token = base64.b64encode(f"{api_key}:".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def request_json(
    url: str,
    auth_header: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": auth_header,
        "Content-Type": "application/json",
        "User-Agent": "ghana-drift-planet-downloader",
    }
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Planet API {exc.code} for {url}: {detail[:1000]}") from exc


def stream_download(location: str, out_path: Path, auth_header: str, force: bool) -> None:
    if out_path.exists() and out_path.stat().st_size > 0 and not force:
        LOG.info("Skipping existing download: %s", out_path)
        return
    request = Request(location, headers={"Authorization": auth_header, "User-Agent": "ghana-drift-planet-downloader"})
    with urlopen(request, timeout=600) as response:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)


def parse_obs_date(value: str) -> str:
    value = value.strip()
    for fmt in ("%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    raise ValueError(f"Unsupported obs_date format: {value!r}")


def load_bounds_features(shapefile_path: Path, ogrinfo_path: Path = DEFAULT_OGRINFO) -> list[dict[str, Any]]:
    cmd = [str(ogrinfo_path), "-json", "-features", str(shapefile_path), shapefile_path.stem]
    completed = subprocess.run(cmd, check=True, capture_output=True, text=True)
    payload = json.loads(completed.stdout)
    features = payload["layers"][0]["features"]
    rows: list[dict[str, Any]] = []
    for feature in features:
        properties = feature.get("properties") or {}
        rows.append(
            {
                "obs_id": str(properties["obs_id"]),
                "obs_date": parse_obs_date(str(properties["obs_date"])),
                "area": str(properties.get("area", "")),
                "pt_count": int(properties.get("pt_count") or 0),
                "geometry": feature["geometry"],
            }
        )
    return rows


def filter_requested_features(features: list[dict[str, Any]], obs_ids: set[str]) -> list[dict[str, Any]]:
    if not obs_ids:
        return features
    return [feature for feature in features if feature["obs_id"] in obs_ids]


def day_bounds_utc(obs_date: str) -> tuple[str, str]:
    start = datetime.strptime(obs_date, "%Y-%m-%d").replace(tzinfo=UTC)
    end = start + timedelta(days=1)
    return (
        start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        end.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def parse_acquired_timestamp(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def geometry_bbox(geometry: dict[str, Any]) -> tuple[float, float, float, float]:
    coordinates = geometry.get("coordinates") or []
    if not coordinates:
        raise ValueError("Geometry has no coordinates")
    points: list[tuple[float, float]] = []

    def collect(values: Any) -> None:
        if isinstance(values, (list, tuple)):
            if len(values) >= 2 and all(isinstance(value, (int, float)) for value in values[:2]):
                points.append((float(values[0]), float(values[1])))
                return
            for child in values:
                collect(child)

    collect(coordinates)
    if not points:
        raise ValueError("Geometry contains no coordinate pairs")
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return (min(xs), min(ys), max(xs), max(ys))


def rectangle_polygon(min_x: float, min_y: float, max_x: float, max_y: float) -> dict[str, Any]:
    return {
        "type": "Polygon",
        "coordinates": [[[min_x, min_y], [min_x, max_y], [max_x, max_y], [max_x, min_y], [min_x, min_y]]],
    }


def split_feature_geometry(feature: dict[str, Any], parts: int) -> list[dict[str, Any]]:
    if parts <= 1:
        return [feature.copy()]
    min_x, min_y, max_x, max_y = geometry_bbox(feature["geometry"])
    width = max_x - min_x
    height = max_y - min_y
    split_along_x = width >= height
    split_features: list[dict[str, Any]] = []
    for index in range(parts):
        if split_along_x:
            part_min_x = min_x + (width * index / parts)
            part_max_x = min_x + (width * (index + 1) / parts)
            part_min_y = min_y
            part_max_y = max_y
        else:
            part_min_x = min_x
            part_max_x = max_x
            part_min_y = min_y + (height * index / parts)
            part_max_y = min_y + (height * (index + 1) / parts)
        split_feature = feature.copy()
        split_feature["geometry"] = rectangle_polygon(part_min_x, part_min_y, part_max_x, part_max_y)
        split_feature["part_index"] = index + 1
        split_feature["part_total"] = parts
        split_features.append(split_feature)
    return split_features


def merge_bboxes(a: tuple[float, float, float, float] | None, b: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    if a is None:
        return b
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def bbox_covers(outer: tuple[float, float, float, float], inner: tuple[float, float, float, float]) -> bool:
    return outer[0] <= inner[0] and outer[1] <= inner[1] and outer[2] >= inner[2] and outer[3] >= inner[3]


def select_covering_item_window(items: list[dict[str, Any]], aoi_geometry: dict[str, Any]) -> list[dict[str, Any]]:
    if len(items) <= 1:
        return items
    try:
        aoi_bbox = geometry_bbox(aoi_geometry)
        ordered_items = sorted(
            items,
            key=lambda item: parse_acquired_timestamp(str(item.get("properties", {}).get("acquired", ""))),
        )
        item_bboxes = [geometry_bbox(item["geometry"]) for item in ordered_items]
    except Exception:
        return items

    best_window: list[dict[str, Any]] | None = None
    best_span_seconds: float | None = None
    for start_index in range(len(ordered_items)):
        union_bbox: tuple[float, float, float, float] | None = None
        for end_index in range(start_index, len(ordered_items)):
            union_bbox = merge_bboxes(union_bbox, item_bboxes[end_index])
            if union_bbox is None or not bbox_covers(union_bbox, aoi_bbox):
                continue
            candidate = ordered_items[start_index : end_index + 1]
            acquired_start = parse_acquired_timestamp(str(candidate[0]["properties"]["acquired"]))
            acquired_end = parse_acquired_timestamp(str(candidate[-1]["properties"]["acquired"]))
            span_seconds = (acquired_end - acquired_start).total_seconds()
            if best_window is None or len(candidate) < len(best_window) or (
                len(candidate) == len(best_window) and (best_span_seconds is None or span_seconds < best_span_seconds)
            ):
                best_window = candidate
                best_span_seconds = span_seconds
            break
    return best_window or items


def build_quick_search_payload(feature: dict[str, Any], item_type: str) -> dict[str, Any]:
    start, end = day_bounds_utc(feature["obs_date"])
    return {
        "item_types": [item_type],
        "geometry": feature["geometry"],
        "filter": {
            "type": "DateRangeFilter",
            "field_name": "acquired",
            "config": {
                "gte": start,
                "lte": end,
            },
        },
    }


def build_order_payload(
    *,
    obs_id: str,
    obs_date: str,
    item_type: str,
    item_ids: list[str],
    geometry: dict[str, Any],
    product_bundle: str,
    order_name_suffix: str = "",
) -> dict[str, Any]:
    return {
        "name": f"ghana_drift_{obs_date}_{obs_id}{order_name_suffix}",
        "source_type": "scenes",
        "order_type": "partial",
        "products": [
            {
                "item_ids": item_ids,
                "item_type": item_type,
                "product_bundle": product_bundle,
            }
        ],
        "tools": [{"clip": {"aoi": geometry}}, {"composite": {}}],
    }


def output_dir_for_feature(download_dir: Path, obs_date: str, obs_id: str) -> Path:
    return download_dir / f"{obs_date}_{obs_id}"


def part_output_dir(out_dir: Path, part_index: int, part_total: int) -> Path:
    return out_dir / "parts" / f"part_{part_index:02d}_of_{part_total:02d}"


def feature_order_suffix(feature: dict[str, Any]) -> str:
    part_total = int(feature.get("part_total") or 1)
    if part_total <= 1:
        return ""
    part_index = int(feature.get("part_index") or 1)
    return f"_part{part_index:02d}of{part_total:02d}"


def existing_download_complete(out_dir: Path) -> bool:
    if not out_dir.exists():
        return False
    return any(path.is_file() and path.suffix.lower() in {".tif", ".tiff"} for path in out_dir.iterdir())


def infer_result_filename(result: dict[str, Any]) -> str:
    location = result.get("location", "")
    name = result.get("name") or Path(unquote(urlparse(location).path)).name or "result"
    return Path(name).name


def search_same_day_items(feature: dict[str, Any], item_type: str, auth_header: str) -> list[dict[str, Any]]:
    payload = build_quick_search_payload(feature, item_type)
    response = request_json(PLANET_QUICK_SEARCH_URL, auth_header, method="POST", payload=payload)
    items = response.get("features", []) or []
    if not items:
        raise RuntimeError(f"No same-day Planet scenes found for {feature['obs_id']} on {feature['obs_date']}")
    selected_items = select_covering_item_window(items, feature["geometry"])
    if len(selected_items) != len(items):
        LOG.info(
            "Reduced %s scenes to %s covering scenes for %s on %s",
            len(items),
            len(selected_items),
            feature["obs_id"],
            feature["obs_date"],
        )
    return selected_items


def create_order(order_payload: dict[str, Any], auth_header: str) -> dict[str, Any]:
    return request_json(PLANET_ORDERS_URL, auth_header, method="POST", payload=order_payload)


def poll_order(order_id: str, auth_header: str, poll_seconds: int, max_polls: int) -> dict[str, Any]:
    url = f"{PLANET_ORDERS_URL}/{order_id}"
    for attempt in range(1, max_polls + 1):
        payload = request_json(url, auth_header)
        state = str(payload.get("state", ""))
        LOG.info("Order poll %s/%s: %s -> %s", attempt, max_polls, order_id, state)
        if state in FINAL_ORDER_STATES:
            return payload
        time.sleep(poll_seconds)
    raise RuntimeError(f"Timed out waiting for order {order_id}")


def download_order_results(order_payload: dict[str, Any], out_dir: Path, auth_header: str, force: bool) -> list[str]:
    results = order_payload.get("_links", {}).get("results", []) or []
    if not results:
        raise RuntimeError("Order completed without downloadable result links.")
    downloaded: list[str] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    for result in results:
        location = result.get("location")
        if not location:
            continue
        out_path = out_dir / infer_result_filename(result)
        stream_download(location, out_path, auth_header, force)
        downloaded.append(str(out_path))
    if not downloaded:
        raise RuntimeError("No downloadable Planet result files were found.")
    return downloaded


def is_split_retryable_error(message: str) -> bool:
    lowered = message.lower()
    return "exceeds the maximum allowed area" in lowered or "over quota" in lowered


def build_split_part_counts(max_split_parts: int) -> list[int]:
    counts = [1]
    current = 2
    while current <= max_split_parts:
        counts.append(current)
        current *= 2
    return counts


def run_gdal_command(command: list[str]) -> None:
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(
            "GDAL command failed: "
            + " ".join(command)
            + f"\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )


def merge_rasters(input_paths: list[Path], output_path: Path, gdal_bin_dir: Path) -> str:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if len(input_paths) == 1:
        shutil.copy2(input_paths[0], output_path)
        return str(output_path)
    vrt_path = output_path.with_suffix(".vrt")
    gdalbuildvrt = gdal_bin_dir / "gdalbuildvrt.exe"
    gdalwarp = gdal_bin_dir / "gdalwarp.exe"
    run_gdal_command([str(gdalbuildvrt), "-overwrite", str(vrt_path), *[str(path) for path in input_paths]])
    run_gdal_command(
        [
            str(gdalwarp),
            "-overwrite",
            "-of",
            "GTiff",
            "-co",
            "COMPRESS=LZW",
            str(vrt_path),
            str(output_path),
        ]
    )
    return str(output_path)


def collect_merge_targets(downloaded_files: list[str], filename: str) -> list[Path]:
    return [Path(path) for path in downloaded_files if Path(path).name.lower() == filename.lower()]


def download_single_order(
    feature: dict[str, Any],
    out_dir: Path,
    args: argparse.Namespace,
    auth_header: str,
) -> dict[str, Any]:
    items = search_same_day_items(feature, args.item_type, auth_header)
    if existing_download_complete(out_dir) and not args.force:
        return {
            "items": items,
            "order_ids": [],
            "order_states": ["already_downloaded"],
            "downloaded_files": [str(path) for path in out_dir.iterdir() if path.is_file()],
        }
    if args.dry_run:
        return {
            "items": items,
            "order_ids": [],
            "order_states": ["dry_run"],
            "downloaded_files": [],
        }

    order_payload = build_order_payload(
        obs_id=feature["obs_id"],
        obs_date=feature["obs_date"],
        item_type=args.item_type,
        item_ids=[item["id"] for item in items],
        geometry=feature["geometry"],
        product_bundle=args.product_bundle,
        order_name_suffix=feature_order_suffix(feature),
    )
    created_order = create_order(order_payload, auth_header)
    order_id = created_order["id"]
    final_order = poll_order(order_id, auth_header, args.poll_seconds, args.max_polls)
    order_state = str(final_order.get("state", ""))
    if order_state not in {"success", "partial"}:
        raise RuntimeError(
            f"Order {order_id} finished in state {order_state}: {str(final_order.get('last_message') or '').strip()}"
        )
    downloaded_files = download_order_results(final_order, out_dir, auth_header, args.force)
    (out_dir / f"{order_id}_order.json").write_text(json.dumps(final_order, indent=2), encoding="utf-8")
    return {
        "items": items,
        "order_ids": [order_id],
        "order_states": [order_state],
        "downloaded_files": downloaded_files,
    }


def download_feature_plan(feature: dict[str, Any], args: argparse.Namespace, auth_header: str, part_count: int) -> dict[str, Any]:
    out_dir = output_dir_for_feature(args.download_dir, feature["obs_date"], feature["obs_id"])
    if part_count == 1:
        result = download_single_order(feature, out_dir, args, auth_header)
        status = "ok"
        if result["order_states"] == ["already_downloaded"]:
            status = "already_downloaded"
        if result["order_states"] == ["dry_run"]:
            status = "dry_run"
        return build_summary_row(
            feature,
            result["items"],
            order_id=";".join(result["order_ids"]),
            order_state=";".join(result["order_states"]),
            output_dir=str(out_dir),
            downloaded_files=result["downloaded_files"],
            status=status,
        )

    all_items: list[dict[str, Any]] = []
    all_order_ids: list[str] = []
    all_order_states: list[str] = []
    all_downloaded_files: list[str] = []
    split_features = split_feature_geometry(feature, part_count)
    for split_feature in split_features:
        split_out_dir = part_output_dir(out_dir, split_feature["part_index"], split_feature["part_total"])
        result = download_single_order(split_feature, split_out_dir, args, auth_header)
        all_items.extend(result["items"])
        all_order_ids.extend(result["order_ids"])
        all_order_states.extend(result["order_states"])
        all_downloaded_files.extend(result["downloaded_files"])

    if not args.dry_run:
        composite_inputs = collect_merge_targets(all_downloaded_files, "composite.tif")
        if composite_inputs:
            all_downloaded_files.append(merge_rasters(composite_inputs, out_dir / "composite.tif", args.gdal_bin_dir))
        udm_inputs = collect_merge_targets(all_downloaded_files, "composite_udm2.tif")
        if udm_inputs:
            all_downloaded_files.append(merge_rasters(udm_inputs, out_dir / "composite_udm2.tif", args.gdal_bin_dir))

    unique_items = {item["id"]: item for item in all_items}
    status = "ok"
    if all_order_states and all(state == "already_downloaded" for state in all_order_states):
        status = "already_downloaded"
    elif all_order_states and all(state == "dry_run" for state in all_order_states):
        status = "dry_run"
    return build_summary_row(
        feature,
        list(unique_items.values()),
        order_id=";".join(all_order_ids),
        order_state=";".join(all_order_states),
        output_dir=str(out_dir),
        downloaded_files=sorted(set(all_downloaded_files)),
        status=status,
    )


def download_feature(feature: dict[str, Any], args: argparse.Namespace, auth_header: str) -> dict[str, Any]:
    last_error: Exception | None = None
    for part_count in build_split_part_counts(args.max_split_parts):
        try:
            if part_count > 1:
                LOG.info("Retrying %s on %s as %s split composites", feature["obs_id"], feature["obs_date"], part_count)
            return download_feature_plan(feature, args, auth_header, part_count)
        except Exception as exc:
            last_error = exc
            if part_count >= args.max_split_parts or not is_split_retryable_error(str(exc)):
                raise
            LOG.warning("Split retry triggered for %s on %s after %s-part attempt: %s", feature["obs_id"], feature["obs_date"], part_count, exc)
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Failed to process feature {feature['obs_id']}")


def write_summary_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "obs_id",
        "obs_date",
        "pt_count",
        "item_ids",
        "item_count",
        "planet_acquired_start",
        "planet_acquired_end",
        "order_id",
        "order_state",
        "output_dir",
        "downloaded_files",
        "status",
        "error",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out = row.copy()
            if isinstance(out.get("item_ids"), list):
                out["item_ids"] = ";".join(out["item_ids"])
            if isinstance(out.get("downloaded_files"), list):
                out["downloaded_files"] = ";".join(out["downloaded_files"])
            writer.writerow({key: out.get(key, "") for key in fieldnames})


def build_summary_row(
    feature: dict[str, Any],
    items: list[dict[str, Any]],
    *,
    order_id: str = "",
    order_state: str = "",
    output_dir: str = "",
    downloaded_files: list[str] | None = None,
    status: str,
    error: str = "",
) -> dict[str, Any]:
    acquired_values = [item.get("properties", {}).get("acquired", "") for item in items]
    acquired_values = [value for value in acquired_values if value]
    return {
        "obs_id": feature["obs_id"],
        "obs_date": feature["obs_date"],
        "pt_count": feature.get("pt_count", 0),
        "item_ids": [item["id"] for item in items],
        "item_count": len(items),
        "planet_acquired_start": min(acquired_values) if acquired_values else "",
        "planet_acquired_end": max(acquired_values) if acquired_values else "",
        "order_id": order_id,
        "order_state": order_state,
        "output_dir": output_dir,
        "downloaded_files": downloaded_files or [],
        "status": status,
        "error": error,
    }


def main() -> int:
    args = parse_args()
    configure_logging(args.log_level)

    api_key = read_api_key(args.api_key_file)
    auth_header = authorization_header(api_key)
    features = filter_requested_features(
        load_bounds_features(args.bounds_shapefile, args.ogrinfo_path),
        set(args.obs_id),
    )
    summary_rows: list[dict[str, Any]] = []
    failures = 0

    for feature in features:
        try:
            LOG.info("Resolving Planet scenes for %s on %s", feature["obs_id"], feature["obs_date"])
            summary_rows.append(download_feature(feature, args, auth_header))
        except Exception as exc:
            failures += 1
            LOG.error("Failed %s (%s): %s", feature["obs_id"], feature["obs_date"], exc)
            summary_rows.append(
                {
                    "obs_id": feature["obs_id"],
                    "obs_date": feature["obs_date"],
                    "pt_count": feature.get("pt_count", 0),
                    "item_ids": [],
                    "item_count": 0,
                    "planet_acquired_start": "",
                    "planet_acquired_end": "",
                    "order_id": "",
                    "order_state": "",
                    "output_dir": str(output_dir_for_feature(args.download_dir, feature["obs_date"], feature["obs_id"])),
                    "downloaded_files": [],
                    "status": "failed",
                    "error": str(exc),
                }
            )

    write_summary_csv(args.summary_csv, summary_rows)
    args.summary_json.write_text(
        json.dumps(
            {
                "bounds_shapefile": str(args.bounds_shapefile),
                "download_dir": str(args.download_dir),
                "dry_run": args.dry_run,
                "rows": summary_rows,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    LOG.info("Wrote summary CSV: %s", args.summary_csv)
    LOG.info("Wrote summary JSON: %s", args.summary_json)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
