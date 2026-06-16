"""
download_biophys_only.py

For every scene under OUT_ROOT/<tile>/<date>/optical and its SAR subfolders,
download ERA5 wind (u10,v10,speed,dir) and CMEMS surface currents (uo,vo),
Stokes drift (VSDX,VSDY) and significant wave height (VHM0),
reprojected to each scene’s grid just like your wind.tif earlier.

Prereqs:
  pip install cdsapi xarray rioxarray rasterio copernicusmarine shapely tqdm pandas
  (once) copernicusmarine login

Usage:
  python download_biophys_only.py
"""

from pathlib import Path
from datetime import datetime
import tempfile
import cdsapi, numpy as np, pandas as pd
import xarray as xr, rioxarray as rxr
import rasterio, rasterio.enums
from tqdm import tqdm
from copernicusmarine import open_dataset

# ── CONFIG ───────────────────────────────────────────────────────────
OUT_ROOT = Path(r"D:\Masters\MARIDA\downloads")
TMP      = Path(tempfile.gettempdir())
ERA_VARS = ["10m_u_component_of_wind","10m_v_component_of_wind"]
CMEMS_PHY = "cmems_mod_glo_phy-cur_anfc_0.083deg_PT6H-i"  # uo,vo
CMEMS_WAV = "cmems_mod_glo_wav_anfc_0.083deg_PT3H-i"     # VSDX,VSDY,VHM0

# ── HELPERS ──────────────────────────────────────────────────────────
def safe_unlink(p: Path):
    try:
        if p.exists(): p.unlink()
    except PermissionError:
        pass

def era5_subset(out_nc: Path, geom, when: datetime):
    """Download ERA5 u10/v10 for the bbox/time."""
    if out_nc.exists(): return
    w,s,e,n = geom.bounds
    cds = cdsapi.Client()
    cds.retrieve("reanalysis-era5-single-levels", {
        "product_type":"reanalysis","variable":ERA_VARS,
        "year":when.strftime("%Y"),"month":when.strftime("%m"),
        "day":when.strftime("%d"),"time":when.strftime("%H:00"),
        "area":[n,w,s,e],"format":"netcdf"
    }, str(out_nc))

def wind_layers(nc: Path):
    """Load ERA5 netcdf and return u10,v10,speed,dir arrays."""
    with xr.open_dataset(nc) as ds:
        u = ds.get("u10", ds["10m_u_component_of_wind"])
        v = ds.get("v10", ds["10m_v_component_of_wind"])
        t = "time" if "time" in u.dims else "valid_time"
        u0 = u.isel({t:0}).astype("float32").load()
        v0 = v.isel({t:0}).astype("float32").load()
    speed = xr.apply_ufunc(np.hypot, u0, v0).rename("wind").load()
    wdir  = ((np.degrees(np.arctan2(-u0, -v0)) + 360) % 360).rename("wind_dir").load()
    return u0.rename("u10"), v0.rename("v10"), speed, wdir

def to_match_grid(da: xr.DataArray, ref: Path, out: Path):
    """Reproject da to match ref raster, write to out."""
    if out.exists(): return
    grid = rxr.open_rasterio(ref, masked=True)
    da.rio.write_crs("EPSG:4326") \
      .rio.reproject_match(grid, resampling=rasterio.enums.Resampling.bilinear) \
      .rio.to_raster(out, compress="DEFLATE")

def _slice_by_bbox(da, w,s,e,n):
    """Subset xarray.DataArray (or Dataset) by bbox, handling any ordering."""
    lon0,lon1 = (w,e) if da.longitude[0]<da.longitude[-1] else (e,w)
    lat0,lat1 = (s,n) if da.latitude[0]<da.latitude[-1] else (n,s)
    return da.sel(longitude=slice(lon0,lon1), latitude=slice(lat0,lat1))

def cmems_to_tifs(poly, when: datetime, ref: Path, out_dir: Path):
    """Fetch and reproject CMEMS variables for one scene."""
    files = ["uo.tif","vo.tif","vsdx.tif","vsdy.tif","swh.tif"]
    if all((out_dir/f).exists() for f in files):
        return
    w,s,e,n = poly.bounds
    ts = pd.Timestamp(when)  # CMEMS expects naive timestamps
    phy = open_dataset(dataset_id=CMEMS_PHY)
    cur = phy[["uo","vo"]].sel(depth=0, time=ts, method="nearest")
    cur = _slice_by_bbox(cur, w,s,e,n)
    for v in ["uo","vo"]:
        to_match_grid(cur[v], ref, out_dir/f"{v}.tif")

    wav = open_dataset(dataset_id=CMEMS_WAV)
    wv  = wav[["VSDX","VSDY","VHM0"]].sel(time=ts, method="nearest")
    wv  = _slice_by_bbox(wv, w,s,e,n)
    to_match_grid(wv["VSDX"], ref, out_dir/"vsdx.tif")
    to_match_grid(wv["VSDY"], ref, out_dir/"vsdy.tif")
    to_match_grid(wv["VHM0"], ref, out_dir/"swh.tif")

# ── MAIN ─────────────────────────────────────────────────────────────
def main():
    # Loop over each tile/date
    for tile_dir in OUT_ROOT.iterdir():
        if not tile_dir.is_dir(): continue
        for date_dir in tile_dir.iterdir():
            opt_ref = date_dir/"optical"/f"S2_{tile_dir.name}_{date_dir.name}_B02.tif"
            if not opt_ref.exists(): continue

            poly = rasterio.open(opt_ref).bounds  # for ERA5 bbox we need geometry; we use bounds
            from shapely.geometry import box
            geom = box(poly.left, poly.bottom, poly.right, poly.top)

            bio2 = date_dir/"bio_s2"; bio2.mkdir(exist_ok=True)
            print(f"\n▶ {tile_dir.name} {date_dir.name}: downloading S2 biophys")
            # ERA5
            tmp = TMP/f"era_s2_{tile_dir.name}_{date_dir.name}.nc"
            era5_subset(tmp, geom, datetime.fromisoformat(date_dir.name))
            u10,v10,spd,wd = wind_layers(tmp)
            to_match_grid(u10, opt_ref, bio2/"u10.tif")
            to_match_grid(v10, opt_ref, bio2/"v10.tif")
            to_match_grid(spd,  opt_ref, bio2/"wind.tif")
            to_match_grid(wd,   opt_ref, bio2/"wind_dir.tif")
            safe_unlink(tmp)
            # CMEMS
            cmems_to_tifs(geom, datetime.fromisoformat(date_dir.name), opt_ref, bio2)

            # Now each SAR subfolder
            for sar_dir in date_dir.glob("SAR_*h"):
                vv = next(sar_dir.glob("S1_*_vv.tif"), None)
                if not vv: continue
                # parse acquisition time from filename
                ts = vv.stem.split("_")[2]  # e.g. 20160905T000626
                acq = datetime.strptime(ts, "%Y%m%dT%H%M%S")
                bio1 = sar_dir/"bio"; bio1.mkdir(exist_ok=True)
                print(f" ▶ SAR Δt={sar_dir.name.split('_')[1]}: downloading biophys")
                # ERA5 @ S1
                tmp1 = TMP/f"era_s1_{tile_dir.name}_{ts}.nc"
                era5_subset(tmp1, geom, acq)
                u10,v10,spd,wd = wind_layers(tmp1)
                to_match_grid(u10, vv, bio1/"u10.tif")
                to_match_grid(v10, vv, bio1/"v10.tif")
                to_match_grid(spd,  vv, bio1/"wind.tif")
                to_match_grid(wd,   vv, bio1/"wind_dir.tif")
                safe_unlink(tmp1)
                # CMEMS @ S1
                cmems_to_tifs(geom, acq, vv, bio1)

    print("\n✓ Finished downloading all biophysical layers.")

if __name__ == "__main__":
    main()
