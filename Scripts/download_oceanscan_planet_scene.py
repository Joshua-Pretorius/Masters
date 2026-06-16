#!/usr/bin/env python3
"""
Resolve and download a Planet scene for one Ocean Scan patch observation.

Examples:
  python3 Scripts/download_oceanscan_planet_scene.py \
    "/mnt/d/Masters/ocean-scan-mireia-- marine litter signatures in sar images-e71e8ee6-e41d-4889-bb08-a821fb5e8bbd.json" \
    --api-key-file "/mnt/d/Masters/planet_api.txt" \
    --patch-index 1 \
    --download-dir "/mnt/d/Masters/MERIA/MERIA_Planet"

  python3 Scripts/download_oceanscan_planet_scene.py \
    "/mnt/d/Masters/ocean-scan-mireia-- marine litter signatures in sar images-e71e8ee6-e41d-4889-bb08-a821fb5e8bbd.json" \
    --api-key-file "/mnt/d/Masters/planet_api.txt" \
    --obs-id "6ec629af-9109-48b3-99f4-9ca1efcc30ab" \
    --asset ortho_analytic_4b \
    --download-dir "/mnt/d/Masters/MERIA/MERIA_Planet"

  python3 Scripts/download_oceanscan_planet_scene.py \
    "/mnt/d/Masters/ocean-scan-mireia-- marine litter signatures in sar images-e71e8ee6-e41d-4889-bb08-a821fb5e8bbd.json" \
    --list-patches
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

try:
    import requests
except ModuleNotFoundError as exc:
    print(
        "Missing dependency: requests\n"
        f"Python executable: {sys.executable}\n"
        "Install it for this exact interpreter with:\n"
        f'  "{sys.executable}" -m pip install requests',
        file=sys.stderr,
    )
    raise SystemExit(1) from exc

try:
    from shapely.geometry import mapping, shape
except ModuleNotFoundError as exc:
    print(
        "Missing dependency: shapely\n"
        f"Python executable: {sys.executable}\n"
        "Install it for this exact interpreter with:\n"
        f'  "{sys.executable}" -m pip install shapely',
        file=sys.stderr,
    )
    raise SystemExit(1) from exc


LOG = logging.getLogger("planet_download")

PLANET_QUICK_SEARCH_URL = (
    "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250"
)
PLANET_ASSETS_URL = (
    "https://api.planet.com/data/v1/item-types/{item_type}/items/{item_id}/assets/"
)
DEFAULT_ITEM_TYPE = "PSScene"
DEFAULT_ASSET_PREFERENCES = [
    "ortho_analytic_4b_sr",
    "ortho_analytic_8b_sr",
    "ortho_analytic_4b",
    "ortho_analytic_8b",
    "analytic_sr",
    "analytic_8b_sr",
    "analytic",
    "analytic_8b",
    "ortho_visual",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve and download one Planet scene for an Ocean Scan patch."
    )
    parser.add_argument("input_json", type=Path, nargs="?", help="Ocean Scan campaign JSON")
    parser.add_argument(
        "--api-key-file",
        type=Path,
        help="Text file containing the Planet API key",
    )
    parser.add_argument(
        "--download-dir",
        type=Path,
        default=default_download_dir(),
        help="Directory where downloaded scene files will be written",
    )
    parser.add_argument(
        "--patch-index",
        type=int,
        help="1-based patch index from the filtered polygon patch list",
    )
    parser.add_argument(
        "--obs-id",
        help="Exact Ocean Scan observation ID to resolve and download",
    )
    parser.add_argument(
        "--item-type",
        default=DEFAULT_ITEM_TYPE,
        help=f"Planet item type to query. Default: {DEFAULT_ITEM_TYPE}",
    )
    parser.add_argument(
        "--asset",
        help="Exact Planet asset name to use. If omitted, the script chooses from preferences.",
    )
    parser.add_argument(
        "--asset-preferences",
        nargs="+",
        default=DEFAULT_ASSET_PREFERENCES,
        help="Ordered list of preferred asset names when --asset is not supplied.",
    )
    parser.add_argument(
        "--search-windows-hours",
        nargs="+",
        type=int,
        default=[12, 24, 72, 168, 720],
        help="Progressive search windows in hours around the patch timestamp.",
    )
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=15,
        help="Seconds between asset-status polls while waiting for activation.",
    )
    parser.add_argument(
        "--max-polls",
        type=int,
        default=40,
        help="Maximum number of asset-status polls before exiting.",
    )
    parser.add_argument(
        "--list-patches",
        action="store_true",
        help="List available polygon patches and exit.",
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Resolve the Planet scene and asset but do not download the file.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if the target file already exists.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Console log level.",
    )
    args = parser.parse_args()

    if not args.list_patches and args.input_json is None:
        parser.error("input_json is required unless --list-patches is used with a default path")
    if args.patch_index is not None and args.patch_index < 1:
        parser.error("--patch-index must be >= 1")
    return args


def default_download_dir() -> Path:
    if os.name == "nt":
        return Path(r"D:\Masters\MERIA\MERIA_Planet")
    return Path("/mnt/d/Masters/MERIA/MERIA_Planet")


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def adapt_path(path: Path | None) -> Path | None:
    if path is None:
        return None

    path_str = str(path)
    if os.name == "nt":
        match = re.match(r"^/mnt/([a-zA-Z])/(.*)$", path_str)
        if match:
            drive = match.group(1).upper()
            rest = match.group(2).replace("/", "\\")
            return Path(f"{drive}:\\{rest}")
        return path

    match = re.match(r"^([a-zA-Z]):[\\/](.*)$", path_str)
    if match:
        drive = match.group(1).lower()
        rest = match.group(2).replace("\\", "/")
        return Path(f"/mnt/{drive}/{rest}")
    if re.match(r"^[a-zA-Z]:$", path_str):
        drive = path_str[0].lower()
        return Path(f"/mnt/{drive}")
    return path


def parse_utc(ts: str) -> datetime:
    ts = ts.strip().replace("Z", "+00:00")
    match = re.match(
        r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d+))?([+-]\d{2}:\d{2})$",
        ts,
    )
    if not match:
        raise ValueError(f"unrecognized timestamp format: {ts!r}")
    base, frac, tz = match.groups()
    frac = ((frac or "0")[:6]).ljust(6, "0")
    dt = datetime.strptime(base, "%Y-%m-%dT%H:%M:%S").replace(microsecond=int(frac))
    sign = 1 if tz[0] == "+" else -1
    hours = int(tz[1:3])
    minutes = int(tz[4:6])
    offset = timezone(sign * timedelta(hours=hours, minutes=minutes))
    return dt.replace(tzinfo=offset).astimezone(timezone.utc)


def format_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def human_bytes(value: int) -> str:
    size = float(value)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0 or unit == "TB":
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{value} B"


def read_api_key(api_key_file: Path | None) -> str:
    if api_key_file:
        api_key = api_key_file.read_text(encoding="utf-8").strip()
        if api_key:
            return api_key
    env_key = os.getenv("PL_API_KEY", "").strip()
    if env_key:
        return env_key
    raise RuntimeError("No Planet API key found. Use --api-key-file or set PL_API_KEY.")


def load_patch_records(input_json: Path) -> list[dict[str, Any]]:
    campaign = json.loads(input_json.read_text(encoding="utf-8"))
    patches: list[dict[str, Any]] = []
    for obs in campaign.get("observations", []):
        geometry = obs.get("geometry") or {}
        if obs.get("class") != "PATCH" or obs.get("isAbsence"):
            continue
        if geometry.get("type") not in {"Polygon", "MultiPolygon"}:
            continue
        geom = shape(geometry)
        if not geom.is_valid:
            geom = geom.buffer(0)
        centroid = geom.centroid
        patches.append(
            {
                "patch_index": len(patches) + 1,
                "obs_id": obs.get("id", ""),
                "source_id": (obs.get("extra") or {}).get("_sourceId", ""),
                "timestamp": obs.get("timestamp", ""),
                "estimated_patch_area_m2": obs.get("estimatedPatchAreaM2"),
                "centroid_lon": centroid.x,
                "centroid_lat": centroid.y,
                "geometry": mapping(geom),
            }
        )
    return patches


def list_patches(patches: list[dict[str, Any]]) -> None:
    for patch in patches:
        area = patch.get("estimated_patch_area_m2")
        area_str = f"{float(area):.3f}" if area is not None else ""
        print(
            f"{patch['patch_index']:03d} | {patch['obs_id']} | {patch['timestamp']} | "
            f"{patch['source_id']} | {patch['centroid_lon']:.6f}, {patch['centroid_lat']:.6f} | {area_str}"
        )


def choose_patch(
    patches: list[dict[str, Any]], patch_index: int | None, obs_id: str | None
) -> dict[str, Any]:
    if obs_id:
        for patch in patches:
            if patch["obs_id"] == obs_id:
                return patch
        raise RuntimeError(f"obs_id not found in polygon patch set: {obs_id}")
    if patch_index is not None:
        for patch in patches:
            if patch["patch_index"] == patch_index:
                return patch
        raise RuntimeError(f"patch_index not found: {patch_index}")
    return patches[0]


def planet_session(api_key: str) -> requests.Session:
    session = requests.Session()
    session.auth = (api_key, "")
    session.headers.update({"Content-Type": "application/json"})
    return session


def search_nearest_item(
    session: requests.Session,
    patch: dict[str, Any],
    item_type: str,
    search_windows_hours: list[int],
) -> tuple[int, dict[str, Any], dict[str, Any]]:
    obs_dt = parse_utc(patch["timestamp"])
    for window in search_windows_hours:
        payload = {
            "item_types": [item_type],
            "geometry": patch["geometry"],
            "filter": {
                "type": "DateRangeFilter",
                "field_name": "acquired",
                "config": {
                    "gte": format_utc(obs_dt - timedelta(hours=window)),
                    "lte": format_utc(obs_dt + timedelta(hours=window)),
                },
            },
        }
        LOG.info("Planet quick-search: window=%sh", window)
        response = session.post(PLANET_QUICK_SEARCH_URL, json=payload, timeout=120)
        response.raise_for_status()
        features = response.json().get("features", [])
        LOG.info("Planet quick-search returned %s candidate scenes", len(features))
        if not features:
            continue

        def delta_hours(feature: dict[str, Any]) -> float:
            acquired_dt = parse_utc(feature["properties"]["acquired"])
            return abs((acquired_dt - obs_dt).total_seconds()) / 3600.0

        nearest = min(features, key=delta_hours)
        LOG.info(
            "Selected nearest scene: item_id=%s acquired=%s delta_hours=%.3f",
            nearest.get("id", ""),
            nearest.get("properties", {}).get("acquired", ""),
            delta_hours(nearest),
        )
        return window, nearest, payload
    raise RuntimeError("No Planet scenes found within the configured search windows.")


def fetch_assets(
    session: requests.Session,
    item_type: str,
    item_id: str,
) -> tuple[str, dict[str, Any]]:
    url = PLANET_ASSETS_URL.format(item_type=item_type, item_id=item_id)
    response = session.get(url, timeout=120)
    response.raise_for_status()
    return url, response.json()


def log_assets(assets_payload: dict[str, Any]) -> None:
    LOG.info("Available downloadable assets:")
    for name, meta in sorted(assets_payload.items()):
        if not isinstance(meta, dict):
            continue
        perms = ",".join(meta.get("_permissions", []) or [])
        status = meta.get("status", "")
        if "download" in perms:
            LOG.info("  %s | status=%s | perms=%s", name, status, perms)


def choose_asset(
    assets_payload: dict[str, Any],
    explicit_asset: str | None,
    asset_preferences: list[str],
) -> str:
    downloadable = []
    for name, meta in assets_payload.items():
        if not isinstance(meta, dict):
            continue
        perms = meta.get("_permissions", []) or []
        if "download" in perms:
            downloadable.append(name)

    if explicit_asset:
        if explicit_asset not in downloadable:
            raise RuntimeError(
                f"Requested asset {explicit_asset!r} is not downloadable for this item."
            )
        return explicit_asset

    for asset in asset_preferences:
        if asset in downloadable:
            return asset

    if downloadable:
        return downloadable[0]
    raise RuntimeError("No downloadable assets available for the selected Planet scene.")


def wait_for_asset_activation(
    session: requests.Session,
    assets_url: str,
    asset_name: str,
    poll_seconds: int,
    max_polls: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    for attempt in range(1, max_polls + 1):
        response = session.get(assets_url, timeout=120)
        response.raise_for_status()
        payload = response.json()
        asset = payload.get(asset_name)
        if not isinstance(asset, dict):
            raise RuntimeError(f"Asset {asset_name!r} disappeared from the assets response.")

        status = asset.get("status", "")
        location = asset.get("location")
        LOG.info(
            "Asset poll %s/%s: asset=%s status=%s",
            attempt,
            max_polls,
            asset_name,
            status,
        )

        if status == "active" and location:
            return asset, payload

        if status == "inactive":
            activate_url = asset.get("_links", {}).get("activate")
            if not activate_url:
                raise RuntimeError(f"No activate link returned for asset {asset_name!r}.")
            LOG.info("Posting asset activation request: %s", activate_url)
            activate_response = session.post(activate_url, timeout=120)
            if activate_response.status_code not in (202, 204):
                raise RuntimeError(
                    "Planet asset activation failed: "
                    f"{activate_response.status_code} {activate_response.text[:400]}"
                )
        time.sleep(poll_seconds)

    raise RuntimeError(
        f"Timed out waiting for asset {asset_name!r} after {max_polls} polls."
    )


def infer_extension(asset_name: str, location: str) -> str:
    parsed = Path(unquote(urlparse(location).path)).name
    suffix = "".join(Path(parsed).suffixes)
    if suffix and parsed.lower() != "download":
        return suffix
    if asset_name.endswith("_xml"):
        return ".xml"
    return ".tif"


def infer_filename(item_id: str, asset_name: str, location: str) -> str:
    return f"{item_id}_{asset_name}{infer_extension(asset_name, location)}"


def stream_download(
    session: requests.Session,
    location: str,
    out_path: Path,
    force: bool,
) -> None:
    if out_path.exists() and out_path.stat().st_size > 0 and not force:
        LOG.info(
            "Output file already exists; skipping download: %s (%s)",
            out_path,
            human_bytes(out_path.stat().st_size),
        )
        return

    LOG.info("Starting file download: %s", location)
    with session.get(location, stream=True, timeout=600) as response:
        response.raise_for_status()
        total_bytes = int(response.headers.get("Content-Length", "0") or 0)
        downloaded = 0
        last_report = 0
        with out_path.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                handle.write(chunk)
                downloaded += len(chunk)
                if downloaded - last_report >= 10 * 1024 * 1024:
                    if total_bytes:
                        percent = 100.0 * downloaded / total_bytes
                        LOG.info(
                            "Download progress: %s / %s (%.1f%%)",
                            human_bytes(downloaded),
                            human_bytes(total_bytes),
                            percent,
                        )
                    else:
                        LOG.info("Download progress: %s", human_bytes(downloaded))
                    last_report = downloaded

    LOG.info(
        "Download complete: %s (%s)",
        out_path,
        human_bytes(out_path.stat().st_size),
    )


def write_metadata(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    LOG.info("Wrote metadata: %s", path)


def main() -> int:
    args = parse_args()
    configure_logging(args.log_level)

    args.input_json = adapt_path(args.input_json)
    args.api_key_file = adapt_path(args.api_key_file)
    args.download_dir = adapt_path(args.download_dir)

    if args.input_json is None:
        raise RuntimeError("input_json is required.")

    patches = load_patch_records(args.input_json)
    LOG.info("Loaded %s polygon patch observations", len(patches))

    if args.list_patches:
        list_patches(patches)
        return 0

    api_key = read_api_key(args.api_key_file)
    session = planet_session(api_key)
    patch = choose_patch(patches, args.patch_index, args.obs_id)

    LOG.info(
        "Selected patch: index=%s obs_id=%s timestamp=%s source_id=%s centroid=(%.6f, %.6f)",
        patch["patch_index"],
        patch["obs_id"],
        patch["timestamp"],
        patch["source_id"],
        patch["centroid_lon"],
        patch["centroid_lat"],
    )

    window_hours, feature, search_payload = search_nearest_item(
        session=session,
        patch=patch,
        item_type=args.item_type,
        search_windows_hours=args.search_windows_hours,
    )

    item_id = feature["id"]
    acquired = feature.get("properties", {}).get("acquired", "")
    delta_hours = abs(
        (parse_utc(acquired) - parse_utc(patch["timestamp"])).total_seconds()
    ) / 3600.0

    assets_url, assets_payload = fetch_assets(session, args.item_type, item_id)
    log_assets(assets_payload)
    asset_name = choose_asset(assets_payload, args.asset, args.asset_preferences)
    LOG.info("Chosen asset: %s", asset_name)

    asset_meta, final_assets_payload = wait_for_asset_activation(
        session=session,
        assets_url=assets_url,
        asset_name=asset_name,
        poll_seconds=args.poll_seconds,
        max_polls=args.max_polls,
    )

    location = asset_meta.get("location")
    if not location:
        raise RuntimeError("Planet marked the asset active but did not return a download URL.")

    args.download_dir.mkdir(parents=True, exist_ok=True)
    filename = infer_filename(item_id, asset_name, location)
    out_path = args.download_dir / filename
    LOG.info("Output filename: %s", out_path.name)

    if args.no_download:
        LOG.info("Skipping download because --no-download was requested")
    else:
        stream_download(session, location, out_path, args.force)

    metadata = {
        "selected_patch": patch,
        "planet_match": {
            "item_id": item_id,
            "acquired": acquired,
            "delta_hours": delta_hours,
            "search_window_hours": window_hours,
            "asset_name": asset_name,
            "assets_url": assets_url,
            "location": location,
        },
        "search_payload": search_payload,
        "feature": feature,
        "assets_payload": final_assets_payload,
        "download_path": str(out_path),
    }
    write_metadata(
        args.download_dir / f"{item_id}_{asset_name}_metadata.json",
        metadata,
    )

    LOG.info("Done")
    LOG.info("Scene item: %s", item_id)
    LOG.info("Asset: %s", asset_name)
    LOG.info("Output: %s", out_path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        LOG.error("Interrupted by user")
        raise SystemExit(130)
    except Exception as exc:
        LOG.exception("Failed: %s", exc)
        raise SystemExit(1)
