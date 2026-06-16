#!/usr/bin/env python3
"""
Download clipped Sentinel-2 bands for scene-level Ocean Scan bounding boxes.

This script reads the CSV produced by `build_sentinel_scene_directory.py`,
fetches each matching S2 item from the Planetary Computer STAC API, signs the
band HREFs, and writes only the subset covering the source-scene bbox.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import rasterio
import requests
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds
from urllib3.util.retry import Retry


LOG = logging.getLogger("download_s2_scene_clips")

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
SAS_TOKEN_URL = "https://planetarycomputer.microsoft.com/api/sas/v1/token"
DEFAULT_BANDS = ["B02", "B03", "B04", "B06", "B08", "B11"]
REQUEST_TIMEOUT = 120

TOKEN_CACHE: dict[tuple[str, str], dict[str, Any]] = {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download clipped Sentinel-2 bands for each row in an S2 scene "
            "directory CSV."
        )
    )
    parser.add_argument(
        "catalog_csv",
        type=Path,
        help="CSV created by build_sentinel_scene_directory.py",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("s2_scene_clips"),
        help="Directory where clipped rasters will be written.",
    )
    parser.add_argument(
        "--bands",
        nargs="+",
        default=DEFAULT_BANDS,
        help=f"Bands to download. Default: {' '.join(DEFAULT_BANDS)}",
    )
    parser.add_argument(
        "--source-scene",
        action="append",
        default=[],
        help="Only download clips for the named source scene(s).",
    )
    parser.add_argument(
        "--s2-item-id",
        action="append",
        default=[],
        help="Only download the listed S2 item ID(s).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing clipped files.",
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
        allowed_methods=["GET"],
    )
    adapter = requests.adapters.HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def sanitize_stem(name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem)
    return stem.strip("_") or "scene"


def parse_dt(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def read_catalog_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def fetch_item(session: requests.Session, collection: str, item_id: str) -> dict[str, Any]:
    response = session.get(
        f"{STAC_URL}/collections/{collection}/items/{item_id}",
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def parse_blob_account_container(url: str) -> tuple[str, str] | None:
    parsed = urlparse(url.rstrip("/"))
    if not parsed.netloc.endswith(".blob.core.windows.net"):
        return None
    if parsed.netloc == "ai4edatasetspublicassets.blob.core.windows.net":
        return None
    path_parts = [part for part in parsed.path.split("/") if part]
    if not path_parts:
        return None
    account = parsed.netloc.split(".")[0]
    container = path_parts[0]
    return account, container


def get_sas_token(session: requests.Session, account: str, container: str) -> dict[str, Any]:
    key = (account, container)
    cached = TOKEN_CACHE.get(key)
    if cached is not None:
        expiry = parse_dt(cached["msft:expiry"])
        if (expiry - datetime.now(timezone.utc)).total_seconds() > 60:
            return cached

    response = session.get(
        f"{SAS_TOKEN_URL}/{account}/{container}",
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    token = response.json()
    TOKEN_CACHE[key] = token
    return token


def sign_href(session: requests.Session, href: str) -> str:
    parsed = urlparse(href)
    if set(parse_qs(parsed.query)) & {"st", "se", "sp"}:
        return href

    account_container = parse_blob_account_container(href)
    if account_container is None:
        return href

    account, container = account_container
    token = get_sas_token(session, account, container)["token"]
    separator = "&" if "?" in href else "?"
    return f"{href}{separator}{token}"


def intersect_bounds(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> tuple[float, float, float, float] | None:
    minx = max(a[0], b[0])
    miny = max(a[1], b[1])
    maxx = min(a[2], b[2])
    maxy = min(a[3], b[3])
    if minx >= maxx or miny >= maxy:
        return None
    return (minx, miny, maxx, maxy)


def clip_asset_to_bbox(
    session: requests.Session,
    href: str,
    bbox_wgs84: tuple[float, float, float, float],
    out_path: Path,
    overwrite: bool,
) -> Path | None:
    if out_path.exists() and not overwrite:
        return out_path

    signed_href = sign_href(session, href)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
        with rasterio.open(signed_href) as src:
            projected = transform_bounds(
                "EPSG:4326",
                src.crs,
                *bbox_wgs84,
                densify_pts=21,
            )
            clipped_bounds = intersect_bounds(projected, src.bounds)
            if clipped_bounds is None:
                LOG.warning("No overlap between bbox and asset %s", href)
                return None

            window = from_bounds(*clipped_bounds, transform=src.transform)
            window = window.round_offsets().round_lengths()
            data = src.read(window=window)
            if data.size == 0:
                LOG.warning("Empty read window for asset %s", href)
                return None

            profile = src.profile.copy()
            profile.update(
                transform=src.window_transform(window),
                width=data.shape[-1],
                height=data.shape[-2],
                compress="deflate",
            )

            with rasterio.open(out_path, "w", **profile) as dst:
                dst.write(data)
    return out_path


def write_clip_metadata(path: Path, row: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s: %(message)s",
    )

    rows = read_catalog_rows(args.catalog_csv)
    if args.source_scene:
        wanted = set(args.source_scene)
        rows = [row for row in rows if row.get("source_scene_name") in wanted]
    if args.s2_item_id:
        wanted = set(args.s2_item_id)
        rows = [row for row in rows if row.get("s2_item_id") in wanted]

    rows = [row for row in rows if row.get("s2_item_id")]
    if not rows:
        LOG.warning("No matching S2 catalogue rows to download.")
        return

    session = build_session()

    for index, row in enumerate(rows, start=1):
        source_scene_name = row["source_scene_name"]
        source_scene_stem = row.get("source_scene_stem") or sanitize_stem(source_scene_name)
        s2_item_id = row["s2_item_id"]
        s2_collection = row["s2_collection"]
        s2_datetime = row["s2_datetime"]
        s2_tile = row.get("s2_mgrs_tile") or "unknown_tile"
        day = s2_datetime[:10]

        LOG.info(
            "[%s/%s] Downloading S2 clip for %s -> %s",
            index,
            len(rows),
            source_scene_name,
            s2_item_id,
        )

        bbox_wgs84 = (
            float(row["scene_min_lon"]),
            float(row["scene_min_lat"]),
            float(row["scene_max_lon"]),
            float(row["scene_max_lat"]),
        )

        item = fetch_item(session, s2_collection, s2_item_id)
        assets = item.get("assets", {})

        out_dir = args.output_dir / source_scene_stem / f"{day}_{s2_tile}_{s2_item_id}"
        write_clip_metadata(out_dir / "clip_metadata.json", row)

        for band in args.bands:
            asset = assets.get(band)
            if asset is None:
                LOG.warning("Band %s missing on %s", band, s2_item_id)
                continue

            out_path = out_dir / f"S2_{source_scene_stem}_{day}_{s2_tile}_{band}.tif"
            clip_asset_to_bbox(
                session=session,
                href=asset["href"],
                bbox_wgs84=bbox_wgs84,
                out_path=out_path,
                overwrite=args.overwrite,
            )

    LOG.info("Finished writing clips to %s", args.output_dir)


if __name__ == "__main__":
    main()
