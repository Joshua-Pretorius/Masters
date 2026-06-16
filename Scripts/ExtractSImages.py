# download_all_intersecting_SAR.py
# ────────────────────────────────
# For every Sentinel-2 scene in CSV_MATCH:
#   1. read its true footprint
#   2. query Planetary-Computer for *all* Sentinel-1 GRD/RTC scenes whose
#      • footprint INTERSECTS that polygon  (any swath / orbit / tile)
#      • acquisition time is within ±MAX_HRS  (set MAX_HRS=None to drop time filter)
#   3. keep only scenes whose intersection area ≥ MIN_COVER of the S-2 tile
#   4. download *every* VV & VH TIFF to   downloads/<tile>/<date>/SAR_<Δt h>/…

from pathlib import Path
from datetime import datetime, timedelta, timezone
import requests, pandas as pd
from tqdm import tqdm
from pystac_client import Client
import planetary_computer as pc
from shapely.geometry import shape

# ─── CONFIG ───────────────────────────────────────────────────────────
DL_ROOT   = Path(r"D:\Masters\MARIDA\downloads")
CSV_MATCH = Path(r"D:\Masters\MARIDA\MARIDA\patches\S1_match.csv")  # S-2 list
MAX_HRS   = 12                 # None = ignore time, else ± hours
MIN_COVER = 0.01               # keep S-1 scenes if ≥20 % of tile area overlaps
S1_COLLS  = ["sentinel-1-grd", "sentinel-1-rtc"]
S2_BANDS  = ["B02","B03","B04","B06","B08","B11"]
S1_POLS   = ["vv","vh"]

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
cat      = Client.open(STAC_URL)
DL_ROOT.mkdir(exist_ok=True, parents=True)

# ─── UTILITIES ────────────────────────────────────────────────────────
def dl(url, out):
    if out.exists(): return
    out.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(url, stream=True, timeout=120); r.raise_for_status()
    tot = int(r.headers.get("content-length",0))
    with open(out,"wb") as f, tqdm(total=tot,unit="B",unit_scale=True,
                                   desc=out.name,leave=False) as bar:
        for chunk in r.iter_content(1<<20):
            f.write(chunk); bar.update(len(chunk))

def s2_item(tile, date):
    day = date.strftime("%Y-%m-%d")
    items = list(cat.search(
        collections=["sentinel-2-l2a"],
        query={"s2:mgrs_tile":{"eq":tile}},
        datetime=f"{day}T00:00:00Z/{day}T23:59:59Z",
        limit=5).items())
    return items[0] if items else None

def s1_candidates(tile_geom, centre_time):
    if MAX_HRS is None:
        tfilter = None
    else:
        t0 = (centre_time-timedelta(hours=MAX_HRS)).strftime("%Y-%m-%dT%H:%M:%SZ")
        t1 = (centre_time+timedelta(hours=MAX_HRS)).strftime("%Y-%m-%dT%H:%M:%SZ")
        tfilter = f"{t0}/{t1}"
    search = cat.search(collections=S1_COLLS,
                        intersects=tile_geom,
                        datetime=tfilter,
                        limit=200)
    return list(search.items())

def signed_dt_hours(t1,t2):
    return (t1-t2).total_seconds()/3600

# ─── MAIN LOOP ────────────────────────────────────────────────────────
s2_rows = pd.read_csv(CSV_MATCH)           # only need tile + datetime
for _,row in s2_rows.iterrows():
    tile = row.s2_tile
    s2_dt = pd.to_datetime(row.s2_datetime)
    item  = s2_item(tile, s2_dt)
    if not item:
        print(f"[!] No S-2 product for {tile} {s2_dt.date()}"); continue
    tile_poly = shape(item.geometry)
    tile_area = tile_poly.area

    # collect all intersecting S-1 scenes
    cand = s1_candidates(tile_poly, s2_dt)
    keep = []
    for it in cand:
        inter = shape(it.geometry).intersection(tile_poly).area
        if inter / tile_area >= MIN_COVER:
            keep.append(it)

    if not keep:
        print(f"[i] No S-1 intersecting ≥{MIN_COVER*100:.0f}% for {tile} {s2_dt.date()}"); continue

    date_str = s2_dt.date().isoformat()
    # download optical once
    opt_dir = DL_ROOT / tile / date_str / "optical"
    signed  = pc.sign(item)
    for b in S2_BANDS:
        if b in signed.assets:
            dl(signed.assets[b].href, opt_dir / f"S2_{tile}_{date_str}_{b}.tif")

    # download every S-1 that passes intersection test
    for it in keep:
        dt_s1 = it.datetime
        delta = f"{signed_dt_hours(dt_s1,s2_dt):+0.1f}h"
        sar_dir = DL_ROOT / tile / date_str / f"SAR_{delta}"
        signed = pc.sign(it)
        for pol in S1_POLS:
            if pol in signed.assets:
                ts = dt_s1.strftime("%Y%m%dT%H%M%S")
                dl(signed.assets[pol].href,
                   sar_dir / f"S1_{tile}_{ts}_{pol}.tif")

print("✓ finished downloading all intersecting SAR scenes")
