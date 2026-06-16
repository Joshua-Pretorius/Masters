#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr
from pyproj import CRS
from shapely import affinity
from shapely.geometry import LineString


PLANET_META = Path("/mnt/d/Masters/MERIA/MERIA_Planet/20181031_095925_103b_ortho_analytic_4b_sr_metadata.json")
DEFAULT_SEEDS = Path("/mnt/d/Masters/Domain_SSL/PreProccess/aoi_accra_2018_10_30/AccraSeedsPlanet.shp")
DEFAULT_FORCING = Path("/mnt/d/Masters/Domain_SSL/PreProccess/aoi_accra_2018_10_30/drift/forcing")
DEFAULT_OUT = Path("/mnt/d/Masters/Domain_SSL/PreProccess/aoi_accra_2018_10_30/drift")
WINDAGE = 0.03
UTM_CRS = CRS.from_epsg(32630)


@dataclass(frozen=True)
class Scenario:
    name: str
    target_time: pd.Timestamp
    note: str


def utc_timestamp(value: str) -> pd.Timestamp:
    return pd.Timestamp(value).tz_convert("UTC") if pd.Timestamp(value).tzinfo else pd.Timestamp(value, tz="UTC")


def naive_utc(value: pd.Timestamp) -> pd.Timestamp:
    return value.tz_convert("UTC").tz_localize(None)


def load_times() -> tuple[pd.Timestamp, list[Scenario]]:
    data = json.loads(PLANET_META.read_text(encoding="utf-8"))
    planet_time = utc_timestamp(data["planet_match"]["acquired"])
    meria_time = utc_timestamp(data["selected_patch"]["timestamp"])
    actual_safe_time = utc_timestamp("2018-10-30T18:17:58Z")
    return planet_time, [
        Scenario(
            name="actual_safe_sar_20181030T181758",
            target_time=actual_safe_time,
            note="Actual Sentinel-1 SAFE filename start time; backward drift from Planet.",
        ),
        Scenario(
            name="meria_label_sar_20181031T181758",
            target_time=meria_time,
            note="MERIA/OceanScan selected patch timestamp; forward drift from Planet.",
        ),
    ]


def coord_name(ds: xr.Dataset | xr.DataArray, candidates: tuple[str, ...]) -> str:
    for candidate in candidates:
        if candidate in ds.coords or candidate in ds.dims:
            return candidate
    raise KeyError(f"None of {candidates} found in {list(ds.coords)} / {list(ds.dims)}")


def time_name(ds: xr.Dataset | xr.DataArray) -> str:
    return coord_name(ds, ("time", "valid_time"))


def var(ds: xr.Dataset, names: tuple[str, ...]) -> xr.DataArray:
    for name in names:
        if name in ds:
            return ds[name]
    raise KeyError(f"None of {names} found in {list(ds.data_vars)}")


def sample_var(da: xr.DataArray, lon: float, lat: float, when: pd.Timestamp) -> float:
    work = da
    for zname in ("depth", "elevation"):
        if zname in work.dims:
            work = work.isel({zname: 0})
    tname = time_name(work)
    xname = coord_name(work, ("longitude", "lon"))
    yname = coord_name(work, ("latitude", "lat"))

    x = lon
    xcoord = work[xname]
    if float(xcoord.min()) >= 0 and x < 0:
        x += 360.0

    selected = work.sel(
        {
            tname: np.datetime64(naive_utc(when)),
            xname: x,
            yname: lat,
        },
        method="nearest",
    )
    return float(np.asarray(selected.values).squeeze())


def mean_pair(start: float, end: float) -> float:
    values = np.asarray([start, end], dtype="float64")
    if np.isfinite(values).any():
        return float(np.nanmean(values))
    return 0.0


def feature_point(geom):
    if geom.geom_type == "Point":
        return geom
    if geom.geom_type in ("Polygon", "MultiPolygon"):
        return geom.representative_point()
    return geom.centroid


def translate_wgs84(geom, dx_m: float, dy_m: float):
    projected = gpd.GeoSeries([geom], crs=4326).to_crs(UTM_CRS).iloc[0]
    moved = affinity.translate(projected, xoff=dx_m, yoff=dy_m)
    return gpd.GeoSeries([moved], crs=UTM_CRS).to_crs(4326).iloc[0]


def load_forcing(forcing_dir: Path) -> dict[str, xr.Dataset | None]:
    paths = {
        "currents": forcing_dir / "cmems_currents_20181030_20181031.nc",
        "waves": forcing_dir / "cmems_waves_20181030_20181031.nc",
        "wind": forcing_dir / "era5_wind_20181030_20181031.nc",
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing[:2]:
        raise FileNotFoundError(f"Missing required CMEMS forcing files: {missing}")
    return {
        "currents": xr.open_dataset(paths["currents"]),
        "waves": xr.open_dataset(paths["waves"]),
        "wind": xr.open_dataset(paths["wind"]) if paths["wind"].exists() else None,
    }


def sample_forcing(datasets: dict[str, xr.Dataset | None], lon: float, lat: float, start: pd.Timestamp, end: pd.Timestamp) -> dict[str, float | str]:
    currents = datasets["currents"]
    waves = datasets["waves"]
    wind = datasets["wind"]
    assert currents is not None
    assert waves is not None

    uo = mean_pair(
        sample_var(var(currents, ("uo",)), lon, lat, start),
        sample_var(var(currents, ("uo",)), lon, lat, end),
    )
    vo = mean_pair(
        sample_var(var(currents, ("vo",)), lon, lat, start),
        sample_var(var(currents, ("vo",)), lon, lat, end),
    )
    vsdx = mean_pair(
        sample_var(var(waves, ("VSDX", "vsdx")), lon, lat, start),
        sample_var(var(waves, ("VSDX", "vsdx")), lon, lat, end),
    )
    vsdy = mean_pair(
        sample_var(var(waves, ("VSDY", "vsdy")), lon, lat, start),
        sample_var(var(waves, ("VSDY", "vsdy")), lon, lat, end),
    )

    if wind is None:
        u10 = 0.0
        v10 = 0.0
        wind_source = "missing_zeroed"
    else:
        u10 = mean_pair(
            sample_var(var(wind, ("u10", "10m_u_component_of_wind")), lon, lat, start),
            sample_var(var(wind, ("u10", "10m_u_component_of_wind")), lon, lat, end),
        )
        v10 = mean_pair(
            sample_var(var(wind, ("v10", "10m_v_component_of_wind")), lon, lat, start),
            sample_var(var(wind, ("v10", "10m_v_component_of_wind")), lon, lat, end),
        )
        wind_source = "era5"

    u_total = uo + vsdx + WINDAGE * u10
    v_total = vo + vsdy + WINDAGE * v10
    return {
        "uo_ms": uo,
        "vo_ms": vo,
        "vsdx_ms": vsdx,
        "vsdy_ms": vsdy,
        "u10_ms": u10,
        "v10_ms": v10,
        "u_total_ms": u_total,
        "v_total_ms": v_total,
        "speed_ms": float(np.hypot(u_total, v_total)),
        "wind_source": wind_source,
    }


def run_scenario(gdf: gpd.GeoDataFrame, datasets: dict[str, xr.Dataset | None], out_root: Path, planet_time: pd.Timestamp, scenario: Scenario) -> dict[str, object]:
    delta_seconds = float((scenario.target_time - planet_time).total_seconds())
    delta_hours = delta_seconds / 3600.0
    out_dir = out_root / scenario.name
    out_dir.mkdir(parents=True, exist_ok=True)

    source = gdf.to_crs(4326).copy()
    predicted_geoms = []
    vector_rows = []
    attrs = []

    for idx, row in source.iterrows():
        rep = feature_point(row.geometry)
        forcing = sample_forcing(datasets, rep.x, rep.y, planet_time, scenario.target_time)
        dx_m = float(forcing["u_total_ms"]) * delta_seconds
        dy_m = float(forcing["v_total_ms"]) * delta_seconds
        moved = translate_wgs84(row.geometry, dx_m, dy_m)
        predicted_geoms.append(moved)
        moved_rep = feature_point(moved)
        vector_rows.append(
            {
                "seed_idx": int(idx),
                "delta_h": delta_hours,
                "dx_m": dx_m,
                "dy_m": dy_m,
                **forcing,
                "geometry": LineString([(rep.x, rep.y), (moved_rep.x, moved_rep.y)]),
            }
        )
        attrs.append(
            {
                "seed_idx": int(idx),
                "delta_h": delta_hours,
                "dx_m": dx_m,
                "dy_m": dy_m,
                **forcing,
            }
        )

    predicted = gpd.GeoDataFrame(attrs, geometry=predicted_geoms, crs=4326)
    vectors = gpd.GeoDataFrame(vector_rows, crs=4326)

    pred_geojson = out_dir / "predicted_seed_polygons.geojson"
    vec_geojson = out_dir / "drift_vectors.geojson"
    pred_shp = out_dir / "predicted_seed_polygons.shp"
    predicted.to_file(pred_geojson, driver="GeoJSON")
    vectors.to_file(vec_geojson, driver="GeoJSON")
    predicted.to_file(pred_shp)

    manifest = {
        "scenario": scenario.name,
        "note": scenario.note,
        "planet_time_utc": planet_time.isoformat(),
        "target_time_utc": scenario.target_time.isoformat(),
        "delta_hours_target_minus_planet": delta_hours,
        "windage": WINDAGE,
        "model": "Endpoint-averaged surface current + Stokes drift + 3% ERA5 windage, applied as UTM translation per seed polygon.",
        "outputs": {
            "predicted_seed_polygons_geojson": str(pred_geojson),
            "predicted_seed_polygons_shp": str(pred_shp),
            "drift_vectors_geojson": str(vec_geojson),
        },
        "mean_dx_m": float(np.nanmean(predicted["dx_m"])),
        "mean_dy_m": float(np.nanmean(predicted["dy_m"])),
        "mean_speed_ms": float(np.nanmean(predicted["speed_ms"])),
    }
    manifest_path = out_dir / "drift_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Predict Accra Planet seed polygon drift to SAR-time locations.")
    parser.add_argument("--seeds", type=Path, default=DEFAULT_SEEDS)
    parser.add_argument("--forcing-dir", type=Path, default=DEFAULT_FORCING)
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    gdf = gpd.read_file(args.seeds)
    if gdf.crs is None:
        gdf = gdf.set_crs(4326)
    datasets = load_forcing(args.forcing_dir)
    planet_time, scenarios = load_times()

    manifests = []
    for scenario in scenarios:
        manifests.append(run_scenario(gdf, datasets, args.out_root, planet_time, scenario))

    summary_path = args.out_root / "drift_summary.json"
    summary_path.write_text(json.dumps({"scenarios": manifests}, indent=2), encoding="utf-8")
    print(f"Wrote drift outputs under {args.out_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
