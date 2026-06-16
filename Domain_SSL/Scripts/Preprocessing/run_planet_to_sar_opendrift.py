#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import xarray as xr
from pyproj import CRS, Transformer
from shapely import affinity
from shapely.geometry import box


def resolve_drift_tools_dir(script_path: Path | None = None) -> Path:
    resolved = script_path.resolve() if script_path is not None else Path(__file__).resolve()
    try:
        work_root = resolved.parents[3]
    except IndexError:
        work_root = resolved.parent
    candidates = [Path("/mnt/d/Masters/Drift"), work_root / "Drift"]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[-1]


DRIFT_TOOLS = resolve_drift_tools_dir()
if str(DRIFT_TOOLS) not in sys.path:
    sys.path.insert(0, str(DRIFT_TOOLS))

from run_opendrift_batch import PlastDrift, reader_netCDF_CF_generic  # noqa: E402


ENSEMBLE_N = 20
DT_MIN = 15
WINDAGE = 0.03
WINDAGE_STD = 0.01
TERM_VEL = 0.01
BOX_HALF_M = 500
MODEL_MAX_SPEED = 5.0
GRID_RES_DEG = 0.001
LAND_SIGMA0_THRESHOLD = 0.01


def utm_crs_for_lonlat(lon: float, lat: float) -> CRS:
    zone = int(np.floor((lon + 180.0) / 6.0)) + 1
    zone = min(max(zone, 1), 60)
    epsg = 32600 + zone if lat >= 0 else 32700 + zone
    return CRS.from_epsg(epsg)


@dataclass(frozen=True)
class WaterSnapper:
    lats: np.ndarray
    lons: np.ndarray
    land_mask: np.ndarray
    water_lons: np.ndarray
    water_lats: np.ndarray
    tree: object
    transformer: Transformer

    @classmethod
    def from_forcing(cls, forcing_nc: Path) -> "WaterSnapper":
        from scipy.spatial import cKDTree

        with xr.open_dataset(forcing_nc) as ds:
            if "land_binary_mask" not in ds:
                raise RuntimeError(f"{forcing_nc} does not contain land_binary_mask")
            lats = np.asarray(ds["latitude"].isel(x=0).values, dtype="float64")
            lons = np.asarray(ds["longitude"].isel(y=0).values, dtype="float64")
            land_mask = np.asarray(ds["land_binary_mask"].isel(time=0).values, dtype="float32") > 0.5

        lon2, lat2 = np.meshgrid(lons, lats)
        water = np.isfinite(land_mask) & ~land_mask
        water_lons = lon2[water].astype("float64")
        water_lats = lat2[water].astype("float64")
        if len(water_lons) == 0:
            raise RuntimeError(f"No water cells found in {forcing_nc}")
        utm_crs = utm_crs_for_lonlat(float(np.mean(water_lons)), float(np.mean(water_lats)))
        transformer = Transformer.from_crs(4326, utm_crs, always_xy=True)
        water_x, water_y = transformer.transform(water_lons, water_lats)
        tree = cKDTree(np.column_stack([water_x, water_y]))
        return cls(
            lats=lats,
            lons=lons,
            land_mask=land_mask,
            water_lons=water_lons,
            water_lats=water_lats,
            tree=tree,
            transformer=transformer,
        )

    def snap(self, lon: np.ndarray, lat: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, int]:
        snapped_lon = np.asarray(lon, dtype="float64").copy()
        snapped_lat = np.asarray(lat, dtype="float64").copy()
        snapped = np.zeros(len(snapped_lon), dtype=bool)
        distances = np.zeros(len(snapped_lon), dtype="float32")

        valid = np.isfinite(snapped_lon) & np.isfinite(snapped_lat)
        inside = (
            valid
            & (snapped_lon >= self.lons.min())
            & (snapped_lon <= self.lons.max())
            & (snapped_lat >= self.lats.min())
            & (snapped_lat <= self.lats.max())
        )
        outside_count = int(np.sum(valid & ~inside))
        if not np.any(inside):
            return snapped_lon, snapped_lat, snapped, distances, outside_count

        ix = np.rint((snapped_lon[inside] - self.lons[0]) / (self.lons[1] - self.lons[0])).astype(int)
        iy = np.rint((snapped_lat[inside] - self.lats[0]) / (self.lats[1] - self.lats[0])).astype(int)
        ix = np.clip(ix, 0, len(self.lons) - 1)
        iy = np.clip(iy, 0, len(self.lats) - 1)

        inside_indices = np.where(inside)[0]
        on_land = self.land_mask[iy, ix]
        if not np.any(on_land):
            return snapped_lon, snapped_lat, snapped, distances, outside_count

        land_indices = inside_indices[on_land]
        px, py = self.transformer.transform(snapped_lon[land_indices], snapped_lat[land_indices])
        dist, water_index = self.tree.query(np.column_stack([px, py]))
        snapped_lon[land_indices] = self.water_lons[water_index]
        snapped_lat[land_indices] = self.water_lats[water_index]
        snapped[land_indices] = True
        distances[land_indices] = dist.astype("float32")
        return snapped_lon, snapped_lat, snapped, distances, outside_count


def utc(value: str) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def naive_datetime(ts: pd.Timestamp):
    return ts.tz_convert("UTC").tz_localize(None).to_pydatetime()


def coord_name(ds: xr.Dataset | xr.DataArray, candidates: tuple[str, ...]) -> str:
    for name in candidates:
        if name in ds.coords or name in ds.dims:
            return name
    raise KeyError(f"Missing one of {candidates}")


def time_name(ds: xr.Dataset | xr.DataArray) -> str:
    return coord_name(ds, ("time", "valid_time"))


def var(ds: xr.Dataset, names: tuple[str, ...]) -> xr.DataArray:
    for name in names:
        if name in ds:
            return ds[name]
    raise KeyError(f"Missing one of {names}")


def first_depth(da: xr.DataArray) -> xr.DataArray:
    for name in ("depth", "elevation"):
        if name in da.dims:
            return da.isel({name: 0})
    return da


def sorted_latlon(da: xr.DataArray) -> xr.DataArray:
    y = coord_name(da, ("latitude", "lat"))
    x = coord_name(da, ("longitude", "lon"))
    if da[y].size > 1 and float(da[y][0]) > float(da[y][-1]):
        da = da.sortby(y)
    if da[x].size > 1 and float(da[x][0]) > float(da[x][-1]):
        da = da.sortby(x)
    return da


def at_time(da: xr.DataArray, when: pd.Timestamp) -> xr.DataArray:
    tname = time_name(da)
    return da.sel({tname: np.datetime64(when.tz_convert("UTC").tz_localize(None))}, method="nearest")


def interp_to_grid(da: xr.DataArray, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    da = sorted_latlon(da)
    y = coord_name(da, ("latitude", "lat"))
    x = coord_name(da, ("longitude", "lon"))
    linear = da.interp({y: lats, x: lons}, method="linear")
    nearest = da.interp({y: lats, x: lons}, method="nearest")
    filled = linear.where(np.isfinite(linear), nearest)
    return np.asarray(filled.values, dtype="float32")


def wind_array(wind_ds: xr.Dataset | None, name: tuple[str, ...], when: pd.Timestamp, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    if wind_ds is None:
        return np.zeros((len(lats), len(lons)), dtype="float32")
    da = at_time(var(wind_ds, name), when)
    return interp_to_grid(da, lats, lons)


def regular_axis(start: float, stop: float, step: float) -> np.ndarray:
    count = int(np.floor((stop - start) / step)) + 1
    return np.round(start + np.arange(count, dtype="float64") * step, 6)


def forcing_paths(forcing_dir: Path) -> tuple[Path, Path, Path | None]:
    currents = sorted(forcing_dir.glob("cmems_currents_*.nc"))
    waves = sorted(forcing_dir.glob("cmems_waves_*.nc"))
    wind = sorted(forcing_dir.glob("era5_wind_*.nc"))
    if not currents or not waves:
        raise FileNotFoundError(f"Expected cmems_currents_*.nc and cmems_waves_*.nc under {forcing_dir}")
    return currents[-1], waves[-1], wind[-1] if wind else None


def grid_bounds(seeds: gpd.GeoDataFrame, raster: Path | None, pad_deg: float) -> tuple[float, float, float, float]:
    west, south, east, north = seeds.to_crs(4326).total_bounds
    if raster is not None:
        with rasterio.open(raster) as src:
            if src.crs and src.crs.to_epsg() == 4326:
                rb = src.bounds
                west = min(west, rb.left)
                south = min(south, rb.bottom)
                east = max(east, rb.right)
                north = max(north, rb.top)
    return west - pad_deg, south - pad_deg, east + pad_deg, north + pad_deg


def build_sar_land_mask(mask_raster: Path, lats: np.ndarray, lons: np.ndarray) -> tuple[np.ndarray, dict[str, object]]:
    lon2, lat2 = np.meshgrid(lons, lats)
    values = np.full(lon2.shape, np.nan, dtype="float32")
    with rasterio.open(mask_raster) as src:
        if src.crs and src.crs.to_epsg() != 4326:
            raise ValueError(f"Expected EPSG:4326 SAR mask raster, got {src.crs}")
        bounds = src.bounds
        inside = (lon2 >= bounds.left) & (lon2 <= bounds.right) & (lat2 >= bounds.bottom) & (lat2 <= bounds.top)
        flat_inside = inside.ravel()
        coords = zip(lon2.ravel()[flat_inside], lat2.ravel()[flat_inside])
        sampled = np.asarray([sample[0] for sample in src.sample(coords, indexes=1)], dtype="float32")
        values.ravel()[flat_inside] = sampled
    mask = np.isfinite(values) & (values > LAND_SIGMA0_THRESHOLD)
    return mask.astype("float32"), {
        "mask_source": str(mask_raster),
        "sigma0_land_threshold": LAND_SIGMA0_THRESHOLD,
        "grid_cells_in_sar_raster": int(np.isfinite(values).sum()),
        "land_cells": int(mask.sum()),
        "land_fraction": float(mask.mean()),
    }


def opendrift_landmask_backend() -> tuple[object | None, dict[str, object]]:
    info: dict[str, object] = {"name": "opendrift_global_landmask"}
    try:
        roaring_spec = importlib.util.find_spec("roaring_landmask")
        cartopy_spec = importlib.util.find_spec("cartopy")
    except ValueError:
        roaring_spec = None
        cartopy_spec = None
    if roaring_spec is None or cartopy_spec is None:
        info.update(available=False, reason="roaring_landmask or cartopy is not installed")
        return None, info
    try:
        from opendrift.readers import reader_global_landmask
    except Exception as exc:
        info.update(available=False, reason=f"reader import failed: {exc}")
        return None, info
    info["available"] = True
    return reader_global_landmask.Reader(), info


def build_forcing_nc(
    forcing_dir: Path,
    out_nc: Path,
    times: list[pd.Timestamp],
    bounds: tuple[float, float, float, float],
    mask_raster: Path | None,
) -> tuple[Path, dict[str, object]]:
    current_path, wave_path, wind_path = forcing_paths(forcing_dir)
    current = xr.open_dataset(current_path)
    waves = xr.open_dataset(wave_path)
    wind = xr.open_dataset(wind_path) if wind_path is not None else None
    west, south, east, north = bounds
    lats = regular_axis(south, north, GRID_RES_DEG)
    lons = regular_axis(west, east, GRID_RES_DEG)
    lon2, lat2 = np.meshgrid(lons, lats)
    arrays = {key: [] for key in ("uo", "vo", "vsdx", "vsdy", "u10", "v10", "swh")}
    mask_stats: dict[str, object] = {
        "mask_source": None,
        "grid_west": float(lons.min()),
        "grid_east": float(lons.max()),
        "grid_south": float(lats.min()),
        "grid_north": float(lats.max()),
        "grid_res_deg": GRID_RES_DEG,
        "grid_shape_yx": [int(len(lats)), int(len(lons))],
    }
    if mask_raster is not None:
        land_mask, mask_stats = build_sar_land_mask(mask_raster, lats, lons)
    else:
        land_mask = np.zeros((len(lats), len(lons)), dtype="float32")
        mask_stats["mask_source"] = "none_all_water"
    arrays["land_binary_mask"] = []
    for when in times:
        arrays["uo"].append(interp_to_grid(at_time(first_depth(var(current, ("uo",))), when), lats, lons))
        arrays["vo"].append(interp_to_grid(at_time(first_depth(var(current, ("vo",))), when), lats, lons))
        arrays["vsdx"].append(interp_to_grid(at_time(var(waves, ("VSDX", "vsdx")), when), lats, lons))
        arrays["vsdy"].append(interp_to_grid(at_time(var(waves, ("VSDY", "vsdy")), when), lats, lons))
        arrays["swh"].append(interp_to_grid(at_time(var(waves, ("VHM0", "swh")), when), lats, lons))
        arrays["u10"].append(wind_array(wind, ("u10", "10m_u_component_of_wind"), when, lats, lons))
        arrays["v10"].append(wind_array(wind, ("v10", "10m_v_component_of_wind"), when, lats, lons))
        arrays["land_binary_mask"].append(land_mask)
    ds = xr.Dataset(
        coords={
            "time": ("time", np.array([t.tz_convert("UTC").tz_localize(None).to_datetime64() for t in times], dtype="datetime64[ns]")),
            "y": ("y", np.arange(len(lats), dtype=np.int32)),
            "x": ("x", np.arange(len(lons), dtype=np.int32)),
            "latitude": (("y", "x"), lat2.astype("float32")),
            "longitude": (("y", "x"), lon2.astype("float32")),
        },
        data_vars={name: (("time", "y", "x"), np.stack(values).astype("float32")) for name, values in arrays.items()},
    )
    attrs = {
        "uo": ("eastward_sea_water_velocity", "m s-1"),
        "vo": ("northward_sea_water_velocity", "m s-1"),
        "vsdx": ("sea_surface_wave_stokes_drift_x_velocity", "m s-1"),
        "vsdy": ("sea_surface_wave_stokes_drift_y_velocity", "m s-1"),
        "u10": ("eastward_wind", "m s-1"),
        "v10": ("northward_wind", "m s-1"),
        "swh": ("sea_surface_wave_significant_height", "m"),
        "land_binary_mask": ("land_binary_mask", "1"),
    }
    for name, (standard_name, units) in attrs.items():
        if name in ds:
            ds[name].attrs.update(standard_name=standard_name, units=units)
    tmp = out_nc.with_suffix(out_nc.suffix + f".tmp.{int(time.time())}")
    ds.to_netcdf(tmp, mode="w", engine="netcdf4")
    ds.close()
    tmp.replace(out_nc)
    return out_nc, mask_stats


def representative(geom):
    if geom.geom_type == "Point":
        return geom
    if geom.geom_type in ("Polygon", "MultiPolygon"):
        return geom.representative_point()
    return geom.centroid


def translate_geometry(geom, src_lon: float, src_lat: float, dst_lon: float, dst_lat: float, utm_crs: CRS):
    src_pt = gpd.GeoSeries(gpd.points_from_xy([src_lon], [src_lat]), crs=4326).to_crs(utm_crs).iloc[0]
    dst_pt = gpd.GeoSeries(gpd.points_from_xy([dst_lon], [dst_lat]), crs=4326).to_crs(utm_crs).iloc[0]
    projected = gpd.GeoSeries([geom], crs=4326).to_crs(utm_crs).iloc[0]
    moved = affinity.translate(projected, xoff=dst_pt.x - src_pt.x, yoff=dst_pt.y - src_pt.y)
    return gpd.GeoSeries([moved], crs=utm_crs).to_crs(4326).iloc[0], dst_pt.x - src_pt.x, dst_pt.y - src_pt.y


def extract_lonlat(model: PlastDrift) -> tuple[np.ndarray, np.ndarray]:
    try:
        lon = np.asarray(model.result["lon"].isel(time=-1).values).ravel()
        lat = np.asarray(model.result["lat"].isel(time=-1).values).ravel()
    except Exception:
        lon = np.asarray(model.get_property("lon")[-1]).ravel()
        lat = np.asarray(model.get_property("lat")[-1]).ravel()
    return lon, lat


def main() -> int:
    parser = argparse.ArgumentParser(description="Run OpenDrift PlastDrift from Planet seeds to a SAR acquisition time.")
    parser.add_argument("--seeds", type=Path, required=True)
    parser.add_argument("--planet-time", required=True)
    parser.add_argument("--target-time", required=True)
    parser.add_argument("--forcing-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--target-raster", type=Path)
    parser.add_argument("--landmask-source", choices=("opendrift", "sar", "none"), default="none")
    parser.add_argument("--ensemble", type=int, default=ENSEMBLE_N)
    parser.add_argument("--dt-min", type=int, default=DT_MIN)
    parser.add_argument("--grid-pad-deg", type=float, default=0.12)
    args = parser.parse_args()

    planet_time = utc(args.planet_time)
    target_time = utc(args.target_time)
    delta_hours = (target_time - planet_time).total_seconds() / 3600.0
    args.out_dir.mkdir(parents=True, exist_ok=True)

    seeds = gpd.read_file(args.seeds)
    if seeds.crs is None:
        seeds = seeds.set_crs(4326)
    seeds = seeds.to_crs(4326)
    bounds = grid_bounds(seeds, args.target_raster, args.grid_pad_deg)
    start_time = min(planet_time, target_time)
    end_time = max(planet_time, target_time)
    forcing_times = sorted([start_time - pd.Timedelta(hours=1), start_time, end_time, end_time + pd.Timedelta(hours=1)])
    include_sar_landmask = args.landmask_source == "sar"
    forcing_nc, mask_stats = build_forcing_nc(
        args.forcing_dir,
        args.out_dir / "forcing_opendrift.nc",
        forcing_times,
        bounds,
        args.target_raster if include_sar_landmask else None,
    )

    reps = [representative(geom) for geom in seeds.geometry]
    seed_lon = np.asarray([pt.x for pt in reps], dtype="float64")
    seed_lat = np.asarray([pt.y for pt in reps], dtype="float64")
    run_utm_crs = utm_crs_for_lonlat(float(seed_lon.mean()), float(seed_lat.mean()))

    model = PlastDrift(loglevel=20)
    model.set_config("general:use_auto_landmask", False)
    model.set_config("general:coastline_action", "previous")
    model.set_config("drift:max_speed", MODEL_MAX_SPEED)
    model.set_config("drift:use_tabularised_stokes_drift", False)
    model.set_config("seed:wind_drift_factor", WINDAGE)
    model.add_reader(reader_netCDF_CF_generic.Reader(str(forcing_nc)))
    landmask_backend: dict[str, object] = {"name": args.landmask_source, "available": True}
    if args.landmask_source == "opendrift":
        reader, landmask_backend = opendrift_landmask_backend()
        if reader is None:
            raise RuntimeError(f"OpenDrift global landmask unavailable: {landmask_backend.get('reason')}")
        model.add_reader(reader)

    lons = np.repeat(seed_lon, args.ensemble)
    lats = np.repeat(seed_lat, args.ensemble)
    model.seed_elements(
        lon=lons.tolist(),
        lat=lats.tolist(),
        number=len(lons),
        time=naive_datetime(planet_time),
        z=0.0,
        terminal_velocity=TERM_VEL,
    )
    if WINDAGE_STD > 0 and model.elements.lon.size > 0:
        np.random.seed(42)
        model.elements.wind_drift_factor = model.elements.wind_drift_factor + np.random.normal(0, WINDAGE_STD, size=model.elements.lon.size)

    delta_seconds = (target_time - planet_time).total_seconds()
    steps = max(1, int(np.ceil(abs(delta_seconds) / (args.dt_min * 60.0))))
    step = timedelta(seconds=delta_seconds / steps)
    model.run(steps=steps, time_step=step, export_variables=[], stop_on_error=True)

    lon_final, lat_final = extract_lonlat(model)
    if include_sar_landmask:
        snapper = WaterSnapper.from_forcing(forcing_nc)
        lon_final, lat_final, snapped_to_water, snap_m, outside_grid = snapper.snap(lon_final, lat_final)
    else:
        snapped_to_water = np.zeros(len(lon_final), dtype=bool)
        snap_m = np.zeros(len(lon_final), dtype="float32")
        outside_grid = 0
    valid = np.isfinite(lon_final) & np.isfinite(lat_final)
    points = gpd.GeoDataFrame(
        {
            "particle": np.arange(len(lon_final), dtype=int),
            "seed_idx": np.repeat(np.arange(len(seeds), dtype=int), args.ensemble)[: len(lon_final)],
            "valid": valid,
            "snap_water": snapped_to_water,
            "snap_m": snap_m,
        },
        geometry=gpd.points_from_xy(lon_final, lat_final),
        crs=4326,
    )
    points = points[valid].copy()
    points_path = args.out_dir / "predicted_particle_points.geojson"
    points.to_file(points_path, driver="GeoJSON")

    rows = []
    moved_geoms = []
    boxes = []
    for i, geom in enumerate(seeds.geometry):
        seg = points[points["seed_idx"] == i]
        if seg.empty:
            continue
        dst_lon = float(seg.geometry.x.mean())
        dst_lat = float(seg.geometry.y.mean())
        if include_sar_landmask:
            mean_lon, mean_lat, mean_snapped, mean_snap_m, mean_outside_grid = snapper.snap(
                np.asarray([dst_lon], dtype="float64"),
                np.asarray([dst_lat], dtype="float64"),
            )
            dst_lon = float(mean_lon[0])
            dst_lat = float(mean_lat[0])
            mean_snap = bool(mean_snapped[0])
            mean_snap_dist = float(mean_snap_m[0])
            mean_outside = int(mean_outside_grid)
        else:
            mean_snap = False
            mean_snap_dist = 0.0
            mean_outside = 0
        moved, dx_m, dy_m = translate_geometry(geom, seed_lon[i], seed_lat[i], dst_lon, dst_lat, run_utm_crs)
        moved_geoms.append(moved)
        rows.append(
            {
                "seed_idx": i,
                "source_id": int(seeds.iloc[i].get("rand_point_id", i)) if pd.notna(seeds.iloc[i].get("rand_point_id", i)) else i,
                "delta_h": delta_hours,
                "mean_lon": dst_lon,
                "mean_lat": dst_lat,
                "dx_m": dx_m,
                "dy_m": dy_m,
                "n_particles": int(len(seg)),
                "snap_water": mean_snap,
                "snap_m": mean_snap_dist,
                "outside_grid": mean_outside,
            }
        )
        dst_projected = gpd.GeoSeries(gpd.points_from_xy([dst_lon], [dst_lat]), crs=4326).to_crs(run_utm_crs).iloc[0]
        search_box = box(dst_projected.x - BOX_HALF_M, dst_projected.y - BOX_HALF_M, dst_projected.x + BOX_HALF_M, dst_projected.y + BOX_HALF_M)
        boxes.append(gpd.GeoSeries([search_box], crs=run_utm_crs).to_crs(4326).iloc[0])

    predicted = gpd.GeoDataFrame(rows, geometry=moved_geoms, crs=4326)
    boxes_gdf = gpd.GeoDataFrame([{"seed_idx": row["seed_idx"], "delta_h": delta_hours} for row in rows], geometry=boxes, crs=4326)
    pred_geojson = args.out_dir / "predicted_seed_polygons.geojson"
    pred_shp = args.out_dir / "predicted_seed_polygons.shp"
    boxes_geojson = args.out_dir / "search_boxes_1km.geojson"
    predicted.to_file(pred_geojson, driver="GeoJSON")
    predicted.to_file(pred_shp)
    boxes_gdf.to_file(boxes_geojson, driver="GeoJSON")

    manifest = {
        "planet_time_utc": planet_time.isoformat(),
        "target_time_utc": target_time.isoformat(),
        "delta_hours_target_minus_planet": delta_hours,
        "model": "OpenDrift PlastDrift with CMEMS surface currents, CMEMS Stokes drift, ERA5 wind, 3% windage.",
        "seeds": str(args.seeds),
        "target_raster": str(args.target_raster) if args.target_raster else None,
        "forcing_dir": str(args.forcing_dir),
        "forcing_opendrift": str(forcing_nc),
        "grid_bounds_wsen": [float(v) for v in bounds],
        "landmask_source": args.landmask_source,
        "landmask_backend": landmask_backend,
        "land_mask": mask_stats,
        "coastline_action": model.get_config("general:coastline_action"),
        "particle_snap_to_water": {
            "snapped_count": int(snapped_to_water.sum()),
            "outside_grid_count": outside_grid,
            "mean_snap_m": float(snap_m[snapped_to_water].mean()) if np.any(snapped_to_water) else 0.0,
            "max_snap_m": float(snap_m[snapped_to_water].max()) if np.any(snapped_to_water) else 0.0,
        },
        "ensemble_per_seed": args.ensemble,
        "requested_time_step_minutes": args.dt_min,
        "actual_time_step_seconds": step.total_seconds(),
        "steps": steps,
        "windage": WINDAGE,
        "windage_std": WINDAGE_STD,
        "terminal_velocity_ms": TERM_VEL,
        "mean_dx_m": float(predicted["dx_m"].mean()),
        "mean_dy_m": float(predicted["dy_m"].mean()),
        "outputs": {
            "predicted_particle_points": str(points_path),
            "predicted_seed_polygons_geojson": str(pred_geojson),
            "predicted_seed_polygons_shp": str(pred_shp),
            "search_boxes_1km": str(boxes_geojson),
        },
    }
    (args.out_dir / "opendrift_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
