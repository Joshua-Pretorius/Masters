#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
import re
import sys
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape


UTC = timezone.utc
CATALOG_BASE = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import slc_match_aoi as aoi

OUT_DIR = ROOT_DIR / "meria_sa_plastic_s1_slc"
CACHE_PATH = OUT_DIR / "copernicus_s1_slc_cache.json"
DOCX_PATH = OUT_DIR / "MERIA_SA_plastic_nearest_S1_SLC_before_after.docx"
CSV_PATH = OUT_DIR / "MERIA_SA_plastic_nearest_S1_SLC_before_after.csv"
POINTS_CSV_PATH = OUT_DIR / "MERIA_SA_plastic_points.csv"
SHP_PATH = OUT_DIR / "MERIA_SA_plastic_points.shp"
GPKG_PATH = OUT_DIR / "MERIA_SA_plastic_points.gpkg"
PLANET_LOOKUP_PATH = ROOT_DIR / "meria_planet_acquisitions.json"
AOI_BUFFER_KM = 5.0
COVERAGE_THRESHOLD = 0.75


@dataclass(frozen=True)
class Observation:
    obs_id: str
    area: str
    date: str
    coords_dms: tuple[str, ...]
    notes: str = ""


OBSERVATIONS = [
    Observation(
        "MERIA_SA_001",
        "Durban",
        "2019-04-24",
        (
            "29° 49′ 33″ S 31° 15′ 07″ E",
            "29° 48′ 40″ S 31° 15′ 26″ E",
            "29° 47′ 09″ S 31° 16′ 09″ E",
            "29° 45′ 18″ S 31° 17′ 59″ E",
            "29° 45′ 42″ S 31° 04′ 01″ E",
            "29° 45′ 46″ S 31° 19′ 23″ E",
            "29° 59′ 32″ S 31° 07′ 59″ E",
        ),
        "Should look 24th onwards.. Big long patch of debris at the mark where river water meets seawater. Thin patch. Lots of ships around need to watch out for false positives.",
    ),
    Observation(
        "MERIA_SA_002",
        "Durban",
        "2019-04-25",
        (
            "29° 50′ 25″ S 31° 03′ 02″ E",
            "29° 57′ 14″ S 31° 03′ 42″ E",
            "29° 56′ 47″ S 31° 03′ 06″ E",
        ),
        "Same as the day before except further south and some accumulation towards the harbour.",
    ),
    Observation(
        "MERIA_SA_003",
        "Durban",
        "2022-04-14",
        (
            "29° 34′ 14″ S 31° 16′ 06″ E",
            "29° 34′ 35″ S 31° 16′ 27″ E",
            "29° 41′ 58″ S 31° 15′ 24″ E",
            "29° 42′ 21″ S 31° 13′ 27″ E",
            "29° 47′ 11″ S 31° 13′ 31″ E",
            "29° 47′ 11″ S 31° 13′ 31″ E",
            "29° 49′ 30″ S 31° 10′ 27″ E",
            "29° 43′ 40″ S 31° 19′ 56″ E",
        ),
        "After large amounts of flooding recorded on the 11th of April onwards. So we would expect to see plastic closer to shore on the 11th - 12th and then further out on the 14th which is seen in the planet images. Too much cloud cover during flood though. But visible debris patches across the area on the 14th out to sea.",
    ),
    Observation(
        "MERIA_SA_004",
        "Durban",
        "2022-04-24",
        (
            "29° 55′ 58″ S 31° 05′ 35″ E",
            "29° 55′ 33″ S 31° 05′ 40″ E",
            "29° 44′ 36″ S 31° 10′ 24″ E",
        ),
        "Still visible debris long after the flood event happened. Could be a nice case to track the drift of the debris.",
    ),
    Observation(
        "MERIA_SA_005",
        "East London",
        "2024-06-13",
        (
            "32° 55′ 51″ S 28° 19′ 24″ E",
            "32° 54′ 17″ S 28° 21′ 10″ E",
        ),
        "Flood was before the 4th of June but too much cloud cover until the 13th. Still visible on the 13th further out to sea.",
    ),
    Observation(
        "MERIA_SA_006",
        "East London",
        "2024-06-06",
        (
            "33° 13′ 47″ S 27° 35′ 45″ E",
            "33° 07′ 50″ S 27° 44′ 23″ E",
        ),
        "Small section with no cloud cover - could be debris.",
    ),
    Observation(
        "MERIA_SA_007",
        "East London",
        "2024-06-04",
        ("33° 14′ 22″ S 27° 43′ 41″ E",),
        "Small section with no cloud cover - could be debris.",
    ),
    Observation(
        "MERIA_SA_008",
        "Gqeberha",
        "2024-06-09",
        (
            "33° 59′ S 25° 11′ E",
            "34° 03′ 49″ S 25° 26′ 35″ E",
        ),
    ),
]


def parse_dms(text: str) -> tuple[float, float]:
    parts = re.findall(r"(\d+(?:\.\d+)?)\s*°(?:\s*(\d+(?:\.\d+)?)\s*[′']?)?(?:\s*(\d+(?:\.\d+)?)\s*[″\"]?)?\s*([NSEW])", text)
    if len(parts) != 2:
        raise ValueError(f"Could not parse coordinate: {text}")
    values = []
    for deg, minute, second, hemi in parts:
        value = float(deg) + (float(minute or 0) / 60.0) + (float(second or 0) / 3600.0)
        if hemi in {"S", "W"}:
            value *= -1
        values.append(value)
    lat, lon = values[0], values[1]
    return lat, lon


def day_bounds(date_text: str) -> tuple[datetime, datetime]:
    start = datetime.strptime(date_text, "%Y-%m-%d").replace(tzinfo=UTC)
    return start, start + timedelta(days=1)


def load_planet_lookup() -> dict[str, dict[str, Any]]:
    payload = json.loads(PLANET_LOOKUP_PATH.read_text(encoding="utf-8"))
    return payload["sa"]


def to_utc_z(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def bbox_for_observation(obs: Observation, pad_deg: float = 0.03) -> tuple[float, float, float, float]:
    coords = observation_points_latlon(obs)
    lats = [lat for lat, _ in coords]
    lons = [lon for _, lon in coords]
    return (
        min(lons) - pad_deg,
        min(lats) - pad_deg,
        max(lons) + pad_deg,
        max(lats) + pad_deg,
    )


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


def build_odata_url(filter_expr: str, top: int = 100, order: str = "desc") -> str:
    params = {
        "$top": str(top),
        "$orderby": f"ContentDate/Start {order}",
        "$filter": filter_expr,
    }
    query = urlencode(params, quote_via=quote, safe="()',$;/:_-.=")
    return f"{CATALOG_BASE}?{query}"


def request_json(url: str, retries: int = 4) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            req = Request(url, headers={"User-Agent": "Codex MERIA S1 SLC Resolver"})
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
    raise RuntimeError("Catalog request failed.")


def load_cache() -> dict[str, Any]:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict[str, Any]) -> None:
    CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")


def s1_identity_key(name: str) -> str:
    match = re.match(r"^(.*)_[0-9A-F]{4}(?:_COG)?\.SAFE$", name)
    return match.group(1) if match else name


def observation_points_latlon(obs: Observation) -> list[tuple[float, float]]:
    return [parse_dms(c) for c in obs.coords_dms]


def candidate_products(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for product in products:
        grouped.setdefault(s1_identity_key(product["Name"]), []).append(product)
    deduped = [
        sorted(items, key=lambda p: (1 if p["Name"].endswith("_COG.SAFE") else 0, p["Name"]))[0]
        for items in grouped.values()
    ]
    return sorted(deduped, key=lambda p: parse_utc(p["ContentDate"]["Start"]))


def cached_payload_is_usable(payload: dict[str, Any] | None) -> bool:
    if payload is None:
        return True
    required = {"candidate_count", "coverage_ratio", "rejection_reason"}
    return required.issubset(payload)


def select_candidate(products: list[dict[str, Any]], direction: str, points: list[tuple[float, float]]) -> dict[str, Any]:
    ordered = candidate_products(products)
    if direction == "before":
        ordered = list(reversed(ordered))
    coverage_by_name: dict[str, float] = {}
    for product in ordered:
        coverage = aoi.coverage_ratio_for_scene(points, product.get("GeoFootprint"), buffer_km=AOI_BUFFER_KM)
        coverage_by_name[product["Name"]] = coverage
        if coverage >= COVERAGE_THRESHOLD:
            return {
                "name": product["Name"],
                "start": product["ContentDate"]["Start"],
                "end": product["ContentDate"].get("End"),
                "id": product.get("Id"),
                "coverage_ratio": f"{coverage:.3f}",
                "candidate_count": len(ordered),
                "rejection_reason": "-",
            }
    rejection_reason = "-" if not ordered else f"no candidate met {COVERAGE_THRESHOLD:.2f} coverage threshold"
    return {
        "name": None,
        "start": None,
        "end": None,
        "id": None,
        "coverage_ratio": "-",
        "candidate_count": len(ordered),
        "rejection_reason": rejection_reason,
    }


def planet_window(obs: Observation, planet_lookup: dict[str, dict[str, Any]]) -> tuple[datetime, datetime]:
    entry = planet_lookup[obs.obs_id]
    return parse_utc(entry["planet_acquired_start"]), parse_utc(entry["planet_acquired_end"])


def query_s1_slc(
    obs: Observation,
    direction: str,
    cache: dict[str, Any],
    planet_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    planet_start, planet_end = planet_window(obs, planet_lookup)
    if direction == "before":
        window_start = planet_start - timedelta(days=30)
        window_end = planet_start
        order = "desc"
    elif direction == "after":
        window_start = planet_end
        window_end = planet_end + timedelta(days=30)
        order = "asc"
    else:
        raise ValueError(direction)

    key = f"{obs.obs_id}:{direction}:{to_utc_z(window_start)}:{to_utc_z(window_end)}"
    if key in cache and cached_payload_is_usable(cache[key]):
        return cache[key]

    polygon = bbox_to_polygon(bbox_for_observation(obs))
    flt = (
        "Collection/Name eq 'SENTINEL-1' and "
        f"OData.CSC.Intersects(area=geography'SRID=4326;{polygon}') and "
        f"ContentDate/Start gt {to_utc_z(window_start)} and "
        f"ContentDate/Start lt {to_utc_z(window_end)} and "
        "contains(Name,'_SLC_')"
    )
    url = build_odata_url(flt, top=100, order=order)
    products = request_json(url).get("value", [])
    payload = select_candidate(products, direction, observation_points_latlon(obs))
    cache[key] = payload
    save_cache(cache)
    return payload


def format_dt(value: str | None) -> str:
    if not value:
        return "-"
    return parse_utc(value).strftime("%Y-%m-%d %H:%M:%S UTC")


def format_planet_acquired(obs: Observation, planet_lookup: dict[str, dict[str, Any]]) -> str:
    planet_start, planet_end = planet_window(obs, planet_lookup)
    start_text = planet_start.strftime("%Y-%m-%d %H:%M:%S UTC")
    end_text = planet_end.strftime("%Y-%m-%d %H:%M:%S UTC")
    return start_text if planet_start == planet_end else f"{start_text} to {end_text}"


def delta_from_planet_window(
    obs: Observation,
    product: dict[str, Any] | None,
    planet_lookup: dict[str, dict[str, Any]],
) -> str:
    if not product or not product.get("start"):
        return "-"
    planet_start, planet_end = planet_window(obs, planet_lookup)
    product_start = parse_utc(product["start"])
    lower_h = (product_start - planet_end).total_seconds() / 3600.0
    upper_h = (product_start - planet_start).total_seconds() / 3600.0
    if math.isclose(lower_h, upper_h, rel_tol=0.0, abs_tol=1e-9):
        return f"{lower_h:+.2f}"
    return f"{lower_h:+.2f} to {upper_h:+.2f}"


def point_coordinates(obs: Observation) -> str:
    return "; ".join(obs.coords_dms)


def product_value(product: dict[str, Any] | None, key: str, default: str = "-") -> str:
    if not product:
        return default
    value = product.get(key)
    if value in {None, ""}:
        return default
    return str(value)


def write_points() -> dict[str, bool]:
    records = []
    for obs in OBSERVATIONS:
        for idx, coord_text in enumerate(obs.coords_dms, start=1):
            lat, lon = parse_dms(coord_text)
            records.append(
                {
                    "obs_id": obs.obs_id,
                    "obs_date": obs.date,
                    "area": obs.area,
                    "pt_id": f"{obs.obs_id}_P{idx:02d}",
                    "lat": lat,
                    "lon": lon,
                    "dms": coord_text,
                    "notes": obs.notes,
                }
            )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with POINTS_CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["obs_id", "obs_date", "area", "pt_id", "lat", "lon", "dms", "notes"])
        writer.writeheader()
        for record in records:
            writer.writerow({k: record[k] for k in writer.fieldnames})

    try:
        import geopandas as gpd
        from shapely.geometry import Point
    except ModuleNotFoundError:
        print("Skipped shapefile and GPKG export because geopandas/shapely are not installed.")
        return {"csv": True, "shp": False, "gpkg": False}

    geo_records = [{**record, "geometry": Point(record["lon"], record["lat"])} for record in records]
    gdf = gpd.GeoDataFrame(geo_records, geometry="geometry", crs="EPSG:4326")
    gdf[["obs_id", "obs_date", "area", "pt_id", "lat", "lon", "notes", "geometry"]].to_file(SHP_PATH)
    gdf[["obs_id", "obs_date", "area", "pt_id", "lat", "lon", "dms", "notes", "geometry"]].to_file(
        GPKG_PATH,
        layer="meria_sa_plastic_points",
        driver="GPKG",
    )
    return {"csv": True, "shp": True, "gpkg": True}


def xml_space_attr(text: str) -> str:
    return ' xml:space="preserve"' if text[:1].isspace() or text[-1:].isspace() else ""


def run(text: str, *, bold: bool = False, size: int = 18) -> str:
    props = ["<w:rPr>"]
    if bold:
        props.append("<w:b/>")
    props.append(f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>')
    props.append("</w:rPr>")
    return f"<w:r>{''.join(props)}<w:t{xml_space_attr(text)}>{escape(text)}</w:t></w:r>"


def paragraph(text: str, *, bold: bool = False, size: int = 20) -> str:
    return "<w:p>" + run(text, bold=bold, size=size) + "</w:p>"


def cell(text: str, width: int, *, bold: bool = False, shade: str | None = None) -> str:
    shade_xml = f'<w:shd w:val="clear" w:color="auto" w:fill="{shade}"/>' if shade else ""
    return (
        f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/><w:vAlign w:val="top"/>{shade_xml}</w:tcPr>'
        f"{paragraph(text or '-', bold=bold, size=16)}</w:tc>"
    )


def table(rows: list[list[str]]) -> str:
    widths = [780, 900, 820, 1450, 520, 2000, 1700, 900, 1700, 900, 850, 850, 850, 850, 2000]
    grid = "<w:tblGrid>" + "".join(f'<w:gridCol w:w="{w}"/>' for w in widths) + "</w:tblGrid>"
    props = """
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
    out_rows = []
    for ridx, row in enumerate(rows):
        out_rows.append(
            "<w:tr>"
            + "".join(cell(value, widths[cidx], bold=ridx == 0, shade="DCE6F1" if ridx == 0 else None) for cidx, value in enumerate(row))
            + "</w:tr>"
        )
    return "<w:tbl>" + props + grid + "".join(out_rows) + "</w:tbl>"


def build_docx(rows: list[dict[str, str]]) -> None:
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    table_rows = [[
        "Obs ID",
        "Area",
        "Planet date",
        "Planet acquired",
        "Points",
        "Point coordinates",
        "S1 SLC before product",
        "Before cov",
        "Before acquired",
        "S1 SLC after product",
        "After cov",
        "After acquired",
        "Before h",
        "After h",
        "Observation notes",
    ]]
    for row in rows:
        table_rows.append([
            row["obs_id"],
            row["area"],
            row["date"],
            row["planet_acquired"],
            row["points"],
            row["point_coordinates"],
            row["before_name"],
            row["before_coverage_ratio"],
            row["before_start"],
            row["after_name"],
            row["after_coverage_ratio"],
            row["after_start"],
            row["before_delta_h"],
            row["after_delta_h"],
            row["notes"],
        ])

    body = [
        paragraph("MERIA South Africa Plastic Observations: Nearest Sentinel-1 SLC Acquisitions", bold=True, size=28),
        paragraph(f"Generated {generated}. Source: Data_Creation/MERIA_IDS_OF_INTERESTS.docx.", size=18),
        paragraph(
            "Planet acquisition times were resolved as the same-day intersecting PlanetScope acquisition window for each South Africa observation. Sentinel-1 matching now uses a broad search, then keeps only scenes covering at least 75% of a 5 km buffered seed-point AOI before choosing the nearest acceptable SLC before the start of that Planet window and after the end of it. Delta values are reported as SAR minus Planet and become ranges when multiple Planet scenes contributed to the observation day.",
            size=18,
        ),
        table(table_rows),
        """
<w:sectPr>
  <w:pgSz w:w="16840" w:h="11900" w:orient="landscape"/>
  <w:pgMar w:top="500" w:right="500" w:bottom="500" w:left="500" w:header="500" w:footer="500" w:gutter="0"/>
</w:sectPr>
""".strip(),
    ]
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
        + "".join(body)
        + "</w:body></w:document>"
    )
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""
    with zipfile.ZipFile(DOCX_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document_xml)


def build_row(
    obs: Observation,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    planet_lookup: dict[str, dict[str, Any]],
) -> dict[str, str]:
    return {
        "obs_id": obs.obs_id,
        "area": obs.area,
        "date": obs.date,
        "planet_acquired": format_planet_acquired(obs, planet_lookup),
        "points": str(len(obs.coords_dms)),
        "point_coordinates": point_coordinates(obs),
        "before_name": product_value(before, "name"),
        "before_start": format_dt(before["start"] if before else None),
        "before_delta_h": delta_from_planet_window(obs, before, planet_lookup),
        "before_coverage_ratio": product_value(before, "coverage_ratio"),
        "before_candidate_count": product_value(before, "candidate_count"),
        "before_rejection_reason": product_value(before, "rejection_reason"),
        "before_download_group_key": product_value(before, "name").removesuffix(".SAFE") if product_value(before, "name") != "-" else "-",
        "after_name": product_value(after, "name"),
        "after_start": format_dt(after["start"] if after else None),
        "after_delta_h": delta_from_planet_window(obs, after, planet_lookup),
        "after_coverage_ratio": product_value(after, "coverage_ratio"),
        "after_candidate_count": product_value(after, "candidate_count"),
        "after_rejection_reason": product_value(after, "rejection_reason"),
        "after_download_group_key": product_value(after, "name").removesuffix(".SAFE") if product_value(after, "name") != "-" else "-",
        "aoi_buffer_km": f"{AOI_BUFFER_KM:.1f}",
        "coverage_threshold": f"{COVERAGE_THRESHOLD:.2f}",
        "notes": obs.notes,
    }


def build_rows(cache: dict[str, Any], planet_lookup: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for obs in OBSERVATIONS:
        before = query_s1_slc(obs, "before", cache, planet_lookup)
        after = query_s1_slc(obs, "after", cache, planet_lookup)
        rows.append(build_row(obs, before, after, planet_lookup))
    return rows


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    point_outputs = write_points()
    cache = load_cache()
    planet_lookup = load_planet_lookup()
    rows = build_rows(cache, planet_lookup)

    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    build_docx(rows)
    print(f"Wrote {DOCX_PATH}")
    print(f"Wrote {CSV_PATH}")
    print(f"Wrote {POINTS_CSV_PATH}")
    if point_outputs["shp"]:
        print(f"Wrote {SHP_PATH}")
    if point_outputs["gpkg"]:
        print(f"Wrote {GPKG_PATH}")


if __name__ == "__main__":
    main()
