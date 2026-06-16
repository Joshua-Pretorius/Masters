# test_wind_wave.py  ── download ERA-5 wind-direction for ONE Sentinel-2 tile
# --------------------------------------------------------------------------
# • Converts the Sentinel-2 B11 footprint (UTM) to lon/lat
# • Expands/snaps the box to the 0.25-degree ERA-5 grid
# • Requests ERA-5 10 m U/V wind for the chosen hour
# • Saves wind-direction raster co-registered to the Sentinel-2 grid
#
# Requires:  pip install cdsapi rasterio rioxarray xarray netCDF4 numpy
# --------------------------------------------------------------------------
from pathlib import Path
from datetime import datetime
import numpy as np, cdsapi, tempfile, rasterio, rioxarray as rxr, xarray as xr
from rasterio.warp import transform_bounds
import rasterio.enums
# ── INPUTS ──────────────────────────────────────────────────────────────
S2_B11 = Path(r"D:\Masters\MARIDA\downloads\48MYU\2019-12-01\optical\S2_48MYU_2019-12-01_B11.tif")
WHEN   = datetime(2019, 12, 1, 12)          # YYYY, MM, DD, HH (UTC)
OUT_TIF = S2_B11.parent.parent / "bio_test" / "wind_dir.tif"
OUT_TIF.parent.mkdir(parents=True, exist_ok=True)

# ── helper: snap to 0.25° grid ─────────────────────────────────────────
def snap(val, res=0.25, up=False):
    return np.floor(val / res + (1 if up else 0)) * res

# ── 1. footprint → lon/lat and snap ───────────────────────────────────
with rasterio.open(S2_B11) as src:
    west_m, south_m, east_m, north_m = src.bounds              # UTM metres
    west, south, east, north = transform_bounds(
        src.crs, "epsg:4326",
        west_m, south_m, east_m, north_m, densify_pts=21
    )

west  = snap(west , 0.25)
south = snap(south, 0.25)
east  = snap(east , 0.25, up=True)
north = snap(north, 0.25, up=True)
print("CDS box  [N W S E] →", [north, west, south, east])

# ── 2. ERA-5 download ─────────────────────────────────────────────────
TMP_NC = Path(tempfile.gettempdir()) / "era_test.nc"
cds    = cdsapi.Client()

cds.retrieve(
    "reanalysis-era5-single-levels",
    {
        "product_type": "reanalysis",
        "variable": ["10m_u_component_of_wind", "10m_v_component_of_wind"],
        "year":  WHEN.strftime("%Y"),
        "month": WHEN.strftime("%m"),
        "day":   WHEN.strftime("%d"),
        "time":  WHEN.strftime("%H:00"),
        "area":  [north, west, south, east],   # N W S E
        "format":"netcdf",
    },
    str(TMP_NC)
)

# ── 3. wind-direction calculation & reprojection ──────────────────────
ds   = xr.open_dataset(TMP_NC)
u, v = ds["u10"], ds["v10"]                  # internal var names
wdir = (np.degrees(np.arctan2(-u, -v)) + 360) % 360

# pick the first (and only) time slice: dimension could be "time" or "valid_time"
t_dim = "time" if "time" in wdir.dims else "valid_time"
wdir  = wdir.isel({t_dim: 0}).rename("wind_dir")

ref = rxr.open_rasterio(S2_B11, masked=True)
wdir = wdir.rio.write_crs("epsg:4326").rio.reproject_match(
        ref, resampling=rasterio.enums.Resampling.bilinear
)
wdir.rio.to_raster(OUT_TIF, compress="DEFLATE")
ds.close()
TMP_NC.unlink()
print("✓ wind_dir.tif written to", OUT_TIF)
