#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import quote, urlencode
from xml.sax.saxutils import escape

import rasterio
from rasterio.warp import transform_geom
from shapely.geometry import mapping, shape
from shapely.ops import unary_union


UTC = timezone.utc
DEFAULT_MARIDA_ROOT = Path("/mnt/d/Masters/MARIDA/downloads")
DEFAULT_PLANETDATA_ROOT = Path("/mnt/d/Masters/PlanetData/marine_debris/nasa-marine-debris/source")
DEFAULT_DOCX = Path("/mnt/d/Masters/Planet_reacquisition_inventory.docx")
DEFAULT_MARIDA_CSV = Path("/mnt/d/Masters/Planet_reacquisition_marida.csv")
DEFAULT_PLANETDATA_CSV = Path("/mnt/d/Masters/Planet_reacquisition_planetdata.csv")
DEFAULT_MARIDA_ALL_SCENES_CSV = Path("/mnt/d/Masters/Planet_reacquisition_marida_all_scenes.csv")
DEFAULT_MARIDA_CACHE = Path("/mnt/d/Masters/.marida_catalog_cache.json")
MARIDA_WINDOW_HOURS = 12
MARIDA_ALL_SCENES_WINDOW_HOURS = 24
MARIDA_S1_WINDOW_DAYS = 15
COPERNICUS_CATALOG_BASE = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"


@dataclass
class MaridaEvent:
    tile: str
    source_date: str
    sar_dir: str
    scene_id: str
    acquired_dt: datetime | None
    lon: float | None
    lat: float | None
    bbox_wgs84: tuple[float, float, float, float]
    raster_file_count: int
    pols: str
    files: list[str]
    planet_search_curl: str


@dataclass
class PlanetParentScene:
    scene_id: str
    acquired_dt: datetime | None
    lon: float | None
    lat: float | None
    bbox_wgs84: tuple[float, float, float, float]
    tif_tile_count: int
    jpg_tile_count: int
    example_tif: str | None
    item_metadata_curl: str
    item_assets_curl: str


@dataclass
class MaridaSceneAcquisition:
    key: str
    tile: str
    scene_date: str
    s2_product: str
    s2_acquired_dt: datetime | None
    s1_product: str
    s1_acquired_dt: datetime | None
    s1_delta_hours: float | None
    lon: float | None
    lat: float | None
    bbox_wgs84: tuple[float, float, float, float]
    planet_search_curl: str
    s1_catalog_query_url: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a Word document and CSVs describing Planet reacquisition needs for "
            "MARIDA SAR events and the local Planet marine debris dataset."
        )
    )
    parser.add_argument("--marida-root", type=Path, default=DEFAULT_MARIDA_ROOT)
    parser.add_argument("--planetdata-root", type=Path, default=DEFAULT_PLANETDATA_ROOT)
    parser.add_argument("--output-docx", type=Path, default=DEFAULT_DOCX)
    parser.add_argument("--marida-csv", type=Path, default=DEFAULT_MARIDA_CSV)
    parser.add_argument("--planetdata-csv", type=Path, default=DEFAULT_PLANETDATA_CSV)
    parser.add_argument("--marida-all-scenes-csv", type=Path, default=DEFAULT_MARIDA_ALL_SCENES_CSV)
    parser.add_argument("--marida-cache", type=Path, default=DEFAULT_MARIDA_CACHE)
    return parser.parse_args()


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def dt_to_z(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def dt_to_display(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


def delta_hours_text(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:+.2f}"


def safe_round(value: float | None, ndp: int = 6) -> float | None:
    if value is None:
        return None
    return round(float(value), ndp)


def bbox_text(bounds: tuple[float, float, float, float]) -> str:
    minx, miny, maxx, maxy = bounds
    return f"{minx:.6f}, {miny:.6f}, {maxx:.6f}, {maxy:.6f}"


def raster_footprint_wgs84(path: Path):
    with rasterio.open(path) as ds:
        bounds = ds.bounds
        footprint = {
            "type": "Polygon",
            "coordinates": [[
                [bounds.left, bounds.bottom],
                [bounds.right, bounds.bottom],
                [bounds.right, bounds.top],
                [bounds.left, bounds.top],
                [bounds.left, bounds.bottom],
            ]],
        }
        if ds.crs:
            footprint = transform_geom(ds.crs, "EPSG:4326", footprint, precision=12)
        return shape(footprint).buffer(0)


def geometry_to_json(geom) -> dict:
    return mapping(geom)


def marida_search_curl(geom, center_dt: datetime | None, window_hours: int = MARIDA_WINDOW_HOURS) -> str:
    if center_dt is None:
        start = datetime(1970, 1, 1, tzinfo=UTC)
        end = datetime(2100, 1, 1, tzinfo=UTC)
    else:
        start = center_dt - timedelta(hours=window_hours)
        end = center_dt + timedelta(hours=window_hours)
    payload = {
        "item_types": ["PSScene"],
        "filter": {
            "type": "AndFilter",
            "config": [
                {
                    "type": "GeometryFilter",
                    "field_name": "geometry",
                    "config": geometry_to_json(geom),
                },
                {
                    "type": "DateRangeFilter",
                    "field_name": "acquired",
                    "config": {
                        "gte": dt_to_z(start),
                        "lte": dt_to_z(end),
                    },
                },
            ],
        },
        "sort": [{"field_name": "acquired", "direction": "asc"}],
        "limit": 250,
    }
    return (
        'curl -u "$PL_API_KEY:" -X POST "https://api.planet.com/data/v1/quick-search" '
        '-H "Content-Type: application/json" '
        f"-d '{json.dumps(payload, separators=(',', ':'))}'"
    )


def item_metadata_curl(scene_id: str) -> str:
    return (
        'curl -u "$PL_API_KEY:" '
        f'"https://api.planet.com/data/v1/item-types/PSScene/items/{scene_id}"'
    )


def item_assets_curl(scene_id: str) -> str:
    return (
        'curl -u "$PL_API_KEY:" '
        f'"https://api.planet.com/data/v1/item-types/PSScene/items/{scene_id}/assets"'
    )


def scene_name_from_tile(tile_path: Path) -> str:
    parts = tile_path.stem.split("_")
    if len(parts) == 4:
        return "_".join(parts[:3])
    if len(parts) == 5:
        return "_".join(parts[:4])
    raise ValueError(f"Unexpected tile name format: {tile_path.name}")


def parse_scene_datetime(scene_id: str) -> datetime | None:
    parts = scene_id.split("_")
    if len(parts) < 3:
        return None
    try:
        return datetime.strptime(f"{parts[0]}_{parts[1]}", "%Y%m%d_%H%M%S").replace(tzinfo=UTC)
    except ValueError:
        return None


def parse_marida_timestamp(name: str) -> datetime | None:
    match = re.search(r"_(\d{8}T\d{6})_", name)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%dT%H%M%S").replace(tzinfo=UTC)
    except ValueError:
        return None


def day_start(date_text: str) -> datetime:
    return datetime.strptime(date_text, "%Y-%m-%d").replace(tzinfo=UTC)


def bbox_to_wkt(bounds: tuple[float, float, float, float]) -> str:
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


def build_odata_url(filter_expr: str, top: int = 100) -> str:
    params = {
        "$top": str(top),
        "$orderby": "ContentDate/Start asc",
        "$filter": filter_expr,
    }
    query = urlencode(params, quote_via=quote, safe="()',$;/:_-.=")
    return f"{COPERNICUS_CATALOG_BASE}?{query}"


def copernicus_s1_query_url(bounds: tuple[float, float, float, float], center_dt: datetime | None) -> str:
    if center_dt is None:
        center_dt = day_start("2000-01-01")
    window_start = center_dt - timedelta(days=MARIDA_S1_WINDOW_DAYS)
    window_end = center_dt + timedelta(days=MARIDA_S1_WINDOW_DAYS)
    polygon = bbox_to_wkt(bounds)
    flt = (
        "Collection/Name eq 'SENTINEL-1' and "
        f"OData.CSC.Intersects(area=geography'SRID=4326;{polygon}') and "
        f"ContentDate/Start gt {dt_to_z(window_start)} and "
        f"ContentDate/Start lt {dt_to_z(window_end)} and "
        "contains(Name,'_GRD')"
    )
    return build_odata_url(flt, top=200)


def load_marida_cache(path: Path) -> dict:
    if not path.exists():
        return {"records": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def discover_marida_events(root: Path) -> list[MaridaEvent]:
    grouped: dict[tuple[str, str, str, str], list[Path]] = defaultdict(list)
    for tif_path in sorted(root.glob("**/SAR_*/*.tif")):
        tile = tif_path.parts[-4]
        source_date = tif_path.parts[-3]
        sar_dir = tif_path.parts[-2]
        acquired_dt = parse_marida_timestamp(tif_path.name)
        dt_key = dt_to_z(acquired_dt) or "unknown"
        grouped[(tile, source_date, sar_dir, dt_key)].append(tif_path)

    events: list[MaridaEvent] = []
    for (tile, source_date, sar_dir, _), tif_paths in sorted(grouped.items()):
        footprints = [raster_footprint_wgs84(path) for path in tif_paths]
        geom = unary_union(footprints)
        centroid = geom.centroid
        acquired_dt = parse_marida_timestamp(tif_paths[0].name)
        pols = sorted({path.stem.rsplit("_", 1)[-1].upper() for path in tif_paths})
        events.append(
            MaridaEvent(
                tile=tile,
                source_date=source_date,
                sar_dir=sar_dir,
                scene_id=tif_paths[0].stem.rsplit("_", 1)[0],
                acquired_dt=acquired_dt,
                lon=safe_round(centroid.x),
                lat=safe_round(centroid.y),
                bbox_wgs84=tuple(float(v) for v in geom.bounds),
                raster_file_count=len(tif_paths),
                pols=",".join(pols),
                files=[path.name for path in tif_paths],
                planet_search_curl=marida_search_curl(geom, acquired_dt),
            )
        )
    return events


def discover_planet_parent_scenes(root: Path) -> list[PlanetParentScene]:
    tif_groups: dict[str, list[Path]] = defaultdict(list)
    jpg_counts: dict[str, int] = defaultdict(int)
    for file_path in sorted(root.iterdir()):
        if not file_path.is_file():
            continue
        scene_id = scene_name_from_tile(file_path)
        if file_path.suffix.lower() == ".tif":
            tif_groups[scene_id].append(file_path)
        elif file_path.suffix.lower() == ".jpg":
            jpg_counts[scene_id] += 1

    scenes: list[PlanetParentScene] = []
    for scene_id, tif_paths in sorted(tif_groups.items()):
        geom = unary_union([raster_footprint_wgs84(path) for path in tif_paths])
        centroid = geom.centroid
        scenes.append(
            PlanetParentScene(
                scene_id=scene_id,
                acquired_dt=parse_scene_datetime(scene_id),
                lon=safe_round(centroid.x),
                lat=safe_round(centroid.y),
                bbox_wgs84=tuple(float(v) for v in geom.bounds),
                tif_tile_count=len(tif_paths),
                jpg_tile_count=jpg_counts.get(scene_id, 0),
                example_tif=tif_paths[0].name if tif_paths else None,
                item_metadata_curl=item_metadata_curl(scene_id),
                item_assets_curl=item_assets_curl(scene_id),
            )
        )
    return scenes


def discover_marida_scene_acquisitions(root: Path, cache_path: Path) -> list[MaridaSceneAcquisition]:
    cache = load_marida_cache(cache_path).get("records", {})
    scenes: list[MaridaSceneAcquisition] = []
    for tile_dir in sorted(root.iterdir()):
        if not tile_dir.is_dir():
            continue
        for date_dir in sorted(tile_dir.iterdir()):
            optical_dir = date_dir / "optical"
            if not optical_dir.is_dir():
                continue
            b02 = optical_dir / f"S2_{tile_dir.name}_{date_dir.name}_B02.tif"
            if not b02.exists():
                matches = sorted(optical_dir.glob("S2_*_B02.tif"))
                if not matches:
                    continue
                b02 = matches[0]

            geom = raster_footprint_wgs84(b02)
            centroid = geom.centroid
            key = f"{tile_dir.name}/{date_dir.name}"
            cached = cache.get(key, {})
            s2 = cached.get("s2") or {}
            s1 = cached.get("s1") or {}
            s2_dt = parse_utc(s2["start"]) if s2.get("start") else None
            s1_dt = parse_utc(s1["start"]) if s1.get("start") else None
            delta_seconds = cached.get("delta_seconds")
            delta_hours = None if delta_seconds is None else float(delta_seconds) / 3600.0
            center_dt = s2_dt or day_start(date_dir.name)

            scenes.append(
                MaridaSceneAcquisition(
                    key=key,
                    tile=tile_dir.name,
                    scene_date=date_dir.name,
                    s2_product=s2.get("name", ""),
                    s2_acquired_dt=s2_dt,
                    s1_product=s1.get("name", ""),
                    s1_acquired_dt=s1_dt,
                    s1_delta_hours=delta_hours,
                    lon=safe_round(centroid.x),
                    lat=safe_round(centroid.y),
                    bbox_wgs84=tuple(float(v) for v in geom.bounds),
                    planet_search_curl=marida_search_curl(
                        geom,
                        center_dt,
                        window_hours=MARIDA_ALL_SCENES_WINDOW_HOURS,
                    ),
                    s1_catalog_query_url=copernicus_s1_query_url(tuple(float(v) for v in geom.bounds), center_dt),
                )
            )
    return scenes


def write_marida_csv(path: Path, events: Iterable[MaridaEvent]) -> None:
    fieldnames = [
        "tile",
        "source_date",
        "sar_dir",
        "scene_id",
        "acquired_utc",
        "centroid_lon",
        "centroid_lat",
        "bbox_wgs84",
        "raster_file_count",
        "pols",
        "files",
        "planet_quick_search_curl",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for event in events:
            writer.writerow(
                {
                    "tile": event.tile,
                    "source_date": event.source_date,
                    "sar_dir": event.sar_dir,
                    "scene_id": event.scene_id,
                    "acquired_utc": dt_to_z(event.acquired_dt),
                    "centroid_lon": event.lon,
                    "centroid_lat": event.lat,
                    "bbox_wgs84": bbox_text(event.bbox_wgs84),
                    "raster_file_count": event.raster_file_count,
                    "pols": event.pols,
                    "files": "; ".join(event.files),
                    "planet_quick_search_curl": event.planet_search_curl,
                }
            )


def write_planetdata_csv(path: Path, scenes: Iterable[PlanetParentScene]) -> None:
    fieldnames = [
        "scene_id",
        "acquired_utc",
        "centroid_lon",
        "centroid_lat",
        "bbox_wgs84",
        "tif_tile_count",
        "jpg_tile_count",
        "example_tif",
        "item_metadata_curl",
        "item_assets_curl",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for scene in scenes:
            writer.writerow(
                {
                    "scene_id": scene.scene_id,
                    "acquired_utc": dt_to_z(scene.acquired_dt),
                    "centroid_lon": scene.lon,
                    "centroid_lat": scene.lat,
                    "bbox_wgs84": bbox_text(scene.bbox_wgs84),
                    "tif_tile_count": scene.tif_tile_count,
                    "jpg_tile_count": scene.jpg_tile_count,
                    "example_tif": scene.example_tif or "",
                    "item_metadata_curl": scene.item_metadata_curl,
                    "item_assets_curl": scene.item_assets_curl,
                }
            )


def write_marida_all_scenes_csv(path: Path, scenes: Iterable[MaridaSceneAcquisition]) -> None:
    fieldnames = [
        "key",
        "tile",
        "scene_date",
        "s2_product",
        "s2_acquired_utc",
        "s1_product",
        "s1_acquired_utc",
        "s1_delta_hours",
        "centroid_lon",
        "centroid_lat",
        "bbox_wgs84",
        "planet_quick_search_curl_extended",
        "s1_catalog_query_url",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for scene in scenes:
            writer.writerow(
                {
                    "key": scene.key,
                    "tile": scene.tile,
                    "scene_date": scene.scene_date,
                    "s2_product": scene.s2_product,
                    "s2_acquired_utc": dt_to_z(scene.s2_acquired_dt),
                    "s1_product": scene.s1_product,
                    "s1_acquired_utc": dt_to_z(scene.s1_acquired_dt),
                    "s1_delta_hours": delta_hours_text(scene.s1_delta_hours),
                    "centroid_lon": scene.lon,
                    "centroid_lat": scene.lat,
                    "bbox_wgs84": bbox_text(scene.bbox_wgs84),
                    "planet_quick_search_curl_extended": scene.planet_search_curl,
                    "s1_catalog_query_url": scene.s1_catalog_query_url,
                }
            )


def xml_space_attr(text: str) -> str:
    return ' xml:space="preserve"' if text[:1].isspace() or text[-1:].isspace() else ""


def make_run(text: str, *, bold: bool = False, size: int = 18, monospace: bool = False) -> str:
    props = ["<w:rPr>"]
    if bold:
        props.append("<w:b/>")
    if monospace:
        props.append('<w:rFonts w:ascii="Courier New" w:eastAsia="Courier New" w:hAnsi="Courier New"/>')
    props.append(f'<w:sz w:val="{size}"/>')
    props.append(f'<w:szCs w:val="{size}"/>')
    props.append("</w:rPr>")
    return (
        "<w:r>"
        + "".join(props)
        + f"<w:t{xml_space_attr(text)}>{escape(text)}</w:t>"
        + "</w:r>"
    )


def make_paragraph(
    text: str,
    *,
    bold: bool = False,
    size: int = 20,
    center: bool = False,
    monospace: bool = False,
) -> str:
    p_pr = "<w:pPr>"
    if center:
        p_pr += '<w:jc w:val="center"/>'
    p_pr += "</w:pPr>"
    return "<w:p>" + p_pr + make_run(text, bold=bold, size=size, monospace=monospace) + "</w:p>"


def make_cell(
    text: str,
    width: int,
    *,
    bold: bool = False,
    shade: str | None = None,
    size: int = 16,
    monospace: bool = False,
) -> str:
    tc_pr = [f'<w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>', '<w:vAlign w:val="top"/>']
    if shade:
        tc_pr.append(f'<w:shd w:val="clear" w:color="auto" w:fill="{shade}"/>')
    tc_pr.append("</w:tcPr>")
    return (
        "<w:tc>"
        + "".join(tc_pr)
        + make_paragraph(text or "-", bold=bold, size=size, monospace=monospace)
        + "</w:tc>"
    )


def make_table(
    headers: list[str],
    rows: list[list[str]],
    widths: list[int],
    *,
    monospace_cols: set[int] | None = None,
) -> str:
    header_fill = "DCE6F1"
    tbl_pr = """
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
    grid = "<w:tblGrid>" + "".join(f'<w:gridCol w:w="{width}"/>' for width in widths) + "</w:tblGrid>"
    xml_rows = []

    header_cells = [
        make_cell(header, widths[index], bold=True, shade=header_fill, size=16)
        for index, header in enumerate(headers)
    ]
    xml_rows.append("<w:tr>" + "".join(header_cells) + "</w:tr>")

    monospace_cols = monospace_cols or set()
    for row in rows:
        cells = []
        for index, value in enumerate(row):
            cells.append(
                make_cell(
                    value,
                    widths[index],
                    size=12 if index in monospace_cols else 14,
                    monospace=index in monospace_cols,
                )
            )
        xml_rows.append("<w:tr>" + "".join(cells) + "</w:tr>")

    return "<w:tbl>" + tbl_pr + grid + "".join(xml_rows) + "</w:tbl>"


def build_document_xml(
    marida_events: list[MaridaEvent],
    marida_scene_acquisitions: list[MaridaSceneAcquisition],
    planet_scenes: list[PlanetParentScene],
    generated_at: datetime,
    marida_csv: Path,
    marida_all_scenes_csv: Path,
    planetdata_csv: Path,
) -> str:
    overview_rows = [
        ["MARIDA SAR folders", str(len({(event.tile, event.source_date, event.sar_dir) for event in marida_events}))],
        ["MARIDA unique SAR acquisitions", str(len(marida_events))],
        ["MARIDA all optical scene acquisitions", str(len(marida_scene_acquisitions))],
        ["PlanetData parent Planet scenes", str(len(planet_scenes))],
        ["PlanetData source tif tiles", str(sum(scene.tif_tile_count for scene in planet_scenes))],
        ["PlanetData source jpg tiles", str(sum(scene.jpg_tile_count for scene in planet_scenes))],
        ["MARIDA CSV", str(marida_csv)],
        ["MARIDA all scenes CSV", str(marida_all_scenes_csv)],
        ["PlanetData CSV", str(planetdata_csv)],
    ]

    marida_rows = [
        [
            event.tile,
            event.source_date,
            event.sar_dir,
            event.scene_id,
            dt_to_display(event.acquired_dt),
            f"{event.lon}, {event.lat}",
            bbox_text(event.bbox_wgs84),
            str(event.raster_file_count),
            event.pols,
            event.planet_search_curl,
        ]
        for event in marida_events
    ]
    planet_rows = [
        [
            scene.scene_id,
            dt_to_display(scene.acquired_dt),
            f"{scene.lon}, {scene.lat}",
            bbox_text(scene.bbox_wgs84),
            str(scene.tif_tile_count),
            str(scene.jpg_tile_count),
            scene.example_tif or "",
            scene.item_metadata_curl,
            scene.item_assets_curl,
        ]
        for scene in planet_scenes
    ]
    marida_all_scene_rows = [
        [
            scene.tile,
            scene.scene_date,
            dt_to_display(scene.s2_acquired_dt),
            scene.s1_product,
            dt_to_display(scene.s1_acquired_dt),
            delta_hours_text(scene.s1_delta_hours),
            scene.planet_search_curl,
            scene.s1_catalog_query_url,
        ]
        for scene in marida_scene_acquisitions
    ]

    body = [
        make_paragraph("Planet Reacquisition Inventory", bold=True, size=30, center=True),
        make_paragraph(
            (
                f"Generated {generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}. "
                "This document inventories the Planet data needed for MARIDA SAR-linked lookups "
                "and for the existing Planet marine debris dataset under D:\\Masters\\PlanetData."
            ),
            size=18,
        ),
        make_paragraph(
            (
                "Planet catalog calls are included, but live Planet resolution was not executed in this run "
                "because no Planet API key was available in the shell environment. "
                "For MARIDA, the calls are geometry + time-window searches. "
                "For PlanetData, the calls target the inferred parent PSScene item IDs directly."
            ),
            size=18,
        ),
        make_paragraph("Overview", bold=True, size=24),
        make_table(["Metric", "Value"], overview_rows, [3400, 11000]),
        make_paragraph("All MARIDA Acquisitions", bold=True, size=24),
        make_paragraph(
            (
                "This separate table covers all MARIDA optical scene acquisitions found under MARIDA/downloads. "
                f"The Planet search window is widened to +/-{MARIDA_ALL_SCENES_WINDOW_HOURS} hours, and each row also includes "
                f"a Copernicus Sentinel-1 catalog query URL using a +/-{MARIDA_S1_WINDOW_DAYS} day window around the MARIDA scene time. "
                "The S2 and nearest S1 fields come from the local MARIDA catalog cache."
            ),
            size=16,
        ),
        make_table(
            [
                "Tile",
                "Scene Date",
                "S2 Acquired",
                "Nearest S1 Product",
                "S1 Acquired",
                "Delta h",
                f"Planet Search +/-{MARIDA_ALL_SCENES_WINDOW_HOURS}h",
                f"S1 Catalog +/-{MARIDA_S1_WINDOW_DAYS}d",
            ],
            marida_all_scene_rows,
            [700, 850, 1250, 2600, 1250, 700, 3450, 3600],
            monospace_cols={6, 7},
        ),
        make_paragraph("MARIDA", bold=True, size=24),
        make_paragraph(
            (
                "Each row represents one unique SAR acquisition timestamp detected inside MARIDA SAR folders. "
                f"The Planet quick-search call uses the unioned MARIDA SAR footprint and a +/-{MARIDA_WINDOW_HOURS} hour window."
            ),
            size=16,
        ),
        make_table(
            [
                "Tile",
                "Source Date",
                "SAR Dir",
                "Scene ID",
                "Acquired",
                "Centroid",
                "BBox WGS84",
                "Raster Files",
                "Pols",
                "Planet Quick Search",
            ],
            marida_rows,
            [600, 850, 900, 1800, 1250, 1100, 1700, 700, 650, 4850],
            monospace_cols={9},
        ),
        make_paragraph("PlanetData", bold=True, size=24),
        make_paragraph(
            (
                "The Planet marine debris dataset stores 256x256 chips. "
                "These have been grouped back to their parent Planet acquisitions using the existing file naming convention. "
                "Use the metadata call to inspect the item and the assets call to list downloadable assets."
            ),
            size=16,
        ),
        make_table(
            [
                "Scene ID",
                "Acquired",
                "Centroid",
                "BBox WGS84",
                "TIF Tiles",
                "JPG Tiles",
                "Example TIF",
                "Item Metadata",
                "Item Assets",
            ],
            planet_rows,
            [1400, 1300, 1100, 1600, 700, 700, 1700, 3000, 2900],
            monospace_cols={7, 8},
        ),
        make_paragraph("How To Use Later", bold=True, size=24),
        make_paragraph('1. Export your Planet key into the shell, for example: export PL_API_KEY="..."', size=16),
        make_paragraph(
            "2. For MARIDA rows, run the quick-search call and choose the returned PSScene item with the smallest time difference from the SAR acquisition.",
            size=16,
        ),
        make_paragraph(
            "3. For PlanetData rows, run the item-assets call for the listed parent scene ID and then activate/download the asset type you need.",
            size=16,
        ),
        """
<w:sectPr>
  <w:pgSz w:w="15840" w:h="12240" w:orient="landscape"/>
  <w:pgMar w:top="720" w:right="720" w:bottom="720" w:left="720" w:header="720" w:footer="720" w:gutter="0"/>
</w:sectPr>
""".strip(),
    ]

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        + "".join(body)
        + "</w:body></w:document>"
    )


def build_core_xml(generated_at: datetime) -> str:
    created = generated_at.isoformat().replace("+00:00", "Z")
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties
    xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:dcterms="http://purl.org/dc/terms/"
    xmlns:dcmitype="http://purl.org/dc/dcmitype/"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>Planet Reacquisition Inventory</dc:title>
  <dc:creator>Codex</dc:creator>
  <cp:lastModifiedBy>Codex</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{created}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{created}</dcterms:modified>
</cp:coreProperties>
"""


def build_app_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
    xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Codex</Application>
</Properties>
"""


def write_docx(output_path: Path, document_xml: str, generated_at: datetime) -> None:
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
"""
    relationships = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", relationships)
        zf.writestr("docProps/core.xml", build_core_xml(generated_at))
        zf.writestr("docProps/app.xml", build_app_xml())
        zf.writestr("word/document.xml", document_xml)


def main() -> None:
    args = parse_args()
    marida_events = discover_marida_events(args.marida_root)
    marida_scene_acquisitions = discover_marida_scene_acquisitions(args.marida_root, args.marida_cache)
    planet_scenes = discover_planet_parent_scenes(args.planetdata_root)
    write_marida_csv(args.marida_csv, marida_events)
    write_marida_all_scenes_csv(args.marida_all_scenes_csv, marida_scene_acquisitions)
    write_planetdata_csv(args.planetdata_csv, planet_scenes)
    generated_at = datetime.now(UTC)
    document_xml = build_document_xml(
        marida_events=marida_events,
        marida_scene_acquisitions=marida_scene_acquisitions,
        planet_scenes=planet_scenes,
        generated_at=generated_at,
        marida_csv=args.marida_csv,
        marida_all_scenes_csv=args.marida_all_scenes_csv,
        planetdata_csv=args.planetdata_csv,
    )
    write_docx(args.output_docx, document_xml, generated_at)


if __name__ == "__main__":
    main()
