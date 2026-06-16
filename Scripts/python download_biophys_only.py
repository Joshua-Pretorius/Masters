"""
download_biophys_only.py

Only download ERA5 wind + CMEMS currents/Stokes/SWH
onto your existing S2 and S1 grids.  Idempotent and skips failures.

Usage:
  python download_biophys_only.py
"""

from pathlib import Path
from datetime import datetime
import tempfile, requests
import numpy as np, pandas as pd
import xarray as xr, rioxarray as rxr
import rasterio, rasterio.enums
from shapely.geometry import box
from tqdm import tqdm
import cdsapi
from copernicusmarine import open_dataset

# ── CONFIG ───────────────────────────────────────────────────────────
OUT_ROOT = Path(r"D:\Masters\MARIDA\downloads")
TMP      = Path(tempfile.gettempdir())

ERA_VARS  = ["10m_u_component_of_wind","10m_v_component_of_wind"]
CMEMS_PHY = "cmems_mod_glo_phy-cur_anfc_0.083deg_PT6H-i"
CMEMS_WAV = "cmems_mod_glo_wav_anfc_0.083deg_PT3H-i"

# ── HELPERS ──────────────────────────────────────────────────────────
def safe_unlink(p: Path):
    try: p.unlink()
    except: pass

def era5_subset(out_nc: Path, geom, when: datetime):
    """Download ERA5 wind; skip on failure."""
    if out_nc.exists(): return
    w,s,e,n = geom.bounds
    cds = cdsapi.Client()
    try:
        cds.retrieve("reanalysis-era5-single-levels", {
            "product_type":"reanalysis","variable":ERA_VARS,
            "year":when.strftime("%Y"),"month":when.strftime("%m"),
            "day":when.strftime("%d"),"time":when.strftime("%H:00"),
            "area":[n,w,s,e],"format":"netcdf"
        }, str(out_nc))
    except Exception as e:
        print(f"   ! ERA5 download failed for {when.date()}: {e}")
        return

def wind_layers(nc: Path):
    with xr.open_dataset(nc) as ds:
        u = ds.get("u10", ds["10m_u_component_of_wind"])
        v = ds.get("v10", ds["10m_v_component_of_wind"])
        t = "time" if "time" in u.dims else "valid_time"
        u0 = u.isel({t:0}).astype("float32").load()
        v0 = v.isel({t:0}).astype("float32").load()
    sp = xr.apply_ufunc(np.hypot,u0,v0).rename("wind").load()
    wd = ((np.degrees(np.arctan2(-u0,-v0))+360)%360).rename("wind_dir").load()
    return u0.rename("u10"), v0.rename("v10"), sp, wd

def to_match_grid(da: xr.DataArray, ref: Path, out: Path):
    if out.exists(): return
    grid = rxr.open_rasterio(ref, masked=True)
    da.rio.write_crs("EPSG:4326") \
      .rio.reproject_match(grid, resampling=rasterio.enums.Resampling.bilinear) \
      .rio.to_raster(out, compress="DEFLATE")

def _slice_by_bbox(ds, w,s,e,n):
    lon0,lon1 = (w,e) if ds.longitude[0]<ds.longitude[-1] else (e,w)
    lat0,lat1 = (s,n) if ds.latitude[0]<ds.latitude[-1] else (n,s)
    return ds.sel(longitude=slice(lon0,lon1), latitude=slice(lat0,lat1))

def cmems_to_tifs(geom, when: datetime, ref: Path, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    needed = ["uo.tif","vo.tif","vsdx.tif","vsdy.tif","swh.tif"]
    if all((out_dir/f).exists() for f in needed): 
        return

    w,s,e,n = geom.bounds
    ts = pd.Timestamp(when)  # naive timestamp

    # currents
    try:
        phy = open_dataset(dataset_id=CMEMS_PHY)
        cur = phy[["uo","vo"]].sel(depth=0, time=ts, method="nearest")
        cur = _slice_by_bbox(cur, w,s,e,n)
        for v in ["uo","vo"]:
            to_match_grid(cur[v], ref, out_dir/f"{v}.tif")
    except Exception as e:
        print(f"   ! CMEMS currents failed for {when}: {e}")

    # waves
    try:
        wav = open_dataset(dataset_id=CMEMS_WAV)
        wv = wav[["VSDX","VSDY","VHM0"]].sel(time=ts, method="nearest")
        wv = _slice_by_bbox(wv, w,s,e,n)
        to_match_grid(wv["VSDX"], ref, out_dir/"vsdx.tif")
        to_match_grid(wv["VSDY"], ref, out_dir/"vsdy.tif")
        to_match_grid(wv["VHM0"], ref, out_dir/"swh.tif")
    except Exception as e:
        print(f"   ! CMEMS waves failed for {when}: {e}")

# ── MAIN ─────────────────────────────────────────────────────────────
def main():
    # Loop tiles/dates
    for tile_dir in sorted(OUT_ROOT.iterdir()):
        for date_dir in sorted(tile_dir.iterdir()):
            # S2 B02 reference grid
            ref2 = date_dir/"optical"/f"S2_{tile_dir.name}_{date_dir.name}_B02.tif"
            if not ref2.exists(): 
                continue

            # build bbox
            b = rasterio.open(ref2).bounds
            geom = box(b.left,b.bottom,b.right,b.top)

            # S2 biophysics
            print(f"▶ {tile_dir.name} {date_dir.name} → S2 biophys")
            bio2 = date_dir/"bio_s2"; bio2.mkdir(exist_ok=True)
            tmp = TMP/f"era_s2_{tile_dir.name}_{date_dir.name}.nc"
            era5_subset(tmp, geom, datetime.fromisoformat(date_dir.name))
            if Path(tmp).exists():
                u10,v10,sp,wd = wind_layers(tmp)
                to_match_grid(u10, ref2, bio2/"u10.tif")
                to_match_grid(v10, ref2, bio2/"v10.tif")
                to_match_grid(sp,  ref2, bio2/"wind.tif")
                to_match_grid(wd,  ref2, bio2/"wind_dir.tif")
                safe_unlink(tmp)
            cmems_to_tifs(geom, datetime.fromisoformat(date_dir.name), ref2, bio2)

            # S1 biophysics
            for sar in sorted(date_dir.glob("SAR_*h")):
                vv = next(sar.glob("S1_*_vv.tif"), None)
                if not vv: continue
                ts = vv.stem.split("_")[2]
                acq = datetime.strptime(ts, "%Y%m%dT%H%M%S")
                print(f"  → SAR {sar.name} biophys")
                bio1 = sar/"bio"; bio1.mkdir(exist_ok=True)
                tmp1 = TMP/f"era_s1_{tile_dir.name}_{ts}.nc"
                era5_subset(tmp1, geom, acq)
                if Path(tmp1).exists():
                    u10,v10,sp,wd = wind_layers(tmp1)
                    to_match_grid(u10, vv, bio1/"u10.tif")
                    to_match_grid(v10, vv, bio1/"v10.tif")
                    to_match_grid(sp,  vv, bio1/"wind.tif")
                    to_match_grid(wd,  vv, bio1/"wind_dir.tif")
                    safe_unlink(tmp1)
                cmems_to_tifs(geom, acq, vv, bio1)

    print("\n✓ All biophysics downloaded (or skipped on errors).")

if __name__ == "__main__":
    main()
