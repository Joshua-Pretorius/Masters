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


def ymd(value: str) -> tuple[str, str, str]:
    year, month, day = value.split("-")
    return year, month, day


def fetch_cmems(args: argparse.Namespace) -> None:
    import copernicusmarine

    credentials = Path(args.cmems_credentials).expanduser()
    current_out = args.out_dir / f"cmems_currents_{args.start_date.replace('-', '')}_{args.end_date.replace('-', '')}.nc"
    wave_out = args.out_dir / f"cmems_waves_{args.start_date.replace('-', '')}_{args.end_date.replace('-', '')}.nc"
    start_datetime = f"{args.start_date}T00:00:00"
    end_datetime = f"{args.end_date}T23:59:00"

    if not current_out.exists() or args.overwrite:
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
            output_directory=args.out_dir,
            output_filename=current_out.name,
            file_format="netcdf",
            credentials_file=credentials,
            overwrite=True,
            disable_progress_bar=True,
            coordinates_selection_method="nearest",
        )

    if not wave_out.exists() or args.overwrite:
        copernicusmarine.subset(
            dataset_id=WAVE_DS,
            variables=["VSDX", "VSDY", "VHM0"],
            minimum_longitude=args.west,
            maximum_longitude=args.east,
            minimum_latitude=args.south,
            maximum_latitude=args.north,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            output_directory=args.out_dir,
            output_filename=wave_out.name,
            file_format="netcdf",
            credentials_file=credentials,
            overwrite=True,
            disable_progress_bar=True,
            coordinates_selection_method="nearest",
        )


def fetch_era5(args: argparse.Namespace) -> None:
    import cdsapi

    out_nc = args.out_dir / f"era5_wind_{args.start_date.replace('-', '')}_{args.end_date.replace('-', '')}.nc"
    if out_nc.exists() and not args.overwrite:
        return

    start_y, start_m, start_d = ymd(args.start_date)
    end_y, end_m, end_d = ymd(args.end_date)
    if (start_y, start_m) != (end_y, end_m):
        raise ValueError("ERA5 fetch currently expects start/end in the same month")

    url, key = parse_cdsapirc(Path(args.cdsapirc).expanduser())
    client = cdsapi.Client(url=url, key=key, quiet=False)
    request = {
        "product_type": "reanalysis",
        "variable": [
            "10m_u_component_of_wind",
            "10m_v_component_of_wind",
        ],
        "year": start_y,
        "month": start_m,
        "day": [f"{day:02d}" for day in range(int(start_d), int(end_d) + 1)],
        "time": [f"{hour:02d}:00" for hour in range(24)],
        "area": [args.north, args.west, args.south, args.east],
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
    parser = argparse.ArgumentParser(description="Fetch CMEMS and ERA5 forcing for OpenDrift.")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--start-date", required=True, help="UTC date YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="UTC date YYYY-MM-DD")
    parser.add_argument("--west", type=float, required=True)
    parser.add_argument("--south", type=float, required=True)
    parser.add_argument("--east", type=float, required=True)
    parser.add_argument("--north", type=float, required=True)
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
