#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import json
import netrc
import os
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import MultiPoint, Point, Polygon, box


ASF_PARAM = "https://api.daac.asf.alaska.edu/services/search/param"
WINDOWS_NETRC = Path("/mnt/c/Users/Joshua Pretorius/_netrc")
HTTP_TIMEOUT = 180


@dataclass(frozen=True)
class Target:
    target_id: str
    label: str
    lat: float
    lon: float
    source_id: str | None = None
    scene_center_lat: float | None = None
    scene_center_lon: float | None = None


@dataclass(frozen=True)
class DateRequest:
    label: str
    target_time: str
    search_start: str
    search_end: str
    must_be_before: str | None = None


TARGETS = [
    Target(
        target_id="honduras_found_20171017",
        label="Honduras Ocean Scan detection",
        lat=15.95362,
        lon=-86.77741,
        source_id="33a32832-fc41-4fdd-8c91-a41844fc1709",
        scene_center_lat=16.025,
        scene_center_lon=-86.392,
    ),
    Target(
        target_id="belize_20171017",
        label="16 deg 20 min 13 sec N, 88 deg 26 min 19 sec W",
        lat=16.0 + 20.0 / 60.0 + 13.0 / 3600.0,
        lon=-(88.0 + 26.0 / 60.0 + 19.0 / 3600.0),
    ),
]

DATE_REQUESTS = [
    DateRequest(
        label="2017-10-17_closest",
        target_time="2017-10-17T11:37:00Z",
        search_start="2017-10-10T00:00:00Z",
        search_end="2017-10-20T23:59:59Z",
    ),
    DateRequest(
        label="2017-10-15_before17",
        target_time="2017-10-15T12:00:00Z",
        search_start="2017-10-09T00:00:00Z",
        search_end="2017-10-17T11:37:00Z",
        must_be_before="2017-10-17T11:37:00Z",
    ),
]


def parse_utc(text: str) -> pd.Timestamp:
    return pd.to_datetime(text, utc=True)


def fmt_asf_time(text: str) -> str:
    return parse_utc(text).strftime("%Y-%m-%dT%H:%M:%SUTC")


def product_footprint(row: pd.Series) -> Polygon:
    points = [
        (row["Near Start Lon"], row["Near Start Lat"]),
        (row["Near End Lon"], row["Near End Lat"]),
        (row["Far End Lon"], row["Far End Lat"]),
        (row["Far Start Lon"], row["Far Start Lat"]),
    ]
    return Polygon(points)


def query_slc(aoi: Polygon, request: DateRequest) -> pd.DataFrame:
    params = {
        "platform": "s1",
        "processingLevel": "SLC",
        "beamMode": "IW",
        "output": "CSV",
        "maxResults": "100",
        "intersectsWith": aoi.wkt,
        "start": fmt_asf_time(request.search_start),
        "end": fmt_asf_time(request.search_end),
    }
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            response = requests.get(
                ASF_PARAM,
                params=params,
                timeout=HTTP_TIMEOUT,
                headers={"Accept": "text/csv", "User-Agent": "ocean-scan-slc-targets/1.0"},
            )
            response.raise_for_status()
            if not response.content.strip():
                return pd.DataFrame()
            df = pd.read_csv(io.BytesIO(response.content))
            if df.empty:
                return df
            df["acq_dt"] = pd.to_datetime(df["Acquisition Date"], utc=True, errors="coerce")
            return df.dropna(subset=["acq_dt"]).drop_duplicates(subset=["Granule Name"])
        except Exception as exc:  # ASF occasionally returns transient 5xx/timeouts.
            last_error = exc
            time.sleep(2**attempt)
    raise RuntimeError(f"ASF query failed after retries: {last_error}")


def select_product(df: pd.DataFrame, target: Target, aoi: Polygon, request: DateRequest) -> pd.Series:
    if df.empty:
        raise RuntimeError(f"No SLC candidates for {target.target_id} {request.label}")

    target_time = parse_utc(request.target_time)
    point = Point(target.lon, target.lat)
    scored = []
    for _, row in df.iterrows():
        footprint = product_footprint(row)
        cover_frac = 0.0
        if footprint.is_valid and not footprint.is_empty:
            cover_frac = footprint.intersection(aoi).area / aoi.area
        contains_point = footprint.contains(point) or footprint.touches(point)
        if request.must_be_before and row["acq_dt"] >= parse_utc(request.must_be_before):
            continue
        if not contains_point or cover_frac < 0.95:
            continue
        scored.append(
            (
                abs((row["acq_dt"] - target_time).total_seconds()),
                -cover_frac,
                row["Granule Name"],
                row,
            )
        )

    if not scored:
        raise RuntimeError(
            f"No containing SLC candidate for {target.target_id} {request.label}; "
            "try increasing the AOI size or search window."
        )
    scored.sort(key=lambda item: item[:3])
    return scored[0][3]


def edl_auth() -> tuple[str | None, str | None]:
    user, password = os.getenv("EDL_USER"), os.getenv("EDL_PASS")
    if user and password:
        return user, password
    for candidate in (None, Path.home() / ".netrc", Path.home() / "_netrc", WINDOWS_NETRC):
        try:
            auths = netrc.netrc(str(candidate)) if candidate else netrc.netrc()
            cred = auths.authenticators("urs.earthdata.nasa.gov")
            if cred and cred[0] and cred[2]:
                return cred[0], cred[2]
        except Exception:
            continue
    return None, None


def open_asf_stream(
    session: requests.Session,
    url: str,
    auth: tuple[str | None, str | None],
    headers: dict[str, str],
) -> requests.Response:
    """Follow ASF redirects while applying Basic auth only at URS."""
    current_url = url
    for _ in range(12):
        host = urlparse(current_url).netloc
        request_auth = auth if host == "urs.earthdata.nasa.gov" else None
        response = session.get(
            current_url,
            headers=headers,
            auth=request_auth,
            allow_redirects=False,
            stream=True,
            timeout=HTTP_TIMEOUT,
        )
        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get("location")
            response.close()
            if not location:
                raise RuntimeError(f"Redirect without Location from {current_url}")
            current_url = urljoin(current_url, location)
            continue
        return response
    raise RuntimeError(f"Too many redirects while opening {url}")


def total_size_from_content_range(value: str | None) -> int | None:
    if not value or "/" not in value:
        return None
    total = value.rsplit("/", 1)[-1]
    return None if total == "*" else int(total)


def download_zip(url: str, out_path: Path, auth: tuple[str | None, str | None]) -> None:
    if out_path.exists() and out_path.stat().st_size > 100_000_000:
        print(f"[skip] {out_path.name} already exists ({out_path.stat().st_size / 1e9:.2f} GB)")
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not auth[0] or not auth[1]:
        raise RuntimeError("Earthdata credentials are required to download ASF products.")

    partial_path = out_path.with_suffix(out_path.suffix + ".part")
    existing = partial_path.stat().st_size if partial_path.exists() else 0
    headers = {"User-Agent": "ocean-scan-slc-targets/1.0"}
    if existing:
        headers["Range"] = f"bytes={existing}-"

    with requests.Session() as session:
        response = open_asf_stream(session, url, auth, headers)
        if response.status_code == 416 and existing:
            response.close()
            partial_path.unlink()
            existing = 0
            headers.pop("Range", None)
            response = open_asf_stream(session, url, auth, headers)
        response.raise_for_status()

        if response.status_code == 206 and existing:
            mode = "ab"
            total = total_size_from_content_range(response.headers.get("content-range"))
        else:
            mode = "wb"
            existing = 0
            total = int(response.headers.get("content-length", "0")) or None

        written = existing
        next_report = written + 512 * 1024 * 1024
        with partial_path.open(mode + "") as handle:
            for chunk in response.iter_content(1024 * 1024):
                if not chunk:
                    continue
                handle.write(chunk)
                written += len(chunk)
                if written >= next_report:
                    if total:
                        pct = written * 100.0 / total
                        print(f"  {out_path.name}: {written / 1e9:.2f}/{total / 1e9:.2f} GB ({pct:.1f}%)")
                    else:
                        print(f"  {out_path.name}: {written / 1e9:.2f} GB")
                    next_report = written + 512 * 1024 * 1024
        response.close()

    if total and written != total:
        raise RuntimeError(f"Incomplete download for {out_path.name}: {written} of {total} bytes")
    partial_path.replace(out_path)
    print(f"[downloaded] {out_path.name} ({out_path.stat().st_size / 1e9:.2f} GB)")


def write_aoi_shapefile(target: Target, aoi: Polygon, shp_path: Path) -> None:
    shp_path.parent.mkdir(parents=True, exist_ok=True)
    if shp_path.exists():
        return
    gdf = gpd.GeoDataFrame(
        [
            {
                "id": target.target_id,
                "label": target.label,
                "lat": target.lat,
                "lon": target.lon,
            }
        ],
        geometry=[aoi],
        crs="EPSG:4326",
    )
    gdf.to_file(shp_path)


def annotation_hull_from_zip(zip_path: Path, subswath: str) -> Polygon | None:
    ss = subswath.lower()
    with zipfile.ZipFile(zip_path) as archive:
        matches = [
            name
            for name in archive.namelist()
            if f"/annotation/s1" in name.lower()
            and f"-{ss}-slc-vv-" in name.lower()
            and name.lower().endswith(".xml")
        ]
        if not matches:
            matches = [
                name
                for name in archive.namelist()
                if f"/annotation/s1" in name.lower()
                and f"-{ss}-slc-" in name.lower()
                and name.lower().endswith(".xml")
            ]
        if not matches:
            return None
        root = ET.fromstring(archive.read(matches[0]))

    coords: list[tuple[float, float]] = []
    for item in root.findall(".//geolocationGridPoint"):
        lat_node = item.find("latitude")
        lon_node = item.find("longitude")
        if lat_node is None or lon_node is None or lat_node.text is None or lon_node.text is None:
            continue
        coords.append((float(lon_node.text), float(lat_node.text)))
    if len(coords) < 3:
        return None
    hull = MultiPoint(coords).convex_hull
    if hull.geom_type == "Polygon":
        return hull
    return None


def infer_subswaths(zip_path: Path, aoi: Polygon, target: Target) -> list[dict]:
    point = Point(target.lon, target.lat)
    rows = []
    for ss in ("IW1", "IW2", "IW3"):
        hull = annotation_hull_from_zip(zip_path, ss)
        if hull is None:
            continue
        cover_frac = hull.intersection(aoi).area / aoi.area
        contains_point = hull.contains(point) or hull.touches(point)
        rows.append(
            {
                "subswath": ss,
                "contains_point": contains_point,
                "aoi_cover_frac": cover_frac,
            }
        )
    selected = [row for row in rows if row["contains_point"] and row["aoi_cover_frac"] > 0.20]
    if not selected:
        selected = [row for row in rows if row["aoi_cover_frac"] > 0.20]
    if not selected:
        raise RuntimeError(f"Could not infer covering subswath for {target.target_id} from {zip_path.name}")
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description="Download targeted Ocean Scan Sentinel-1 SLCs and write manifests.")
    parser.add_argument(
        "--out-root",
        default=str(Path(__file__).resolve().parents[2] / "downloads_S1" / "ocean_scan_2017"),
    )
    parser.add_argument("--half-size-deg", type=float, default=0.10)
    parser.add_argument("--skip-download", action="store_true")
    args = parser.parse_args()

    out_root = Path(args.out_root)
    cache_dir = out_root / "_slc_cache"
    aoi_dir = out_root / "_aois"
    auth = edl_auth()
    if not args.skip_download and (not auth[0] or not auth[1]):
        raise RuntimeError("No Earthdata credentials found in env, ~/.netrc, or Windows _netrc.")

    summary = []
    for target in TARGETS:
        aoi = box(
            target.lon - args.half_size_deg,
            target.lat - args.half_size_deg,
            target.lon + args.half_size_deg,
            target.lat + args.half_size_deg,
        )
        shp_path = aoi_dir / f"{target.target_id}.shp"
        write_aoi_shapefile(target, aoi, shp_path)

        for request in DATE_REQUESTS:
            df = query_slc(aoi, request)
            row = select_product(df, target, aoi, request)
            granule = row["Granule Name"]
            zip_path = cache_dir / f"{granule}.zip"
            if not args.skip_download:
                print(f"[download] {target.target_id} {request.label}: {granule}")
                download_zip(row["URL"], zip_path, auth)

            subswaths: list[dict] = []
            if zip_path.exists() and zip_path.stat().st_size > 100_000_000:
                subswaths = infer_subswaths(zip_path, aoi, target)

            delta_hours = (row["acq_dt"] - parse_utc(request.target_time)).total_seconds() / 3600.0
            manifest = {
                "aoi_id": target.target_id,
                "date": request.label,
                "target": {
                    "label": target.label,
                    "lat": target.lat,
                    "lon": target.lon,
                    "source_id": target.source_id,
                    "scene_center_lat": target.scene_center_lat,
                    "scene_center_lon": target.scene_center_lon,
                    "aoi_half_size_deg": args.half_size_deg,
                    "aoi_shp": str(shp_path),
                },
                "aoi_shp": str(shp_path),
                "request": {
                    "label": request.label,
                    "target_time_utc": parse_utc(request.target_time).isoformat(),
                    "search_start_utc": parse_utc(request.search_start).isoformat(),
                    "search_end_utc": parse_utc(request.search_end).isoformat(),
                    "must_be_before_utc": parse_utc(request.must_be_before).isoformat()
                    if request.must_be_before
                    else None,
                },
                "slc": {
                    "granule": granule,
                    "platform": row.get("Platform"),
                    "acquisition_date": row["Acquisition Date"],
                    "url": row["URL"],
                    "zip": str(zip_path),
                    "size_mb": float(row["Size (MB)"]),
                    "delta_hours_from_target": delta_hours,
                    "subswaths": [item["subswath"] for item in subswaths],
                    "subswath_coverage": subswaths,
                },
            }
            manifest_dir = out_root / target.target_id / request.label
            manifest_dir.mkdir(parents=True, exist_ok=True)
            manifest_path = manifest_dir / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            summary.append(
                {
                    "target": target.target_id,
                    "request": request.label,
                    "granule": granule,
                    "acquisition_date": row["Acquisition Date"],
                    "delta_hours": delta_hours,
                    "subswaths": manifest["slc"]["subswaths"],
                    "manifest": str(manifest_path),
                }
            )
            print(
                f"[ok] {target.target_id} {request.label}: {granule} "
                f"({delta_hours:+.2f} h), subswaths={manifest['slc']['subswaths']}"
            )

    summary_path = out_root / "selection_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[done] wrote {summary_path}")


if __name__ == "__main__":
    main()
