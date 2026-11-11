#!/usr/bin/env python3
from __future__ import annotations

import argparse
import calendar
import os
from tempfile import TemporaryDirectory
from datetime import date, timedelta
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


def ymd(value: str) -> tuple[str, str, str]:
    year, month, day = value.split("-")
    return year, month, day


def month_chunks(start_date: str, end_date: str) -> list[tuple[date, date]]:
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    if end < start:
        raise ValueError("end date must not be before start date")
    chunks: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        last_day = calendar.monthrange(cursor.year, cursor.month)[1]
        chunk_end = min(date(cursor.year, cursor.month, last_day), end)
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return chunks


def fetch_cmems(args: argparse.Namespace) -> None:
    import copernicusmarine

    credentials = Path(args.cmems_credentials).expanduser()
    current_out = args.out_dir / f"cmems_currents_{args.start_date.replace('-', '')}_{args.end_date.replace('-', '')}.nc"
    wave_out = args.out_dir / f"cmems_waves_{args.start_date.replace('-', '')}_{args.end_date.replace('-', '')}.nc"
    start_datetime = f"{args.start_date}T00:00:00"
    end_datetime = f"{args.end_date}T23:59:00"

    if not current_out.exists() or args.overwrite:
        with TemporaryDirectory(dir=args.out_dir) as staging:
            copernicusmarine.subset(
                dataset_id=CURR_DS,
                variables=["uo", "vo"],
                minimum_longitude=args.west,
                maximum_longitude=args.east,
                minimum_latitude=args.south,
                maximum_latitude=args.north,
                minimum_depth=SURFACE_DEPTH_M,
                maximum_depth=SURFACE_DEPTH_M,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                output_directory=staging,
                output_filename=current_out.name,
                file_format="netcdf",
                credentials_file=credentials,
                overwrite=True,
                disable_progress_bar=True,
                coordinates_selection_method="nearest",
            )
            os.replace(Path(staging) / current_out.name, current_out)

    if not wave_out.exists() or args.overwrite:
        with TemporaryDirectory(dir=args.out_dir) as staging:
            copernicusmarine.subset(
                dataset_id=WAVE_DS,
                variables=["VSDX", "VSDY", "VHM0"],
                minimum_longitude=args.west,
                maximum_longitude=args.east,
                minimum_latitude=args.south,
                maximum_latitude=args.north,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                output_directory=staging,
                output_filename=wave_out.name,
                file_format="netcdf",
                credentials_file=credentials,
                overwrite=True,
                disable_progress_bar=True,
                coordinates_selection_method="nearest",
            )
            os.replace(Path(staging) / wave_out.name, wave_out)


ARCO_ERA5 = (
    "https://storage.googleapis.com/gcp-public-data-arco-era5/"
    "ar/full_37-1h-0p25deg-chunk-1.zarr-v3"
)


def fetch_archive_wind(args: argparse.Namespace, output: Path) -> bool:
    """Read hourly ERA5 on its 0.25-degree grid, including bounding grid cells."""
    import aiohttp
    import numpy as np
    import xarray as xr

    options = {"client_kwargs": {"timeout": aiohttp.ClientTimeout(total=90), "trust_env": True}}
    with xr.open_zarr(ARCO_ERA5, consolidated=True, chunks=None, storage_options=options) as ds:
        if not (ds.attrs["valid_time_start"] <= args.start_date <= args.end_date <= ds.attrs["valid_time_stop"]):
            return False
        first = np.datetime64(args.start_date, "h")
        stop = np.datetime64(args.end_date, "h") + np.timedelta64(1, "D")
        hours = np.arange(first, stop, dtype="datetime64[h]")
        # Integer quarter degrees also handle western longitudes and the Greenwich seam.
        lon = np.arange(np.floor(args.west * 4), np.ceil(args.east * 4) + 1) / 4
        lat = np.arange(max(-360, np.floor(args.south * 4)), min(360, np.ceil(args.north * 4)) + 1) / 4
        wind = ds[["10m_u_component_of_wind", "10m_v_component_of_wind"]].rename(
            {"10m_u_component_of_wind": "u10", "10m_v_component_of_wind": "v10"}
        )
        wind = wind.sel(latitude=lat, longitude=lon % 360).assign_coords(longitude=lon)
        parts = []
        for offset in range(0, len(hours), 6):
            print(f"Reading ERA5 winds for {hours[offset]} UTC", flush=True)
            part = wind.sel(time=hours[offset:offset + 6]).load()
            if any(not np.isfinite(part[name].values).all() for name in ("u10", "v10")):
                raise ValueError(f"Incomplete public ERA5 wind fields at {hours[offset]}")
            parts.append(part)
        subset = xr.concat(parts, dim="time")
        subset.attrs = {"source": ARCO_ERA5}
        for variable in subset.variables.values():
            variable.encoding.clear()
        with TemporaryDirectory(dir=output.parent) as staging:
            temp = Path(staging) / output.name
            subset.to_netcdf(temp)
            os.replace(temp, output)
    return True


def fetch_era5(args: argparse.Namespace) -> None:
    import xarray as xr

    out_nc = args.out_dir / f"era5_wind_{args.start_date.replace('-', '')}_{args.end_date.replace('-', '')}.nc"
    if out_nc.exists() and not args.overwrite:
        return

    if args.era5_source == "archive-first" and fetch_archive_wind(args, out_nc):
        return

    import cdsapi

    url, key = parse_cdsapirc(Path(args.cdsapirc).expanduser())
    client = cdsapi.Client(url=url, key=key, quiet=False)
    part_paths: list[Path] = []
    try:
        for chunk_start, chunk_end in month_chunks(args.start_date, args.end_date):
            part_path = args.out_dir / f".era5_wind_{chunk_start:%Y%m%d}_{chunk_end:%Y%m%d}.part.nc"
            part_paths.append(part_path)
            request = {
                "product_type": "reanalysis",
                "variable": [
                    "10m_u_component_of_wind",
                    "10m_v_component_of_wind",
                ],
                "year": f"{chunk_start.year:04d}",
                "month": f"{chunk_start.month:02d}",
                "day": [f"{day:02d}" for day in range(chunk_start.day, chunk_end.day + 1)],
                "time": [f"{hour:02d}:00" for hour in range(24)],
                "area": [args.north, args.west, args.south, args.east],
                "data_format": "netcdf",
                "download_format": "unarchived",
            }
            try:
                client.retrieve("reanalysis-era5-single-levels", request, str(part_path))
            except Exception:
                fallback = dict(request)
                fallback.pop("data_format", None)
                fallback.pop("download_format", None)
                fallback["format"] = "netcdf"
                client.retrieve("reanalysis-era5-single-levels", fallback, str(part_path))

        if len(part_paths) == 1:
            os.replace(part_paths[0], out_nc)
        else:
            datasets = [xr.open_dataset(path) for path in part_paths]
            merged_part = out_nc.with_suffix(out_nc.suffix + ".part")
            combined = None
            try:
                combined = xr.combine_by_coords(datasets, combine_attrs="override")
                combined.to_netcdf(merged_part)
                os.replace(merged_part, out_nc)
            finally:
                if combined is not None:
                    combined.close()
                for dataset in datasets:
                    dataset.close()
                merged_part.unlink(missing_ok=True)
    finally:
        for part_path in part_paths:
            part_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch CMEMS and ERA5 forcing for OpenDrift.")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--start-date", required=True, help="UTC date YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="UTC date YYYY-MM-DD")
    parser.add_argument("--west", type=float, required=True)
    parser.add_argument("--south", type=float, required=True)
    parser.add_argument("--east", type=float, required=True)
    parser.add_argument("--north", type=float, required=True)
    parser.add_argument("--era5-source", choices=("cds", "archive-first"), default="cds")
    parser.add_argument("--skip-era5", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--cmems-credentials", default="/mnt/c/Users/Joshua Pretorius/.copernicusmarine/.copernicusmarine-credentials")
    parser.add_argument("--cdsapirc", default="/mnt/c/Users/Joshua Pretorius/.cdsapirc")
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    fetch_cmems(args)
    if not args.skip_era5:
        fetch_era5(args)
    print(f"Wrote forcing files under {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
