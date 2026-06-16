#!/usr/bin/env python3
# download_cmems_only.py

from pathlib import Path
from datetime import datetime
import numpy as np
import xarray as xr, rioxarray as rxr
import rasterio, rasterio.enums
from shapely.geometry import box
from tqdm import tqdm
from copernicusmarine import open_dataset

# ── CONFIG ───────────────────────────────────────────────────────────
OUT_ROOT         = Path(r"D:\Masters\MARIDA\downloads")
CMEMS_CUR_DS     = "cmems_mod_glo_phy-cur_anfc_0.083deg_PT6H-i"  # uo,vo (6 h)
CMEMS_WAV_DS     = "cmems_mod_glo_wav_anfc_0.083deg_PT3H-i"      # VSDX,VSDY,VHM0 (3 h)

# ── HELPERS ──────────────────────────────────────────────────────────
def to_match_grid(da: xr.DataArray, ref: Path, out: Path):
    """Reproject da to match ref GeoTIFF and write out."""
    if out.exists(): return
    grid = rxr.open_rasterio(ref, masked=True)
    da.rio.write_crs("EPSG:4326") \
      .rio.reproject_match(grid, resampling=rasterio.enums.Resampling.bilinear) \
      .rio.to_raster(out, compress="DEFLATE")

def slice_bbox(ds, w, s, e, n):
    """Slice an xarray dataset/DA by bbox, handling 0–360 vs –180–180 lon."""
    # detect if the dataset's lon is 0..360
    lon = ds.longitude
    if float(lon.min()) >= 0:
        # convert negative bbox longs to [0,360)
        w, e = (w + 360 if w < 0 else w), (e + 360 if e < 0 else e)
    # ensure correct slice direction
    lon0,lon1 = (w,e) if lon[0]<lon[-1] else (e,w)
    lat = ds.latitude
    lat0,lat1 = (s,n) if lat[0]<lat[-1] else (n,s)
    return ds.sel(longitude=slice(lon0,lon1), latitude=slice(lat0,lat1))

def cmems_to_tifs(geom, when: datetime, ref: Path, out_dir: Path):
    """
    Fetch uo,vo at depth=0, and VSDX,VSDY,VHM0 at the nearest time,
    slice them by the scene bbox, reproject, and write to out_dir.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    needed = ["uo.tif","vo.tif","vsdx.tif","vsdy.tif","swh.tif"]
    if all((out_dir / f).exists() for f in needed):
        return

    w, s, e, n = geom.bounds
    ts = when.replace(tzinfo=None)  # force to naive datetime

    # 1) surface currents
    try:
        phy = open_dataset(dataset_id=CMEMS_CUR_DS)
        cur = phy[["uo","vo"]].sel(depth=0, time=ts, method="nearest")
        cur = slice_bbox(cur, w, s, e, n)
        for var in ["uo","vo"]:
            to_match_grid(cur[var], ref, out_dir/ f"{var}.tif")
        print(f"    ✓ CMEMS currents @ {ts.time()}")
    except Exception as ex:
        print(f"    ! CMEMS currents error @ {ts.time()}: {ex}")

    # 2) stokes drift & waves
    try:
        wav = open_dataset(dataset_id=CMEMS_WAV_DS)
        wv  = wav[["VSDX","VSDY","VHM0"]].sel(time=ts, method="nearest")
        wv  = slice_bbox(wv, w, s, e, n)
        to_match_grid(wv["VSDX"], ref, out_dir/"vsdx.tif")
        to_match_grid(wv["VSDY"], ref, out_dir/"vsdy.tif")
        to_match_grid(wv["VHM0"], ref, out_dir/"swh.tif")
        print(f"    ✓ CMEMS waves  @ {ts.time()}")
    except Exception as ex:
        print(f"    ! CMEMS waves error  @ {ts.time()}: {ex}")

# ── MAIN ─────────────────────────────────────────────────────────────
def main():
    for tile_dir in sorted(OUT_ROOT.iterdir()):
        if not tile_dir.is_dir(): continue
        tile = tile_dir.name

        for date_dir in sorted(tile_dir.iterdir()):
            date = date_dir.name
            print(f"\n▶ {tile} {date} → S2 biophys")

            # find S2 B02 reference grid
            ref2 = date_dir/"optical"/f"S2_{tile}_{date}_B02.tif"
            if not ref2.exists():
                print("   ! missing S2 B02 grid, skipping")
                continue

            # compute bbox in lon/lat
            b = rasterio.open(ref2).bounds
            geom = box(b.left, b.bottom, b.right, b.top)

            # S2-date CMEMS
            bio2 = date_dir/"bio_s2"
            cmems_to_tifs(geom,
                          when=datetime.fromisoformat(date),  # midday of the date
                          ref=ref2,
                          out_dir=bio2)

            # per-SAR CMEMS
            for sar in sorted(date_dir.glob("SAR_*h")):
                vv = next(sar.glob("S1_*_vv.tif"), None)
                if not vv: 
                    continue
                # parse timestamp from filename: S1_<tile>_<YYYYMMDDThhmmss>_vv.tif
                ts = vv.stem.split("_")[2]    
                acq = datetime.strptime(ts, "%Y%m%dT%H%M%S")
                print(f"  → SAR {sar.name} @ {acq.time()} biophys")
                cmems_to_tifs(geom,
                              when=acq,
                              ref=vv,
                              out_dir=sar/"bio")

    print("\n✓ All CMEMS layers done (or skipped).")

if __name__ == "__main__":
    main()
