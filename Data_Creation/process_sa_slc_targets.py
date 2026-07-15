#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import shutil
import sys
import time
import xml.etree.ElementTree as ET
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import numpy as np
import rasterio as rio
import requests
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds


REPO_ROOT = Path(__file__).resolve().parents[1]
PREPROCESSING_DIR = REPO_ROOT / "Domain_SSL" / "Scripts" / "Preprocessing"
sys.path.insert(0, str(PREPROCESSING_DIR))

from process_drift_slc import (  # noqa: E402
    cleanup_dim_product,
    edl_auth,
    find_gpt,
    polarizations_for_granule,
    setup_logging,
    unzip_safe,
)
from snap_utils import (  # noqa: E402
    export_to_geotiff,
    graph_has_operator,
    patch_graph_io,
    patch_graph_params,
    run_graph,
    uses_windows_paths,
)


DATA_DIR = REPO_ROOT / "Data_Creation" / "meria_sa_plastic_s1_slc"
MATCH_CSV = DATA_DIR / "MERIA_SA_plastic_nearest_S1_SLC_before_after.csv"
POINTS_CSV = DATA_DIR / "MERIA_SA_plastic_points.csv"
OUT_ROOT = DATA_DIR / "processed_slc"
WORK_ROOT = DATA_DIR / "_slc_work"
DEFAULT_TARGETS = (
    ("MERIA_SA_001", "after"),
    ("MERIA_SA_002", "after"),
    ("MERIA_SA_003", "before"),
)
SUBSWATHS = ("IW1", "IW2", "IW3")
RESOLUTION_POLICIES = ("snap-native", "utm-grid")
OUTPUT_MODES = ("scene", "subswath", "both")
SUBSET_MODES = ("aoi", "full-swath")
FOLDER_NAME_STYLES = ("obs-first", "area-first")
FOLDER_NAME_STYLE = "obs-first"

GLCM_SETTINGS = {
    "source_bands": "Sigma0_VV,Sigma0_VH",
    "window_size": "5x5",
    "angle": "ALL",
    "quantizer": "Probabilistic Quantizer",
    "quantization_levels": 32,
    "displacement": 1,
    "snap_nodata": -9999.0,
}
SPECKLE_FILTER = {
    "filter": "Refined Lee",
    "filter_size": [3, 3],
}
DECOMPOSITION = {
    "type": "H-Alpha Dual Pol Decomposition",
    "window_size": 5,
    "outputs": ["Entropy", "Anisotropy", "Alpha"],
}


def resolve_graphs_dir(repo_root: Path = REPO_ROOT) -> Path:
    candidates = (
        repo_root / "SAR_PP" / "graphs",
        repo_root / "sar_ml_pipeline" / "graphs",
        repo_root / "sar_ml_pipeline_legacy" / "graphs",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


GRAPHS_DIR = resolve_graphs_dir()


@dataclass(frozen=True)
class Target:
    obs_id: str
    area: str
    role: str
    obs_date: str
    granule_safe: str
    acquisition_start: str
    delta_h: str
    download_group_key: str = ""

    @property
    def region_key(self) -> str:
        return f"{self.obs_id}_{slug(self.area)}"

    @property
    def folder_key(self) -> str:
        area_slug = slug(self.area)
        if FOLDER_NAME_STYLE == "area-first":
            return f"{area_slug}_{self.obs_id}"
        return self.region_key

    @property
    def granule(self) -> str:
        return self.granule_safe.removesuffix(".SAFE")

    @property
    def acquisition_key(self) -> str:
        return self.granule.split("_")[5]

    @property
    def scene_id(self) -> str:
        return f"{self.region_key}_{self.role}_{self.acquisition_key}"

    @property
    def url(self) -> str:
        platform_dir = {"S1A": "SA", "S1B": "SB", "S1C": "SC"}[self.granule[:3]]
        return f"https://datapool.asf.alaska.edu/SLC/{platform_dir}/{self.granule}.zip"


@dataclass(frozen=True)
class ProductSpec:
    key: str
    suffix: str
    source: str
    band_tokens: tuple[str, ...]
    description: str
    mask_zero: bool = False
    mask_glcm_nodata: bool = False
    postprocess: str | None = None
    output_grid: str = "final"


@dataclass(frozen=True)
class SubswathProducts:
    subswath: str
    paths: dict[str, Path]
    bands: dict[str, dict[str, int]]


PRODUCT_SPECS = (
    ProductSpec(
        key="vv",
        suffix="vv",
        source="sigma0",
        band_tokens=("vv",),
        description="Sentinel-1 SLC calibrated terrain-corrected VV sigma0",
        mask_zero=True,
    ),
    ProductSpec(
        key="vh",
        suffix="vh",
        source="sigma0",
        band_tokens=("vh",),
        description="Sentinel-1 SLC calibrated terrain-corrected VH sigma0",
        mask_zero=True,
    ),
    ProductSpec(
        key="vv_refined_lee",
        suffix="vv_refined_lee",
        source="filtered",
        band_tokens=("vv",),
        description="Sentinel-1 SLC VV sigma0 with SNAP Refined Lee 3x3 speckle filtering",
        mask_zero=True,
    ),
    ProductSpec(
        key="vv_refined_lee_db",
        suffix="vv_refined_lee_db",
        source="filtered",
        band_tokens=("vv",),
        description="Sentinel-1 SLC VV sigma0 with SNAP Refined Lee 3x3 speckle filtering on AOI UTM grid in dB",
        mask_zero=True,
        postprocess="db",
        output_grid="utm",
    ),
    ProductSpec(
        key="vv_glcm_mean",
        suffix="vv_glcm_mean",
        source="texture",
        band_tokens=("vv", "glcmmean"),
        description="Sentinel-1 SLC VV SNAP GLCM mean from Refined Lee filtered sigma0",
        mask_glcm_nodata=True,
    ),
    ProductSpec(
        key="vv_glcm_std",
        suffix="vv_glcm_std",
        source="texture",
        band_tokens=("vv", "glcmvariance"),
        description="Sentinel-1 SLC VV SNAP GLCM standard deviation from Refined Lee filtered sigma0",
        mask_glcm_nodata=True,
        postprocess="sqrt",
    ),
    ProductSpec(
        key="vv_glcm_entropy",
        suffix="vv_glcm_entropy",
        source="texture",
        band_tokens=("vv", "entropy"),
        description="Sentinel-1 SLC VV SNAP GLCM entropy from Refined Lee filtered sigma0",
        mask_glcm_nodata=True,
    ),
    ProductSpec(
        key="decomp_entropy",
        suffix="decomp_entropy",
        source="decomp",
        band_tokens=("entropy",),
        description="Sentinel-1 SLC H-alpha dual-pol decomposition entropy",
    ),
    ProductSpec(
        key="decomp_anisotropy",
        suffix="decomp_anisotropy",
        source="decomp",
        band_tokens=("anisotropy",),
        description="Sentinel-1 SLC H-alpha dual-pol decomposition anisotropy",
    ),
    ProductSpec(
        key="decomp_alpha",
        suffix="decomp_alpha",
        source="decomp",
        band_tokens=("alpha",),
        description="Sentinel-1 SLC H-alpha dual-pol decomposition alpha",
    ),
)


def slug(text: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in text.strip()).strip("_")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser("Process selected South Africa Sentinel-1 SLC targets through the SNAP SLC pipeline.")
    ap.add_argument(
        "--target",
        action="append",
        default=[],
        help="Target in obs_id:before|after form. Defaults to MERIA_SA_001:after, MERIA_SA_002:after, MERIA_SA_003:before.",
    )
    ap.add_argument("--out-root", default=str(OUT_ROOT))
    ap.add_argument("--work-root", default=str(WORK_ROOT))
    ap.add_argument("--graphs-dir", default=str(resolve_graphs_dir()))
    ap.add_argument("--gpt", default=None)
    ap.add_argument("--resolution-policy", choices=RESOLUTION_POLICIES, default="snap-native")
    ap.add_argument(
        "--output-mode",
        choices=OUTPUT_MODES,
        default="scene",
        help="Write scene mosaic products, per-subswath products, or both.",
    )
    ap.add_argument(
        "--subset-mode",
        choices=SUBSET_MODES,
        default="aoi",
        help="Subset each subswath to the AOI or process each full split subswath.",
    )
    ap.add_argument("--subswaths", default="IW1,IW2,IW3", help="Comma-separated subswaths to process, e.g. IW1,IW2,IW3 or IW3.")
    ap.add_argument("--resolution-m", type=float, default=10.0, help="Final UTM grid spacing when --resolution-policy utm-grid.")
    ap.add_argument("--pad-deg", type=float, default=0.25)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--cache-gb", type=int, default=8)
    ap.add_argument("--download-only", action="store_true")
    ap.add_argument("--prepare-only", action="store_true", help="Create AOI manifest metadata without downloading.")
    ap.add_argument("--keep-zip", action="store_true")
    ap.add_argument("--keep-safe", action="store_true")
    ap.add_argument("--force", action="store_true", help="Reprocess even if enhanced outputs already exist.")
    ap.add_argument("--verbose", "-v", action="count", default=1)
    return ap.parse_args()


def parse_targets(values: list[str]) -> set[tuple[str, str]]:
    if not values:
        return set(DEFAULT_TARGETS)
    targets: set[tuple[str, str]] = set()
    for value in values:
        if ":" not in value:
            raise ValueError(f"Target must be obs_id:before|after, got {value!r}")
        obs_id, role = value.split(":", 1)
        role = role.lower()
        if role not in {"before", "after"}:
            raise ValueError(f"Target role must be before or after, got {value!r}")
        targets.add((obs_id.strip(), role))
    return targets


def parse_subswaths(value: str) -> tuple[str, ...]:
    subswaths = tuple(item.strip().upper() for item in value.split(",") if item.strip())
    if not subswaths:
        raise ValueError("--subswaths must include at least one of IW1,IW2,IW3")
    invalid = [item for item in subswaths if item not in SUBSWATHS]
    if invalid:
        raise ValueError(f"Invalid subswath(s): {', '.join(invalid)}. Valid choices are {', '.join(SUBSWATHS)}")
    return subswaths


def load_matches(selected: set[tuple[str, str]]) -> list[Target]:
    rows: list[Target] = []
    with MATCH_CSV.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            obs_id = row["obs_id"]
            area = row["area"]
            for role in ("before", "after"):
                if (obs_id, role) not in selected:
                    continue
                rows.append(
                    Target(
                        obs_id=obs_id,
                        area=area,
                        role=role,
                        obs_date=row["date"],
                        granule_safe=row[f"{role}_name"],
                        acquisition_start=row[f"{role}_start"],
                        delta_h=row[f"{role}_delta_h"],
                        download_group_key=(row.get(f"{role}_download_group_key") or row[f"{role}_name"]).removesuffix(".SAFE"),
                    )
                )
    found = {(target.obs_id, target.role) for target in rows}
    missing = sorted(selected - found)
    if missing:
        raise RuntimeError("Requested target(s) not found in match CSV: " + ", ".join(f"{a}:{b}" for a, b in missing))
    return rows


def load_points(obs_id: str) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    with POINTS_CSV.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row["obs_id"] == obs_id:
                points.append((float(row["lon"]), float(row["lat"])))
    if not points:
        raise RuntimeError(f"No point rows found for {obs_id}")
    return points


def target_bounds_wgs84(target: Target, pad_deg: float) -> tuple[float, float, float, float]:
    points = load_points(target.obs_id)
    lons = [p[0] for p in points]
    lats = [p[1] for p in points]
    return (min(lons) - pad_deg, min(lats) - pad_deg, max(lons) + pad_deg, max(lats) + pad_deg)


def shared_zip_path(target: Target) -> Path:
    group_key = target.download_group_key or target.granule
    return DATA_DIR / "_shared_slc_zips" / group_key / f"{target.granule}.zip"


def bounds_wkt(bounds: tuple[float, float, float, float]) -> str:
    minx, miny, maxx, maxy = bounds
    return (
        f"POLYGON (({minx} {miny}, {maxx} {miny}, {maxx} {maxy}, "
        f"{minx} {maxy}, {minx} {miny}))"
    )


def utm_crs_for(points: list[tuple[float, float]]) -> CRS:
    lon = sum(p[0] for p in points) / len(points)
    lat = sum(p[1] for p in points) / len(points)
    zone = int((lon + 180.0) // 6.0) + 1
    epsg = (32700 if lat < 0 else 32600) + zone
    return CRS.from_epsg(epsg)


def ensure_reference_grid(target: Target, out_dir: Path, resolution_m: float, pad_deg: float) -> Path:
    resolution_label = f"{resolution_m:g}".replace(".", "p")
    ref_path = out_dir / f"{target.scene_id}_aoi_reference_utm{resolution_label}m.tif"
    if ref_path.exists():
        return ref_path

    points = load_points(target.obs_id)
    bounds_wgs84 = target_bounds_wgs84(target, pad_deg)
    dst_crs = utm_crs_for(points)
    left, bottom, right, top = transform_bounds("EPSG:4326", dst_crs, *bounds_wgs84, densify_pts=64)

    left = math.floor(left / resolution_m) * resolution_m
    bottom = math.floor(bottom / resolution_m) * resolution_m
    right = math.ceil(right / resolution_m) * resolution_m
    top = math.ceil(top / resolution_m) * resolution_m
    width = int(math.ceil((right - left) / resolution_m))
    height = int(math.ceil((top - bottom) / resolution_m))

    profile = final_raster_profile(
        {
            "driver": "GTiff",
            "width": width,
            "height": height,
            "crs": dst_crs,
            "transform": from_origin(left, top, resolution_m, resolution_m),
        }
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    with rio.open(ref_path, "w", **profile) as dst:
        block = np.full((1, min(512, height), min(512, width)), np.nan, dtype="float32")
        for _, window in dst.block_windows(1):
            dst.write(block[:, : window.height, : window.width], window=window)
        dst.set_band_description(1, f"{target.obs_id} {target.area} AOI reference grid")
    return ref_path


def final_raster_profile(base: dict) -> dict:
    width = int(base["width"])
    height = int(base["height"])
    profile = dict(base)
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
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid raster dimensions: {width}x{height}")
    return profile


def product_name_policy(spec: ProductSpec, resolution_policy: str) -> str:
    if spec.output_grid == "utm":
        return "utm"
    return "native" if resolution_policy == "snap-native" else "utm"


def product_output_paths(target: Target, out_dir: Path, resolution_policy: str) -> dict[str, Path]:
    return {
        spec.key: out_dir / f"{target.scene_id}_slc_{product_name_policy(spec, resolution_policy)}_{spec.suffix}.tif"
        for spec in PRODUCT_SPECS
    }


def subswath_product_output_paths(
    target: Target,
    out_dir: Path,
    resolution_policy: str,
    requested_subswaths: tuple[str, ...],
) -> dict[str, dict[str, Path]]:
    return {
        subswath: {
            spec.key: out_dir
            / "subswaths"
            / subswath
            / f"{target.scene_id}_slc_{product_name_policy(spec, resolution_policy)}_{subswath}_{spec.suffix}.tif"
            for spec in PRODUCT_SPECS
        }
        for subswath in requested_subswaths
    }


def expected_product_keys(selected_pols: list[str]) -> set[str]:
    keys = {spec.key for spec in PRODUCT_SPECS}
    if "VH" not in selected_pols:
        keys.discard("vh")
    return keys


def needs_reference_grid(resolution_policy: str) -> bool:
    return resolution_policy == "utm-grid" or any(spec.output_grid == "utm" for spec in PRODUCT_SPECS)


def processing_metadata(
    resolution_policy: str,
    output_mode: str,
    subset_mode: str,
    requested_subswaths: tuple[str, ...],
    pad_deg: float,
    aoi_bounds_wgs84: tuple[float, float, float, float],
    graphs: dict[str, Path] | None,
    grid: dict | None = None,
    subswath_grids: dict[str, dict] | None = None,
    processed_subswaths: list[str] | None = None,
) -> dict:
    metadata = {
        "resolution_policy": resolution_policy,
        "output_mode": output_mode,
        "subset_mode": subset_mode,
        "aoi_bounds_wgs84": list(aoi_bounds_wgs84),
        "aoi_wkt": bounds_wkt(aoi_bounds_wgs84),
        "pad_deg": pad_deg,
        "subswaths": list(requested_subswaths),
        "glcm": GLCM_SETTINGS,
        "speckle_filter": SPECKLE_FILTER,
        "decomposition": DECOMPOSITION,
    }
    if processed_subswaths is not None:
        metadata["processed_subswaths"] = processed_subswaths
    if graphs:
        metadata["graphs"] = {name: str(path) for name, path in graphs.items()}
    if grid:
        metadata["final_grid"] = grid
    if subswath_grids:
        metadata["subswath_grids"] = subswath_grids
    return metadata


def outputs_complete(
    manifest_path: Path,
    output_paths: dict[str, Path],
    subswath_output_paths: dict[str, dict[str, Path]],
    expected_keys: set[str],
    resolution_policy: str,
    output_mode: str,
    subset_mode: str,
    requested_subswaths: tuple[str, ...],
) -> bool:
    if not manifest_path.exists():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    processing = manifest.get("processing", {})
    if processing.get("resolution_policy") != resolution_policy:
        return False
    manifest_output_mode = processing.get("output_mode", "scene")
    if manifest_output_mode != output_mode:
        return False
    if processing.get("subset_mode", "aoi") != subset_mode:
        return False
    if manifest.get("status") != "processed":
        return False

    if output_mode in {"scene", "both"}:
        outputs = manifest.get("outputs", {})
        for key in expected_keys:
            path = outputs.get(key)
            if not path:
                return False
            if not Path(path).exists() and not output_paths[key].exists():
                return False

    if output_mode in {"subswath", "both"}:
        processed_subswaths = processing.get("processed_subswaths") or []
        requested = set(requested_subswaths)
        if not processed_subswaths or any(subswath not in requested for subswath in processed_subswaths):
            return False
        subswath_outputs = manifest.get("subswath_outputs", {})
        for subswath in processed_subswaths:
            outputs = subswath_outputs.get(subswath, {})
            fallback = subswath_output_paths.get(subswath, {})
            for key in expected_keys:
                path = outputs.get(key)
                if not path:
                    return False
                if not Path(path).exists() and not fallback.get(key, Path("__missing__")).exists():
                    return False
    return True


def process_target(
    target: Target,
    out_root: Path,
    work_root: Path,
    graphs: dict[str, Path] | None,
    gpt: str | None,
    auth: tuple[str, str],
    resolution_policy: str,
    output_mode: str,
    subset_mode: str,
    requested_subswaths: tuple[str, ...],
    resolution_m: float,
    pad_deg: float,
    cache_gb: int,
    workers: int,
    download_only: bool,
    prepare_only: bool,
    keep_zip: bool,
    keep_safe: bool,
    force: bool,
) -> None:
    out_dir = out_root / target.folder_key / f"{target.role}_{target.acquisition_key}"
    raw_dir = out_dir / "SLC"
    zip_path = raw_dir / f"{target.granule}.zip"
    shared_path = shared_zip_path(target)
    safe_dir = raw_dir / target.granule
    manifest_path = out_dir / f"{target.scene_id}_slc_manifest.json"
    output_paths = product_output_paths(target, out_dir, resolution_policy)
    subswath_output_paths = subswath_product_output_paths(target, out_dir, resolution_policy, requested_subswaths)
    selected_pols = polarizations_for_granule(target.granule)
    expected_keys = expected_product_keys(selected_pols)
    aoi_bounds = target_bounds_wgs84(target, pad_deg)
    ref_path = None
    if needs_reference_grid(resolution_policy):
        ref_path = ensure_reference_grid(target, out_dir, resolution_m, pad_deg)

    if "VV" not in selected_pols:
        raise RuntimeError(f"{target.scene_id}: enhanced MERIA products require VV polarisation, got {selected_pols}")

    if not force and outputs_complete(
        manifest_path,
        output_paths,
        subswath_output_paths,
        expected_keys,
        resolution_policy,
        output_mode,
        subset_mode,
        requested_subswaths,
    ):
        logging.info("Skip %s: enhanced %s %s outputs already exist", target.scene_id, resolution_policy, output_mode)
        return

    if prepare_only and manifest_path.exists() and not force:
        try:
            existing_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            existing_manifest = {}
        if existing_manifest.get("status") == "processed":
            logging.info("Prepared %s: existing processed manifest left unchanged", target.scene_id)
            return

    raw_dir.mkdir(parents=True, exist_ok=True)
    write_manifest(
        target=target,
        manifest_path=manifest_path,
        ref_path=ref_path,
        zip_path=shared_path,
        selected_pols=selected_pols,
        outputs={key: None for key in output_paths},
        subswath_outputs={subswath: {key: None for key in paths} for subswath, paths in subswath_output_paths.items()},
        processing=processing_metadata(resolution_policy, output_mode, subset_mode, requested_subswaths, pad_deg, aoi_bounds, graphs),
        status="prepared",
    )
    if prepare_only:
        logging.info("Prepared %s", target.scene_id)
        return

    active_zip_path = shared_path
    if shared_path.exists():
        logging.info("Using shared zip %s", shared_path.name)
    elif zip_path.exists():
        active_zip_path = zip_path
        logging.info("Using existing zip %s", zip_path.name)
    else:
        cached_zip = find_cached_slc_zip(target.granule, shared_path)
        if cached_zip is not None:
            active_zip_path = cached_zip
            logging.info("Using cached zip %s", cached_zip)
        else:
            logging.info("Downloading %s", shared_path.name)
            stream_download_asf(target.url, shared_path, auth)

    if download_only:
        write_manifest(
            target=target,
            manifest_path=manifest_path,
            ref_path=ref_path,
            zip_path=active_zip_path,
            selected_pols=selected_pols,
            outputs={key: None for key in output_paths},
            subswath_outputs={subswath: {key: None for key in paths} for subswath, paths in subswath_output_paths.items()},
            processing=processing_metadata(resolution_policy, output_mode, subset_mode, requested_subswaths, pad_deg, aoi_bounds, graphs),
            status="downloaded",
        )
        return

    if graphs is None or gpt is None:
        raise RuntimeError("graphs and gpt are required unless --download-only or --prepare-only is used")

    safe_root = unzip_safe(active_zip_path, safe_dir)
    safe_candidates = [p for p in safe_root.iterdir() if p.suffix == ".SAFE" and p.is_dir()]
    slc_input = safe_candidates[0] if safe_candidates else safe_root

    scene_work = work_root / target.scene_id
    if force and scene_work.exists():
        shutil.rmtree(scene_work, ignore_errors=True)
    scene_work.mkdir(parents=True, exist_ok=True)

    success = False
    try:
        subswath_products = [
            item
            for item in (
                run_enhanced_subswath(
                    gpt=gpt,
                    graphs=graphs,
                    slc_input=slc_input,
                    work_dir=scene_work / subswath,
                    subswath=subswath,
                    selected_pols=selected_pols,
                    aoi_wkt=bounds_wkt(aoi_bounds),
                    subset_mode=subset_mode,
                    cache_gb=cache_gb,
                    workers=workers,
                )
                for subswath in requested_subswaths
            )
            if item is not None
        ]
        if not subswath_products:
            raise RuntimeError(f"{target.scene_id}: AOI did not intersect any Sentinel-1 IW subswath")

        outputs: dict[str, Path | None] = {key: None for key in output_paths}
        subswath_outputs: dict[str, dict[str, Path | None]] = {}
        grid_info = None
        subswath_grids: dict[str, dict] = {}
        ref_profile = None
        if ref_path is not None:
            if ref_path is None:
                raise RuntimeError("UTM grid processing requires a reference grid")
            with rio.open(ref_path) as ref:
                ref_profile = final_raster_profile(ref.profile.copy())

        if output_mode in {"scene", "both"}:
            if resolution_policy == "utm-grid" and ref_profile is not None:
                final_profile = ref_profile
            else:
                final_profile = native_scene_profile(
                    aoi_bounds_wgs84=aoi_bounds,
                    source_paths=[item.paths["sigma0"] for item in subswath_products],
                    use_source_bounds=subset_mode == "full-swath",
                )
            outputs = write_scene_products(
                subswath_products=subswath_products,
                output_paths=output_paths,
                expected_keys=expected_keys,
                final_profile=final_profile,
                ref_profile=ref_profile,
            )
            grid_info = grid_metadata(next(path for path in outputs.values() if path is not None))

        if output_mode in {"subswath", "both"}:
            subswath_outputs = write_subswath_products(
                subswath_products=subswath_products,
                output_paths=subswath_output_paths,
                expected_keys=expected_keys,
                resolution_policy=resolution_policy,
                ref_profile=ref_profile,
            )
            for subswath, paths in subswath_outputs.items():
                first_path = next((path for path in paths.values() if path is not None), None)
                if first_path is not None:
                    subswath_grids[subswath] = grid_metadata(first_path)

        write_manifest(
            target=target,
            manifest_path=manifest_path,
            ref_path=ref_path,
            zip_path=active_zip_path,
            selected_pols=selected_pols,
            outputs=outputs,
            subswath_outputs=subswath_outputs,
            processing=processing_metadata(
                resolution_policy,
                output_mode,
                subset_mode,
                requested_subswaths,
                pad_deg,
                aoi_bounds,
                graphs,
                grid=grid_info,
                subswath_grids=subswath_grids,
                processed_subswaths=[item.subswath for item in subswath_products],
            ),
            status="processed",
        )
        success = True
    finally:
        if success:
            shutil.rmtree(scene_work, ignore_errors=True)
        else:
            logging.warning("Preserving work directory after failure: %s", scene_work)

    if not keep_safe:
        shutil.rmtree(safe_dir, ignore_errors=True)
    if not keep_zip and zip_path.exists():
        zip_path.unlink()


def find_cached_slc_zip(granule: str, expected_path: Path) -> Path | None:
    if expected_path.exists():
        return expected_path
    shared_root = DATA_DIR / "_shared_slc_zips"
    if shared_root.exists():
        for candidate in shared_root.rglob(f"{granule}.zip"):
            if candidate.resolve() != expected_path.resolve():
                return candidate
    global_root = REPO_ROOT / "Data_Creation" / "meria_global_s1_slc"
    if not global_root.exists():
        return None
    expected_resolved = expected_path.resolve()
    for candidate in global_root.rglob(f"{granule}.zip"):
        if candidate.resolve() != expected_resolved:
            return candidate
    return None


def write_manifest(
    target: Target,
    manifest_path: Path,
    ref_path: Path | None,
    zip_path: Path,
    selected_pols: list[str],
    outputs: dict[str, Path | None],
    subswath_outputs: dict[str, dict[str, Path | None]] | None,
    processing: dict,
    status: str,
) -> None:
    manifest = {
        "observation_id": target.obs_id,
        "area": target.area,
        "role": target.role,
        "observation_date": target.obs_date,
        "acquisition_start": target.acquisition_start,
        "delta_hours_from_observation_date": target.delta_h,
        "scene_id": target.scene_id,
        "download_group_key": target.download_group_key or target.granule,
        "slc": {
            "granule": target.granule,
            "url": target.url,
            "zip": str(zip_path),
            "selected_polarisations": selected_pols,
        },
        "reference_grid": str(ref_path) if ref_path else None,
        "outputs": {key: str(path) if path else None for key, path in outputs.items()},
        "subswath_outputs": {
            subswath: {key: str(path) if path else None for key, path in paths.items()}
            for subswath, paths in (subswath_outputs or {}).items()
        },
        "processing": processing,
        "status": status,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def stream_download_asf(url: str, out_path: Path, auth: tuple[str, str]) -> None:
    if not auth[0] or not auth[1]:
        raise RuntimeError("Earthdata credentials are required to download ASF products.")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    part_path = out_path.with_suffix(out_path.suffix + ".part")
    session = requests.Session()
    headers = {"User-Agent": "meria-sa-slc/2.0"}
    ensure_asf_session(session, url, auth, headers)

    resume_at = part_path.stat().st_size if part_path.exists() else 0
    request_headers = dict(headers)
    mode = "wb"
    if resume_at:
        request_headers["Range"] = f"bytes={resume_at}-"
        mode = "ab"

    with session.get(url, headers=request_headers, allow_redirects=True, stream=True, timeout=(30, 180)) as response:
        if response.status_code == 200 and resume_at:
            logging.info("Server did not resume %s; restarting download", out_path.name)
            resume_at = 0
            mode = "wb"
        elif response.status_code not in {200, 206}:
            raise RuntimeError(f"ASF download failed for {out_path.name}: HTTP {response.status_code} at {response.url}")

        total = response.headers.get("content-range") or response.headers.get("content-length") or "unknown"
        logging.info("ASF download response for %s: HTTP %s, size %s", out_path.name, response.status_code, total)
        written = resume_at
        last_log = time.monotonic()
        with part_path.open(mode + "") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                handle.write(chunk)
                written += len(chunk)
                now = time.monotonic()
                if now - last_log >= 30:
                    logging.info("Downloaded %.1f MB for %s", written / (1024 * 1024), out_path.name)
                    last_log = now

    part_path.replace(out_path)
    logging.info("Downloaded %.1f MB to %s", out_path.stat().st_size / (1024 * 1024), out_path)


def ensure_asf_session(session: requests.Session, url: str, auth: tuple[str, str], headers: dict[str, str]) -> None:
    response = session.get(url, headers=headers, allow_redirects=False, timeout=60)
    for _ in range(12):
        if "asf-urs" in session.cookies:
            return
        if not response.is_redirect:
            if response.status_code in {200, 206}:
                return
            raise RuntimeError(f"Unexpected ASF login response HTTP {response.status_code} at {response.url}")

        location = urljoin(response.url, response.headers["Location"])
        host = urlparse(location).netloc.lower()
        if host == "urs.earthdata.nasa.gov":
            response = session.get(location, headers=headers, auth=auth, allow_redirects=False, timeout=60)
        else:
            response = session.get(location, headers=headers, allow_redirects=False, timeout=60)

    raise RuntimeError("ASF login redirect chain did not complete.")


def run_enhanced_subswath(
    gpt: str,
    graphs: dict[str, Path],
    slc_input: Path,
    work_dir: Path,
    subswath: str,
    selected_pols: list[str],
    aoi_wkt: str,
    subset_mode: str,
    cache_gb: int,
    workers: int,
) -> SubswathProducts | None:
    logging.info("Processing %s", subswath)
    work_dir.mkdir(parents=True, exist_ok=True)
    windows_paths = uses_windows_paths(gpt)
    pols = ",".join(selected_pols)

    split = work_dir / f"{subswath}_split.dim"
    orbit = work_dir / f"{subswath}_orbit.dim"
    calibrated = work_dir / f"{subswath}_cal.dim"
    calibrated_deburst = work_dir / f"{subswath}_cal_deburst.dim"
    calibrated_subset = work_dir / f"{subswath}_cal_deburst_subset.dim"
    sigma0_tc = work_dir / f"{subswath}_sigma0_tc.dim"
    sigma0_tif = work_dir / f"{subswath}_sigma0_tc.tif"
    filtered = work_dir / f"{subswath}_cal_filtered.dim"
    filtered_tc = work_dir / f"{subswath}_filtered_tc.dim"
    filtered_tif = work_dir / f"{subswath}_filtered_tc.tif"
    texture = work_dir / f"{subswath}_tex.dim"
    texture_tc = work_dir / f"{subswath}_tex_tc.dim"
    texture_tif = work_dir / f"{subswath}_tex_tc.tif"
    c2_deburst = work_dir / f"{subswath}_deburst.dim"
    c2 = work_dir / f"{subswath}_c2.dim"
    c2_subset = work_dir / f"{subswath}_c2_subset.dim"
    decomp = work_dir / f"{subswath}_decomp.dim"
    decomp_tc = work_dir / f"{subswath}_decomp_tc.dim"
    decomp_tif = work_dir / f"{subswath}_decomp_tc.tif"

    def checkpoint_bands(path: Path) -> dict[str, int] | None:
        if path.suffix.lower() == ".dim":
            if not snap_product_exists(path):
                return None
        elif not path.exists():
            return None
        try:
            return load_band_indexes(path)
        except Exception as exc:
            logging.warning("Ignoring unreadable checkpoint %s: %s", path, exc)
            return None

    def current_outputs() -> dict[str, tuple[Path, dict[str, int] | None]]:
        return {
            "sigma0": (sigma0_tif, checkpoint_bands(sigma0_tif)),
            "filtered": (filtered_tif, checkpoint_bands(filtered_tif)),
            "texture": (texture_tif, checkpoint_bands(texture_tif)),
            "decomp": (decomp_tif, checkpoint_bands(decomp_tif)),
        }

    def build_completed_result() -> SubswathProducts | None:
        outputs = current_outputs()
        if any(bands is None for _, bands in outputs.values()):
            return None
        return SubswathProducts(
            subswath=subswath,
            paths={key: path for key, (path, _) in outputs.items()},
            bands={key: bands for key, (_, bands) in outputs.items() if bands is not None},
        )

    completed = build_completed_result()
    if completed is not None:
        logging.info("Reusing completed %s outputs from %s", subswath, work_dir)
        return completed

    def ensure_orbit_product() -> Path:
        if checkpoint_bands(orbit) is not None:
            return orbit
        if checkpoint_bands(split) is None:
            run_graph_with_io(
                gpt,
                graphs["split"],
                slc_input,
                split,
                cache_gb,
                workers,
                windows_paths,
                [
                    {"op": "TOPSAR-Split", "param": "subswath", "value": subswath},
                    {"op": "TOPSAR-Split", "param": "selectedPolarisations", "value": pols},
                    {"op": "TOPSAR-Split", "param": "firstBurstIndex", "value": None},
                    {"op": "TOPSAR-Split", "param": "lastBurstIndex", "value": None},
                    {"op": "TOPSAR-Split", "param": "selectedBursts", "value": None},
                ],
            )
        run_graph_with_io(gpt, graphs["orbit"], split, orbit, cache_gb, workers, windows_paths)
        cleanup_dim_product(split)
        return orbit

    def ensure_calibrated_source() -> Path | None:
        if subset_mode == "aoi" and checkpoint_bands(calibrated_subset) is not None:
            return calibrated_subset
        if checkpoint_bands(calibrated_deburst) is None:
            if checkpoint_bands(calibrated) is None:
                orbit_source = ensure_orbit_product()
                run_graph_with_io(
                    gpt,
                    graphs["calibration"],
                    orbit_source,
                    calibrated,
                    cache_gb,
                    workers,
                    windows_paths,
                    [{"op": "Calibration", "param": "selectedPolarisations", "value": pols}],
                )
            run_graph_with_io(gpt, graphs["deburst"], calibrated, calibrated_deburst, cache_gb, workers, windows_paths)
            if snap_product_exists(calibrated):
                cleanup_dim_product(calibrated)
        if subset_mode != "aoi":
            return calibrated_deburst
        run_graph_with_io(
            gpt,
            graphs["subset"],
            calibrated_deburst,
            calibrated_subset,
            cache_gb,
            workers,
            windows_paths,
            [{"op": "Subset", "param": "geoRegion", "value": aoi_wkt}],
        )
        if snap_product_exists(calibrated_deburst):
            cleanup_dim_product(calibrated_deburst)
        if checkpoint_bands(calibrated_subset) is None:
            logging.info("%s has no AOI intersection after subset; skipping subswath", subswath)
            cleanup_dim_product(calibrated_subset)
            return None
        return calibrated_subset

    sigma0_bands = checkpoint_bands(sigma0_tif)
    if sigma0_bands is None:
        sigma0_stage_bands = checkpoint_bands(sigma0_tc)
        if sigma0_stage_bands is None:
            calibrated_source = ensure_calibrated_source()
            if calibrated_source is None:
                return None
            run_graph_with_io(gpt, graphs["terrain"], calibrated_source, sigma0_tc, cache_gb, workers, windows_paths)
            sigma0_stage_bands = load_band_indexes(sigma0_tc)
        export_to_geotiff(gpt, sigma0_tc, sigma0_tif, cache_gb=cache_gb, workers=workers, windows_paths=windows_paths)
        sigma0_bands = sigma0_stage_bands
        if snap_product_exists(sigma0_tc):
            cleanup_dim_product(sigma0_tc)

    filtered_bands = checkpoint_bands(filtered_tif)
    filtered_stage_bands = checkpoint_bands(filtered_tc)
    if filtered_bands is None:
        if filtered_stage_bands is None:
            if checkpoint_bands(filtered) is None:
                calibrated_source = ensure_calibrated_source()
                if calibrated_source is None:
                    return None
                run_graph_with_io(gpt, graphs["speckle"], calibrated_source, filtered, cache_gb, workers, windows_paths)
            run_graph_with_io(gpt, graphs["terrain"], filtered, filtered_tc, cache_gb, workers, windows_paths)
            filtered_stage_bands = load_band_indexes(filtered_tc)
        export_to_geotiff(gpt, filtered_tc, filtered_tif, cache_gb=cache_gb, workers=workers, windows_paths=windows_paths)
        filtered_bands = filtered_stage_bands
        if snap_product_exists(filtered_tc):
            cleanup_dim_product(filtered_tc)

    texture_bands = checkpoint_bands(texture_tif)
    texture_stage_bands = checkpoint_bands(texture_tc)
    if texture_bands is None:
        if texture_stage_bands is None:
            if checkpoint_bands(texture) is None:
                if checkpoint_bands(filtered) is None:
                    calibrated_source = ensure_calibrated_source()
                    if calibrated_source is None:
                        return None
                    run_graph_with_io(gpt, graphs["speckle"], calibrated_source, filtered, cache_gb, workers, windows_paths)
                run_graph_with_io(gpt, graphs["texture"], filtered, texture, cache_gb, workers, windows_paths)
            run_graph_with_io(gpt, graphs["terrain"], texture, texture_tc, cache_gb, workers, windows_paths)
            texture_stage_bands = load_band_indexes(texture_tc)
        export_to_geotiff(gpt, texture_tc, texture_tif, cache_gb=cache_gb, workers=workers, windows_paths=windows_paths)
        texture_bands = texture_stage_bands
        if snap_product_exists(texture):
            cleanup_dim_product(texture)
        if snap_product_exists(texture_tc):
            cleanup_dim_product(texture_tc)

    decomp_bands = checkpoint_bands(decomp_tif)
    if decomp_bands is None:
        decomp_stage_bands = checkpoint_bands(decomp_tc)
        if decomp_stage_bands is None:
            if checkpoint_bands(decomp) is None:
                if subset_mode == "aoi" and checkpoint_bands(c2_subset) is not None:
                    c2_source = c2_subset
                else:
                    if checkpoint_bands(c2) is None:
                        orbit_source = ensure_orbit_product()
                        c2_input = orbit_source
                        if not graph_has_operator(graphs["c2"], "TOPSAR-Deburst"):
                            if checkpoint_bands(c2_deburst) is None:
                                run_graph_with_io(gpt, graphs["deburst"], orbit_source, c2_deburst, cache_gb, workers, windows_paths)
                            c2_input = c2_deburst
                        run_graph_with_io(gpt, graphs["c2"], c2_input, c2, cache_gb, workers, windows_paths)
                    c2_source = c2
                    if subset_mode == "aoi":
                        if checkpoint_bands(c2_subset) is None:
                            run_graph_with_io(
                                gpt,
                                graphs["subset"],
                                c2,
                                c2_subset,
                                cache_gb,
                                workers,
                                windows_paths,
                                [{"op": "Subset", "param": "geoRegion", "value": aoi_wkt}],
                            )
                        if checkpoint_bands(c2_subset) is None:
                            raise RuntimeError(f"{subswath}: calibrated branch intersected AOI, but C2 branch did not")
                        c2_source = c2_subset
                run_graph_with_io(gpt, graphs["decomp"], c2_source, decomp, cache_gb, workers, windows_paths)
            run_graph_with_io(gpt, graphs["terrain"], decomp, decomp_tc, cache_gb, workers, windows_paths)
            decomp_stage_bands = load_band_indexes(decomp_tc)
        export_to_geotiff(gpt, decomp_tc, decomp_tif, cache_gb=cache_gb, workers=workers, windows_paths=windows_paths)
        decomp_bands = decomp_stage_bands
        if snap_product_exists(decomp):
            cleanup_dim_product(decomp)
        if snap_product_exists(decomp_tc):
            cleanup_dim_product(decomp_tc)

    return SubswathProducts(
        subswath=subswath,
        paths={
            "sigma0": sigma0_tif,
            "filtered": filtered_tif,
            "texture": texture_tif,
            "decomp": decomp_tif,
        },
        bands={
            "sigma0": sigma0_bands,
            "filtered": filtered_bands,
            "texture": texture_bands,
            "decomp": decomp_bands,
        },
    )


def snap_product_exists(dim_path: Path) -> bool:
    return dim_path.exists() and dim_path.with_suffix(".data").exists()


def run_graph_with_io(
    gpt: str,
    graph: Path,
    src: Path,
    dst: Path,
    cache_gb: int,
    workers: int,
    windows_paths: bool,
    params: list[dict] | None = None,
) -> None:
    tmp_paths: list[Path] = []
    patched = patch_graph_io(graph, src, dst, windows_paths=windows_paths)
    tmp_paths.append(patched)
    graph_to_run = patched
    if params:
        graph_to_run = patch_graph_params(patched, params)
        tmp_paths.append(graph_to_run)
    try:
        run_graph(gpt, graph_to_run, cache_gb, workers)
    finally:
        for tmp in tmp_paths:
            if tmp.exists():
                tmp.unlink()


def dim_band_indexes(dim_path: Path) -> dict[str, int]:
    tree = ET.parse(dim_path)
    band_map: dict[str, int] = {}
    for band in tree.findall(".//Spectral_Band_Info"):
        name = band.findtext("BAND_NAME")
        index = band.findtext("BAND_INDEX")
        if name is None or index is None:
            continue
        band_map[normalize_band_name(name)] = int(index) + 1
    if not band_map:
        raise RuntimeError(f"No band names found in {dim_path}")
    return band_map


def raster_band_indexes(raster_path: Path) -> dict[str, int]:
    with rio.open(raster_path) as ds:
        band_map = {
            normalize_band_name(description): index
            for index, description in enumerate(ds.descriptions, start=1)
            if description
        }
        if band_map:
            return band_map
        inferred = inferred_raster_band_indexes(raster_path, ds.count)
        if inferred is not None:
            return inferred
    raise RuntimeError(f"No raster band descriptions found in {raster_path}")


def inferred_raster_band_indexes(raster_path: Path, count: int) -> dict[str, int] | None:
    name = raster_path.name.lower()
    if "sigma0_tc" in name or "filtered_tc" in name:
        if count == 2:
            # SNAP preserves VH before VV for these dual-pol stacks.
            return {"sigma0vh": 1, "sigma0vv": 2}
        if count == 1:
            return {"sigma0vv": 1}
    if "tex_tc" in name:
        if count == 20:
            return {
                "sigma0vhcontrast": 1,
                "sigma0vhdissimilarity": 2,
                "sigma0vhhomogeneity": 3,
                "sigma0vhasm": 4,
                "sigma0vhenergy": 5,
                "sigma0vhmax": 6,
                "sigma0vhentropy": 7,
                "sigma0vhglcmmean": 8,
                "sigma0vhglcmvariance": 9,
                "sigma0vhglcmcorrelation": 10,
                "sigma0vvcontrast": 11,
                "sigma0vvdissimilarity": 12,
                "sigma0vvhomogeneity": 13,
                "sigma0vvasm": 14,
                "sigma0vvenergy": 15,
                "sigma0vvmax": 16,
                "sigma0vventropy": 17,
                "sigma0vvglcmmean": 18,
                "sigma0vvglcmvariance": 19,
                "sigma0vvglcmcorrelation": 20,
            }
        if count == 10:
            return {
                "sigma0vvcontrast": 1,
                "sigma0vvdissimilarity": 2,
                "sigma0vvhomogeneity": 3,
                "sigma0vvasm": 4,
                "sigma0vvenergy": 5,
                "sigma0vvmax": 6,
                "sigma0vventropy": 7,
                "sigma0vvglcmmean": 8,
                "sigma0vvglcmvariance": 9,
                "sigma0vvglcmcorrelation": 10,
            }
    if "decomp_tc" in name:
        if count == 3:
            return {"entropy": 1, "anisotropy": 2, "alpha": 3}
    if count == 1:
        return {normalize_band_name(raster_path.stem): 1}
    return None


def load_band_indexes(path: Path) -> dict[str, int]:
    if path.suffix.lower() == ".dim":
        return dim_band_indexes(path)
    return raster_band_indexes(path)


def normalize_band_name(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum())


def find_band_index(band_map: dict[str, int], tokens: tuple[str, ...], source_name: str) -> int:
    norm_tokens = tuple(normalize_band_name(token) for token in tokens)
    matches = [idx for name, idx in band_map.items() if all(token in name for token in norm_tokens)]
    if not matches:
        raise RuntimeError(f"Could not find band tokens {tokens} in {source_name}; available={sorted(band_map)}")
    if len(matches) > 1:
        logging.debug("Multiple band matches for %s in %s; using band %s", tokens, source_name, matches[0])
    return matches[0]


def native_scene_profile(
    aoi_bounds_wgs84: tuple[float, float, float, float],
    source_paths: list[Path],
    *,
    use_source_bounds: bool = False,
) -> dict:
    first = next((path for path in source_paths if path.exists()), None)
    if first is None:
        raise RuntimeError("No SNAP terrain-corrected sources available to define native scene grid")
    with rio.open(first) as ref:
        if ref.crs is None:
            raise RuntimeError(f"Native source has no CRS: {first}")
        transform = ref.transform
        if transform.b != 0 or transform.d != 0 or transform.a <= 0 or transform.e >= 0:
            raise RuntimeError(f"Unsupported non-north-up source transform in {first}: {transform}")
        res_x = float(abs(transform.a))
        res_y = float(abs(transform.e))
        if use_source_bounds:
            projected_bounds = []
            for path in source_paths:
                if not path.exists():
                    continue
                with rio.open(path) as src:
                    if src.crs != ref.crs:
                        raise RuntimeError(f"Native source CRS mismatch between {first} and {path}")
                    projected_bounds.append((src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top))
            if not projected_bounds:
                raise RuntimeError("No SNAP terrain-corrected sources available to define full-scene native grid")
            left = min(bounds[0] for bounds in projected_bounds)
            bottom = min(bounds[1] for bounds in projected_bounds)
            right = max(bounds[2] for bounds in projected_bounds)
            top = max(bounds[3] for bounds in projected_bounds)
        else:
            left, bottom, right, top = transform_bounds("EPSG:4326", ref.crs, *aoi_bounds_wgs84, densify_pts=64)

        col_min = math.floor((left - transform.c) / res_x)
        col_max = math.ceil((right - transform.c) / res_x)
        row_min = math.floor((transform.f - top) / res_y)
        row_max = math.ceil((transform.f - bottom) / res_y)

        snapped_left = transform.c + col_min * res_x
        snapped_top = transform.f - row_min * res_y
        width = int(col_max - col_min)
        height = int(row_max - row_min)
        return final_raster_profile(
            {
                "driver": "GTiff",
                "width": width,
                "height": height,
                "crs": ref.crs,
                "transform": from_origin(snapped_left, snapped_top, res_x, res_y),
            }
        )


def write_scene_products(
    subswath_products: list[SubswathProducts],
    output_paths: dict[str, Path],
    expected_keys: set[str],
    final_profile: dict,
    ref_profile: dict | None,
) -> dict[str, Path | None]:
    outputs: dict[str, Path | None] = {key: None for key in output_paths}
    for spec in PRODUCT_SPECS:
        if spec.key not in expected_keys:
            continue
        sources: list[tuple[Path, int]] = []
        support_sources: list[tuple[Path, int]] = []
        for item in subswath_products:
            source_path = item.paths[spec.source]
            if not source_path.exists():
                continue
            band_index = find_band_index(item.bands[spec.source], spec.band_tokens, f"{item.subswath}:{spec.source}")
            sources.append((source_path, band_index))
            support_sources.append((item.paths["sigma0"], support_band_index(item.bands["sigma0"])))
        if not sources:
            logging.warning("No source bands available for %s", spec.key)
            continue
        spec_profile = resolve_product_profile(spec, final_profile, ref_profile)
        write_mosaic_product(spec_profile, sources, output_paths[spec.key], spec, support_sources=support_sources)
        outputs[spec.key] = output_paths[spec.key]
    return outputs


def write_subswath_products(
    subswath_products: list[SubswathProducts],
    output_paths: dict[str, dict[str, Path]],
    expected_keys: set[str],
    resolution_policy: str,
    ref_profile: dict | None,
) -> dict[str, dict[str, Path | None]]:
    outputs: dict[str, dict[str, Path | None]] = {}
    for item in subswath_products:
        paths = output_paths[item.subswath]
        final_profile = ref_profile if resolution_policy == "utm-grid" else source_raster_profile(item.paths["sigma0"])
        outputs[item.subswath] = write_scene_products(
            subswath_products=[item],
            output_paths=paths,
            expected_keys=expected_keys,
            final_profile=final_profile,
            ref_profile=ref_profile,
        )
    return outputs


def source_raster_profile(path: Path) -> dict:
    with rio.open(path) as src:
        return final_raster_profile(
            {
                "driver": "GTiff",
                "width": src.width,
                "height": src.height,
                "crs": src.crs,
                "transform": src.transform,
            }
        )


def support_band_index(band_map: dict[str, int]) -> int:
    for token in (("vv",), ("vh",)):
        try:
            return find_band_index(band_map, token, "sigma0-support")
        except RuntimeError:
            continue
    return next(iter(band_map.values()))


def resolve_product_profile(spec: ProductSpec, final_profile: dict, ref_profile: dict | None) -> dict:
    if spec.output_grid != "utm":
        return final_profile
    if ref_profile is None:
        raise RuntimeError(f"{spec.key} requires a UTM reference profile")
    return ref_profile


def write_mosaic_product(
    final_profile: dict,
    sources: list[tuple[Path, int]],
    out_path: Path,
    spec: ProductSpec,
    support_sources: list[tuple[Path, int]] | None = None,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_name(f".{out_path.stem}.tmp{out_path.suffix}")
    if tmp_path.exists():
        tmp_path.unlink()
    profile = final_raster_profile(final_profile)
    with rio.open(tmp_path, "w", **profile) as dst, ExitStack() as stack:
        opened = [stack.enter_context(rio.open(path)) for path, _ in sources]
        vrts = [
            stack.enter_context(
                WarpedVRT(
                    src,
                    crs=dst.crs,
                    transform=dst.transform,
                    width=dst.width,
                    height=dst.height,
                    resampling=Resampling.bilinear,
                )
            )
            for src in opened
        ]
        support_vrts = None
        if support_sources is not None:
            support_opened = [stack.enter_context(rio.open(path)) for path, _ in support_sources]
            support_vrts = [
                stack.enter_context(
                    WarpedVRT(
                        src,
                        crs=dst.crs,
                        transform=dst.transform,
                        width=dst.width,
                        height=dst.height,
                        resampling=Resampling.nearest,
                    )
                )
                for src in support_opened
            ]
        for _, window in dst.block_windows(1):
            merged = np.full((window.height, window.width), np.nan, dtype="float32")
            for idx, (vrt, (_, band_index)) in enumerate(zip(vrts, sources)):
                arr = vrt.read(band_index, window=window, masked=True).astype("float32")
                data = arr.filled(np.nan).astype("float32")
                invalid = np.ma.getmaskarray(arr) | ~np.isfinite(data)
                if support_vrts is not None:
                    support_vrt = support_vrts[idx]
                    _, support_band = support_sources[idx]
                    support_arr = support_vrt.read(support_band, window=window, masked=True).astype("float32")
                    support_data = support_arr.filled(np.nan).astype("float32")
                    invalid |= np.ma.getmaskarray(support_arr) | ~np.isfinite(support_data) | (support_data == 0.0)
                if spec.mask_zero:
                    invalid |= data == 0.0
                if spec.mask_glcm_nodata:
                    invalid |= np.isclose(data, GLCM_SETTINGS["snap_nodata"]) | (data <= GLCM_SETTINGS["snap_nodata"])
                if spec.postprocess == "db":
                    invalid |= data <= 0.0
                data[invalid] = np.nan
                if spec.postprocess == "sqrt":
                    data = np.sqrt(np.maximum(data, np.float32(0.0))).astype("float32")
                elif spec.postprocess == "db":
                    with np.errstate(divide="ignore", invalid="ignore"):
                        data = (10.0 * np.log10(data)).astype("float32")
                fill = np.isnan(merged) & ~invalid
                merged[fill] = data[fill]
            dst.write(merged, 1, window=window)
        dst.set_band_description(1, spec.description)
    tmp_path.replace(out_path)


def grid_metadata(path: Path) -> dict:
    with rio.open(path) as ds:
        return {
            "crs": ds.crs.to_string() if ds.crs else None,
            "resolution": [float(abs(ds.transform.a)), float(abs(ds.transform.e))],
            "shape_yx": [int(ds.height), int(ds.width)],
            "bounds": [float(ds.bounds.left), float(ds.bounds.bottom), float(ds.bounds.right), float(ds.bounds.top)],
            "transform": [float(v) for v in ds.transform],
        }


def ensure_graphs(graphs_dir: Path) -> dict[str, Path]:
    graphs = {
        "split": graphs_dir / "01_split.xml",
        "orbit": graphs_dir / "02_orbit_apply.xml",
        "calibration": graphs_dir / "03_calibration.xml",
        "deburst": graphs_dir / "04_deburst.xml",
        "subset": graphs_dir / "05_subset.xml",
        "c2": graphs_dir / "06_polarimetric_matrix.xml",
        "speckle": graphs_dir / "07_speckle_filter.xml",
        "terrain": graphs_dir / "08_terrain_correction.xml",
        "decomp": graphs_dir / "09_polarimetric_decomposition.xml",
        "texture": graphs_dir / "10_feature_extraction.xml",
    }
    missing = [str(path) for path in graphs.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing SNAP graph(s): " + ", ".join(missing))
    return graphs


def main() -> None:
    args = parse_args()
    setup_logging(args.verbose)
    selected = parse_targets(args.target)
    requested_subswaths = parse_subswaths(args.subswaths)
    targets = load_matches(selected)
    auth = ("", "") if args.prepare_only else edl_auth()
    if not args.prepare_only and (not auth[0] or not auth[1]):
        raise RuntimeError("No Earthdata credentials found. Set EDL_USER/EDL_PASS or add urs.earthdata.nasa.gov to netrc.")

    graphs = None if args.download_only or args.prepare_only else ensure_graphs(Path(args.graphs_dir))
    gpt = None if args.download_only or args.prepare_only else find_gpt(args.gpt)
    if gpt:
        logging.info("Using SNAP GPT: %s (windows_paths=%s)", gpt, uses_windows_paths(gpt))

    for target in targets:
        process_target(
            target=target,
            out_root=Path(args.out_root),
            work_root=Path(args.work_root),
            graphs=graphs,
            gpt=gpt,
            auth=(auth[0], auth[1]),
            resolution_policy=args.resolution_policy,
            output_mode=args.output_mode,
            subset_mode=args.subset_mode,
            requested_subswaths=requested_subswaths,
            resolution_m=args.resolution_m,
            pad_deg=args.pad_deg,
            cache_gb=args.cache_gb,
            workers=args.workers,
            download_only=args.download_only,
            prepare_only=args.prepare_only,
            keep_zip=args.keep_zip,
            keep_safe=args.keep_safe,
            force=args.force,
        )


if __name__ == "__main__":
    main()
