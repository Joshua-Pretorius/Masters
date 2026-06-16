#!/usr/bin/env python3
"""
Build a GeoJSON and Planet acquisition report from an Ocean Scan campaign JSON.

Outputs:
- GeoJSON with polygon patch observations only
- Markdown report describing each patch and the nearest Planet acquisition
- CSV with per-patch Planet search/download calls

If PL_API_KEY is set, the script will query Planet's Data API and resolve the
nearest PSScene item intersecting each patch. Without credentials, it still
generates ready-to-run API calls and marks the Planet match as unresolved.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from shapely.geometry import mapping, shape


PLANET_QUICK_SEARCH_URL = (
    "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250"
)
PLANET_ITEM_URL = "https://api.planet.com/data/v1/item-types/{item_type}/items/{item_id}"
PLANET_ASSETS_URL = (
    "https://api.planet.com/data/v1/item-types/{item_type}/items/{item_id}/assets"
)
PLANET_ORDERS_URL = "https://api.planet.com/compute/ops/orders/v2"

DEFAULT_ITEM_TYPE = "PSScene"
DEFAULT_WINDOWS_HOURS = (12, 24, 72, 168, 720)
DEFAULT_PRODUCT_BUNDLE = "analytic_udm2,analytic_8b_udm2"


@dataclass
class PlanetMatch:
    status: str
    item_id: str = ""
    acquired: str = ""
    delta_hours: str = ""
    search_window_hours: str = ""
    available_assets: str = ""
    preferred_asset_type: str = ""
    product_bundle: str = DEFAULT_PRODUCT_BUNDLE
    cloud_cover: str = ""
    clear_percent: str = ""
    quality_category: str = ""
    error: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build GeoJSON + Planet report from Ocean Scan patch JSON."
    )
    parser.add_argument("input_json", type=Path, help="Ocean Scan campaign JSON path")
    parser.add_argument(
        "--out-geojson",
        type=Path,
        help="Output GeoJSON path. Defaults next to input JSON.",
    )
    parser.add_argument(
        "--out-report",
        type=Path,
        help="Output Markdown report path. Defaults next to input JSON.",
    )
    parser.add_argument(
        "--out-csv",
        type=Path,
        help="Output CSV path. Defaults next to input JSON.",
    )
    parser.add_argument(
        "--planet-api-key",
        default=os.getenv("PL_API_KEY", ""),
        help="Planet API key. Defaults to PL_API_KEY env var.",
    )
    parser.add_argument(
        "--item-type",
        default=DEFAULT_ITEM_TYPE,
        help=f"Planet item type to search. Default: {DEFAULT_ITEM_TYPE}",
    )
    parser.add_argument(
        "--search-windows-hours",
        nargs="+",
        type=int,
        default=list(DEFAULT_WINDOWS_HOURS),
        help="Progressive Planet search windows in hours. Default: 12 24 72 168 720",
    )
    return parser.parse_args()


def parse_utc(timestamp: str | None) -> datetime | None:
    if not timestamp:
        return None
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(
        timezone.utc
    )


def fmt_utc(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def format_float(value: Any, digits: int = 6) -> str:
    if value is None or value == "":
        return ""
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "ocean_scan_campaign"


def default_output_paths(input_json: Path) -> tuple[Path, Path, Path]:
    stem = slugify(input_json.stem)
    base = input_json.parent
    return (
        base / f"{stem}_patches.geojson",
        base / f"{stem}_planet_report.md",
        base / f"{stem}_planet_requests.csv",
    )


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def canonical_geometry(geometry: dict[str, Any]) -> dict[str, Any]:
    geom = shape(geometry)
    if not geom.is_valid:
        geom = geom.buffer(0)
    return mapping(geom)


def load_patch_records(input_json: Path) -> tuple[dict[str, Any], list[dict[str, Any]], int]:
    campaign = json.loads(input_json.read_text(encoding="utf-8"))
    observations = campaign.get("observations", [])
    patch_records: list[dict[str, Any]] = []
    skipped = 0

    for idx, obs in enumerate(observations, start=1):
        geometry = obs.get("geometry")
        if not geometry:
            skipped += 1
            continue
        if obs.get("class") != "PATCH" or obs.get("isAbsence"):
            skipped += 1
            continue
        if geometry.get("type") not in {"Polygon", "MultiPolygon"}:
            skipped += 1
            continue

        geom = shape(geometry)
        centroid = geom.centroid
        record = {
            "patch_index": len(patch_records) + 1,
            "source_observation_index": idx,
            "obs_id": obs.get("id", ""),
            "source_id": (obs.get("extra") or {}).get("_sourceId", ""),
            "timestamp": obs.get("timestamp", ""),
            "class": obs.get("class", ""),
            "validation_type": obs.get("validationType", ""),
            "source_type": obs.get("sourceType", ""),
            "estimated_patch_area_m2": obs.get("estimatedPatchAreaM2"),
            "estimated_area_above_surface_m2": obs.get("estimatedAreaAboveSurfaceM2"),
            "estimated_filament_length_m": obs.get("estimatedFilamentLengthM"),
            "depth_m": obs.get("depthM"),
            "comments": obs.get("comments", "") or "",
            "centroid_lon": centroid.x,
            "centroid_lat": centroid.y,
            "geometry": canonical_geometry(geometry),
        }
        patch_records.append(record)

    return campaign, patch_records, skipped


def build_geojson_feature(record: dict[str, Any]) -> dict[str, Any]:
    props = {
        "patch_index": record["patch_index"],
        "source_observation_index": record["source_observation_index"],
        "obs_id": record["obs_id"],
        "source_id": record["source_id"],
        "timestamp": record["timestamp"],
        "class": record["class"],
        "validation_type": record["validation_type"],
        "source_type": record["source_type"],
        "estimated_patch_area_m2": record["estimated_patch_area_m2"],
        "estimated_area_above_surface_m2": record["estimated_area_above_surface_m2"],
        "estimated_filament_length_m": record["estimated_filament_length_m"],
        "depth_m": record["depth_m"],
        "comments": record["comments"],
        "centroid_lon": round(record["centroid_lon"], 8),
        "centroid_lat": round(record["centroid_lat"], 8),
    }
    return {
        "type": "Feature",
        "id": record["obs_id"],
        "properties": props,
        "geometry": record["geometry"],
    }


def write_geojson(path: Path, features: list[dict[str, Any]]) -> None:
    ensure_parent(path)
    collection = {"type": "FeatureCollection", "features": features}
    path.write_text(json.dumps(collection, indent=2), encoding="utf-8")


def build_search_payload(
    geometry: dict[str, Any], center_dt: datetime | None, window_hours: int, item_type: str
) -> dict[str, Any]:
    if center_dt is None:
        gte = "1970-01-01T00:00:00Z"
        lte = "2100-01-01T00:00:00Z"
    else:
        start = center_dt - timedelta(hours=window_hours)
        end = center_dt + timedelta(hours=window_hours)
        gte = fmt_utc(start)
        lte = fmt_utc(end)
    return {
        "item_types": [item_type],
        "geometry": geometry,
        "filter": {
            "type": "DateRangeFilter",
            "field_name": "acquired",
            "config": {"gte": gte, "lte": lte},
        },
    }


def build_quick_search_curl(payload: dict[str, Any]) -> str:
    return (
        'curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" '
        '-u "$PL_API_KEY:" '
        '-H "Content-Type: application/json" '
        f"-d '{json.dumps(payload, separators=(',', ':'))}'"
    )


def build_item_curl(item_type: str, item_id: str) -> str:
    url = PLANET_ITEM_URL.format(item_type=item_type, item_id=item_id)
    return f'curl -u "$PL_API_KEY:" "{url}"'


def build_assets_curl(item_type: str, item_id: str) -> str:
    url = PLANET_ASSETS_URL.format(item_type=item_type, item_id=item_id)
    return f'curl -u "$PL_API_KEY:" "{url}"'


def build_activate_curl(item_type: str, item_id: str, asset_type: str) -> str:
    url = PLANET_ASSETS_URL.format(item_type=item_type, item_id=item_id)
    return f'curl -X POST -u "$PL_API_KEY:" "{url}/{asset_type}/activate"'


def build_order_payload(
    patch_name: str,
    item_type: str,
    item_id: str,
    geometry: dict[str, Any],
    product_bundle: str,
) -> dict[str, Any]:
    return {
        "name": patch_name,
        "source_type": "scenes",
        "products": [
            {
                "item_ids": [item_id],
                "item_type": item_type,
                "product_bundle": product_bundle,
            }
        ],
        "tools": [{"clip": {"aoi": geometry}}],
    }


def build_order_curl(payload: dict[str, Any]) -> str:
    return (
        f'curl -X POST "{PLANET_ORDERS_URL}" '
        '-u "$PL_API_KEY:" '
        '-H "Content-Type: application/json" '
        f"-d '{json.dumps(payload, separators=(',', ':'))}'"
    )


def choose_asset_and_bundle(asset_names: list[str]) -> tuple[str, str]:
    asset_set = set(asset_names)
    if "ortho_analytic_8b" in asset_set:
        return "ortho_analytic_8b", "analytic_8b_udm2,analytic_udm2"
    if "ortho_analytic_4b" in asset_set:
        return "ortho_analytic_4b", "analytic_udm2,analytic_8b_udm2"
    if "analytic_8b" in asset_set:
        return "analytic_8b", "analytic_8b_udm2,analytic_udm2"
    if "analytic" in asset_set:
        return "analytic", "analytic_udm2,analytic_8b_udm2"
    if asset_names:
        return asset_names[0], DEFAULT_PRODUCT_BUNDLE
    return "", DEFAULT_PRODUCT_BUNDLE


def planet_session(api_key: str) -> requests.Session:
    session = requests.Session()
    session.auth = (api_key, "")
    session.headers.update({"Content-Type": "application/json"})
    return session


def list_item_assets(
    session: requests.Session, item_type: str, item_id: str
) -> tuple[list[str], str]:
    url = PLANET_ASSETS_URL.format(item_type=item_type, item_id=item_id)
    response = session.get(url, timeout=60)
    response.raise_for_status()
    payload = response.json()
    asset_names = sorted(
        key for key, value in payload.items() if isinstance(value, dict) and key != "_links"
    )
    return asset_names, url


def resolve_planet_match(
    record: dict[str, Any],
    session: requests.Session | None,
    item_type: str,
    windows_hours: list[int],
) -> PlanetMatch:
    if session is None:
        return PlanetMatch(status="unresolved_no_api_key")

    obs_dt = parse_utc(record["timestamp"])
    last_error = ""

    for window_hours in windows_hours:
        payload = build_search_payload(record["geometry"], obs_dt, window_hours, item_type)
        try:
            response = session.post(PLANET_QUICK_SEARCH_URL, json=payload, timeout=90)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            last_error = str(exc)
            break

        features = data.get("features", [])
        if not features:
            continue

        def delta_seconds(feature: dict[str, Any]) -> float:
            acquired = parse_utc(feature.get("properties", {}).get("acquired"))
            if acquired is None or obs_dt is None:
                return float("inf")
            return abs((acquired - obs_dt).total_seconds())

        nearest = min(features, key=delta_seconds)
        props = nearest.get("properties", {})
        item_id = nearest.get("id", "")
        acquired = props.get("acquired", "")
        delta_hours = ""
        if acquired and obs_dt is not None:
            acquired_dt = parse_utc(acquired)
            if acquired_dt is not None:
                delta = abs((acquired_dt - obs_dt).total_seconds()) / 3600.0
                delta_hours = f"{delta:.3f}"

        try:
            asset_names, _ = list_item_assets(session, item_type, item_id)
        except requests.RequestException as exc:
            asset_names = []
            last_error = str(exc)

        preferred_asset, product_bundle = choose_asset_and_bundle(asset_names)
        return PlanetMatch(
            status="resolved",
            item_id=item_id,
            acquired=acquired,
            delta_hours=delta_hours,
            search_window_hours=str(window_hours),
            available_assets=";".join(asset_names),
            preferred_asset_type=preferred_asset,
            product_bundle=product_bundle,
            cloud_cover=format_float(props.get("cloud_cover"), 4),
            clear_percent=format_float(props.get("clear_percent"), 2),
            quality_category=str(props.get("quality_category", "") or ""),
            error=last_error,
        )

    if last_error:
        return PlanetMatch(status="error", error=last_error)
    return PlanetMatch(status="unresolved_no_results")


def placeholder_item_id(record: dict[str, Any]) -> str:
    return f"PATCH_{record['patch_index']:03d}_ITEM_ID"


def build_patch_output(record: dict[str, Any], match: PlanetMatch, item_type: str) -> dict[str, Any]:
    obs_dt = parse_utc(record["timestamp"])
    template_payload = build_search_payload(record["geometry"], obs_dt, 720, item_type)
    quick_search_curl = build_quick_search_curl(template_payload)

    item_id = match.item_id or placeholder_item_id(record)
    asset_type = match.preferred_asset_type or "ortho_analytic_4b"
    product_bundle = match.product_bundle or DEFAULT_PRODUCT_BUNDLE
    patch_name = f"mireia_patch_{record['patch_index']:03d}"

    order_payload = build_order_payload(
        patch_name=patch_name,
        item_type=item_type,
        item_id=item_id,
        geometry=record["geometry"],
        product_bundle=product_bundle,
    )

    return {
        "patch_index": record["patch_index"],
        "obs_id": record["obs_id"],
        "source_id": record["source_id"],
        "timestamp": record["timestamp"],
        "centroid_lon": format_float(record["centroid_lon"], 6),
        "centroid_lat": format_float(record["centroid_lat"], 6),
        "estimated_patch_area_m2": format_float(record["estimated_patch_area_m2"], 3),
        "validation_type": record["validation_type"],
        "source_type": record["source_type"],
        "planet_status": match.status,
        "planet_item_id": match.item_id,
        "planet_acquired": match.acquired,
        "planet_delta_hours": match.delta_hours,
        "planet_search_window_hours": match.search_window_hours,
        "planet_available_assets": match.available_assets,
        "planet_preferred_asset_type": match.preferred_asset_type,
        "planet_product_bundle": product_bundle,
        "planet_cloud_cover": match.cloud_cover,
        "planet_clear_percent": match.clear_percent,
        "planet_quality_category": match.quality_category,
        "planet_error": match.error,
        "quick_search_curl": quick_search_curl,
        "item_curl": build_item_curl(item_type, item_id),
        "assets_curl": build_assets_curl(item_type, item_id),
        "activate_asset_curl": build_activate_curl(item_type, item_id, asset_type),
        "orders_clip_curl": build_order_curl(order_payload),
        "orders_status_curl": f'curl -u "$PL_API_KEY:" "{PLANET_ORDERS_URL}/YOUR_ORDER_ID"',
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    ensure_parent(path)
    fieldnames = [
        "patch_index",
        "obs_id",
        "source_id",
        "timestamp",
        "centroid_lon",
        "centroid_lat",
        "estimated_patch_area_m2",
        "validation_type",
        "source_type",
        "planet_status",
        "planet_item_id",
        "planet_acquired",
        "planet_delta_hours",
        "planet_search_window_hours",
        "planet_available_assets",
        "planet_preferred_asset_type",
        "planet_product_bundle",
        "planet_cloud_cover",
        "planet_clear_percent",
        "planet_quality_category",
        "planet_error",
        "quick_search_curl",
        "item_curl",
        "assets_curl",
        "activate_asset_curl",
        "orders_clip_curl",
        "orders_status_curl",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def markdown_summary_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| Patch | Obs ID | Timestamp (UTC) | Centroid (lon, lat) | Est. area m2 | Planet status | Planet item | Acquired | Delta h |",
        "| --- | --- | --- | --- | ---: | --- | --- | --- | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"{row['patch_index']:03d}",
                    row["obs_id"],
                    row["timestamp"],
                    f"{row['centroid_lon']}, {row['centroid_lat']}",
                    row["estimated_patch_area_m2"] or "",
                    row["planet_status"],
                    row["planet_item_id"] or "",
                    row["planet_acquired"] or "",
                    row["planet_delta_hours"] or "",
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def write_markdown_report(
    path: Path,
    campaign: dict[str, Any],
    input_json: Path,
    geojson_path: Path,
    csv_path: Path,
    rows: list[dict[str, Any]],
    skipped: int,
    has_api_key: bool,
) -> None:
    ensure_parent(path)
    generated_at = fmt_utc(datetime.now(timezone.utc))
    resolved_count = sum(1 for row in rows if row["planet_status"] == "resolved")

    parts = [
        f"# {campaign.get('name', 'Ocean Scan campaign')} patch report",
        "",
        f"- Generated: `{generated_at}`",
        f"- Input JSON: `{input_json}`",
        f"- GeoJSON: `{geojson_path}`",
        f"- CSV: `{csv_path}`",
        f"- Total observations in source JSON: `{len(campaign.get('observations', []))}`",
        f"- Polygon patches exported: `{len(rows)}`",
        f"- Non-patch / skipped observations: `{skipped}`",
        f"- Planet nearest acquisitions resolved live: `{resolved_count}`",
        "",
        "## Notes",
        "",
        "- Patch export includes only polygon observations with `class=PATCH` and `isAbsence=false`.",
        "- Planet matching is defined here as the `PSScene` acquisition with the smallest absolute time delta to each patch timestamp, constrained to scenes intersecting the patch polygon.",
        "- Progressive search windows used by the resolver: `12`, `24`, `72`, `168`, `720` hours.",
        "- No Planet API key was available while generating this report, so item IDs remain unresolved and the API calls below are ready-to-run templates once `PL_API_KEY` is set."
        if not has_api_key
        else "- Planet API key was available while generating this report, so resolved rows include live item IDs and item-specific download calls.",
        "- Planet docs referenced for these calls: Data API item search, items/assets, and Orders API mechanics/reference.",
        "",
        "## Summary",
        "",
        markdown_summary_table(rows),
        "",
        "## Per-patch Details",
        "",
    ]

    for row in rows:
        parts.extend(
            [
                f"### Patch {row['patch_index']:03d}",
                "",
                f"- Observation ID: `{row['obs_id']}`",
                f"- Source ID: `{row['source_id']}`" if row["source_id"] else "- Source ID: ``",
                f"- Timestamp (UTC): `{row['timestamp']}`",
                f"- Centroid (lon, lat): `{row['centroid_lon']}, {row['centroid_lat']}`",
                f"- Estimated patch area m2: `{row['estimated_patch_area_m2']}`"
                if row["estimated_patch_area_m2"]
                else "- Estimated patch area m2: ``",
                f"- Validation type: `{row['validation_type']}`",
                f"- Source type: `{row['source_type']}`",
                f"- Planet status: `{row['planet_status']}`",
                f"- Closest Planet item: `{row['planet_item_id']}`"
                if row["planet_item_id"]
                else "- Closest Planet item: unresolved",
                f"- Planet acquired (UTC): `{row['planet_acquired']}`"
                if row["planet_acquired"]
                else "- Planet acquired (UTC): unresolved",
                f"- Time delta hours: `{row['planet_delta_hours']}`"
                if row["planet_delta_hours"]
                else "- Time delta hours: unresolved",
                f"- Available assets: `{row['planet_available_assets']}`"
                if row["planet_available_assets"]
                else "- Available assets: unresolved",
                f"- Preferred asset type: `{row['planet_preferred_asset_type']}`"
                if row["planet_preferred_asset_type"]
                else "- Preferred asset type: template uses `ortho_analytic_4b`",
                f"- Product bundle for clip order: `{row['planet_product_bundle']}`",
            ]
        )
        if row["planet_error"]:
            parts.append(f"- Planet API note: `{row['planet_error']}`")
        parts.extend(
            [
                "",
                "Quick search for candidate Planet acquisitions:",
                "",
                "```bash",
                row["quick_search_curl"],
                "```",
                "",
                "Item metadata lookup:",
                "",
                "```bash",
                row["item_curl"],
                "```",
                "",
                "Available assets for the item:",
                "",
                "```bash",
                row["assets_curl"],
                "```",
                "",
                "Activate the preferred single-scene asset:",
                "",
                "```bash",
                row["activate_asset_curl"],
                "```",
                "",
                "Create a clipped Orders API download for the patch polygon:",
                "",
                "```bash",
                row["orders_clip_curl"],
                "```",
                "",
                "Check order status and read result download links:",
                "",
                "```bash",
                row["orders_status_curl"],
                "```",
                "",
            ]
        )

    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> int:
    args = parse_args()
    input_json = args.input_json.resolve()
    default_geojson, default_report, default_csv = default_output_paths(input_json)
    out_geojson = (args.out_geojson or default_geojson).resolve()
    out_report = (args.out_report or default_report).resolve()
    out_csv = (args.out_csv or default_csv).resolve()

    campaign, patch_records, skipped = load_patch_records(input_json)
    if not patch_records:
        print("No polygon patch observations found.", file=sys.stderr)
        return 1

    geojson_features = [build_geojson_feature(record) for record in patch_records]
    write_geojson(out_geojson, geojson_features)

    session = planet_session(args.planet_api_key) if args.planet_api_key else None
    rows: list[dict[str, Any]] = []
    for record in patch_records:
        match = resolve_planet_match(
            record=record,
            session=session,
            item_type=args.item_type,
            windows_hours=args.search_windows_hours,
        )
        rows.append(build_patch_output(record, match, args.item_type))

    write_csv(out_csv, rows)
    write_markdown_report(
        path=out_report,
        campaign=campaign,
        input_json=input_json,
        geojson_path=out_geojson,
        csv_path=out_csv,
        rows=rows,
        skipped=skipped,
        has_api_key=bool(args.planet_api_key),
    )

    print(f"Wrote GeoJSON: {out_geojson}")
    print(f"Wrote report:  {out_report}")
    print(f"Wrote CSV:     {out_csv}")
    print(f"Patch polygons: {len(patch_records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
