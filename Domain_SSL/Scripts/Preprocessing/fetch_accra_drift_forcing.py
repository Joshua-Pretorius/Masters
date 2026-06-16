#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


CURR_DS = "cmems_mod_glo_phy_my_0.083deg_P1D-m"
WAVE_DS = "cmems_mod_glo_wav_my_0.2deg_PT3H-i"
SURFACE_DEPTH_M = 0.49402499198913574


def parse_cdsapirc(path: Path) -> tuple[str | None, str | None]:
    if not path.exists():
        return None, None
    url = None
    key = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        name, value = line.split(":", 1)
        if name.strip() == "url":
            url = value.strip()
        elif name.strip() == "key":
            key = value.strip()
    return url, key


def fetch_cmems(out_dir: Path, bounds: tuple[float, float, float, float]) -> None:
    import copernicusmarine

    west, south, east, north = bounds
    credentials = Path("/mnt/c/Users/Joshua Pretorius/.copernicusmarine/.copernicusmarine-credentials")

    current_out = out_dir / "cmems_currents_20181030_20181031.nc"
    wave_out = out_dir / "cmems_waves_20181030_20181031.nc"

    if not current_out.exists():
        copernicusmarine.subset(
            dataset_id=CURR_DS,
            variables=["uo", "vo"],
            minimum_longitude=west,
            maximum_longitude=east,
            minimum_latitude=south,
            maximum_latitude=north,
            minimum_depth=SURFACE_DEPTH_M,
            maximum_depth=SURFACE_DEPTH_M,
            start_datetime="2018-10-30T00:00:00",
            end_datetime="2018-10-31T23:59:00",
            output_directory=out_dir,
            output_filename=current_out.name,
            file_format="netcdf",
            credentials_file=credentials,
            overwrite=True,
            disable_progress_bar=True,
            coordinates_selection_method="nearest",
        )

    if not wave_out.exists():
        copernicusmarine.subset(
            dataset_id=WAVE_DS,
            variables=["VSDX", "VSDY", "VHM0"],
            minimum_longitude=west,
            maximum_longitude=east,
            minimum_latitude=south,
            maximum_latitude=north,
            start_datetime="2018-10-30T00:00:00",
            end_datetime="2018-10-31T23:59:00",
            output_directory=out_dir,
            output_filename=wave_out.name,
            file_format="netcdf",
            credentials_file=credentials,
            overwrite=True,
            disable_progress_bar=True,
            coordinates_selection_method="nearest",
        )


def fetch_era5(out_dir: Path, bounds: tuple[float, float, float, float]) -> None:
    import cdsapi

    west, south, east, north = bounds
    out_nc = out_dir / "era5_wind_20181030_20181031.nc"
    if out_nc.exists():
        return

    url, key = parse_cdsapirc(Path("/mnt/c/Users/Joshua Pretorius/.cdsapirc"))
    client = cdsapi.Client(url=url, key=key, quiet=False)
    request = {
        "product_type": "reanalysis",
        "variable": [
            "10m_u_component_of_wind",
            "10m_v_component_of_wind",
        ],
        "year": "2018",
        "month": "10",
        "day": ["30", "31"],
        "time": ["09:00", "10:00", "18:00"],
        "area": [north, west, south, east],
        "data_format": "netcdf",
        "download_format": "unarchived",
    }
    try:
        client.retrieve("reanalysis-era5-single-levels", request, str(out_nc))
    except Exception:
        fallback = dict(request)
        fallback.pop("data_format", None)
        fallback.pop("download_format", None)
        fallback["format"] = "netcdf"
        client.retrieve("reanalysis-era5-single-levels", fallback, str(out_nc))


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Accra drift forcing for Planet-to-SAR prediction.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("/mnt/d/Masters/Domain_SSL/PreProccess/aoi_accra_2018_10_30/drift/forcing"),
    )
    parser.add_argument("--west", type=float, default=-0.70)
    parser.add_argument("--south", type=float, default=5.20)
    parser.add_argument("--east", type=float, default=0.20)
    parser.add_argument("--north", type=float, default=5.85)
    parser.add_argument("--skip-era5", action="store_true")
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    bounds = (args.west, args.south, args.east, args.north)
    fetch_cmems(args.out_dir, bounds)
    if not args.skip_era5:
        fetch_era5(args.out_dir, bounds)
    print(f"Wrote forcing files under {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
