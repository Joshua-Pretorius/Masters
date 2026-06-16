#!/usr/bin/env python3
"""
MERIA.py

Download exactly the Sentinel‑1 GRD (preferred) or SLC (fallback) product
named (by prefix) in each observation’s JSON `extra._sourceId`, ensuring
the product footprint fully contains the patch polygon, and ERA‑5 10 m wind.
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
import cdsapi
import numpy as np
import xarray as xr
import rioxarray as rxr
import rasterio.enums
from shapely.geometry import shape
import asf_search as asf
from tqdm import tqdm

# ── CONFIG ───────────────────────────────────────────────────────────
JSON_F      = Path(
    r"C:\Users\Joshua Pretorius\Desktop"
    r"\ocean-scan-mireia-- marine litter signatures "
    r"in sar images-e71e8ee6-e41d-4889-bb08-a821fb5e8bbd.json"
)
RAW_DIR     = Path(r"D:\Masters\MERIA\raw_grd")
TIME_PAD_HR = 12
ERA_VARS    = ["10m_u_component_of_wind", "10m_v_component_of_wind"]

RAW_DIR.mkdir(parents=True, exist_ok=True)

# ── LOGGING ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S"
)
logger = logging.getLogger(__name__)

# ── SESSIONS ─────────────────────────────────────────────────────────
session = asf.ASFSession()   # uses ~/.netrc for Earthdata creds
era     = cdsapi.Client()     # for ERA‑5

# ── HELPERS ──────────────────────────────────────────────────────────
def search_sentinel1(geom, when):
    t0 = (when - timedelta(hours=TIME_PAD_HR)).strftime("%Y-%m-%dT%H:%M:%SZ")
    t1 = (when + timedelta(hours=TIME_PAD_HR)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return asf.geo_search(
        intersectsWith=geom.wkt,
        platform=asf.PLATFORM.SENTINEL1,
        start=t0, end=t1
    )

def download_sar(prod, scene_dir):
    scene_dir.mkdir(parents=True, exist_ok=True)
    fid = prod.properties["fileID"]
    logger.info(f"Downloading SAR {fid}")
    prod.download(path=str(scene_dir), session=session)

def era5_subset(out_nc, bounds, when):
    west, south, east, north = bounds
    logger.info(f"Fetching ERA‑5 wind for {when.isoformat()} over {bounds}")
    era.retrieve(
        "reanalysis-era5-single-levels",
        {
            "product_type":"reanalysis",
            "variable":    ERA_VARS,
            "year":        when.strftime("%Y"),
            "month":       when.strftime("%m"),
            "day":         when.strftime("%d"),
            "time":        when.strftime("%H:00"),
            "area":        [north, west, south, east],
            "format":      "netcdf"
        },
        str(out_nc)
    )

def wind_layers(nc):
    ds = xr.open_dataset(nc)
    u = ds.get("u10",  ds.get("10m_u_component_of_wind"))
    v = ds.get("v10",  ds.get("10m_v_component_of_wind"))
    tdim = "time" if "time" in u.dims else next(d for d in u.dims if "time" in d)
    u0, v0 = u.isel({tdim: 0}), v.isel({tdim: 0})
    speed = np.sqrt(u0**2 + v0**2).rename("wind_speed")
    wdir  = ((np.degrees(np.arctan2(-u0, -v0)) + 360) % 360).rename("wind_dir")
    ds.close()
    return speed, wdir

def to_match_grid(da, ref_tif, out_tif):
    grid = rxr.open_rasterio(ref_tif, masked=True)
    da2 = da.rio.write_crs("EPSG:4326") \
             .rio.reproject_match(grid, resampling=rasterio.enums.Resampling.bilinear)
    out_tif.parent.mkdir(parents=True, exist_ok=True)
    da2.rio.to_raster(out_tif, compress="DEFLATE")

# ── MAIN ──────────────────────────────────────────────────────────────
def main():
    logger.info(f"Loading patches from {JSON_F}")
    with open(JSON_F, "r", encoding="utf-8", errors="replace") as f:
        patches = json.load(f)["observations"]

    for idx, obs in enumerate(patches, start=1):
        extra = obs.get("extra") or {}
        prefix = extra.get("_sourceId")
        if not prefix or obs.get("isAbsence", False):
            logger.info(f"[{idx}/{len(patches)}] skipping absence or missing sourceId")
            continue

        when = datetime.fromisoformat(obs["timestamp"].replace("Z",""))
        patch_geom = shape(obs["geometry"])
        logger.info(f"[{idx}/{len(patches)}] patch {prefix} @ {when.isoformat()}")

        results = search_sentinel1(patch_geom, when)
        logger.info(f"[{idx}] found {len(results)} candidates")

        # 1) try to match by prefix AND contain the patch polygon
        match = [
            p for p in results
            if p.properties.get("fileID","").startswith(prefix)
               and shape(p.geometry).contains(patch_geom)
        ]

        # 2) fallback: first GRD that fully contains patch
        if not match:
            for p in results:
                lvl = p.properties.get("processingLevel","").upper()
                if lvl.startswith("GRD") and shape(p.geometry).contains(patch_geom):
                    match = [p]
                    break

        # 3) fallback: first SLC that fully contains patch
        if not match:
            for p in results:
                lvl = p.properties.get("processingLevel","").upper()
                if lvl.startswith("SLC") and shape(p.geometry).contains(patch_geom):
                    match = [p]
                    break

        if not match:
            logger.error(f"[{idx}] no matching GRD or SLC containing patch; skipping")
            continue
        
        # after the prefix+contains filtering…
        logger.info(f"[{idx}] {len(match)} products whose footprint contains the patch")

        prod = match[0]
        scene_dir = RAW_DIR / prod.properties["fileID"]

        # download SAR
        download_sar(prod, scene_dir)

        # download ERA‑5
        nc = scene_dir / f"{prod.properties['fileID']}_era.nc"
        era5_subset(nc, patch_geom.bounds, when)
        spd, wdir = wind_layers(nc)
        nc.unlink()

        # reproject wind to VV grid
        vv = next(scene_dir.glob("*VV*.tif"), None)
        if vv:
            logger.info(f"[{idx}] reprojecting wind to match {vv.name}")
            to_match_grid(spd, vv, scene_dir/"wind_speed.tif")
            to_match_grid(wdir, vv, scene_dir/"wind_dir.tif")
        else:
            logger.warning(f"[{idx}] no VV TIFF found in {scene_dir}")

    logger.info("✓ All patches processed.")

if __name__ == "__main__":
    main()
