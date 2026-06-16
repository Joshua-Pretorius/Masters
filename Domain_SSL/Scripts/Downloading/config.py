#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
s1_param_pairs_bio.py

Single-file pipeline using ASF PARAM API (CSV):
  • AOIs (ids 1,2,3,6) from a shapefile (EPSG:4326)
  • Query SAME-DAY IW GRD + SLC (2019–2025), platforms: S1A (+ S1C when available)
  • Season-balanced sampling to target counts per AOI
  • Download zips with EDL auth, unzip GRD SAFE, pick VV/VH measurement GeoTIFF as reference
  • Fetch ERA5 u10/v10 -> wind/wind_dir + CMEMS uo/vo + VSDX/VSDY/SWH; reproject to GRD grid
"""

from pathlib import Path
import os, sys, csv, io, zipfile, random, logging, netrc
from datetime import datetime
import requests
import pandas as pd, numpy as np, geopandas as gpd
from shapely.geometry import mapping
from tqdm import tqdm

import cdsapi, xarray as xr, rioxarray as rxr, rasterio.enums
from copernicusmarine import open_dataset as cm_open

# ----------------------- CONFIG -----------------------
AOI_SHP   = r"D:\Masters\Domain_SSL\Aois\Domain_SSL.shp"
OUT_ROOT  = Path(r"D:\Masters\Domain_SSL\downloads_S1")
AOI_COUNTS = {1:30, 2:4,  3:10, 6:30}

START_DATE = "2019-01-01T00:00:00"
END_DATE   = "2025-08-19T23:59:59"

# ASF PARAM API endpoint
ASF_PARAM = "https://api.daac.asf.alaska.edu/services/search/param"

# filters
BEAM = "IW"
PLATFORMS_KEEP = {"Sentinel-1A", "Sentinel-1C"}     # per your ask
MIN_COVER_FRAC = 0.20                                # AOI overlap threshold

# CMEMS dataset ids
CURR_DS  = "cmems_mod_glo_phy-cur_anfc_0.083deg_PT6H-i"
WAVE_DS  = "cmems_mod_glo_wav_anfc_0.083deg_PT3H-i"

# random seed for season balancing
random.seed(42)

# ----------------------- LOGGING ----------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("s1_param_pairs_bio")

# ----------------------- AUTH -------------------------
def edl_auth():
    # ENV wins; else try ~/.netrc for urs.earthdata.nasa.gov
    u, p = os.getenv("EDL_USER"), os.getenv("EDL_PASS")
    if u and p:
        return (u, p)
    try:
        cred = netrc.netrc().authenticators("urs.earthdata.nasa.gov")
        if cred: return (cred[0], cred[2])
    except Exception:
        pass
    log.warning("No Earthdata creds found. Set EDL_USER/EDL_PASS or ~/.netrc.")
    return (None, None)

EDL = edl_auth()
CDS = cdsapi.Client()

# ----------------------- UTILS ------------------------
def month_to_season(m):
    return ("DJF","DJF","MAM","MAM","MAM","JJA","JJA","JJA","SON","SON","SON","DJF")[m-1]

def load_aois(path, ids):
    gdf = gpd.read_file(path).to_crs(4326)
    if "id" not in gdf.columns: raise ValueError("AOI shapefile needs 'id' field.")
    gdf = gdf[gdf["id"].isin(ids)].copy()
    if gdf.empty: raise ValueError("No matching AOIs for requested ids.")
    return gdf

def bbox_str(geom):
    minx, miny, maxx, maxy = geom.bounds
    return f"{minx:.6f},{miny:.6f},{maxx:.6f},{maxy:.6f}"

def get_param_csv(level, bbox, start, end, beam="IW", flight=None, relOrbit=None):
    params = {
        "platform":"s1",
        "bbox": bbox,
        "start": f"{start}UTC",
        "end":   f"{end}UTC",
        "processingLevel": level,      # SLC or GRD_*
        "beamMode": beam,
        "maxResults":"10000",
        "output":"CSV",
    }
    if flight:    params["flightDirection"] = flight.upper()
    if relOrbit:  params["relativeOrbit"]   = str(relOrbit)
    r = requests.get(ASF_PARAM, params=params, timeout=120)
    r.raise_for_status()
    # Pandas can read CSV from bytes/str
    df = pd.read_csv(io.BytesIO(r.content))
    if df.empty:  return df
    # keep S1A/S1C only
    if "Platform" in df.columns:
        df = df[df["Platform"].isin(PLATFORMS_KEEP)]
    # to datetime
    df["acq_dt"] = pd.to_datetime(df["Acquisition Date"], utc=True)
    df["date"]   = df["acq_dt"].dt.date.astype(str)
    return df

def query_grd_all_subtypes(bbox, start, end):
    # GRD variants used by ASF (aligning to asf_search constants)
    levels = ["GRD_HD","GRD_MD","GRD_MS","GRD_HS","GRD_FD"]
    dfs = []
    for lvl in levels:
        try:
            dfs.append(get_param_csv(lvl, bbox, start, end))
        except Exception as ex:
            log.debug(f"  GRD {lvl} query failed: {ex}")
    if not dfs: return pd.DataFrame()
    df = pd.concat(dfs, ignore_index=True).drop_duplicates(subset=["Granule Name"])
    return df

def fraction_overlap_wkt(prod_wkt, aoi_geom):
    try:
        g = gpd.GeoSeries.from_wkt([prod_wkt], crs=4326).iloc[0]
        return g.intersection(aoi_geom).area / aoi_geom.area
    except Exception:
        return 0.0

def filter_by_overlap(df, aoi_geom, min_frac=0.2):
    if df.empty: return df
    if "Geometry" not in df.columns:
        return df  # sometimes not returned; skip filter
    keep = []
    for _, r in df.iterrows():
        frac = fraction_overlap_wkt(r["Geometry"], aoi_geom)
        if frac >= min_frac: keep.append(True)
        else: keep.append(False)
    return df.loc[keep].copy()

def build_same_day_pairs(df_grd, df_slc):
    # index by date
    G = {d: g.sort_values("acq_dt") for d,g in df_grd.groupby("date")}
    S = {d: s.sort_values("acq_dt") for d,s in df_slc.groupby("date")}
    days = sorted(set(G) & set(S))
    pairs = []
    for d in days:
        gset, sset = G[d], S[d]
        # nearest-in-time pairing
        best, bestdt = None, 1e18
        for _, g in gset.iterrows():
            for _, s in sset.iterrows():
                dt = abs((g["acq_dt"] - s["acq_dt"]).total_seconds())
                if dt < bestdt:
                    bestdt = dt; best = (g, s)
        g, s = best
        tg = g["acq_dt"].to_pydatetime()
        pairs.append({
            "date": d,
            "season": month_to_season(tg.month),
            "platform": g.get("Platform", "Sentinel-1A"),
            "g": g, "s": s
        })
    return pairs

def pick_balanced(pairs, n):
    by_season = {"DJF":[],"MAM":[],"JJA":[],"SON":[]}
    for p in pairs: by_season[p["season"]].append(p)
    for s in by_season: random.shuffle(by_season[s])
    base, extra = n//4, n%4
    order = ["DJF","MAM","JJA","SON"]
    want  = {s: base + (1 if i<extra else 0) for i,s in enumerate(order)}
    picked = []
    for s in order:
        take = min(want[s], len(by_season[s]))
        picked.extend(by_season[s][:take])
    if len(picked)<n:
        leftovers = [p for s in order for p in by_season[s][want[s]:]]
        random.shuffle(leftovers)
        picked.extend(leftovers[:n-len(picked)])
    # unique dates
    seen=set(); out=[]
    for p in picked:
        if p["date"] in seen: continue
        seen.add(p["date"]); out.append(p)
        if len(out)==n: break
    return out

def out_dirs(aoi_id, day):
    base = OUT_ROOT / f"aoi_{aoi_id}" / day
    return {"base": base, "grd": base/"GRD", "slc": base/"SLC", "bio": base/"bio"}

def stream_download(url, out_path, auth=None):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=600, auth=auth) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        with open(out_path, "wb") as f, tqdm(total=total, unit="B", unit_scale=True, desc=out_path.name, leave=False) as bar:
            for chunk in r.iter_content(1<<20):
                if chunk:
                    f.write(chunk); bar.update(len(chunk))

def unzip_safe(zip_path: Path, out_dir: Path):
    if out_dir.exists() and any(out_dir.iterdir()):
        return out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(out_dir)
    return out_dir

def find_grd_ref_tif(unzipped_dir: Path):
    cands = list(unzipped_dir.rglob("*measurement/*VV*.tif*")) + \
            list(unzipped_dir.rglob("*measurement/*VV*.tiff*")) + \
            list(unzipped_dir.rglob("*measurement/*VH*.tif*")) + \
            list(unzipped_dir.rglob("*measurement/*VH*.tiff*"))
    return cands[0] if cands else None

# ---------- Reprojection helper ----------
def _reproject_match(da: xr.DataArray, ref_tif: Path, out_tif: Path):
    grid = rxr.open_rasterio(ref_tif, masked=True)
    da = da.astype("float32").rio.write_crs(4326)
    da2 = da.rio.reproject_match(grid, resampling=rasterio.enums.Resampling.bilinear)
    da2.rio.to_raster(out_tif, compress="DEFLATE")

# ---------- ERA5 + CMEMS ----------
def fetch_era5_to_ref(aoi_geom, when, ref_tif, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    yy,mm,dd,hh = when.strftime("%Y %m %d %H").split()
    area = [aoi_geom.bounds[3], aoi_geom.bounds[0], aoi_geom.bounds[1], aoi_geom.bounds[2]]  # N,W,S,E
    nc = out_dir / f"era5_{yy}{mm}{dd}{hh}.nc"
    if not nc.exists():
        CDS.retrieve(
            "reanalysis-era5-single-levels",
            {"product_type":"reanalysis",
             "variable":["u10","v10"],
             "year":yy,"month":mm,"day":dd,"time":[f"{hh}:00"],
             "area":area,"format":"netcdf"},
            str(nc)
        )
    with xr.open_dataset(nc) as ds:
        u = (ds.get("u10") or ds["10m_u_component_of_wind"]).isel(time=0).astype("float32")
        v = (ds.get("v10") or ds["10m_v_component_of_wind"]).isel(time=0).astype("float32")
        sp = xr.apply_ufunc(np.hypot, u, v).rename("wind").astype("float32")
        wd = ((np.degrees(np.arctan2(-u,-v))+360)%360).rename("wind_dir").astype("float32")
        for da, name in [(u,"u10"),(v,"v10"),(sp,"wind"),(wd,"wind_dir")]:
            _reproject_match(da, ref_tif, out_dir/f"{name}.tif")

def _slice_bbox_360(ds, w,s,e,n):
    lon_name = "longitude" if "longitude" in ds.coords else "lon"
    lat_name = "latitude"  if "latitude"  in ds.coords else "lat"
    lon = ds[lon_name]
    if float(lon.min())>=0 and w<0: w += 360
    if float(lon.min())>=0 and e<0: e += 360
    lon0,lon1 = (w,e) if lon[0] < lon[-1] else (e,w)
    lat = ds[lat_name]; lat0,lat1 = (s,n) if lat[0] < lat[-1] else (n,s)
    return ds.sel({lon_name: slice(lon0,lon1), lat_name: slice(lat0,lat1)})

def fetch_cmems_to_ref(aoi_geom, when, ref_tif, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    w,s,e,n = aoi_geom.bounds
    t = when.to_pydatetime().replace(tzinfo=None)

    # currents
    try:
        cur = cm_open(dataset_id=CURR_DS)[["uo","vo"]]
        cur = cur.sel(depth=0, time=t, method="nearest")
        cur = _slice_bbox_360(cur, w,s,e,n)
        for var in ["uo","vo"]:
            da = cur[var].astype("float32").rio.write_crs(4326)
            _reproject_match(da, ref_tif, out_dir/f"{var}.tif")
        log.info("  CMEMS currents ✓")
    except Exception as ex:
        log.warning(f"  CMEMS currents ✗ {ex}")

    # waves
    try:
        wav = cm_open(dataset_id=WAVE_DS)[["VSDX","VSDY","VHM0"]]
        wav = wav.sel(time=t, method="nearest")
        wav = _slice_bbox_360(wav, w,s,e,n)
        for src,dst in [("VSDX","vsdx"),("VSDY","vsdy"),("VHM0","swh")]:
            da = wav[src].astype("float32").rio.write_crs(4326)
            _reproject_match(da, ref_tif, out_dir/f"{dst}.tif")
        log.info("  CMEMS waves ✓")
    except Exception as ex:
        log.warning(f"  CMEMS waves ✗ {ex}")

# ----------------------- MAIN -------------------------
def main():
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    aois = load_aois(AOI_SHP, AOI_COUNTS.keys())
    for _, row in aois.iterrows():
        aid = int(row["id"]); need = AOI_COUNTS[aid]; geom = row.geometry
        bbox = bbox_str(geom)
        log.info(f"\nAOI {aid}: query PARAM API within {START_DATE}..{END_DATE} (IW, S1A/S1C)")

        # Lists
        df_slc = get_param_csv("SLC", bbox, START_DATE, END_DATE, beam=BEAM)
        df_grd = query_grd_all_subtypes(bbox, START_DATE, END_DATE)

        if df_slc.empty or df_grd.empty:
            log.warning("  No SLC or no GRD found after filters.")
            continue

        # Overlap filter (if Geometry present)
        df_slc = filter_by_overlap(df_slc, geom, MIN_COVER_FRAC)
        df_grd = filter_by_overlap(df_grd, geom, MIN_COVER_FRAC)

        pairs = build_same_day_pairs(df_grd, df_slc)
        if not pairs:
            log.warning("  No same-day GRD+SLC pairs.")
            continue

        chosen = pick_balanced(pairs, need)
        log.info(f"  picked {len(chosen)} dates (season-balanced)")

        for p in tqdm(chosen, desc=f"AOI {aid}"):
            day = p["date"]; g, s = p["g"], p["s"]
            dirs = {"base": OUT_ROOT/f"aoi_{aid}"/day,
                    "grd": OUT_ROOT/f"aoi_{aid}"/day/"GRD",
                    "slc": OUT_ROOT/f"aoi_{aid}"/day/"SLC",
                    "bio": OUT_ROOT/f"aoi_{aid}"/day/"bio"}
            for d in dirs.values(): d.mkdir(parents=True, exist_ok=True)

            # Download zips
            g_zip = dirs["grd"]/f"{g['Granule Name']}.zip"
            s_zip = dirs["slc"]/f"{s['Granule Name']}.zip"
            if not g_zip.exists():
                stream_download(g["URL"], g_zip, auth=EDL)
            if not s_zip.exists():
                stream_download(s["URL"], s_zip, auth=EDL)

            # Unzip GRD and find reference tif
            grd_safe = unzip_safe(g_zip, dirs["grd"]/g_zip.stem)
            ref_tif  = find_grd_ref_tif(grd_safe)
            if not ref_tif:
                log.warning(f"  {day}: no VV/VH GeoTIFF under GRD SAFE — skipping bio")
                continue

            # Biophysical (use GRD time)
            when = g["acq_dt"].to_pydatetime()
            fetch_era5_to_ref(geom, when, ref_tif, dirs["bio"])
            fetch_cmems_to_ref(geom, when, ref_tif, dirs["bio"])

    log.info("\n✓ Done.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.warning("Interrupted.")
        sys.exit(130)