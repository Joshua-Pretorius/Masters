#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import xml.etree.ElementTree as ET
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile

import geopandas as gpd
from shapely.geometry import Point


WGS84_CRS = "EPSG:4326"
DOCX_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")
COORD_RE = re.compile(
    r"^\s*([0-9]+(?:\.[0-9]+)?)\D+([NS])\s*,\s*([0-9]+(?:\.[0-9]+)?)\D+([EW])\s*$"
)
WGS84_PRJ = """GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],PRIMEM["Greenwich",0],UNIT["Degree",0.0174532925199433]]"""


@dataclass(frozen=True)
class PointRecord:
    obs_date: str
    obs_time: str | None
    subcollect: int
    pt_order: int
    lat_dd: float
    lon_dd: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract Ghana Planet drift points from the full Word document and write one "
            "shapefile per date. Blank paragraphs split subcollections."
        )
    )
    parser.add_argument(
        "--docx-path",
        type=Path,
        default=Path(r"D:\Masters\Ghana_Drift\Ghana_planet_full_drift.docx"),
        help="Path to the Word document containing the dated drift point lists.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(r"D:\Masters\Ghana_Drift\planet"),
        help="Directory where per-date shapefiles will be written.",
    )
    return parser.parse_args()


def iter_docx_paragraphs(docx_path: Path) -> list[str]:
    with ZipFile(docx_path) as archive:
        xml_bytes = archive.read("word/document.xml")

    root = ET.fromstring(xml_bytes)
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", DOCX_NS):
        text = "".join(run.text or "" for run in paragraph.findall(".//w:t", DOCX_NS)).strip()
        paragraphs.append(text.replace("ｰ", "°"))
    return paragraphs


def parse_coordinate(text: str) -> tuple[float, float] | None:
    match = COORD_RE.match(text)
    if not match:
        return None

    lat = float(match.group(1))
    if match.group(2) == "S":
        lat *= -1

    lon = float(match.group(3))
    if match.group(4) == "W":
        lon *= -1

    return lat, lon


def iso_date(text: str) -> str:
    day, month, year = text.split("/")
    return f"{year}-{month}-{day}"


def parse_point_records(paragraphs: list[str]) -> OrderedDict[str, list[PointRecord]]:
    records_by_date: OrderedDict[str, list[PointRecord]] = OrderedDict()
    current_date: str | None = None
    current_time: str | None = None
    current_subcollect: int | None = None
    point_order = 0

    for raw_text in paragraphs:
        text = raw_text.strip()

        if DATE_RE.match(text):
            current_date = iso_date(text)
            records_by_date.setdefault(current_date, [])
            current_time = None
            current_subcollect = None
            point_order = 0
            continue

        if current_date is None:
            continue

        if TIME_RE.match(text):
            current_time = text
            continue

        if not text:
            current_subcollect = None
            continue

        coords = parse_coordinate(text)
        if coords is None:
            continue

        if current_subcollect is None:
            last_sub = records_by_date[current_date][-1].subcollect if records_by_date[current_date] else 0
            current_subcollect = last_sub + 1

        point_order += 1
        lat_dd, lon_dd = coords
        records_by_date[current_date].append(
            PointRecord(
                obs_date=current_date,
                obs_time=current_time,
                subcollect=current_subcollect,
                pt_order=point_order,
                lat_dd=lat_dd,
                lon_dd=lon_dd,
            )
        )

    return records_by_date


def build_geodataframe(records: list[PointRecord]) -> gpd.GeoDataFrame:
    rows = [
        {
            "obs_date": record.obs_date,
            "obs_time": record.obs_time or "",
            "subcollect": record.subcollect,
            "pt_order": record.pt_order,
            "lat_dd": record.lat_dd,
            "lon_dd": record.lon_dd,
            "geometry": Point(record.lon_dd, record.lat_dd),
        }
        for record in records
    ]
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=WGS84_CRS)


def build_empty_geodataframe(obs_date: str) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "obs_date": [obs_date],
            "obs_time": [""],
            "subcollect": [0],
            "pt_order": [0],
            "lat_dd": [None],
            "lon_dd": [None],
            "geometry": [None],
        },
        geometry="geometry",
        crs=WGS84_CRS,
    ).iloc[0:0]


def write_prj(shapefile_path: Path) -> None:
    shapefile_path.with_suffix(".prj").write_text(WGS84_PRJ, encoding="ascii")


def write_shapefiles(records_by_date: OrderedDict[str, list[PointRecord]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    for obs_date, records in records_by_date.items():
        gdf = build_geodataframe(records) if records else build_empty_geodataframe(obs_date)
        shapefile_path = output_dir / f"ghana_planet_{obs_date}.shp"
        gdf.to_file(shapefile_path, driver="ESRI Shapefile")
        write_prj(shapefile_path)
        print(
            f"{shapefile_path.name}: points={len(records)} "
            f"subcollections={len({record.subcollect for record in records}) if records else 0}"
        )


def main() -> None:
    args = parse_args()
    paragraphs = iter_docx_paragraphs(args.docx_path)
    records_by_date = parse_point_records(paragraphs)
    write_shapefiles(records_by_date, args.output_dir)


if __name__ == "__main__":
    main()
