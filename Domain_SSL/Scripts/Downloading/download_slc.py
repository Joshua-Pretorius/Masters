#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
download_slc.py

Purpose
-------
Build a domain-specific SSL dataset:
  • Read AOIs (with fields: id, images) from a shapefile (EPSG:4326)
  • Query ASF PARAM API for SAME-DAY Sentinel-1 IW SLC + GRD over 2019–2025
  • Slice queries (quarterly by default) to avoid timeouts; WKT intersection; retry/backoff
  • Season-balanced sampling to reach requested 'images' count per AOI
  • Download SLC (for SSL) and companion GRD (only to define a georeferenced grid)
  • Fetch ERA5 (u10, v10, wind, wind_dir) and CMEMS (uo, vo, VSDX, VSDY, SWH), reproject to GRD grid
  • Write a manifest.json per date for traceability

Notes
-----
• Set Earthdata Login in env (EDL_USER / EDL_PASS) or ~/.netrc (urs.earthdata.nasa.gov).
• Log in once to CMEMS via `copernicusmarine login` if not configured.
"""

from pathlib import Path
import os, io, sys, json, zipfile, logging, random, netrc, time
from datetime import datetime
from contextlib import contextmanager
from typing import Optional, List, Dict, Tuple

import requests
import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import mapping
from tqdm import tqdm

import cdsapi
import xarray as xr
import rioxarray as rxr
import rasterio
from rasterio.enums import Resampling
from copernicusmarine import open_dataset as cm_open

# =========================
# CONFIG
# =========================
AOI_INPUT      = r"D:\Masters\Domain_SSL\Aois\Domain_SSL.shp"     # shapefile with fields: id, images
OUT_ROOT       = Path(r"D:\Masters\Domain_SSL\downloads_S1")

START_DATE     = "2019-01-01T00:00:00"
END_DATE       = "2025-08-19T23:59:59"

BEAM_MODE      = "IW"
PLATFORMS_KEEP = {"Sentinel-1A", "Sentinel-1C"}                   # prefer A + C
MIN_COVER_FRAC = 0.20                                             # product ∩ AOI / AOI >= 20%

# ASF PARAM API
ASF_PARAM      = "https://api.daac.asf.alaska.edu/services/search/param"

# Query slicing & robustness
DATE_SLICE         = "quarter"   # 'month' | 'quarter' | 'year'
SLICE_MAX_RESULTS  = 2000        # cap per slice to avoid huge responses
HTTP_TIMEOUT       = 180         # seconds
RETRY_5XX          = 4           # attempts
BACKOFF_BASE       = 2.0         # seconds (exponential backoff)
USE_WKT            = True        # prefer intersectsWith=WKT instead of bbox

# CMEMS datasets
CURR_DS  = "cmems_mod_glo_phy-cur_anfc_0.083deg_PT6H-i"  # uo, vo (surface currents)
WAVE_DS  = "cmems_mod_glo_wav_anfc_0.083deg_PT3H-i"      # VSDX, VSDY, VHM0 (swh)

# Repro & progress
random.seed(42)

# =========================
# LOGGING
# =========================
def _setup_logging():
    log = logging.getLogger("s1_ssl")
    log.setLevel(logging.INFO)

    if not log.handlers:
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%dT%H:%M:%S")
        ch = logging.StreamHandler(sys.stdout); ch.setFormatter(fmt); ch.setLevel(logging.INFO)
        log.addHandler(ch)

        OUT_ROOT.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(OUT_ROOT / "download.log", encoding="utf-8")
        fh.setFormatter(fmt); fh.setLevel(logging.INFO)
        log.addHandler(fh)
    return log

log = _setup_logging()

@contextmanager
def elapsed(msg: str):
    t0 = time.time()
    log.info(msg)
    try:
        yield
    finally:
        log.info(f"↳ done in {time.time()-t0:.1f}s")

# =========================
# AUTH
# =========================
def edl_auth():
    """Return (user, pass) for Earthdata Login."""
    u, p = os.getenv("EDL_USER"), os.getenv("EDL_PASS")
    if u and p:
        return (u, p)
    netrc_candidates = [
        None,
        Path.home() / ".netrc",
        Path.home() / "_netrc",
        Path("/mnt/c/Users/Joshua Pretorius/_netrc"),
    ]
    for candidate in netrc_candidates:
        try:
            auths = netrc.netrc(str(candidate)) if candidate else netrc.netrc()
            cred = auths.authenticators("urs.earthdata.nasa.gov")
            if cred:
                return (cred[0], cred[2])
        except Exception:
            continue
    log.warning("No Earthdata creds found. Set EDL_USER/EDL_PASS or ~/.netrc for urs.earthdata.nasa.gov.")
    return (None, None)

EDL = edl_auth()
CDS = cdsapi.Client()

# =========================
# AOIs
# =========================
def load_aois(aoi_input: str) -> gpd.GeoDataFrame:
    p = Path(aoi_input)
    if p.is_dir():
        parts = []
        for shp in p.glob("*.shp"):
            g = gpd.read_file(shp).to_crs(4326)
            parts.append(g)
        if not parts:
            raise ValueError("No shapefiles found in AOI directory.")
        gdf = pd.concat(parts, ignore_index=True)
    else:
        gdf = gpd.read_file(aoi_input).to_crs(4326)

    if "id" not in gdf.columns or "images" not in gdf.columns:
        raise ValueError("AOIs must have 'id' and 'images' attributes.")
    gdf["images"] = gdf["images"].astype(int)
    gdf = gdf[~gdf.geometry.is_empty].copy()
    return gdf

# =========================
# TIME SLICING
# =========================
def daterange_slices(start_iso: str, end_iso: str, mode: str):
    start = pd.to_datetime(start_iso, utc=True)
    end   = pd.to_datetime(end_iso, utc=True)
    if mode == "month":
        freq = "MS"
    elif mode == "quarter":
        freq = "QS"
    elif mode == "year":
        freq = "YS"
    else:
        raise ValueError("DATE_SLICE must be one of: month | quarter | year")

    edges = list(pd.date_range(start.normalize(), end.normalize(), freq=freq, tz="UTC"))
    if not edges or edges[0] != start.normalize():
        edges = [start.normalize()] + edges
    if edges[-1] < end.normalize():
        edges.append(end.normalize())

    windows = []
    for i in range(len(edges)-1):
        a = max(start, edges[i])
        b = min(end,   edges[i+1] - pd.Timedelta(seconds=1))
        if a <= b:
            windows.append((a, b))
    if not windows:
        windows.append((start, end))
    return windows

# =========================
# HTTP (retry/backoff)
# =========================
def get_with_retry(url, params, timeout=HTTP_TIMEOUT, attempts=RETRY_5XX):
    last = None
    for k in range(attempts):
        try:
            r = requests.get(
                url,
                params=params,
                timeout=timeout,
                headers={"Accept": "text/csv", "User-Agent": "s1-ssl-downloader/1.0"}
            )
            # retry 5xx
            if 500 <= r.status_code < 600:
                raise requests.HTTPError(f"{r.status_code} Server Error", response=r)
            r.raise_for_status()
            return r
        except (requests.Timeout, requests.HTTPError) as ex:
            last = ex
            wait = BACKOFF_BASE * (2 ** k)
            log.warning(f"HTTP get failed ({ex}); retrying in {wait:.1f}s …")
            time.sleep(wait)
    if last:
        raise last

# =========================
# ASF PARAM queries (sliced)
# =========================
def geom_to_wkt(geom) -> str:
    return geom.wkt  # gdf is in EPSG:4326

def _log_slice_result(label: str, a: pd.Timestamp, b: pd.Timestamp, df: pd.DataFrame):
    n = 0 if df is None else len(df)
    log.info(f"  slice {label}: {a.strftime('%Y-%m-%d')}..{b.strftime('%Y-%m-%d')} → {n} rows")

def param_csv_sliced(processing_level: str, aoi_geom, start: str, end: str, beam: str = "IW") -> pd.DataFrame:
    slices = daterange_slices(start, end, DATE_SLICE)
    frames: List[pd.DataFrame] = []

    for a, b in slices:
        params = {
            "platform": "s1",
            "processingLevel": processing_level,     # "SLC" or GRD_* (HD/HS/MD/MS/FD)
            "beamMode": beam,
            "maxResults": str(SLICE_MAX_RESULTS),
            "output": "CSV",
            "start": f"{a.strftime('%Y-%m-%dT%H:%M:%S')}UTC",
            "end":   f"{b.strftime('%Y-%m-%dT%H:%M:%S')}UTC",
        }
        if USE_WKT:
            params["intersectsWith"] = geom_to_wkt(aoi_geom)
        else:
            minx, miny, maxx, maxy = aoi_geom.bounds
            params["bbox"] = f"{minx:.6f},{miny:.6f},{maxx:.6f},{maxy:.6f}"

        try:
            r = get_with_retry(ASF_PARAM, params)
            if not r.content or r.content.strip() == b'':
                _log_slice_result(processing_level, a, b, None)
                continue

            df = pd.read_csv(io.BytesIO(r.content))
            if df.empty:
                _log_slice_result(processing_level, a, b, df)
                continue
            if "Platform" in df.columns:
                df = df[df["Platform"].isin(PLATFORMS_KEEP)]
            if df.empty:
                _log_slice_result(processing_level, a, b, df)
                continue

            df["acq_dt"] = pd.to_datetime(df["Acquisition Date"], utc=True, errors="coerce")
            df["date"]   = df["acq_dt"].dt.date.astype(str)
            frames.append(df)
            _log_slice_result(processing_level, a, b, df)
        except Exception as ex:
            log.warning(f"  slice {processing_level} {a.date()}..{b.date()} failed: {ex}")

    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["Granule Name"])
    log.info(f"  total {processing_level}: {len(out)} rows after de-dup")
    return out

def query_grd_variants_sliced(aoi_geom, start, end) -> pd.DataFrame:
    levels = ["GRD_HD","GRD_MD","GRD_MS","GRD_HS","GRD_FD"]
    parts = []
    for lv in levels:
        df = param_csv_sliced(lv, aoi_geom, start, end, beam=BEAM_MODE)
        if not df.empty:
            parts.append(df)
    if not parts:
        return pd.DataFrame()
    out = pd.concat(parts, ignore_index=True).drop_duplicates(subset=["Granule Name"])
    log.info(f"  total GRD (all variants): {len(out)} rows after de-dup")
    return out

# =========================
# GEOMETRY FILTER (overlap)
# =========================
def overlap_frac(prod_wkt: str, aoi_geom) -> float:
    try:
        g = gpd.GeoSeries.from_wkt([prod_wkt], crs=4326).iloc[0]
        inter = g.intersection(aoi_geom)
        if inter.is_empty:
            return 0.0
        return inter.area / aoi_geom.area
    except Exception:
        return 0.0

def filter_by_overlap(df: pd.DataFrame, aoi_geom, min_frac: float, label: str) -> pd.DataFrame:
    if df.empty or "Geometry" not in df.columns:
        return df
    before = len(df)
    keep = []
    for _, r in df.iterrows():
        keep.append(overlap_frac(r["Geometry"], aoi_geom) >= min_frac)
    out = df.loc[keep].copy()
    log.info(f"  overlap filter {label}: {before} → {len(out)} (min {min_frac*100:.0f}% cover)")
    return out

# =========================
# PAIRING & SEASON BALANCE
# =========================
def month_to_season(m: int) -> str:
    return ("DJF","DJF","MAM","MAM","MAM","JJA","JJA","JJA","SON","SON","SON","DJF")[m-1]

def build_same_day_pairs(df_grd: pd.DataFrame, df_slc: pd.DataFrame) -> List[dict]:
    if df_grd.empty or df_slc.empty:
        return []
    G = {d: g.sort_values("acq_dt") for d, g in df_grd.groupby("date")}
    S = {d: s.sort_values("acq_dt") for d, s in df_slc.groupby("date")}
    days = sorted(set(G) & set(S))
    pairs = []
    for d in days:
        best, bestdt = None, 1e18
        for _, g in G[d].iterrows():
            for _, s in S[d].iterrows():
                dt = abs((g["acq_dt"] - s["acq_dt"]).total_seconds())
                if dt < bestdt:
                    bestdt, best = dt, (g, s)
        g, s = best
        t = g["acq_dt"].to_pydatetime()
        pairs.append({
            "date": d,
            "season": month_to_season(t.month),
            "platform": g.get("Platform", "Sentinel-1A"),
            "grd": g, "slc": s
        })
    log.info(f"  same-day pairs: {len(pairs)}")
    return pairs

def pick_by_season(pairs: List[dict], n: int) -> List[dict]:
    buckets = {"DJF":[], "MAM":[], "JJA":[], "SON":[]}
    for p in pairs:
        buckets[p["season"]].append(p)
    for v in buckets.values():
        random.shuffle(v)
    base, extra = n // 4, n % 4
    order = ["DJF","MAM","JJA","SON"]
    want = {s: base + (1 if i < extra else 0) for i, s in enumerate(order)}
    chosen: List[dict] = []
    for s in order:
        take = min(want[s], len(buckets[s]))
        chosen.extend(buckets[s][:take])
    if len(chosen) < n:
        leftovers = [p for s in order for p in buckets[s][want[s]:]]
        random.shuffle(leftovers)
        chosen.extend(leftovers[: n - len(chosen)])
    # unique by date
    out, seen = [], set()
    for p in chosen:
        if p["date"] in seen:
            continue
        seen.add(p["date"])
        out.append(p)
        if len(out) == n:
            break
    # log season balance
    cnt = pd.Series([x["season"] for x in out]).value_counts().to_dict()
    log.info(f"  picked {len(out)}/{n} dates; season split: {cnt}")
    if out:
        sample = ", ".join([f"{x['date']}({x['season']})" for x in out[:min(6,len(out))]])
        log.info(f"  sample dates: {sample}{' …' if len(out)>6 else ''}")
    return out

# =========================
# DOWNLOAD / UNZIP / REF GRID
# =========================
def stream_download(url: str, out_path: Path, auth=None):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=600, auth=auth) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        desc = out_path.name
        if total == 0:
            log.info(f"  downloading {desc} (unknown size)")
        with open(out_path, "wb") as f, tqdm(total=total, unit="B", unit_scale=True, desc=desc, leave=False) as bar:
            for chunk in r.iter_content(1 << 20):
                if chunk:
                    f.write(chunk); bar.update(len(chunk))

def unzip_safe(zip_path: Path, out_dir: Path) -> Path:
    if out_dir.exists() and any(out_dir.iterdir()):
        log.info(f"  unzip skip: {out_dir.name} already populated")
        return out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(out_dir)
    log.info(f"  unzipped → {out_dir}")
    return out_dir

def find_grd_ref_tif(unzipped_safe_dir: Path) -> Optional[Path]:
    # prefer VV if present, else VH
    patterns = [
        "*measurement/*VV*.tif",  "*measurement/*VV*.tiff",
        "*measurement/*VH*.tif",  "*measurement/*VH*.tiff",
    ]
    for p in patterns:
        hits = list(unzipped_safe_dir.rglob(p))
        if hits:
            return hits[0]
    return None

# =========================
# ERA5 & CMEMS → reproject to GRD grid
# =========================
def reproject_match(da: xr.DataArray, ref_tif: Path, out_tif: Path):
    if out_tif.exists():
        log.info(f"    skip: {out_tif.name} exists")
        return
    grid = rxr.open_rasterio(ref_tif, masked=True)
    da = da.astype("float32").rio.write_crs(4326, inplace=False)
    da2 = da.rio.reproject_match(grid, resampling=Resampling.bilinear)
    da2.rio.to_raster(out_tif, compress="DEFLATE")
    log.info(f"    wrote {out_tif.name}")

def fetch_era5_to_ref(aoi_geom, when: datetime, ref_tif: Path, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    yy, mm, dd, hh = when.strftime("%Y %m %d %H").split()
    area = [aoi_geom.bounds[3], aoi_geom.bounds[0], aoi_geom.bounds[1], aoi_geom.bounds[2]]  # [N, W, S, E]
    nc = out_dir / f"era5_{yy}{mm}{dd}{hh}.nc"
    targets = [out_dir / f"{name}.tif" for name in ("u10","v10","wind","wind_dir")]
    if all(t.exists() for t in targets):
        log.info("  ERA5: all GeoTIFFs present — skip")
        return
    if not nc.exists():
        with elapsed(f"  ERA5: retrieve {yy}-{mm}-{dd}T{hh}:00"):
            CDS.retrieve(
                "reanalysis-era5-single-levels",
                {
                    "product_type": "reanalysis",
                    "variable": ["u10", "v10"],
                    "year": yy, "month": mm, "day": dd, "time": [f"{hh}:00"],
                    "area": area, "format": "netcdf",
                },
                str(nc),
            )
    with xr.open_dataset(nc) as ds:
        # Be tolerant with variable names
        u = (ds.get("u10") or ds["10m_u_component_of_wind"]).isel(time=0).astype("float32")
        v = (ds.get("v10") or ds["10m_v_component_of_wind"]).isel(time=0).astype("float32")
        ws = xr.apply_ufunc(np.hypot, u, v).rename("wind").astype("float32")
        wd = ((np.degrees(np.arctan2(-u, -v)) + 360) % 360).rename("wind_dir").astype("float32")
        for da, name in [(u,"u10"), (v,"v10"), (ws,"wind"), (wd,"wind_dir")]:
            reproject_match(da, ref_tif, out_dir / f"{name}.tif")
    log.info("  ERA5 ✓")

def slice_bbox_360(ds: xr.Dataset, w, s, e, n) -> xr.Dataset:
    # handle datasets using 0..360 longitudes
    lon_name = "longitude" if "longitude" in ds.coords else "lon"
    lat_name = "latitude"  if "latitude"  in ds.coords else "lat"
    lon = ds[lon_name]
    if float(lon.min()) >= 0 and w < 0: w += 360
    if float(lon.min()) >= 0 and e < 0: e += 360
    lon0, lon1 = (w, e) if lon[0] < lon[-1] else (e, w)
    lat = ds[lat_name]
    lat0, lat1 = (s, n) if lat[0] < lat[-1] else (n, s)
    return ds.sel({lon_name: slice(lon0, lon1), lat_name: slice(lat0, lat1)})

def fetch_cmems_to_ref(aoi_geom, when: pd.Timestamp, ref_tif: Path, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    w, s, e, n = aoi_geom.bounds
    t = when.to_pydatetime().replace(tzinfo=None)

    cur_targets = [out_dir / "uo.tif", out_dir / "vo.tif"]
    wav_targets = [out_dir / "vsdx.tif", out_dir / "vsdy.tif", out_dir / "swh.tif"]

    # currents
    try:
        if all(p.exists() for p in cur_targets):
            log.info("  CMEMS currents: GeoTIFFs present — skip")
        else:
            with elapsed("  CMEMS currents: fetch + reproject"):
                cur = cm_open(dataset_id=CURR_DS)[["uo", "vo"]]
                cur = cur.sel(depth=0, time=t, method="nearest")
                cur = slice_bbox_360(cur, w, s, e, n)
                for var in ["uo", "vo"]:
                    reproject_match(cur[var].astype("float32"), ref_tif, out_dir / f"{var}.tif")
            log.info("  CMEMS currents ✓")
    except Exception as ex:
        log.warning(f"  CMEMS currents ✗ {ex}")

    # waves
    try:
        if all(p.exists() for p in wav_targets):
            log.info("  CMEMS waves: GeoTIFFs present — skip")
        else:
            with elapsed("  CMEMS waves: fetch + reproject"):
                wav = cm_open(dataset_id=WAVE_DS)[["VSDX", "VSDY", "VHM0"]]
                wav = wav.sel(time=t, method="nearest")
                wav = slice_bbox_360(wav, w, s, e, n)
                for src, dst in [("VSDX","vsdx"), ("VSDY","vsdy"), ("VHM0","swh")]:
                    reproject_match(wav[src].astype("float32"), ref_tif, out_dir / f"{dst}.tif")
            log.info("  CMEMS waves ✓")
    except Exception as ex:
        log.warning(f"  CMEMS waves ✗ {ex}")

# =========================
# MAIN
# =========================
def main():
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    aois = load_aois(AOI_INPUT)
    log.info(f"AOIs loaded: {len(aois)} (EPSG:4326)")

    for _, row in aois.iterrows():
        aoi_id = int(row["id"]); need = int(row["images"]); geom = row.geometry
        log.info(f"\nAOI {aoi_id}: querying {START_DATE}..{END_DATE} ({BEAM_MODE}, S1A/S1C)")

        with elapsed("  query SLC (sliced)"):
            slc = param_csv_sliced("SLC", geom, START_DATE, END_DATE, beam=BEAM_MODE)
        with elapsed("  query GRD variants (sliced)"):
            grd = query_grd_variants_sliced(geom, START_DATE, END_DATE)

        if slc.empty:
            log.warning("  No SLC found after sliced query.")
            continue
        if grd.empty:
            log.warning("  No GRD found after sliced query.")
            continue

        # Overlap filter (if Geometry present)
        slc = filter_by_overlap(slc, geom, MIN_COVER_FRAC, "SLC")
        grd = filter_by_overlap(grd, geom, MIN_COVER_FRAC, "GRD")
        if slc.empty or grd.empty:
            log.warning("  Empty after overlap filter.")
            continue

        # Same-day pairing and season-balanced selection
        pairs = build_same_day_pairs(grd, slc)
        if not pairs:
            log.warning("  No same-day GRD+SLC pairs.")
            continue

        chosen = pick_by_season(pairs, need)

        # Download + Biophysical parameters
        for p in tqdm(chosen, desc=f"AOI {aoi_id}", unit="date"):
            day = p["date"]; g = p["grd"]; s = p["slc"]
            base = OUT_ROOT / f"aoi_{aoi_id}" / day
            manifest_path = base / "manifest.json"

            # Full idempotency: skip the day if manifest exists
            if manifest_path.exists():
                log.info(f"  {day}: manifest exists — skip entire day")
                continue

            d_grd = base / "GRD"; d_slc = base / "SLC"; d_bio = base / "bio"
            for d in (d_grd, d_slc, d_bio):
                d.mkdir(parents=True, exist_ok=True)

            gzip = d_grd / f"{g['Granule Name']}.zip"
            szip = d_slc / f"{s['Granule Name']}.zip"

            # Downloads
            if gzip.exists():
                log.info(f"  {day}: GRD zip present — skip download")
            else:
                log.info(f"  {day}: downloading GRD → {gzip.name}")
                stream_download(g["URL"], gzip, auth=EDL)

            if szip.exists():
                log.info(f"  {day}: SLC zip present — skip download")
            else:
                log.info(f"  {day}: downloading SLC → {szip.name}")
                stream_download(s["URL"], szip, auth=EDL)

            # Unzip GRD; pick a VV/VH GeoTIFF as reference grid
            grd_safe = unzip_safe(gzip, d_grd / gzip.stem)
            ref_tif = find_grd_ref_tif(grd_safe)
            if ref_tif is None:
                log.warning(f"  {day}: no VV/VH GeoTIFF in GRD SAFE — skipping biophysical fetch.")
                # Minimal manifest
                manifest = {
                    "aoi_id": aoi_id, "date": day, "platform": p["platform"],
                    "slc": {"granule": s["Granule Name"], "url": s["URL"], "zip": str(szip)},
                    "grd": {"granule": g["Granule Name"], "url": g["URL"], "zip": str(gzip), "ref_tif": None},
                    "biophysical": {"dir": str(d_bio), "files": []},
                }
                with open(manifest_path, "w") as f:
                    json.dump(manifest, f, indent=2)
                continue

            when = g["acq_dt"]  # use GRD acquisition timestamp

            # ERA5 & CMEMS reprojected to GRD grid
            try:
                fetch_era5_to_ref(geom, when.to_pydatetime(), ref_tif, d_bio)
            except Exception as ex:
                log.warning(f"  ERA5 fetch failed: {ex}")
            try:
                fetch_cmems_to_ref(geom, when, ref_tif, d_bio)
            except Exception as ex:
                log.warning(f"  CMEMS fetch failed: {ex}")

            # Manifest
            manifest = {
                "aoi_id": aoi_id,
                "date": day,
                "platform": p["platform"],
                "slc": {
                    "granule": s["Granule Name"],
                    "url": s["URL"],
                    "zip": str(szip),
                },
                "grd": {
                    "granule": g["Granule Name"],
                    "url": g["URL"],
                    "zip": str(gzip),
                    "ref_tif": str(ref_tif),
                },
                "biophysical": {
                    "dir": str(d_bio),
                    "files": sorted([f.name for f in d_bio.glob("*.tif")]),
                },
            }
            with open(manifest_path, "w") as f:
                json.dump(manifest, f, indent=2)
            log.info(f"  {day}: manifest written")

    log.info("\n✓ Done.")

# =========================
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.warning("Interrupted.")
        sys.exit(130)
