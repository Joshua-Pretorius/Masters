#!/usr/bin/env python3
"""
Download clipped Planet scenes for a subset of Ocean Scan observations.

Behavior:
- Reads the observation ID allowlist from a DOCX file.
- Filters the Ocean Scan JSON down to only those polygon patch observations.
- Resolves the nearest Planet item for each observation.
- Creates a Planet Orders API clip order using the observation bounding box
  expanded by an approximate 5 km buffer.
- Downloads the clipped order results into a per-observation folder.

This replaces the previous full-scene batch download behavior for quota control.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import re
import time
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import download_oceanscan_planet_scene as dl
from shapely.geometry import mapping, shape


LOG = logging.getLogger("planet_batch_download")

PLANET_ORDERS_URL = "https://api.planet.com/compute/ops/orders/v2"
FINAL_ORDER_STATES = {"success", "partial", "failed", "cancelled"}
DEFAULT_PRODUCT_BUNDLE = "analytic_udm2,analytic_8b_udm2"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve and download clipped Planet scenes for selected Ocean Scan "
            "observations listed in a DOCX file."
        )
    )
    parser.add_argument("input_json", type=Path, help="Ocean Scan campaign JSON")
    parser.add_argument(
        "--api-key-file",
        type=Path,
        required=True,
        help="Text file containing the Planet API key",
    )
    parser.add_argument(
        "--obs-id-docx",
        type=Path,
        default=Path(r"D:\Masters\MERIA\MERIA_IDS_OF_INTERESTS.docx"),
        help="DOCX file containing the observation IDs to download.",
    )
    parser.add_argument(
        "--download-dir",
        type=Path,
        default=Path(r"D:\Masters\MERIA\MERIA_Planet"),
        help="Directory where clipped order results will be written.",
    )
    parser.add_argument(
        "--item-type",
        default=dl.DEFAULT_ITEM_TYPE,
        help=f"Planet item type to query. Default: {dl.DEFAULT_ITEM_TYPE}",
    )
    parser.add_argument(
        "--product-bundle",
        default=DEFAULT_PRODUCT_BUNDLE,
        help=(
            "Orders product bundle string. Default prefers 4-band analytic clipped "
            "imagery, then 8-band if needed."
        ),
    )
    parser.add_argument(
        "--buffer-km",
        type=float,
        default=5.0,
        help="Approximate buffer in kilometers added to the observation bbox.",
    )
    parser.add_argument(
        "--search-windows-hours",
        nargs="+",
        type=int,
        default=[12, 24, 72, 168, 720],
        help="Progressive search windows in hours around the observation timestamp.",
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
        help="Maximum number of order-status polls before exiting.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download result files even if they already exist.",
    )
    parser.add_argument(
        "--summary-csv",
        type=Path,
        default=Path(r"D:\Masters\MERIA\MERIA_Planet\planet_batch_download_summary.csv"),
        help="CSV summary output path.",
    )
    parser.add_argument(
        "--summary-json",
        type=Path,
        default=Path(r"D:\Masters\MERIA\MERIA_Planet\planet_batch_download_summary.json"),
        help="JSON summary output path.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Console log level.",
    )
    return parser.parse_args()


def read_docx_obs_ids(docx_path: Path) -> list[str]:
    pattern = re.compile(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
    )
    with zipfile.ZipFile(docx_path) as zf:
        xml = zf.read("word/document.xml").decode("utf-8", errors="replace")
    seen: set[str] = set()
    ordered: list[str] = []
    for obs_id in pattern.findall(xml):
        obs_id = obs_id.lower()
        if obs_id not in seen:
            seen.add(obs_id)
            ordered.append(obs_id)
    return ordered


def filter_patches_by_obs_ids(
    patches: list[dict[str, Any]], obs_ids: list[str]
) -> tuple[list[dict[str, Any]], list[str]]:
    patch_map = {str(p["obs_id"]).lower(): p for p in patches}
    selected: list[dict[str, Any]] = []
    missing: list[str] = []
    for obs_id in obs_ids:
        patch = patch_map.get(obs_id.lower())
        if patch is None:
            missing.append(obs_id)
        else:
            selected.append(patch)
    return selected, missing


def buffered_bbox_aoi(geometry: dict[str, Any], buffer_km: float) -> dict[str, Any]:
    geom = shape(geometry)
    if not geom.is_valid:
        geom = geom.buffer(0)
    minx, miny, maxx, maxy = geom.bounds
    centroid_lat = max(min(geom.centroid.y, 89.9999), -89.9999)
    delta_lat = buffer_km / 110.574
    cos_lat = math.cos(math.radians(centroid_lat))
    if abs(cos_lat) < 1e-6:
        delta_lon = buffer_km / 111.320
    else:
        delta_lon = buffer_km / (111.320 * abs(cos_lat))
    minx = max(-180.0, minx - delta_lon)
    maxx = min(180.0, maxx + delta_lon)
    miny = max(-90.0, miny - delta_lat)
    maxy = min(90.0, maxy + delta_lat)
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [minx, miny],
                [maxx, miny],
                [maxx, maxy],
                [minx, maxy],
                [minx, miny],
            ]
        ],
    }


def create_clip_order(
    session: Any,
    item_type: str,
    item_id: str,
    obs_id: str,
    aoi: dict[str, Any],
    product_bundle: str,
) -> dict[str, Any]:
    payload = {
        "name": f"oceanscan_{obs_id}_{item_id}",
        "source_type": "scenes",
        "order_type": "partial",
        "products": [
            {
                "item_ids": [item_id],
                "item_type": item_type,
                "product_bundle": product_bundle,
            }
        ],
        "tools": [{"clip": {"aoi": aoi}}],
    }
    response = session.post(PLANET_ORDERS_URL, json=payload, timeout=120)
    response.raise_for_status()
    return response.json()


def poll_order(session: Any, order_id: str, poll_seconds: int, max_polls: int) -> dict[str, Any]:
    order_url = f"{PLANET_ORDERS_URL}/{order_id}"
    for attempt in range(1, max_polls + 1):
        response = session.get(order_url, timeout=120)
        response.raise_for_status()
        payload = response.json()
        state = str(payload.get("state", ""))
        LOG.info("Order poll %s/%s: order_id=%s state=%s", attempt, max_polls, order_id, state)
        if state in FINAL_ORDER_STATES:
            return payload
        time.sleep(poll_seconds)
    raise RuntimeError(f"Timed out waiting for order {order_id} after {max_polls} polls.")


def download_order_results(
    session: Any,
    order_payload: dict[str, Any],
    out_dir: Path,
    force: bool,
) -> list[str]:
    results = order_payload.get("_links", {}).get("results", []) or []
    if not results:
        raise RuntimeError("Order completed without downloadable results.")

    out_dir.mkdir(parents=True, exist_ok=True)
    downloaded_paths: list[str] = []
    for result in results:
        location = result.get("location")
        if not location:
            continue
        name = result.get("name") or Path(unquote(urlparse(location).path)).name or "result"
        filename = Path(name).name
        out_path = out_dir / filename
        dl.stream_download(session, location, out_path, force)
        downloaded_paths.append(str(out_path))
    if not downloaded_paths:
        raise RuntimeError("Order results were present but none had downloadable locations.")
    return downloaded_paths


def write_summary_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "patch_index",
        "obs_id",
        "source_id",
        "patch_timestamp",
        "planet_item_id",
        "planet_acquired",
        "delta_hours",
        "search_window_hours",
        "order_id",
        "order_state",
        "product_bundle",
        "output_dir",
        "downloaded_files",
        "status",
        "error",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out = row.copy()
            if isinstance(out.get("downloaded_files"), list):
                out["downloaded_files"] = ";".join(out["downloaded_files"])
            writer.writerow({key: out.get(key, "") for key in fieldnames})


def main() -> int:
    args = parse_args()
    dl.configure_logging(args.log_level)

    args.input_json = dl.adapt_path(args.input_json)
    args.api_key_file = dl.adapt_path(args.api_key_file)
    args.obs_id_docx = dl.adapt_path(args.obs_id_docx)
    args.download_dir = dl.adapt_path(args.download_dir)
    args.summary_csv = dl.adapt_path(args.summary_csv)
    args.summary_json = dl.adapt_path(args.summary_json)

    api_key = dl.read_api_key(args.api_key_file)
    session = dl.planet_session(api_key)
    patches = dl.load_patch_records(args.input_json)
    obs_ids = read_docx_obs_ids(args.obs_id_docx)
    selected_patches, missing_obs_ids = filter_patches_by_obs_ids(patches, obs_ids)

    LOG.info("Loaded %s polygon patch observations from JSON", len(patches))
    LOG.info("Loaded %s observation IDs from DOCX", len(obs_ids))
    LOG.info("Matched %s observations from the allowlist", len(selected_patches))
    if missing_obs_ids:
        LOG.warning("Observation IDs from DOCX not found in JSON: %s", len(missing_obs_ids))

    args.download_dir.mkdir(parents=True, exist_ok=True)
    summary_rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for idx, patch in enumerate(selected_patches, start=1):
        patch_tag = f"{idx:03d}/{len(selected_patches):03d}"
        try:
            LOG.info(
                "Processing observation %s: obs_id=%s timestamp=%s",
                patch_tag,
                patch["obs_id"],
                patch["timestamp"],
            )
            window_hours, feature, _payload = dl.search_nearest_item(
                session=session,
                patch=patch,
                item_type=args.item_type,
                search_windows_hours=args.search_windows_hours,
            )
            item_id = feature["id"]
            acquired = feature.get("properties", {}).get("acquired", "")
            delta_hours = abs(
                (dl.parse_utc(acquired) - dl.parse_utc(patch["timestamp"])).total_seconds()
            ) / 3600.0

            aoi = buffered_bbox_aoi(patch["geometry"], args.buffer_km)
            LOG.info(
                "Submitting clip order: obs_id=%s item_id=%s bundle=%s buffer_km=%.2f",
                patch["obs_id"],
                item_id,
                args.product_bundle,
                args.buffer_km,
            )
            order = create_clip_order(
                session=session,
                item_type=args.item_type,
                item_id=item_id,
                obs_id=patch["obs_id"],
                aoi=aoi,
                product_bundle=args.product_bundle,
            )
            order_id = order["id"]
            final_order = poll_order(session, order_id, args.poll_seconds, args.max_polls)
            order_state = str(final_order.get("state", ""))
            if order_state not in {"success", "partial"}:
                raise RuntimeError(f"Order {order_id} finished in state {order_state}")

            obs_dir = args.download_dir / patch["obs_id"]
            downloaded_files = download_order_results(
                session=session,
                order_payload=final_order,
                out_dir=obs_dir,
                force=args.force,
            )
            order_json_path = obs_dir / f"{order_id}_order.json"
            order_json_path.write_text(json.dumps(final_order, indent=2), encoding="utf-8")
            LOG.info("Wrote order record: %s", order_json_path)

            summary_rows.append(
                {
                    "patch_index": patch["patch_index"],
                    "obs_id": patch["obs_id"],
                    "source_id": patch["source_id"],
                    "patch_timestamp": patch["timestamp"],
                    "planet_item_id": item_id,
                    "planet_acquired": acquired,
                    "delta_hours": round(delta_hours, 3),
                    "search_window_hours": window_hours,
                    "order_id": order_id,
                    "order_state": order_state,
                    "product_bundle": args.product_bundle,
                    "output_dir": str(obs_dir),
                    "downloaded_files": downloaded_files,
                    "status": "ok",
                    "error": "",
                }
            )
        except Exception as exc:
            LOG.error("Failed observation %s (%s): %s", patch_tag, patch["obs_id"], exc)
            failure = {
                "patch_index": patch["patch_index"],
                "obs_id": patch["obs_id"],
                "source_id": patch["source_id"],
                "patch_timestamp": patch["timestamp"],
                "planet_item_id": "",
                "planet_acquired": "",
                "delta_hours": "",
                "search_window_hours": "",
                "order_id": "",
                "order_state": "",
                "product_bundle": args.product_bundle,
                "output_dir": "",
                "downloaded_files": [],
                "status": "failed",
                "error": str(exc),
            }
            summary_rows.append(failure)
            failures.append(failure)

    for missing_obs_id in missing_obs_ids:
        summary_rows.append(
            {
                "patch_index": "",
                "obs_id": missing_obs_id,
                "source_id": "",
                "patch_timestamp": "",
                "planet_item_id": "",
                "planet_acquired": "",
                "delta_hours": "",
                "search_window_hours": "",
                "order_id": "",
                "order_state": "",
                "product_bundle": args.product_bundle,
                "output_dir": "",
                "downloaded_files": [],
                "status": "missing_from_json",
                "error": "Observation ID was present in DOCX but not found in the JSON patch set.",
            }
        )

    write_summary_csv(args.summary_csv, summary_rows)
    summary_json = {
        "input_json": str(args.input_json),
        "obs_id_docx": str(args.obs_id_docx),
        "download_dir": str(args.download_dir),
        "requested_observation_ids": len(obs_ids),
        "matched_observations": len(selected_patches),
        "missing_observation_ids": missing_obs_ids,
        "successful_downloads": sum(1 for row in summary_rows if row["status"] == "ok"),
        "failed_downloads": len(failures),
        "summary_csv": str(args.summary_csv),
        "rows": summary_rows,
    }
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary_json, indent=2), encoding="utf-8")

    LOG.info("Wrote summary CSV: %s", args.summary_csv)
    LOG.info("Wrote summary JSON: %s", args.summary_json)
    LOG.info("Successful observations: %s", summary_json["successful_downloads"])
    LOG.info("Failed observations: %s", summary_json["failed_downloads"])
    LOG.info("Missing DOCX IDs: %s", len(missing_obs_ids))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
