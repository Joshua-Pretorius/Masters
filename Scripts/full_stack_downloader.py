#!/usr/bin/env python3
# full_stack_downloader.py

"""
Downloads:
  • Sentinel‑2 optical bands
  • Sentinel‑1 SAR vv
  • ERA‑5 wind (u10, v10) at nearest hour ±1 h
  • CMEMS surface currents (uo, vo)
  • CMEMS Stokes drift & SWH (VSDX, VSDY, VHM0)

Writes into:
  OUT_ROOT/<tile>/<YYYY‑MM‑DD>/
    optical/
      S2_<tile>_<date>_<band>.tif
    bio_s2/
      u10.tif, v10.tif, wind.tif, wind_dir.tif,
      uo.tif, vo.tif, vsdx.tif, vsdy.tif, swh.tif
    SAR_<±Δh>/
      S1_<tile>_<ts>_vv.tif
      bio/
        uo.tif, vo.tif, vsdx.tif, vsdy.tif, swh.tif
"""

from pathlib import Path
from datetime import datetime, timedelta
import tempfile, requests, numpy as np, pandas as pd
import xarray as xr, rioxarray as rxr
import rasterio, rasterio.enums
from shapely.geometry import shape
from pystac_client import Client
import planetary_computer as pc
import cdsapi
from copernicusmarine import open_dataset
from tqdm import tqdm

# ── CONFIG ───────────────────────────────────────────────────────────
CSV_MATCH     = Path(r"D:\Masters\MARIDA\MARIDA\patches\S1_match.csv")
OUT_ROOT      = Path(r"D:\Masters\MARIDA\downloads")
S2_BANDS      = ["B02","B03","B04","B06","B08","B11"]
S1_POLS       = ["vv"]
MAX_HRS       = 12
MIN_COVER     = 0.20
STAC_URL      = "https://planetarycomputer.microsoft.com/api/stac/v1"
ERA5_VARS     = ["u10","v10"]
CMEMS_CUR_DS  = "cmems_mod_glo_phy-cur_anfc_0.083deg_PT6H-i"
CMEMS_WAV_DS  = "cmems_mod_glo_wav_anfc_0.083deg_PT3H-i"

# ── CLIENTS ──────────────────────────────────────────────────────────
cat = Client.open(STAC_URL)
era = cdsapi.Client()
TMP = Path(tempfile.gettempdir())
OUT_ROOT.mkdir(parents=True, exist_ok=True)

# ── LOAD S2 TIMES ────────────────────────────────────────────────────
df = pd.read_csv(CSV_MATCH, parse_dates=["s2_datetime"])

# ── HELPERS ──────────────────────────────────────────────────────────
def safe_unlink(p: Path):
    try: p.unlink()
    except: pass

def download_stream(url, out: Path):
    out.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(url, stream=True, timeout=120); r.raise_for_status()
    total = int(r.headers.get("content-length",0))
    with open(out,"wb") as f, tqdm(total=total,unit="B",unit_scale=True,desc=out.name,leave=False) as bar:
        for chunk in r.iter_content(1<<20):
            f.write(chunk); bar.update(len(chunk))

def fetch_signed_asset(item, asset_key, out: Path):
    if out.exists(): return
    def once():
        signed = pc.sign(item.clone())
        download_stream(signed.assets[asset_key].href, out)
    try: once()
    except requests.HTTPError as e:
        if e.response and e.response.status_code==403: once()
        else: raise

def to_match_grid(da: xr.DataArray, ref: Path, out: Path):
    if out.exists(): return
    grid = rxr.open_rasterio(ref, masked=True)
    da.rio.write_crs("EPSG:4326") \
      .rio.reproject_match(grid, resampling=rasterio.enums.Resampling.bilinear) \
      .rio.to_raster(out, compress="DEFLATE")

def slice_bbox(ds, w,s,e,n):
    lon = ds.longitude
    if float(lon.min())>=0:
        w,e = (w+360 if w<0 else w),(e+360 if e<0 else e)
    lon0,lon1 = (w,e) if lon[0]<lon[-1] else (e,w)
    lat=ds.latitude; lat0,lat1=(s,n) if lat[0]<lat[-1] else (n,s)
    return ds.sel(longitude=slice(lon0,lon1), latitude=slice(lat0,lat1))

# ── ERA5 wind @ S2 (nearest hour ±1h) ────────────────────────────────
def era5_subset(out_nc: Path, geom, when: datetime):
    if out_nc.exists(): return True
    w,s,e,n = geom.bounds
    area = [n,w,s,e]
    center = pd.Timestamp(when)
    candidates = [
        center.round('h'),
        (center - pd.Timedelta(hours=1)).round('h'),
        (center + pd.Timedelta(hours=1)).round('h'),
    ]
    for hr in candidates:
        try:
            era.retrieve("reanalysis-era5-single-levels", {
                "product_type":"reanalysis",
                "variable": ERA5_VARS,
                "year":   hr.strftime("%Y"), "month": hr.strftime("%m"),
                "day":    hr.strftime("%d"),
                "time":   [hr.strftime("%H:00")],  # list!
                "area":   area,
                "format":"netcdf"
            }, str(out_nc))
            print(f"    ✓ ERA5 @ {hr.time()}")
            return True
        except Exception as ex:
            print(f"    ! ERA5 ⛔ {hr.time()}: {ex}")
    return False

def wind_layers(nc: Path):
    with xr.open_dataset(nc) as ds:
        u = ds["u10"] if "u10" in ds else ds["10m_u_component_of_wind"]
        v = ds["v10"] if "v10" in ds else ds["10m_v_component_of_wind"]
        t = "time" if "time" in u.dims else "valid_time"
        u0 = u.isel({t:0}).astype("float32").load()
        v0 = v.isel({t:0}).astype("float32").load()
    sp = xr.apply_ufunc(np.hypot, u0, v0).rename("wind").load()
    wd = ((np.degrees(np.arctan2(-u0,-v0))+360)%360).rename("wind_dir").load()
    return u0.rename("u10"), v0.rename("v10"), sp, wd

# ── CMEMS currents + waves ────────────────────────────────────────────
def cmems_to_tifs(geom, when: datetime, ref: Path, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    needed = ["uo.tif","vo.tif","vsdx.tif","vsdy.tif","swh.tif"]
    if all((out_dir/f).exists() for f in needed): return
    w,s,e,n = geom.bounds
    # ensure naive datetime
    ts = pd.Timestamp(when).to_pydatetime().replace(tzinfo=None)

    try:
        phy = open_dataset(dataset_id=CMEMS_CUR_DS)
        cur = phy[["uo","vo"]].sel(depth=0, time=ts, method="nearest")
        cur = slice_bbox(cur, w,s,e,n)
        for var in ["uo","vo"]:
            to_match_grid(cur[var], ref, out_dir/f"{var}.tif")
        print(f"    ✓ CMEMS currents @ {ts.time()}")
    except Exception as ex:
        print(f"    ! CMEMS currents ⛔ {ts.time()}: {ex}")

    try:
        wav = open_dataset(dataset_id=CMEMS_WAV_DS)
        wv  = wav[["VSDX","VSDY","VHM0"]].sel(time=ts, method="nearest")
        wv  = slice_bbox(wv, w,s,e,n)
        to_match_grid(wv["VSDX"], ref, out_dir/"vsdx.tif")
        to_match_grid(wv["VSDY"], ref, out_dir/"vsdy.tif")
        to_match_grid(wv["VHM0"], ref, out_dir/"swh.tif")
        print(f"    ✓ CMEMS waves    @ {ts.time()}")
    except Exception as ex:
        print(f"    ! CMEMS waves   ⛔ {ts.time()}: {ex}")

# ── STAC SEARCH ──────────────────────────────────────────────────────
def s2_item(tile, when):
    day = when.strftime("%Y-%m-%d")
    return next(cat.search(
        collections=["sentinel-2-l2a"],
        query={"s2:mgrs_tile":{"eq":tile}},
        datetime=f"{day}T00:00:00Z/{day}T23:59:59Z", limit=5
    ).items(), None)

def s1_items(poly, t0, t1):
    return list(cat.search(
        collections=["sentinel-1-grd","sentinel-1-rtc"],
        intersects=poly, datetime=f"{t0}/{t1}", limit=200
    ).items())

def overlap_ratio(g1,g2):
    return shape(g1).intersection(g2).area / g2.area

# ── MAIN ─────────────────────────────────────────────────────────────
def main():
    for _, rec in df.iterrows():
        tile, s2_dt = rec.s2_tile, rec.s2_datetime
        day = s2_dt.date().isoformat()
        tile_path = OUT_ROOT/tile/day

        # only process dates with a SAR folder
        if not any(tile_path.glob("SAR_*h")):
            continue

        print(f"\n▶ {tile} {day} @ {s2_dt.time()}")

        # 1) S2 optical
        s2 = s2_item(tile, s2_dt)
        if not s2:
            print("   ! no S2; skip"); continue
        poly = shape(s2.geometry)
        opt_dir = tile_path/"optical"
        for b in S2_BANDS:
            if b in s2.assets:
                fetch_signed_asset(s2, b, opt_dir/f"S2_{tile}_{day}_{b}.tif")
        ref_s2 = opt_dir/f"S2_{tile}_{day}_B02.tif"
        if not ref_s2.exists():
            print("   ! missing B02; skip"); continue

        # 2) ERA‑5 wind @ S2
        bio_s2 = tile_path/"bio_s2"; bio_s2.mkdir(exist_ok=True)
        tmp_nc = TMP/f"era5_{tile}_{day}.nc"
        if era5_subset(tmp_nc, poly, s2_dt):
            u10, v10, sp, wd = wind_layers(tmp_nc)
            to_match_grid(u10, ref_s2, bio_s2/"u10.tif")
            to_match_grid(v10, ref_s2, bio_s2/"v10.tif")
            to_match_grid(sp,  ref_s2, bio_s2/"wind.tif")
            to_match_grid(wd,  ref_s2, bio_s2/"wind_dir.tif")
            safe_unlink(tmp_nc)

        # 3) CMEMS @ S2
        cmems_to_tifs(poly, s2_dt, ref_s2, bio_s2)

        # 4) SAR loop
        t0 = (s2_dt - timedelta(hours=MAX_HRS)).strftime("%Y-%m-%dT%H:%M:%SZ")
        t1 = (s2_dt + timedelta(hours=MAX_HRS)).strftime("%Y-%m-%dT%H:%M:%SZ")
        for s1 in s1_items(poly, t0, t1):
            if overlap_ratio(s1.geometry, poly) < MIN_COVER: continue
            s1_dt = s1.datetime
            dt = (s1_dt - s2_dt).total_seconds()/3600
            sar_dir = tile_path/f"SAR_{dt:+0.1f}h"; sar_dir.mkdir(exist_ok=True)
            for pol in S1_POLS:
                if pol in s1.assets:
                    ts = s1_dt.strftime("%Y%m%dT%H%M%S")
                    fetch_signed_asset(s1, pol, sar_dir/f"S1_{tile}_{ts}_{pol}.tif")

            ref_s1 = next(sar_dir.glob("S1_*_vv.tif"), None)
            if not ref_s1: continue
            bio_s1 = sar_dir/"bio"; bio_s1.mkdir(exist_ok=True)

            # 5) CMEMS @ S1
            cmems_to_tifs(poly, s1_dt, ref_s1, bio_s1)

    print("\n✓ All done.")

if __name__=="__main__":
    main()
