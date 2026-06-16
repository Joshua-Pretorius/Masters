#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape

import rasterio
from rasterio.warp import transform_bounds


UTC = timezone.utc
CATALOG_BASE = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
S2_WINDOW_DAYS = 1
S1_WINDOW_DAYS = 15
CACHE_VERSION = 1


@dataclass
class Scene:
    key: str
    tile: str
    scene_date: str
    optical_b02: str
    bbox_wgs84: tuple[float, float, float, float]
    has_local_sar: bool
    local_sar_dirs: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a Word document listing each MARIDA Sentinel-2 scene and the "
            "nearest Sentinel-1 acquisition for the same footprint."
        )
    )
    parser.add_argument(
        "--marida-root",
        type=Path,
        default=Path("/mnt/d/Masters/MARIDA/downloads"),
        help="Path to MARIDA downloads root.",
    )
    parser.add_argument(
        "--output-docx",
        type=Path,
        default=Path("/mnt/d/Masters/MARIDA_S2_nearest_S1_time_differences.docx"),
        help="Output .docx path.",
    )
    parser.add_argument(
        "--cache-path",
        type=Path,
        default=Path("/mnt/d/Masters/.marida_catalog_cache.json"),
        help="JSON cache for resolved catalog matches.",
    )
    return parser.parse_args()


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def to_utc_z(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def format_utc(value: str | None) -> str:
    if not value:
        return "-"
    return parse_utc(value).strftime("%Y-%m-%d %H:%M:%S UTC")


def format_delta(td: timedelta | None) -> str:
    if td is None:
        return "-"
    total_seconds = int(round(td.total_seconds()))
    sign = "+" if total_seconds >= 0 else "-"
    total_seconds = abs(total_seconds)
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    if days:
        return f"{sign}{days}d {hours:02}:{minutes:02}:{seconds:02}"
    return f"{sign}{hours:02}:{minutes:02}:{seconds:02}"


def delta_hours(td: timedelta | None) -> str:
    if td is None:
        return "-"
    return f"{td.total_seconds() / 3600.0:+.2f}"


def scene_day_bounds(scene_date: str) -> tuple[datetime, datetime]:
    day = datetime.strptime(scene_date, "%Y-%m-%d").replace(tzinfo=UTC)
    return day, day + timedelta(days=S2_WINDOW_DAYS)


def bbox_to_polygon(bounds: tuple[float, float, float, float]) -> str:
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


def read_bbox_wgs84(raster_path: Path) -> tuple[float, float, float, float]:
    with rasterio.open(raster_path) as ds:
        return transform_bounds(ds.crs, "EPSG:4326", *ds.bounds, densify_pts=21)


def discover_scenes(root: Path) -> list[Scene]:
    scenes: list[Scene] = []
    for tile_dir in sorted(root.iterdir()):
        if not tile_dir.is_dir():
            continue
        for date_dir in sorted(tile_dir.iterdir()):
            if not date_dir.is_dir():
                continue
            optical_dir = date_dir / "optical"
            if not optical_dir.is_dir():
                continue
            b02 = optical_dir / f"S2_{tile_dir.name}_{date_dir.name}_B02.tif"
            if not b02.exists():
                matches = sorted(optical_dir.glob("S2_*_B02.tif"))
                if not matches:
                    continue
                b02 = matches[0]
            local_sar_dirs = sorted(
                p.name for p in date_dir.iterdir() if p.is_dir() and p.name.startswith("SAR_")
            )
            scenes.append(
                Scene(
                    key=f"{tile_dir.name}/{date_dir.name}",
                    tile=tile_dir.name,
                    scene_date=date_dir.name,
                    optical_b02=str(b02),
                    bbox_wgs84=read_bbox_wgs84(b02),
                    has_local_sar=bool(local_sar_dirs),
                    local_sar_dirs=local_sar_dirs,
                )
            )
    return scenes


def load_cache(cache_path: Path) -> dict[str, Any]:
    if not cache_path.exists():
        return {"version": CACHE_VERSION, "records": {}}
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": CACHE_VERSION, "records": {}}
    if data.get("version") != CACHE_VERSION:
        return {"version": CACHE_VERSION, "records": {}}
    data.setdefault("records", {})
    return data


def save_cache(cache_path: Path, cache: dict[str, Any]) -> None:
    cache_path.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")


def request_json(url: str, retries: int = 4) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            req = Request(url, headers={"User-Agent": "Codex MARIDA Scene Resolver"})
            with urlopen(req, timeout=90) as resp:
                return json.load(resp)
        except HTTPError as exc:
            last_error = exc
            if exc.code not in {429, 500, 502, 503, 504} or attempt == retries - 1:
                raise
        except URLError as exc:
            last_error = exc
            if attempt == retries - 1:
                raise
        time.sleep(1.5 * (attempt + 1))
    if last_error is not None:
        raise last_error
    raise RuntimeError("Catalog query failed without an explicit exception.")


def build_odata_url(filter_expr: str, top: int = 50) -> str:
    params = {
        "$top": str(top),
        "$orderby": "ContentDate/Start asc",
        "$filter": filter_expr,
    }
    query = urlencode(
        params,
        quote_via=quote,
        safe="()',$;/:_-.=",
    )
    return f"{CATALOG_BASE}?{query}"


def query_catalog(filter_expr: str, top: int = 50) -> list[dict[str, Any]]:
    url = build_odata_url(filter_expr, top=top)
    payload = request_json(url)
    return payload.get("value", [])


def s2_level_rank(name: str) -> int:
    if "_MSIL2A_" in name:
        return 0
    if "_MSIL1C_" in name:
        return 1
    return 9


def parse_generation_timestamp(name: str) -> float:
    match = re.search(r"_(\d{8}T\d{6})\.SAFE$", name)
    if not match:
        return 0.0
    return datetime.strptime(match.group(1), "%Y%m%dT%H%M%S").replace(tzinfo=UTC).timestamp()


def choose_s2_product(products: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not products:
        return None
    ordered = sorted(
        products,
        key=lambda product: (
            s2_level_rank(product["Name"]),
            -parse_generation_timestamp(product["Name"]),
            product["Name"],
        ),
    )
    return ordered[0]


def s1_identity_key(name: str) -> str:
    match = re.match(r"^(.*)_[0-9A-F]{4}(?:_COG)?\.SAFE$", name)
    return match.group(1) if match else name


def choose_preferred_identity_product(products: list[dict[str, Any]]) -> dict[str, Any]:
    return sorted(
        products,
        key=lambda product: (
            1 if product["Name"].endswith("_COG.SAFE") else 0,
            product["Name"],
        ),
    )[0]


def dedupe_s1_products(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for product in products:
        grouped.setdefault(s1_identity_key(product["Name"]), []).append(product)
    return [choose_preferred_identity_product(items) for items in grouped.values()]


def choose_s1_product(products: list[dict[str, Any]], s2_start: datetime) -> dict[str, Any] | None:
    if not products:
        return None
    deduped = dedupe_s1_products(products)
    return sorted(
        deduped,
        key=lambda product: (
            abs((parse_utc(product["ContentDate"]["Start"]) - s2_start).total_seconds()),
            1 if product["Name"].endswith("_COG.SAFE") else 0,
            product["Name"],
        ),
    )[0]


def resolve_s2(scene: Scene) -> dict[str, Any] | None:
    start, end = scene_day_bounds(scene.scene_date)
    polygon = bbox_to_polygon(scene.bbox_wgs84)
    flt = (
        "Collection/Name eq 'SENTINEL-2' and "
        f"OData.CSC.Intersects(area=geography'SRID=4326;{polygon}') and "
        f"ContentDate/Start gt {to_utc_z(start)} and "
        f"ContentDate/Start lt {to_utc_z(end)} and "
        f"contains(Name,'_T{scene.tile}_')"
    )
    products = query_catalog(flt, top=20)
    if not products:
        return None
    return choose_s2_product(products)


def resolve_s1(scene: Scene, s2_start: datetime) -> dict[str, Any] | None:
    window_start = s2_start - timedelta(days=S1_WINDOW_DAYS)
    window_end = s2_start + timedelta(days=S1_WINDOW_DAYS)
    polygon = bbox_to_polygon(scene.bbox_wgs84)

    def _search(extra_clause: str, top: int) -> list[dict[str, Any]]:
        flt = (
            "Collection/Name eq 'SENTINEL-1' and "
            f"OData.CSC.Intersects(area=geography'SRID=4326;{polygon}') and "
            f"ContentDate/Start gt {to_utc_z(window_start)} and "
            f"ContentDate/Start lt {to_utc_z(window_end)}"
        )
        if extra_clause:
            flt += f" and {extra_clause}"
        return query_catalog(flt, top=top)

    products = _search("contains(Name,'_GRD')", 200)
    if not products:
        products = _search("", 200)
    if not products:
        return None
    return choose_s1_product(products, s2_start)


def product_payload(product: dict[str, Any] | None) -> dict[str, Any] | None:
    if not product:
        return None
    return {
        "name": product["Name"],
        "start": product["ContentDate"]["Start"],
        "end": product["ContentDate"].get("End"),
    }


def resolve_scene(scene: Scene, cache: dict[str, Any], cache_path: Path) -> dict[str, Any]:
    cached = cache["records"].get(scene.key)
    if cached is not None:
        return cached

    s2_product = resolve_s2(scene)
    if s2_product is None:
        result = {
            "scene": asdict(scene),
            "s2": None,
            "s1": None,
            "delta_seconds": None,
            "error": "No Sentinel-2 catalog product found for MARIDA scene footprint and day.",
        }
        cache["records"][scene.key] = result
        save_cache(cache_path, cache)
        return result

    s2_payload = product_payload(s2_product)
    s2_start = parse_utc(s2_payload["start"])
    s1_product = resolve_s1(scene, s2_start)
    s1_payload = product_payload(s1_product)

    delta_seconds: float | None = None
    if s1_payload is not None:
        delta_seconds = (parse_utc(s1_payload["start"]) - s2_start).total_seconds()

    result = {
        "scene": asdict(scene),
        "s2": s2_payload,
        "s1": s1_payload,
        "delta_seconds": delta_seconds,
        "error": None if s1_payload is not None else "No intersecting Sentinel-1 product found.",
    }
    cache["records"][scene.key] = result
    save_cache(cache_path, cache)
    return result


def xml_space_attr(text: str) -> str:
    return ' xml:space="preserve"' if text[:1].isspace() or text[-1:].isspace() else ""


def make_run(text: str, *, bold: bool = False, size: int = 18) -> str:
    props = ["<w:rPr>"]
    if bold:
        props.append("<w:b/>")
    props.append(f'<w:sz w:val="{size}"/>')
    props.append(f'<w:szCs w:val="{size}"/>')
    props.append("</w:rPr>")
    return (
        "<w:r>"
        + "".join(props)
        + f"<w:t{xml_space_attr(text)}>{escape(text)}</w:t>"
        + "</w:r>"
    )


def make_paragraph(text: str, *, bold: bool = False, size: int = 20, center: bool = False) -> str:
    p_pr = "<w:pPr>"
    if center:
        p_pr += '<w:jc w:val="center"/>'
    p_pr += "</w:pPr>"
    return "<w:p>" + p_pr + make_run(text, bold=bold, size=size) + "</w:p>"


def make_cell(text: str, width: int, *, bold: bool = False, shade: str | None = None) -> str:
    tc_pr = [f'<w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>', '<w:vAlign w:val="top"/>']
    if shade:
        tc_pr.append(f'<w:shd w:val="clear" w:color="auto" w:fill="{shade}"/>')
    tc_pr.append("</w:tcPr>")
    return "<w:tc>" + "".join(tc_pr) + make_paragraph(text or "-", bold=bold, size=18) + "</w:tc>"


def make_table(rows: list[list[str]]) -> str:
    widths = [360, 780, 950, 3400, 1500, 3400, 1500, 1200, 850]
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
    for row_index, row in enumerate(rows):
        cells = []
        for col_index, value in enumerate(row):
            cells.append(
                make_cell(
                    value,
                    widths[col_index],
                    bold=row_index == 0,
                    shade=header_fill if row_index == 0 else None,
                )
            )
        xml_rows.append("<w:tr>" + "".join(cells) + "</w:tr>")
    return "<w:tbl>" + tbl_pr + grid + "".join(xml_rows) + "</w:tbl>"


def build_document_xml(records: list[dict[str, Any]], generated_at: datetime) -> str:
    resolved_s1 = sum(1 for record in records if record.get("s1"))
    unresolved = [record for record in records if record.get("error")]
    rows = [[
        "#",
        "Tile",
        "Scene Date",
        "Sentinel-2 Product",
        "S2 Acquired (UTC)",
        "Nearest Sentinel-1 Product",
        "S1 Acquired (UTC)",
        "Delta (S1 - S2)",
        "Hours",
    ]]

    for index, record in enumerate(records, start=1):
        s2 = record.get("s2") or {}
        s1 = record.get("s1") or {}
        delta_seconds = record.get("delta_seconds")
        delta = timedelta(seconds=delta_seconds) if delta_seconds is not None else None
        rows.append([
            str(index),
            record["scene"]["tile"],
            record["scene"]["scene_date"],
            s2.get("name", "-"),
            format_utc(s2.get("start")),
            s1.get("name", "-"),
            format_utc(s1.get("start")),
            format_delta(delta),
            delta_hours(delta),
        ])

    body = [
        make_paragraph("MARIDA S2 Scenes and Nearest S1 Acquisitions", bold=True, size=30, center=True),
        make_paragraph(
            f"Generated {generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')} from {len(records)} MARIDA scenes.",
            size=20,
        ),
        make_paragraph(
            (
                "Sentinel-2 products were resolved from the Copernicus Data Space catalog by MARIDA "
                "scene footprint and UTC day, preferring Level-2A and then the latest catalog version. "
                "Sentinel-1 products were resolved as the nearest intersecting GRD acquisition within "
                f"+/- {S1_WINDOW_DAYS} days, preferring native SAFE products over COG duplicates."
            ),
            size=18,
        ),
        make_paragraph(f"Nearest Sentinel-1 product resolved for {resolved_s1} of {len(records)} scenes.", size=18),
        make_table(rows),
    ]

    if unresolved:
        body.append(make_paragraph("Unresolved Scenes", bold=True, size=22))
        for record in unresolved:
            body.append(
                make_paragraph(
                    f"{record['scene']['key']}: {record['error']}",
                    size=18,
                )
            )

    body.append(
        """
<w:sectPr>
  <w:pgSz w:w="15840" w:h="12240" w:orient="landscape"/>
  <w:pgMar w:top="720" w:right="720" w:bottom="720" w:left="720" w:header="720" w:footer="720" w:gutter="0"/>
</w:sectPr>
""".strip()
    )

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
  <dc:title>MARIDA S2 Scenes and Nearest S1 Acquisitions</dc:title>
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
    scenes = discover_scenes(args.marida_root)
    if not scenes:
        raise SystemExit(f"No MARIDA scenes found under {args.marida_root}")

    cache = load_cache(args.cache_path)
    records = []
    for index, scene in enumerate(scenes, start=1):
        print(f"[{index}/{len(scenes)}] Resolving {scene.key} ...", flush=True)
        record = resolve_scene(scene, cache, args.cache_path)
        records.append(record)

    records.sort(key=lambda record: (record["scene"]["tile"], record["scene"]["scene_date"]))
    generated_at = datetime.now(tz=UTC)
    document_xml = build_document_xml(records, generated_at)
    write_docx(args.output_docx, document_xml, generated_at)

    resolved_s1 = sum(1 for record in records if record.get("s1"))
    print(f"Wrote {args.output_docx}")
    print(f"Resolved Sentinel-1 product for {resolved_s1}/{len(records)} scenes.")


if __name__ == "__main__":
    main()
