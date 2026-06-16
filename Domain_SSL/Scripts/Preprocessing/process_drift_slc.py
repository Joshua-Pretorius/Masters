#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import json
import logging
import netrc
import os
import re
import shutil
import subprocess
import tempfile
import time
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

# Clear conflicting GIS env vars inherited from other Python/Conda installs.
# This script should use the PROJ/GDAL data bundled with the active venv packages.
for _env_key in ("PROJ_LIB", "PROJ_DATA", "GDAL_DATA"):
    _env_val = os.environ.get(_env_key)
    if _env_val and "anaconda3" in _env_val.lower():
        os.environ.pop(_env_key, None)
os.environ.setdefault("GTIFF_SRS_SOURCE", "EPSG")

import numpy as np
import pandas as pd
import requests
import rasterio as rio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds

from snap_utils import (
    export_to_geotiff,
    find_gpt,
    patch_graph_io,
    patch_graph_params,
    resolve_local_path,
    run_graph,
    setup_logging,
    uses_windows_paths,
)

ASF_PARAM = "https://api.daac.asf.alaska.edu/services/search/param"
WINDOWS_NETRC = Path("/mnt/c/Users/Joshua Pretorius/_netrc")
SCENE_RE = re.compile(r"^(S1_[0-9A-Z]{5}_\d{8}T\d{6})_(vv|vh)\.tif$", re.IGNORECASE)
GRD_LEVELS = ["GRD_HD", "GRD_MD", "GRD_MS", "GRD_HS", "GRD_FD"]
KEEP_PLATFORMS = {"Sentinel-1A", "Sentinel-1B", "Sentinel-1C"}
HTTP_TIMEOUT = 180
RETRY_5XX = 4
BACKOFF_BASE = 2.0


@dataclass(frozen=True)
class DriftScene:
    scene_id: str
    ref_tif: Path
    scene_dir: Path
    timestamp: pd.Timestamp

    @property
    def out_vv(self) -> Path:
        return self.scene_dir / f"{self.scene_id}_slc_vv.tif"

    @property
    def out_vh(self) -> Path:
        return self.scene_dir / f"{self.scene_id}_slc_vh.tif"

    @property
    def manifest_path(self) -> Path:
        return self.scene_dir / f"{self.scene_id}_slc_manifest.json"


def polarizations_for_granule(granule_name: str) -> list[str]:
    if "_1SDV_" in granule_name or "_1SDH_" in granule_name:
        return ["VV", "VH"] if granule_name.endswith("DV") or "_1SDV_" in granule_name else ["HH", "HV"]
    if "_1SSV_" in granule_name:
        return ["VV"]
    if "_1SSH_" in granule_name:
        return ["HH"]
    if "_DV_" in granule_name:
        return ["VV", "VH"]
    return ["VV", "VH"]


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[3]
    ap = argparse.ArgumentParser(
        "Download the matching Sentinel-1 SLC for each Drift GRD scene and "
        "export terrain-corrected VV/VH GeoTIFFs on the Drift grid."
    )
    ap.add_argument("--drift-root", default=str(repo_root / "Drift"))
    ap.add_argument("--graphs-dir", default=str(repo_root / "sar_ml_pipeline" / "graphs"))
    ap.add_argument("--work-root", default=str(repo_root / "Drift" / "_slc_work"))
    ap.add_argument("--gpt", default=None)
    ap.add_argument("--window-hours", type=int, default=12)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--cache-gb", type=int, default=12)
    ap.add_argument(
        "--scene-id",
        action="append",
        default=[],
        help="Only process matching Drift scene id(s), e.g. S1_16PCC_20160905T000626.",
    )
    ap.add_argument("--download-only", action="store_true", help="Only download the matching SLC zip files and write manifests.")
    ap.add_argument("--keep-zip", action="store_true", help="Keep downloaded SLC zip files after success.")
    ap.add_argument("--keep-safe", action="store_true", help="Keep unzipped SAFE folders after success.")
    ap.add_argument("--verbose", "-v", action="count", default=1)
    return ap.parse_args()


def edl_auth() -> tuple[str | None, str | None]:
    user, password = os.getenv("EDL_USER"), os.getenv("EDL_PASS")
    if user and password:
        return user, password

    candidates = [
        None,
        Path.home() / ".netrc",
        Path.home() / "_netrc",
        WINDOWS_NETRC,
    ]
    for candidate in candidates:
        try:
            auths = netrc.netrc(str(candidate)) if candidate else netrc.netrc()
            cred = auths.authenticators("urs.earthdata.nasa.gov")
            if cred and cred[0] and cred[2]:
                return cred[0], cred[2]
        except Exception:
            continue
    return None, None


def get_with_retry(url: str, params: dict[str, str], timeout: int = HTTP_TIMEOUT, attempts: int = RETRY_5XX):
    last_error = None
    for idx in range(attempts):
        try:
            response = requests.get(
                url,
                params=params,
                timeout=timeout,
                headers={"Accept": "text/csv", "User-Agent": "drift-slc/1.0"},
            )
            if 500 <= response.status_code < 600:
                raise requests.HTTPError(f"{response.status_code} Server Error", response=response)
            response.raise_for_status()
            return response
        except (requests.Timeout, requests.HTTPError) as exc:
            last_error = exc
            wait = BACKOFF_BASE * (2**idx)
            logging.warning("HTTP get failed (%s); retrying in %.1fs", exc, wait)
            time.sleep(wait)
    if last_error:
        raise last_error
    raise RuntimeError("HTTP request failed without an exception")


def discover_scenes(drift_root: Path) -> list[DriftScene]:
    grouped: dict[tuple[Path, str], dict[str, Path]] = {}
    for tif in sorted(drift_root.glob("*/SAR_*h/S1_*_*.tif")):
        match = SCENE_RE.match(tif.name)
        if not match:
            continue
        scene_id, pol = match.groups()
        grouped.setdefault((tif.parent, scene_id), {})[pol.lower()] = tif

    scenes: list[DriftScene] = []
    for (scene_dir, scene_id), pols in sorted(grouped.items()):
        ref_tif = pols.get("vv") or pols.get("vh")
        if ref_tif is None:
            continue
        timestamp = pd.to_datetime(scene_id.split("_")[2], utc=True)
        scenes.append(DriftScene(scene_id=scene_id, ref_tif=ref_tif, scene_dir=scene_dir, timestamp=timestamp))
    return scenes


def scene_wkt(ref_tif: Path) -> str:
    with rio.open(ref_tif) as ds:
        bounds = transform_bounds(ds.crs, "EPSG:4326", *ds.bounds, densify_pts=64)
    minx, miny, maxx, maxy = bounds
    return (
        f"POLYGON (({minx} {miny}, {maxx} {miny}, {maxx} {maxy}, "
        f"{minx} {maxy}, {minx} {miny}))"
    )


def query_level(level: str, footprint_wkt: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    params = {
        "platform": "s1",
        "processingLevel": level,
        "beamMode": "IW",
        "output": "CSV",
        "maxResults": "500",
        "intersectsWith": footprint_wkt,
        "start": start.strftime("%Y-%m-%dT%H:%M:%SUTC"),
        "end": end.strftime("%Y-%m-%dT%H:%M:%SUTC"),
    }
    response = get_with_retry(ASF_PARAM, params)
    if not response.content or response.content.strip() == b"":
        return pd.DataFrame()
    df = pd.read_csv(io.BytesIO(response.content))
    if df.empty:
        return df
    if "Platform" in df.columns:
        df = df[df["Platform"].isin(KEEP_PLATFORMS)].copy()
    if df.empty:
        return df
    df["acq_dt"] = pd.to_datetime(df["Acquisition Date"], utc=True, errors="coerce")
    df = df.dropna(subset=["acq_dt"]).copy()
    df["date"] = df["acq_dt"].dt.date.astype(str)
    return df.drop_duplicates(subset=["Granule Name"])


def query_matching_products(scene: DriftScene, window_hours: int) -> tuple[pd.Series, pd.Series]:
    footprint_wkt = scene_wkt(scene.ref_tif)
    start = scene.timestamp - pd.Timedelta(hours=window_hours)
    end = scene.timestamp + pd.Timedelta(hours=window_hours)

    grd_parts = [query_level(level, footprint_wkt, start, end) for level in GRD_LEVELS]
    grd = pd.concat([df for df in grd_parts if not df.empty], ignore_index=True) if any(not df.empty for df in grd_parts) else pd.DataFrame()
    slc = query_level("SLC", footprint_wkt, start, end)
    if grd.empty:
        raise RuntimeError(f"No GRD matches found for {scene.scene_id}")
    if slc.empty:
        raise RuntimeError(f"No SLC matches found for {scene.scene_id}")

    grd["dt_seconds"] = (grd["acq_dt"] - scene.timestamp).abs().dt.total_seconds()
    best_grd = grd.sort_values(["dt_seconds", "Granule Name"]).iloc[0]

    slc_same_day = slc[slc["date"] == best_grd["date"]].copy()
    if slc_same_day.empty:
        slc_same_day = slc.copy()
    slc_same_day["dt_seconds"] = (slc_same_day["acq_dt"] - best_grd["acq_dt"]).abs().dt.total_seconds()
    best_slc = slc_same_day.sort_values(["dt_seconds", "Granule Name"]).iloc[0]
    return best_grd, best_slc


def netrc_path_for_download(auth: tuple[str | None, str | None]) -> tuple[Path, bool]:
    if WINDOWS_NETRC.exists():
        return WINDOWS_NETRC, False
    handle, path_str = tempfile.mkstemp(prefix="earthdata_", suffix=".netrc")
    path = Path(path_str)
    os.close(handle)
    path.write_text(
        "machine urs.earthdata.nasa.gov\n"
        f"  login {auth[0]}\n"
        f"  password {auth[1]}\n",
        encoding="utf-8",
    )
    os.chmod(path, 0o600)
    return path, True


def stream_download(url: str, out_path: Path, auth: tuple[str, str] | None) -> None:
    if auth is None or not auth[0] or not auth[1]:
        raise RuntimeError("Earthdata credentials are required to download ASF products.")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    netrc_path, remove_netrc = netrc_path_for_download(auth)
    cookie_handle, cookie_path_str = tempfile.mkstemp(prefix="earthdata_", suffix=".cookies")
    os.close(cookie_handle)
    cookie_path = Path(cookie_path_str)
    try:
        cmd = [
            "curl",
            "-L",
            "-f",
            "--retry",
            "5",
            "--retry-all-errors",
            "-c",
            str(cookie_path),
            "-b",
            str(cookie_path),
            "--netrc-file",
            str(netrc_path),
            "-o",
            str(out_path),
            url,
        ]
        subprocess.run(cmd, check=True)
    finally:
        if cookie_path.exists():
            cookie_path.unlink()
        if remove_netrc and netrc_path.exists():
            netrc_path.unlink()


def unzip_safe(zip_path: Path, out_dir: Path) -> Path:
    if out_dir.exists() and any(out_dir.iterdir()):
        return out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.unpack_archive(str(zip_path), str(out_dir))
    return out_dir


def cleanup_dim_product(dim_path: Path) -> None:
    data_dir = dim_path.with_suffix(".data")
    if dim_path.exists():
        dim_path.unlink()
    if data_dir.exists():
        shutil.rmtree(data_dir, ignore_errors=True)


def ensure_graphs(graphs_dir: Path) -> dict[str, Path]:
    graphs = {
        "split": graphs_dir / "01_split.xml",
        "orbit": graphs_dir / "02_orbit_apply.xml",
        "calibration": graphs_dir / "03_calibration.xml",
        "deburst": graphs_dir / "04_deburst.xml",
        "terrain": graphs_dir / "08_terrain_correction.xml",
    }
    missing = [str(path) for path in graphs.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing SNAP graph(s): " + ", ".join(missing))
    return graphs


def run_sigma0_tc(
    gpt: str,
    graphs: dict[str, Path],
    slc_input: Path,
    work_dir: Path,
    subswath: str,
    selected_pols: list[str],
    cache_gb: int,
    workers: int,
) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)
    windows_paths = uses_windows_paths(gpt)
    split = work_dir / f"{subswath}_split.dim"
    orbit = work_dir / f"{subswath}_orbit.dim"
    calibrated = work_dir / f"{subswath}_cal.dim"
    deburst = work_dir / f"{subswath}_deburst.dim"
    sigma0_tc = work_dir / f"{subswath}_sigma0_tc.dim"
    sigma0_tc_tif = work_dir / f"{subswath}_sigma0_tc.tif"

    if sigma0_tc_tif.exists():
        logging.info("%s already exported: %s", subswath, sigma0_tc_tif)
        return sigma0_tc_tif

    graph = patch_graph_io(graphs["split"], slc_input, split, windows_paths=windows_paths)
    graph = patch_graph_params(
        graph,
        [
            {"op": "TOPSAR-Split", "param": "subswath", "value": subswath},
            {"op": "TOPSAR-Split", "param": "selectedPolarisations", "value": ",".join(selected_pols)},
            {"op": "TOPSAR-Split", "param": "firstBurstIndex", "value": None},
            {"op": "TOPSAR-Split", "param": "lastBurstIndex", "value": None},
            {"op": "TOPSAR-Split", "param": "selectedBursts", "value": None},
        ],
    )
    run_graph(gpt, graph, cache_gb, workers)
    run_graph(gpt, patch_graph_io(graphs["orbit"], split, orbit, windows_paths=windows_paths), cache_gb, workers)
    graph = patch_graph_io(graphs["calibration"], orbit, calibrated, windows_paths=windows_paths)
    graph = patch_graph_params(
        graph,
        [{"op": "Calibration", "param": "selectedPolarisations", "value": ",".join(selected_pols)}],
    )
    run_graph(gpt, graph, cache_gb, workers)
    run_graph(gpt, patch_graph_io(graphs["deburst"], calibrated, deburst, windows_paths=windows_paths), cache_gb, workers)
    run_graph(gpt, patch_graph_io(graphs["terrain"], deburst, sigma0_tc, windows_paths=windows_paths), cache_gb, workers)
    export_to_geotiff(gpt, sigma0_tc, sigma0_tc_tif, cache_gb=cache_gb, workers=workers, windows_paths=windows_paths)

    for product in [split, orbit, calibrated, deburst, sigma0_tc]:
        cleanup_dim_product(product)
    return sigma0_tc_tif


def band_indexes(tc_path: Path) -> dict[str, int]:
    with rio.open(tc_path) as ds:
        descs = [(desc or "").lower() for desc in ds.descriptions]
        vv = next((idx for idx, desc in enumerate(descs, start=1) if "vv" in desc), None)
        vh = next((idx for idx, desc in enumerate(descs, start=1) if "vh" in desc), None)
        if vv is None and ds.count >= 1:
            vv = 1
        if vh is None and ds.count >= 2:
            vh = 2
        if vv is None and vh is None:
            raise RuntimeError(f"Could not identify any supported polarisation bands in {tc_path}")
        out: dict[str, int] = {}
        if vv is not None:
            out["vv"] = vv
        if vh is not None:
            out["vh"] = vh
        return out


def write_band_on_ref(ref_tif: Path, sigma_paths: list[Path], band_index: int, out_path: Path, description: str) -> None:
    with rio.open(ref_tif) as ref:
        profile = ref.profile.copy()
        profile.update(
            driver="GTiff",
            count=1,
            dtype="float32",
            nodata=float("nan"),
            compress="deflate",
            predictor=2,
            tiled=True,
            blockxsize=512,
            blockysize=512,
            bigtiff="IF_SAFER",
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with rio.open(out_path, "w", **profile) as dst, ExitStack() as stack:
            srcs = [stack.enter_context(rio.open(path)) for path in sigma_paths]
            vrts = [
                stack.enter_context(
                    WarpedVRT(
                        src,
                        crs=ref.crs,
                        transform=ref.transform,
                        width=ref.width,
                        height=ref.height,
                        resampling=Resampling.bilinear,
                    )
                )
                for src in srcs
            ]
            for _, window in dst.block_windows(1):
                merged = None
                for vrt in vrts:
                    arr = vrt.read(band_index, window=window, masked=True).astype("float32")
                    data = arr.filled(float("nan"))
                    if merged is None:
                        merged = data
                        continue
                    fill = (~arr.mask) & np.isnan(merged)
                    merged[fill] = data[fill]
                if merged is None:
                    raise RuntimeError(f"No data available while writing {out_path}")
                dst.write(merged, 1, window=window)
            dst.set_band_description(1, description)


def process_scene(
    scene: DriftScene,
    graphs: dict[str, Path] | None,
    gpt: str | None,
    work_root: Path,
    auth: tuple[str, str],
    window_hours: int,
    cache_gb: int,
    workers: int,
    download_only: bool,
    keep_zip: bool,
    keep_safe: bool,
) -> None:
    if scene.manifest_path.exists():
        try:
            manifest = json.loads(scene.manifest_path.read_text(encoding="utf-8"))
            if download_only:
                zip_path = manifest.get("slc", {}).get("zip")
                if zip_path and resolve_local_path(zip_path).exists():
                    logging.info("Skip %s: SLC zip already present", scene.scene_id)
                    return
            outputs = manifest.get("outputs", {})
            wanted = [resolve_local_path(path) for path in outputs.values() if path]
            if wanted and all(path.exists() for path in wanted):
                logging.info("Skip %s: outputs already present", scene.scene_id)
                return
        except Exception:
            pass

    best_grd, best_slc = query_matching_products(scene, window_hours)
    logging.info(
        "%s matched GRD=%s (%.1fs) | SLC=%s (%.1fs)",
        scene.scene_id,
        best_grd["Granule Name"],
        float(best_grd["dt_seconds"]),
        best_slc["Granule Name"],
        float(best_slc["dt_seconds"]),
    )

    scene_work = work_root / scene.scene_id
    raw_dir = scene.scene_dir / "SLC"
    zip_path = raw_dir / f"{best_slc['Granule Name']}.zip"
    safe_dir = raw_dir / best_slc["Granule Name"]
    sigma_dir = scene_work / "sigma0_tc"

    if not zip_path.exists():
        logging.info("Downloading %s", zip_path.name)
        stream_download(best_slc["URL"], zip_path, auth)
    else:
        logging.info("Using existing zip %s", zip_path.name)

    selected_pols = polarizations_for_granule(best_slc["Granule Name"])
    if download_only:
        manifest = {
            "scene_id": scene.scene_id,
            "ref_tif": str(scene.ref_tif),
            "grd": {
                "granule": best_grd["Granule Name"],
                "platform": best_grd.get("Platform"),
                "acquisition_date": best_grd["Acquisition Date"],
                "url": best_grd["URL"],
            },
            "slc": {
                "granule": best_slc["Granule Name"],
                "platform": best_slc.get("Platform"),
                "acquisition_date": best_slc["Acquisition Date"],
                "url": best_slc["URL"],
                "zip": str(zip_path),
                "selected_polarisations": selected_pols,
            },
            "outputs": {
                "vv": None,
                "vh": None,
            },
        }
        scene.manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return

    if graphs is None or gpt is None:
        raise RuntimeError("graphs and gpt are required unless --download-only is used")

    safe_root = unzip_safe(zip_path, safe_dir)
    safe_candidates = [p for p in safe_root.iterdir() if p.suffix == ".SAFE" and p.is_dir()]
    slc_input = safe_candidates[0] if safe_candidates else safe_root

    sigma_paths: list[Path] = []
    for subswath in ("IW1", "IW2", "IW3"):
        logging.info("%s | %s", scene.scene_id, subswath)
        sigma_paths.append(
            run_sigma0_tc(
                gpt=gpt,
                graphs=graphs,
                slc_input=slc_input,
                work_dir=sigma_dir / subswath,
                subswath=subswath,
                selected_pols=selected_pols,
                cache_gb=cache_gb,
                workers=workers,
            )
        )

    bands = band_indexes(sigma_paths[0])
    if "vv" in bands:
        write_band_on_ref(scene.ref_tif, sigma_paths, bands["vv"], scene.out_vv, "Sentinel-1 SLC Calibrated and Terrain Corrected VV")
    if "vh" in bands:
        write_band_on_ref(scene.ref_tif, sigma_paths, bands["vh"], scene.out_vh, "Sentinel-1 SLC Calibrated and Terrain Corrected VH")

    manifest = {
        "scene_id": scene.scene_id,
        "ref_tif": str(scene.ref_tif),
        "grd": {
            "granule": best_grd["Granule Name"],
            "platform": best_grd.get("Platform"),
            "acquisition_date": best_grd["Acquisition Date"],
            "url": best_grd["URL"],
        },
        "slc": {
            "granule": best_slc["Granule Name"],
            "platform": best_slc.get("Platform"),
            "acquisition_date": best_slc["Acquisition Date"],
            "url": best_slc["URL"],
            "zip": str(zip_path),
            "selected_polarisations": selected_pols,
        },
        "outputs": {
            "vv": str(scene.out_vv) if "vv" in bands else None,
            "vh": str(scene.out_vh) if "vh" in bands else None,
        },
    }
    scene.manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    shutil.rmtree(scene_work, ignore_errors=True)
    if not keep_safe:
        shutil.rmtree(safe_dir, ignore_errors=True)
    if not keep_zip and zip_path.exists():
        zip_path.unlink()


def main() -> None:
    args = parse_args()
    setup_logging(args.verbose)

    auth = edl_auth()
    if not auth[0] or not auth[1]:
        raise RuntimeError(
            "No Earthdata credentials found. Set EDL_USER/EDL_PASS or add urs.earthdata.nasa.gov "
            f"to ~/.netrc or {WINDOWS_NETRC}."
        )

    drift_root = Path(args.drift_root)
    work_root = Path(args.work_root)
    scenes = discover_scenes(drift_root)
    if not scenes:
        raise RuntimeError(f"No Drift SAR scenes found under {drift_root}")
    if args.scene_id:
        requested = {scene_id.lower() for scene_id in args.scene_id}
        scenes = [scene for scene in scenes if scene.scene_id.lower() in requested]
        missing = sorted(requested - {scene.scene_id.lower() for scene in scenes})
        if missing:
            raise RuntimeError("Requested scene id(s) not found: " + ", ".join(missing))

    graphs = None if args.download_only else ensure_graphs(Path(args.graphs_dir))
    gpt = None if args.download_only else find_gpt(args.gpt)
    logging.info("Scenes discovered: %d", len(scenes))
    for scene in scenes:
        process_scene(
            scene=scene,
            graphs=graphs,
            gpt=gpt,
            work_root=work_root,
            auth=(auth[0], auth[1]),
            window_hours=args.window_hours,
            cache_gb=args.cache_gb,
            workers=args.workers,
            download_only=args.download_only,
            keep_zip=args.keep_zip,
            keep_safe=args.keep_safe,
        )


if __name__ == "__main__":
    main()
