#!/usr/bin/env python3
"""Batch OpenDrift runner for Drift scenes.

This script matches each Drift optical scene to the corresponding MARIDA
shapefile, filters seeds to class/id 1 (Marine Debris), builds a minimal
OpenDrift forcing file from the available biophysical rasters, and writes:

- predicted_points_plast.*
- search_boxes_1km_plast.*

It uses the bundled ``opendrift-master.zip`` source tree and installs a small
set of local import shims for optional plotting/service dependencies that are
not needed for this batch workflow.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
import types
import zipfile
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import xarray as xr
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.transform import xy
from rasterio.warp import reproject
from shapely.geometry import box


START_TIME0 = np.datetime64("2000-01-01T00:00:00")
DECIMATE = 30
ENSEMBLE_N = 20
DT_MIN = 60
WINDAGE = 0.03
WINDAGE_STD = 0.01
TERM_VEL = 0.01
BOX_HALF_M = 500


def _install_opendrift_shims() -> None:
    """Install lightweight module shims for optional OpenDrift deps."""

    if "copernicusmarine" not in sys.modules:
        mod = types.ModuleType("copernicusmarine")

        def _unsupported(*args, **kwargs):
            raise RuntimeError("copernicusmarine is not available in this environment")

        mod.describe = _unsupported
        mod.open_dataset = _unsupported
        sys.modules["copernicusmarine"] = mod

    if "geojson" not in sys.modules:
        mod = types.ModuleType("geojson")

        class LineString(dict):
            def __init__(self, coords):
                super().__init__(type="LineString", coordinates=list(coords))

        class Feature(dict):
            def __init__(self, geometry=None, properties=None):
                super().__init__(
                    type="Feature",
                    geometry=geometry,
                    properties=properties or {},
                )

        class FeatureCollection(dict):
            def __init__(self, features):
                super().__init__(type="FeatureCollection", features=list(features))

        def loads(text):
            import json

            return json.loads(text)

        def _coords_walk(node):
            if isinstance(node, (list, tuple)):
                if node and isinstance(node[0], (int, float)):
                    yield tuple(node)
                else:
                    for item in node:
                        yield from _coords_walk(item)

        class _Utils:
            @staticmethod
            def coords(obj):
                if isinstance(obj, dict):
                    if "coordinates" in obj:
                        return list(_coords_walk(obj["coordinates"]))
                    if obj.get("type") == "Feature":
                        return _Utils.coords(obj.get("geometry") or {})
                    if obj.get("type") == "FeatureCollection":
                        out = []
                        for feature in obj.get("features", []):
                            out.extend(_Utils.coords(feature))
                        return out
                return []

        mod.LineString = LineString
        mod.Feature = Feature
        mod.FeatureCollection = FeatureCollection
        mod.loads = loads
        mod.utils = _Utils
        sys.modules["geojson"] = mod

    if "roaring_landmask" not in sys.modules:
        mod = types.ModuleType("roaring_landmask")

        class RoaringLandmask:
            dx = 1.0
            dy = 1.0

            def __init__(self):
                self.mask = self

            @classmethod
            def new(cls):
                return cls()

            def contains_many(self, lon, lat):
                return np.zeros(np.asarray(lon).shape, dtype=bool)

        class LandmaskProvider:
            Gshhg = "Gshhg"

        class Shapes:
            @classmethod
            def new(cls, provider):
                return cls()

            @staticmethod
            def wkb(provider):
                return b"GEOMETRYCOLLECTION EMPTY"

        mod.RoaringLandmask = RoaringLandmask
        mod.LandmaskProvider = LandmaskProvider
        mod.Shapes = Shapes
        sys.modules["roaring_landmask"] = mod

    if "cmocean" not in sys.modules:
        mod = types.ModuleType("cmocean")
        mod.cm = types.SimpleNamespace(
            algae=None,
            amp=None,
            balance=None,
            curl=None,
            deep=None,
            delta=None,
            dense=None,
            gray=None,
            haline=None,
            ice=None,
            matter=None,
            oxy=None,
            phase=None,
            rain=None,
            solar=None,
            speed=None,
            tarn=None,
            tempo=None,
            thermal=None,
            topo=None,
            turbid=None,
        )
        sys.modules["cmocean"] = mod

    if "coloredlogs" not in sys.modules:
        mod = types.ModuleType("coloredlogs")
        mod.DEFAULT_FIELD_STYLES = {"levelname": {}}

        def install(*args, **kwargs):
            return None

        mod.install = install
        sys.modules["coloredlogs"] = mod

    if "cartopy" not in sys.modules:
        cartopy = types.ModuleType("cartopy")
        crs = types.ModuleType("cartopy.crs")
        feature = types.ModuleType("cartopy.feature")
        io = types.ModuleType("cartopy.io")
        shapereader = types.ModuleType("cartopy.io.shapereader")

        class CRS:
            def __init__(self, *args, **kwargs):
                self.globe = kwargs.get("globe")

            def transform_points(self, src_crs, x, y):
                x = np.asarray(x)
                y = np.asarray(y)
                z = np.zeros_like(x, dtype=float)
                return np.stack([x, y, z], axis=-1)

        class Globe:
            def __init__(self, *args, **kwargs):
                self.kwargs = kwargs

        class PlateCarree(CRS):
            pass

        class Geodetic(CRS):
            pass

        class Mercator(CRS):
            pass

        class Stereographic(CRS):
            pass

        class AdaptiveScaler:
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

        class GSHHSFeature:
            _geometries_cache = {}

            def __init__(self, scale="auto", **kwargs):
                self._scale = scale
                self._levels = kwargs.get("levels", [])
                self._crs = kwargs.get("globe")

            def _scale_from_extent(self, extent):
                return "c"

            def geometries(self):
                return []

            def intersecting_geometries(self, extent):
                return []

        def gshhs(scale, level):
            return None

        class Reader:
            def __init__(self, path):
                self.path = path

            def geometries(self):
                return []

        crs.CRS = CRS
        crs.Globe = Globe
        crs.PlateCarree = PlateCarree
        crs.Geodetic = Geodetic
        crs.Mercator = Mercator
        crs.Stereographic = Stereographic

        feature.COLORS = {"land": "#dddddd"}
        feature.AdaptiveScaler = AdaptiveScaler
        feature.GSHHSFeature = GSHHSFeature

        shapereader.gshhs = gshhs
        shapereader.Reader = Reader

        cartopy.crs = crs
        cartopy.feature = feature
        cartopy.io = io
        io.shapereader = shapereader

        sys.modules["cartopy"] = cartopy
        sys.modules["cartopy.crs"] = crs
        sys.modules["cartopy.feature"] = feature
        sys.modules["cartopy.io"] = io
        sys.modules["cartopy.io.shapereader"] = shapereader


def _ensure_local_opendrift(zip_path: Path) -> None:
    """Extract the bundled OpenDrift source and prepend it to sys.path."""

    target_root = Path("/tmp/opendrift_local")
    extract_root = target_root / "opendrift-master"
    if not extract_root.exists():
        target_root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(target_root)
    sys.path.insert(0, str(extract_root))


os.environ.setdefault("MPLCONFIGDIR", "/tmp/mpl-opendrift")
_install_opendrift_shims()

SCRIPT_DIR = Path(__file__).resolve().parent
OPEN_DRIFT_ZIP = SCRIPT_DIR / "opendrift-master.zip"
_ensure_local_opendrift(OPEN_DRIFT_ZIP)

from opendrift.models.plastdrift import PlastDrift
from opendrift.readers import reader_netCDF_CF_generic


@dataclass
class RasterRef:
    path: Path
    crs: object
    transform: object
    width: int
    height: int
    x: np.ndarray
    y: np.ndarray


def get_ref_grid(ref_tif: Path) -> RasterRef:
    with rasterio.open(ref_tif) as src:
        x = np.array(
            [xy(src.transform, 0, col, offset="center")[0] for col in range(src.width)],
            dtype="float64",
        )
        y = np.array(
            [xy(src.transform, row, 0, offset="center")[1] for row in range(src.height)],
            dtype="float64",
        )
        return RasterRef(
            path=ref_tif,
            crs=src.crs,
            transform=src.transform,
            width=src.width,
            height=src.height,
            x=x,
            y=y,
        )


def open_match(path: Path, ref: RasterRef) -> np.ndarray:
    with rasterio.open(path) as src:
        dst = np.full((ref.height, ref.width), np.nan, dtype="float32")
        src_arr = src.read(1)
        src_nodata = src.nodata
        reproject(
            source=src_arr,
            destination=dst,
            src_transform=src.transform,
            src_crs=src.crs or ref.crs,
            dst_transform=ref.transform,
            dst_crs=ref.crs,
            src_nodata=src_nodata,
            dst_nodata=np.nan,
            resampling=Resampling.bilinear,
        )
        return dst


def atomic_netcdf_write(ds: xr.Dataset, out_nc: Path) -> None:
    tmp = out_nc.with_suffix(out_nc.suffix + f".tmp.{int(time.time())}")
    ds.to_netcdf(tmp, mode="w", engine="netcdf4")
    ds.close()
    if out_nc.exists():
        out_nc.unlink()
    tmp.replace(out_nc)


def get_optical_ref(date_dir: Path) -> Path:
    ref_tif = next((date_dir / "optical").glob("S2_*_B02.tif"), None)
    if ref_tif is None:
        raise FileNotFoundError(f"No optical B02 reference found in {date_dir}")
    return ref_tif


def parse_tile_date_from_optical(ref_tif: Path) -> tuple[str, pd.Timestamp]:
    match = re.match(r"S2_([A-Z0-9]{5})_(\d{4}-\d{2}-\d{2})_B02\.tif$", ref_tif.name)
    if not match:
        raise ValueError(f"Unexpected optical name: {ref_tif.name}")
    tile = match.group(1)
    date = pd.to_datetime(match.group(2)).date()
    return tile, date


def candidate_shp_names(date_obj, tile: str) -> list[str]:
    yy = f"{date_obj.year % 100:02d}"
    day_z, day_n = f"{date_obj.day:02d}", str(date_obj.day)
    month_z, month_n = f"{date_obj.month:02d}", str(date_obj.month)
    stems = [
        f"S2_{day_n}-{month_n}-{yy}_{tile}",
        f"S2_{day_z}-{month_n}-{yy}_{tile}",
        f"S2_{day_n}-{month_z}-{yy}_{tile}",
        f"S2_{day_z}-{month_z}-{yy}_{tile}",
    ]
    return [stem + ".shp" for stem in stems]


def find_matching_shapefile(shp_root: Path, tile: str, date_obj) -> Path | None:
    for name in candidate_shp_names(date_obj, tile):
        path = shp_root / name
        if path.exists():
            return path

    pattern = re.compile(r"S2_(\d{1,2})-(\d{1,2})-(\d{2})_([A-Z0-9]{5})\.shp$")
    for path in shp_root.glob("S2_*-*-*_*.shp"):
        match = pattern.match(path.name)
        if not match:
            continue
        day, month, yy2, this_tile = match.groups()
        if this_tile != tile:
            continue
        try:
            this_date = pd.to_datetime(f"20{yy2}-{int(month):02d}-{int(day):02d}").date()
        except Exception:
            continue
        if this_date == date_obj:
            return path
    return None


def seeds_wgs84_from_shp(shp_path: Path) -> tuple[list[float], list[float]]:
    gdf = gpd.read_file(shp_path)
    gdf = gdf[gdf.get("id", 0) == 1].copy()
    if gdf.empty:
        return [], []

    reps = []
    for geom in gdf.geometry:
        if geom.geom_type == "Point":
            reps.append(geom)
        elif geom.geom_type in ("Polygon", "MultiPolygon"):
            reps.append(geom.representative_point())
        else:
            reps.append(geom.centroid)

    gdf_rep = gpd.GeoDataFrame(geometry=reps, crs=gdf.crs).to_crs(4326)
    return [geom.x for geom in gdf_rep.geometry], [geom.y for geom in gdf_rep.geometry]


def extract_final_lonlat(o: PlastDrift) -> tuple[np.ndarray, np.ndarray]:
    try:
        lon = np.asarray(o.result["lon"].isel(time=-1).values).ravel()
        lat = np.asarray(o.result["lat"].isel(time=-1).values).ravel()
    except Exception:
        lon = np.asarray(o.get_property("lon")[-1]).ravel()
        lat = np.asarray(o.get_property("lat")[-1]).ravel()
    return lon, lat


def build_plast_forcing(date_dir: Path, sar_dir: Path, decimate: int = DECIMATE) -> Path:
    ref_tif = get_optical_ref(date_dir)
    ref = get_ref_grid(ref_tif)
    bio0 = date_dir / "bio_s2"
    bio1 = sar_dir / "bio"

    uo0 = open_match(bio0 / "uo.tif", ref)
    vo0 = open_match(bio0 / "vo.tif", ref)
    vsdx0 = open_match(bio0 / "vsdx.tif", ref)
    vsdy0 = open_match(bio0 / "vsdy.tif", ref)
    swh0 = open_match(bio0 / "swh.tif", ref) if (bio0 / "swh.tif").exists() else np.zeros_like(uo0)
    wspd0 = open_match(bio0 / "wind.tif", ref)
    wdir0 = open_match(bio0 / "wind_dir.tif", ref)
    th0 = np.deg2rad(wdir0)
    u10_0 = (wspd0 * np.sin(th0)).astype("float32")
    v10_0 = (wspd0 * np.cos(th0)).astype("float32")

    uo1 = open_match(bio1 / "uo.tif", ref)
    vo1 = open_match(bio1 / "vo.tif", ref)
    vsdx1 = open_match(bio1 / "vsdx.tif", ref)
    vsdy1 = open_match(bio1 / "vsdy.tif", ref)
    swh1 = open_match(bio1 / "swh.tif", ref) if (bio1 / "swh.tif").exists() else np.zeros_like(uo1)
    wspd1 = open_match(bio1 / "wind.tif", ref)
    wdir1 = open_match(bio1 / "wind_dir.tif", ref)
    th1 = np.deg2rad(wdir1)
    u10_1 = (wspd1 * np.sin(th1)).astype("float32")
    v10_1 = (wspd1 * np.cos(th1)).astype("float32")

    def dec(arr: np.ndarray) -> np.ndarray:
        return arr[::decimate, ::decimate].astype("float32")

    xs = ref.x[::decimate]
    ys = ref.y[::decimate]
    X, Y = np.meshgrid(xs, ys)
    to_wgs = Transformer.from_crs(ref.crs, 4326, always_xy=True)
    lon, lat = to_wgs.transform(X, Y)

    match = re.search(r"SAR_([+-]?\d+\.?\d*)h", sar_dir.name)
    if not match:
        raise ValueError(f"Bad SAR directory name: {sar_dir.name}")
    delta_h = float(match.group(1))
    delta_sec = int(abs(delta_h) * 3600)
    times = np.array(
        [START_TIME0, START_TIME0 + np.timedelta64(delta_sec, "s")],
        dtype="datetime64[ns]",
    )

    ds = xr.Dataset(
        coords={
            "time": ("time", times),
            "y": ("y", np.arange(lon.shape[0], dtype=np.int32)),
            "x": ("x", np.arange(lon.shape[1], dtype=np.int32)),
            "latitude": (("y", "x"), lat.astype("float32")),
            "longitude": (("y", "x"), lon.astype("float32")),
        },
        data_vars={
            "uo": (("time", "y", "x"), np.stack([dec(uo0), dec(uo1)])),
            "vo": (("time", "y", "x"), np.stack([dec(vo0), dec(vo1)])),
            "vsdx": (("time", "y", "x"), np.stack([dec(vsdx0), dec(vsdx1)])),
            "vsdy": (("time", "y", "x"), np.stack([dec(vsdy0), dec(vsdy1)])),
            "u10": (("time", "y", "x"), np.stack([dec(u10_0), dec(u10_1)])),
            "v10": (("time", "y", "x"), np.stack([dec(v10_0), dec(v10_1)])),
            "swh": (("time", "y", "x"), np.stack([dec(swh0), dec(swh1)])),
        },
    )

    ds["uo"].attrs.update(standard_name="eastward_sea_water_velocity", units="m s-1")
    ds["vo"].attrs.update(standard_name="northward_sea_water_velocity", units="m s-1")
    ds["vsdx"].attrs.update(
        standard_name="sea_surface_wave_stokes_drift_x_velocity",
        units="m s-1",
    )
    ds["vsdy"].attrs.update(
        standard_name="sea_surface_wave_stokes_drift_y_velocity",
        units="m s-1",
    )
    ds["u10"].attrs.update(standard_name="eastward_wind", units="m s-1")
    ds["v10"].attrs.update(standard_name="northward_wind", units="m s-1")
    ds["swh"].attrs.update(standard_name="sea_surface_wave_significant_height", units="m")

    out_nc = sar_dir / "forcing_plast.nc"
    atomic_netcdf_write(ds, out_nc)
    return out_nc


def run_plast(date_dir: Path, sar_dir: Path, shp_path: Path) -> None:
    forcing_nc = sar_dir / "forcing_plast.nc"
    if not forcing_nc.exists():
        forcing_nc = build_plast_forcing(date_dir, sar_dir)

    reader = reader_netCDF_CF_generic.Reader(str(forcing_nc))
    model = PlastDrift(loglevel=20)
    model.set_config("general:use_auto_landmask", True)
    model.set_config("drift:use_tabularised_stokes_drift", False)
    model.set_config("seed:wind_drift_factor", WINDAGE)
    model.add_reader(reader)

    lons, lats = seeds_wgs84_from_shp(shp_path)
    if not lons:
        raise RuntimeError(f"No id==1 marine debris seeds found in {shp_path.name}")

    lons_e = np.repeat(lons, ENSEMBLE_N)
    lats_e = np.repeat(lats, ENSEMBLE_N)
    model.seed_elements(
        lon=lons_e.tolist(),
        lat=lats_e.tolist(),
        number=len(lons_e),
        time=pd.Timestamp(START_TIME0).to_pydatetime(),
        z=0.0,
        terminal_velocity=TERM_VEL,
    )

    if WINDAGE_STD > 0 and model.elements.lon.size > 0:
        model.elements.wind_drift_factor = (
            model.elements.wind_drift_factor
            + np.random.normal(0, WINDAGE_STD, size=model.elements.lon.size)
        )

    match = re.search(r"SAR_([+-]?\d+\.?\d*)h", sar_dir.name)
    if not match:
        raise ValueError(f"Bad SAR directory name: {sar_dir.name}")
    delta_h = float(match.group(1))
    end_time = (pd.Timestamp(START_TIME0) + pd.Timedelta(hours=delta_h)).to_pydatetime()
    step = timedelta(minutes=DT_MIN)
    time_step = step if delta_h >= 0 else -step

    model.run(end_time=end_time, time_step=time_step, export_variables=[])

    lon_all, lat_all = extract_final_lonlat(model)
    valid = np.isfinite(lon_all) & np.isfinite(lat_all)
    pred = gpd.GeoDataFrame(
        {"obj_id": np.arange(int(valid.sum()), dtype=int)},
        geometry=gpd.points_from_xy(lon_all[valid], lat_all[valid]),
        crs=4326,
    )
    pred.to_file(sar_dir / "predicted_points_plast.shp")

    ref = get_ref_grid(get_optical_ref(date_dir))
    to_scene = Transformer.from_crs(4326, ref.crs, always_xy=True)
    back_wgs = Transformer.from_crs(ref.crs, 4326, always_xy=True)

    means = []
    for i in range(len(lons)):
        seg_lon = lon_all[i * ENSEMBLE_N : (i + 1) * ENSEMBLE_N]
        seg_lat = lat_all[i * ENSEMBLE_N : (i + 1) * ENSEMBLE_N]
        means.append((float(np.nanmean(seg_lon)), float(np.nanmean(seg_lat))))

    boxes = []
    for lon_mean, lat_mean in means:
        if not (np.isfinite(lon_mean) and np.isfinite(lat_mean)):
            continue
        x, y = to_scene.transform(lon_mean, lat_mean)
        scene_box = box(x - BOX_HALF_M, y - BOX_HALF_M, x + BOX_HALF_M, y + BOX_HALF_M)
        xs, ys = zip(*list(scene_box.exterior.coords))
        box_lons, box_lats = back_wgs.transform(xs, ys)
        boxes.append(box(min(box_lons), min(box_lats), max(box_lons), max(box_lats)))

    boxes_gdf = gpd.GeoDataFrame(
        {"seed_id": np.arange(len(boxes), dtype=int)},
        geometry=boxes,
        crs=4326,
    )
    boxes_gdf.to_file(sar_dir / "search_boxes_1km_plast.shp")


def iter_date_dirs(drift_root: Path) -> list[Path]:
    return sorted(
        path
        for path in drift_root.iterdir()
        if path.is_dir() and re.match(r"\d{4}-\d{2}-\d{2}$", path.name)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run OpenDrift over Drift scenes.")
    parser.add_argument(
        "--drift-root",
        type=Path,
        default=SCRIPT_DIR,
        help="Root directory containing <YYYY-MM-DD> Drift scene folders.",
    )
    parser.add_argument(
        "--shp-root",
        type=Path,
        default=Path("/mnt/d/Masters/MARIDA/MARIDA/shapefiles"),
        help="Directory containing MARIDA seed shapefiles.",
    )
    parser.add_argument(
        "--dates",
        nargs="*",
        default=None,
        help="Optional subset of date directory names to process.",
    )
    parser.add_argument(
        "--include-existing",
        action="store_true",
        help="Re-run scenes even if predicted_points_plast.shp already exists.",
    )
    args = parser.parse_args()

    date_dirs = iter_date_dirs(args.drift_root)
    if args.dates:
        wanted = set(args.dates)
        date_dirs = [path for path in date_dirs if path.name in wanted]

    if not date_dirs:
        print("No matching date directories found.")
        return 1

    failures = []
    for date_dir in date_dirs:
        try:
            ref_tif = get_optical_ref(date_dir)
            tile, date_obj = parse_tile_date_from_optical(ref_tif)
            shp_path = find_matching_shapefile(args.shp_root, tile, date_obj)
            if shp_path is None:
                raise FileNotFoundError(f"No shapefile match for tile={tile} date={date_obj}")

            sar_dirs = sorted(path for path in date_dir.iterdir() if path.is_dir() and path.name.startswith("SAR_"))
            if not sar_dirs:
                raise FileNotFoundError(f"No SAR_* directory found in {date_dir}")

            print(f"\n[{date_dir.name}] tile={tile} shapefile={shp_path.name}")
            for sar_dir in sar_dirs:
                out_shp = sar_dir / "predicted_points_plast.shp"
                if out_shp.exists() and not args.include_existing:
                    print(f"  skip {sar_dir.name}: existing predicted_points_plast.shp")
                    continue
                print(f"  run  {sar_dir.name}")
                run_plast(date_dir, sar_dir, shp_path)
                print(f"  done {sar_dir.name}")
        except Exception as exc:
            failures.append((date_dir.name, str(exc)))
            print(f"  fail {date_dir.name}: {exc}")

    if failures:
        print("\nFailures:")
        for date_name, message in failures:
            print(f"- {date_name}: {message}")
        return 1

    print("\nAll requested scenes processed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
