#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import zipfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape

import rasterio
import requests
from requests.adapters import HTTPAdapter
from shapely.geometry import box, mapping
from shapely.ops import unary_union
from urllib3.util.retry import Retry


STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
S1_COLLECTION = "sentinel-1-grd"


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def fmt_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso_utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


def scene_name_from_tile(tile_path: Path) -> str:
    parts = tile_path.stem.split("_")
    if len(parts) == 4:
        return "_".join(parts[:3])
    if len(parts) == 5:
        return "_".join(parts[:4])
    raise ValueError(f"Unexpected tile name format: {tile_path.name}")


def parse_scene_datetime(scene_name: str) -> datetime:
    date_part, time_part, *_ = scene_name.split("_")
    return datetime.strptime(f"{date_part}_{time_part}", "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)


def collect_scene_tiles(source_dir: Path) -> dict[str, list[Path]]:
    grouped: dict[str, list[Path]] = defaultdict(list)
    for tile_path in sorted(source_dir.glob("*.tif")):
        grouped[scene_name_from_tile(tile_path)].append(tile_path)
    return dict(sorted(grouped.items()))


def scene_geometry(tile_paths: Iterable[Path]):
    geoms = []
    for tile_path in tile_paths:
        with rasterio.open(tile_path) as ds:
            bounds = ds.bounds
            geoms.append(box(bounds.left, bounds.bottom, bounds.right, bounds.top))
    geom = unary_union(geoms)
    if geom.is_empty:
        raise ValueError("Computed empty geometry from training tiles")
    return geom


def bbox_text(geom) -> str:
    minx, miny, maxx, maxy = geom.bounds
    return f"{minx:.6f}, {miny:.6f}, {maxx:.6f}, {maxy:.6f}"


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": "marine-debris-s1-match/1.0"})
    retries = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["POST"]),
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def search_s1_candidates(
    session: requests.Session,
    geom,
    center_time: datetime,
    search_days: int,
    limit: int,
) -> list[dict]:
    body = {
        "collections": [S1_COLLECTION],
        "intersects": mapping(geom),
        "datetime": (
            f"{fmt_utc(center_time - timedelta(days=search_days))}/"
            f"{fmt_utc(center_time + timedelta(days=search_days))}"
        ),
        "limit": limit,
    }
    response = session.post(STAC_URL, json=body, timeout=120)
    response.raise_for_status()
    payload = response.json()
    features = payload.get("features", [])
    matched = payload.get("context", {}).get("matched")
    if matched and matched > limit:
        raise RuntimeError(
            f"Search returned {matched} matches, which exceeds limit={limit}. Increase the limit."
        )
    return features


def feature_datetime(feature: dict) -> datetime:
    value = feature.get("properties", {}).get("datetime")
    if not value:
        raise ValueError(f"Feature missing datetime: {feature.get('id')}")
    return parse_iso_utc(value)


def product_name(feature: dict) -> str:
    assets = feature.get("assets", {})
    href = assets.get("safe-manifest", {}).get("href")
    if href:
        return Path(href.split("?", 1)[0]).parent.name
    return feature.get("id", "")


def nearest_products(scene_name: str, planet_dt: datetime, features: list[dict]) -> list[dict]:
    if not features:
        return []

    scored = []
    for feature in features:
        s1_dt = feature_datetime(feature)
        delta_hours = (s1_dt - planet_dt).total_seconds() / 3600.0
        scored.append(
            {
                "planet_scene": scene_name,
                "planet_datetime_utc": fmt_utc(planet_dt),
                "s1_product_name": product_name(feature),
                "s1_datetime_utc": fmt_utc(s1_dt),
                "delta_t_hours": delta_hours,
                "abs_delta_t_hours": abs(delta_hours),
            }
        )

    min_abs_delta = min(item["abs_delta_t_hours"] for item in scored)
    nearest = [
        item for item in scored if abs(item["abs_delta_t_hours"] - min_abs_delta) <= 1e-9
    ]
    nearest.sort(key=lambda item: (item["s1_datetime_utc"], item["s1_product_name"]))
    return nearest


def write_csv(rows: list[dict], out_csv: Path) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "planet_scene",
        "planet_datetime_utc",
        "training_tiles",
        "aoi_bbox_wgs84",
        "s1_product_name",
        "s1_datetime_utc",
        "delta_t_hours",
        "abs_delta_t_hours",
    ]
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def w_text(text: str) -> str:
    pieces = []
    for index, line in enumerate(text.split("\n")):
        if index:
            pieces.append("<w:br/>")
        pieces.append(f'<w:t xml:space="preserve">{escape(line)}</w:t>')
    return "".join(pieces)


def paragraph(text: str, *, bold: bool = False) -> str:
    run_props = "<w:rPr><w:b/></w:rPr>" if bold else ""
    return f"<w:p><w:r>{run_props}{w_text(text)}</w:r></w:p>"


def table_cell(text: str, *, bold: bool = False) -> str:
    return (
        "<w:tc>"
        "<w:tcPr><w:tcW w:w=\"0\" w:type=\"auto\"/></w:tcPr>"
        f"{paragraph(text, bold=bold)}"
        "</w:tc>"
    )


def table_row(cells: list[str], *, header: bool = False) -> str:
    return "<w:tr>" + "".join(table_cell(cell, bold=header) for cell in cells) + "</w:tr>"


def display_delta_hours(value) -> str:
    if value in ("", None):
        return ""
    if isinstance(value, str):
        return value
    return f"{value:+.3f}"


def document_xml(rows: list[dict], search_days: int) -> str:
    generated = fmt_utc(utc_now())
    intro = (
        "Closest Sentinel-1 GRD products for the NASA marine debris training scenes\n"
        f"Generated: {generated}"
    )
    note = (
        "Method: each Planet parent scene was matched using the union of all 256x256 training tile "
        f"footprints in that scene. Delta t is Sentinel-1 catalog datetime minus Planet scene datetime. "
        f"Search window: +/-{search_days} days."
    )

    header = [
        "Planet scene",
        "Planet datetime (UTC)",
        "Training tiles",
        "Sentinel-1 product name",
        "Sentinel-1 datetime (UTC)",
        "Delta t (hours)",
    ]
    body_rows = [
        table_row(
            [
                row["planet_scene"],
                row["planet_datetime_utc"],
                str(row["training_tiles"]),
                row["s1_product_name"],
                row["s1_datetime_utc"],
                display_delta_hours(row["delta_t_hours"]),
            ]
        )
        for row in rows
    ]
    table = (
        "<w:tbl>"
        "<w:tblPr>"
        "<w:tblW w:w=\"0\" w:type=\"auto\"/>"
        "<w:tblBorders>"
        "<w:top w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
        "<w:left w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
        "<w:bottom w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
        "<w:right w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
        "<w:insideH w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
        "<w:insideV w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
        "</w:tblBorders>"
        "</w:tblPr>"
        f"{table_row(header, header=True)}"
        f"{''.join(body_rows)}"
        "</w:tbl>"
    )

    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {paragraph(intro, bold=True)}
    {paragraph(note)}
    {table}
    <w:sectPr>
      <w:pgSz w:w="15840" w:h="12240" w:orient="landscape"/>
      <w:pgMar w:top="720" w:right="720" w:bottom="720" w:left="720" w:header="708" w:footer="708" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>
"""


def content_types_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
"""


def rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
"""


def core_xml() -> str:
    now = fmt_utc(utc_now())
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties
  xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
  xmlns:dc="http://purl.org/dc/elements/1.1/"
  xmlns:dcterms="http://purl.org/dc/terms/"
  xmlns:dcmitype="http://purl.org/dc/dcmitype/"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>Closest Sentinel-1 Products for NASA Marine Debris Training Data</dc:title>
  <dc:creator>Codex</dc:creator>
  <cp:lastModifiedBy>Codex</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>
</cp:coreProperties>
"""


def app_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
  xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Codex</Application>
</Properties>
"""


def empty_document_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>
"""


def write_docx(rows: list[dict], out_docx: Path, search_days: int) -> None:
    out_docx.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_docx, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml())
        zf.writestr("_rels/.rels", rels_xml())
        zf.writestr("docProps/core.xml", core_xml())
        zf.writestr("docProps/app.xml", app_xml())
        zf.writestr("word/document.xml", document_xml(rows, search_days))
        zf.writestr("word/_rels/document.xml.rels", empty_document_rels_xml())


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    dataset_root = project_root / "nasa-marine-debris"
    outputs_dir = project_root / "outputs"

    parser = argparse.ArgumentParser(
        description="Find the closest Sentinel-1 GRD product names for each NASA marine debris Planet scene."
    )
    parser.add_argument("--dataset-root", type=Path, default=dataset_root)
    parser.add_argument("--output-dir", type=Path, default=outputs_dir)
    parser.add_argument("--search-days", type=int, default=30)
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()

    source_dir = args.dataset_root / "source"
    scene_tiles = collect_scene_tiles(source_dir)
    session = build_session()

    out_rows: list[dict] = []
    for scene_name, tile_paths in scene_tiles.items():
        planet_dt = parse_scene_datetime(scene_name)
        geom = scene_geometry(tile_paths)
        features = search_s1_candidates(
            session=session,
            geom=geom,
            center_time=planet_dt,
            search_days=args.search_days,
            limit=args.limit,
        )
        matches = nearest_products(scene_name, planet_dt, features)
        if not matches:
            out_rows.append(
                {
                    "planet_scene": scene_name,
                    "planet_datetime_utc": fmt_utc(planet_dt),
                    "training_tiles": len(tile_paths),
                    "aoi_bbox_wgs84": bbox_text(geom),
                    "s1_product_name": "",
                    "s1_datetime_utc": "",
                    "delta_t_hours": "",
                    "abs_delta_t_hours": "",
                }
            )
            print(f"[!] No Sentinel-1 match found for {scene_name}")
            continue

        min_abs_hours = matches[0]["abs_delta_t_hours"]
        for match in matches:
            match["training_tiles"] = len(tile_paths)
            match["aoi_bbox_wgs84"] = bbox_text(geom)
            match["delta_t_hours"] = f'{match["delta_t_hours"]:+.6f}'
            match["abs_delta_t_hours"] = f'{match["abs_delta_t_hours"]:.6f}'
            out_rows.append(match)

        print(
            f"[ok] {scene_name}: {len(matches)} closest Sentinel-1 product(s), "
            f"min |delta t| = {min_abs_hours:.3f} h"
        )

    out_rows.sort(key=lambda row: (row["planet_datetime_utc"], row["planet_scene"], row["s1_product_name"]))

    csv_path = args.output_dir / "nasa_marine_debris_closest_s1_products.csv"
    docx_path = args.output_dir / "nasa_marine_debris_closest_s1_products.docx"
    write_csv(out_rows, csv_path)
    write_docx(out_rows, docx_path, args.search_days)
    print(f"[done] wrote {csv_path}")
    print(f"[done] wrote {docx_path}")


if __name__ == "__main__":
    main()
