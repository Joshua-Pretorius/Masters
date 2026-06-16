#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Mapping, Sequence

from affine import Affine
import numpy as np
import rasterio as rio
from rasterio import features
from rasterio.windows import Window
from shapely.geometry import shape


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_CREATION_ROOT = REPO_ROOT / "Data_Creation"
PATCHES_ROOT = DATA_CREATION_ROOT / "Patches"
LIBRARY_ROOT = DATA_CREATION_ROOT / "Library"
PATCH_SIZE = 256
SCENE_ROOTS = (
    DATA_CREATION_ROOT / "meria_sa_plastic_s1_slc" / "processed_slc",
    DATA_CREATION_ROOT / "meria_global_s1_slc" / "processed_slc",
)
BAND_ORDER = (
    "vv_db",
    "vh_db",
    "vv_vh_ratio_db",
    "vv_minus_vh_db",
    "vv_glcm_mean",
    "vv_glcm_std",
    "vv_glcm_entropy",
    "decomp_entropy",
    "decomp_anisotropy",
    "decomp_alpha",
)
REQUIRED_OUTPUT_KEYS = (
    "vv",
    "vh",
    "vv_refined_lee_db",
    "vv_glcm_mean",
    "vv_glcm_std",
    "vv_glcm_entropy",
    "decomp_entropy",
    "decomp_anisotropy",
    "decomp_alpha",
)
SCENE_TIF_PATTERNS = {
    "vv": ("_slc_native_vv.tif",),
    "vh": ("_slc_native_vh.tif",),
    "vv_refined_lee_db": ("_slc_native_vv_refined_lee_db.tif", "_slc_utm_vv_refined_lee_db.tif"),
    "vv_glcm_mean": ("_slc_native_vv_glcm_mean.tif",),
    "vv_glcm_std": ("_slc_native_vv_glcm_std.tif",),
    "vv_glcm_entropy": ("_slc_native_vv_glcm_entropy.tif",),
    "decomp_entropy": ("_slc_native_decomp_entropy.tif",),
    "decomp_anisotropy": ("_slc_native_decomp_anisotropy.tif",),
    "decomp_alpha": ("_slc_native_decomp_alpha.tif",),
}


@dataclass(frozen=True)
class LayerSource:
    dataset: str
    scene_id: str
    scene_dir: Path
    shapefile_path: Path
    layer_kind: str


@dataclass(frozen=True)
class RasterBandSpec:
    name: str
    key: str
    path: Path
    mode: str


@dataclass(frozen=True)
class PatchWindow:
    row_off: int
    col_off: int
    width: int
    height: int
    touches_edge: bool


def dataset_name_for_path(path: Path) -> str:
    path_str = str(path)
    if "meria_global_s1_slc" in path_str:
        return "meria_global"
    return "meria_sa"


def normalize_class_name(value: str) -> str:
    return "_".join(value.strip().lower().split())


def discover_digitized_layers(processed_roots: Iterable[Path]) -> list[LayerSource]:
    results: list[LayerSource] = []
    for processed_root in processed_roots:
        for shp_path in sorted(processed_root.glob("**/*.shp")):
            parent_name = shp_path.parent.name.lower()
            if parent_name != "digitised_patches":
                continue
            scene_dir = shp_path.parent.parent
            results.append(
                LayerSource(
                    dataset=dataset_name_for_path(processed_root),
                    scene_id=scene_dir.name,
                    scene_dir=scene_dir,
                    shapefile_path=shp_path,
                    layer_kind="digitised_other_features" if "other_features" in shp_path.stem.lower() else "digitised_patches",
                )
            )
    return results


def resolve_feature_class(source: LayerSource, properties: Mapping[str, object]) -> tuple[str | None, str]:
    if source.layer_kind == "digitised_patches":
        return None, "plastic"
    raw_label = str(properties.get("Class", ""))
    return raw_label, normalize_class_name(raw_label)


def read_manifest(manifest_path: Path) -> dict[str, object]:
    return json.loads(manifest_path.read_text(encoding="utf-8-sig"))


def outputs_complete(outputs: Mapping[str, object] | None) -> bool:
    return bool(outputs) and all(outputs.get(key) for key in REQUIRED_OUTPUT_KEYS)


def infer_outputs_from_scene_dir(scene_dir: Path) -> dict[str, str | None]:
    outputs: dict[str, str | None] = {key: None for key in REQUIRED_OUTPUT_KEYS}
    tif_paths = [path for path in scene_dir.glob("*.tif") if path.is_file()]
    for key, suffixes in SCENE_TIF_PATTERNS.items():
        for tif_path in tif_paths:
            if tif_path.name.endswith(suffixes):
                outputs[key] = str(tif_path)
                break
    return outputs


def select_output_bundle(
    manifest: Mapping[str, object],
    centroid_x: float | None = None,
    centroid_y: float | None = None,
    manifest_path: Path | None = None,
) -> Mapping[str, object]:
    outputs = manifest.get("outputs", {})
    if outputs_complete(outputs):
        return outputs

    subswath_outputs = manifest.get("subswath_outputs", {})
    subswath_grids = manifest.get("processing", {}).get("subswath_grids", {})
    if centroid_x is not None and centroid_y is not None:
        for subswath, grid in subswath_grids.items():
            bounds = grid.get("bounds")
            candidate = subswath_outputs.get(subswath, {})
            if not bounds or not outputs_complete(candidate):
                continue
            min_x, min_y, max_x, max_y = bounds
            if min_x <= centroid_x <= max_x and min_y <= centroid_y <= max_y:
                return candidate

    for subswath in sorted(subswath_outputs):
        candidate = subswath_outputs.get(subswath, {})
        if outputs_complete(candidate):
            return candidate

    if manifest_path is not None:
        inferred = infer_outputs_from_scene_dir(manifest_path.parent)
        if outputs_complete(inferred):
            return inferred

    scene_id = manifest.get("scene_id", "<unknown>")
    raise ValueError(f"No complete raster output bundle found for {scene_id}")


def build_scene_raster_map(
    manifest_path: Path,
    centroid_x: float | None = None,
    centroid_y: float | None = None,
) -> dict[str, RasterBandSpec]:
    manifest = read_manifest(manifest_path)
    outputs = select_output_bundle(manifest, centroid_x=centroid_x, centroid_y=centroid_y, manifest_path=manifest_path)
    band_specs = {
        "vv_db": RasterBandSpec("vv_db", "vv_refined_lee_db", Path(outputs["vv_refined_lee_db"]), "identity"),
        "vh_db": RasterBandSpec("vh_db", "vh", Path(outputs["vh"]), "db"),
        "vv_glcm_mean": RasterBandSpec("vv_glcm_mean", "vv_glcm_mean", Path(outputs["vv_glcm_mean"]), "identity"),
        "vv_glcm_std": RasterBandSpec("vv_glcm_std", "vv_glcm_std", Path(outputs["vv_glcm_std"]), "identity"),
        "vv_glcm_entropy": RasterBandSpec("vv_glcm_entropy", "vv_glcm_entropy", Path(outputs["vv_glcm_entropy"]), "identity"),
        "decomp_entropy": RasterBandSpec("decomp_entropy", "decomp_entropy", Path(outputs["decomp_entropy"]), "identity"),
        "decomp_anisotropy": RasterBandSpec("decomp_anisotropy", "decomp_anisotropy", Path(outputs["decomp_anisotropy"]), "identity"),
        "decomp_alpha": RasterBandSpec("decomp_alpha", "decomp_alpha", Path(outputs["decomp_alpha"]), "identity"),
    }
    return band_specs


def centroid_patch_window(
    profile: Mapping[str, object],
    centroid_x: float,
    centroid_y: float,
    patch_size: int,
) -> PatchWindow:
    transform = profile["transform"]
    if not isinstance(transform, Affine):
        transform = Affine(*transform[:6])
    col_f, row_f = ~transform * (centroid_x, centroid_y)
    half_size = patch_size // 2
    col_off = int(round(col_f)) - half_size
    row_off = int(round(row_f)) - half_size
    width = int(profile["width"])
    height = int(profile["height"])
    touches_edge = col_off < 0 or row_off < 0 or col_off + patch_size > width or row_off + patch_size > height
    return PatchWindow(
        row_off=row_off,
        col_off=col_off,
        width=patch_size,
        height=patch_size,
        touches_edge=touches_edge,
    )


def load_reference_profile(raster_path: Path) -> dict[str, object]:
    with rio.open(raster_path) as src:
        return src.profile.copy()


def patch_profile(transform: Affine, width: int, height: int, count: int) -> dict[str, object]:
    return {
        "driver": "GTiff",
        "width": width,
        "height": height,
        "count": count,
        "dtype": "float32",
        "transform": transform,
        "crs": None,
        "nodata": np.nan,
    }


def extract_patch_stack(
    raster_map: Mapping[str, RasterBandSpec],
    reference_profile: Mapping[str, object],
    window: PatchWindow,
) -> tuple[np.ndarray, dict[str, object]]:
    band_names = list(raster_map.keys())
    stack = np.full((len(band_names), window.height, window.width), np.nan, dtype="float32")
    for band_index, band_name in enumerate(band_names):
        band = raster_map[band_name]
        with rio.open(band.path) as src:
            read_col_off = max(window.col_off, 0)
            read_row_off = max(window.row_off, 0)
            read_width = max(0, min(window.col_off + window.width, src.width) - read_col_off)
            read_height = max(0, min(window.row_off + window.height, src.height) - read_row_off)
            if read_width == 0 or read_height == 0:
                continue
            data = src.read(
                1,
                window=Window(read_col_off, read_row_off, read_width, read_height),
                boundless=False,
            ).astype("float32")
            dest_col_off = read_col_off - window.col_off
            dest_row_off = read_row_off - window.row_off
            stack[
                band_index,
                dest_row_off : dest_row_off + read_height,
                dest_col_off : dest_col_off + read_width,
            ] = data
    transform = reference_profile["transform"]
    if not isinstance(transform, Affine):
        transform = Affine(*transform[:6])
    out_transform = transform * Affine.translation(window.col_off, window.row_off)
    out_profile = patch_profile(out_transform, window.width, window.height, len(band_names))
    out_profile["crs"] = reference_profile.get("crs")
    return stack, out_profile


def rasterize_feature_mask(geometry: Mapping[str, object], profile: Mapping[str, object]) -> np.ndarray:
    mask = features.rasterize(
        [(geometry, 1)],
        out_shape=(int(profile["height"]), int(profile["width"])),
        transform=profile["transform"],
        fill=0,
        dtype="uint8",
    )
    return mask


def compute_band_statistics(stack: np.ndarray, mask: np.ndarray, band_names: Sequence[str]) -> dict[str, float | int]:
    stats: dict[str, float | int] = {}
    labeled = mask == 1
    for index, band_name in enumerate(band_names):
        values = stack[index][labeled]
        values = values[np.isfinite(values)]
        stats[f"{band_name}_valid_pixel_count"] = int(values.size)
        if values.size == 0:
            stats[f"{band_name}_mean"] = np.nan
            stats[f"{band_name}_std"] = np.nan
            stats[f"{band_name}_min"] = np.nan
            stats[f"{band_name}_max"] = np.nan
            stats[f"{band_name}_median"] = np.nan
            stats[f"{band_name}_p10"] = np.nan
            stats[f"{band_name}_p25"] = np.nan
            stats[f"{band_name}_p75"] = np.nan
            stats[f"{band_name}_p90"] = np.nan
            continue
        stats[f"{band_name}_mean"] = float(np.mean(values))
        stats[f"{band_name}_std"] = float(np.std(values))
        stats[f"{band_name}_min"] = float(np.min(values))
        stats[f"{band_name}_max"] = float(np.max(values))
        stats[f"{band_name}_median"] = float(np.median(values))
        stats[f"{band_name}_p10"] = float(np.percentile(values, 10))
        stats[f"{band_name}_p25"] = float(np.percentile(values, 25))
        stats[f"{band_name}_p75"] = float(np.percentile(values, 75))
        stats[f"{band_name}_p90"] = float(np.percentile(values, 90))
    return stats


def safe_log10(data: np.ndarray) -> np.ndarray:
    out = np.full(data.shape, np.nan, dtype="float32")
    valid = data > 0
    out[valid] = 10.0 * np.log10(data[valid])
    return out


def sample_id_for_feature(source: LayerSource, feature: Mapping[str, object]) -> str:
    properties = feature.get("properties", {})
    patch_id = properties.get("patch_id") or properties.get("patchid")
    if patch_id:
        return f"{source.scene_id}_{patch_id}"
    feature_id = properties.get("id") or properties.get("fid") or "feature"
    return f"{source.scene_id}_{feature_id}"


def derived_patch_stack(
    raster_map: Mapping[str, RasterBandSpec],
    reference_profile: Mapping[str, object],
    window: PatchWindow,
) -> tuple[np.ndarray, dict[str, object]]:
    base_names = (
        "vv_db",
        "vh_db",
        "vv_glcm_mean",
        "vv_glcm_std",
        "vv_glcm_entropy",
        "decomp_entropy",
        "decomp_anisotropy",
        "decomp_alpha",
    )
    base_stack, out_profile = extract_patch_stack({name: raster_map[name] for name in base_names}, reference_profile, window)
    name_to_array = {name: base_stack[index] for index, name in enumerate(base_names)}
    vv_db = name_to_array["vv_db"]
    vh_source = name_to_array["vh_db"]
    vh_mode = raster_map["vh_db"].mode
    vh_db = safe_log10(vh_source) if vh_mode == "db" else vh_source
    vv_vh_ratio_db = vv_db - vh_db
    vv_minus_vh_db = vv_db - vh_db
    full_stack = np.stack(
        [
            vv_db,
            vh_db,
            vv_vh_ratio_db,
            vv_minus_vh_db,
            name_to_array["vv_glcm_mean"],
            name_to_array["vv_glcm_std"],
            name_to_array["vv_glcm_entropy"],
            name_to_array["decomp_entropy"],
            name_to_array["decomp_anisotropy"],
            name_to_array["decomp_alpha"],
        ],
        axis=0,
    ).astype("float32")
    out_profile["count"] = len(BAND_ORDER)
    return full_stack, out_profile


def write_patch_raster(out_path: Path, stack: np.ndarray, profile: Mapping[str, object]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_profile = dict(profile)
    out_profile["driver"] = "GTiff"
    out_profile["dtype"] = "float32"
    out_profile["count"] = int(stack.shape[0])
    with rio.open(out_path, "w", **out_profile) as dst:
        dst.write(stack.astype("float32"))


def write_mask_raster(out_path: Path, mask: np.ndarray, profile: Mapping[str, object]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_profile = dict(profile)
    out_profile["driver"] = "GTiff"
    out_profile["dtype"] = "uint8"
    out_profile["count"] = 1
    out_profile["nodata"] = 0
    with rio.open(out_path, "w", **out_profile) as dst:
        dst.write(mask.astype("uint8"), 1)


def append_csv_row(csv_path: Path, fieldnames: Sequence[str], row: Mapping[str, object]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    exists = csv_path.exists()
    with csv_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        if not exists:
            writer.writeheader()
        writer.writerow({name: row.get(name) for name in fieldnames})


def manifest_path_for_scene(scene_dir: Path) -> Path:
    matches = sorted(scene_dir.glob("*_slc_manifest.json"))
    if not matches:
        raise FileNotFoundError(f"No manifest found in {scene_dir}")
    return matches[0]


def process_feature(
    source: LayerSource,
    feature: Mapping[str, object],
    manifest_path: Path,
    patches_root: Path,
    library_root: Path,
    patch_size: int = PATCH_SIZE,
) -> tuple[dict[str, object], dict[str, object]]:
    properties = dict(feature.get("properties", {}))
    geometry_mapping = feature["geometry"]
    geometry = shape(geometry_mapping)
    raw_label, normalized_label = resolve_feature_class(source, properties)
    centroid = geometry.centroid
    raster_map = build_scene_raster_map(manifest_path, centroid_x=centroid.x, centroid_y=centroid.y)
    reference_profile = load_reference_profile(raster_map["vv_db"].path)
    window = centroid_patch_window(reference_profile, centroid.x, centroid.y, patch_size)
    stack, patch_raster_profile = derived_patch_stack(raster_map, reference_profile, window)
    mask = rasterize_feature_mask(geometry_mapping, patch_raster_profile)
    sample_id = sample_id_for_feature(source, feature)
    image_path = patches_root / source.dataset / source.scene_id / normalized_label / f"{sample_id}_image.tif"
    mask_path = patches_root / source.dataset / source.scene_id / normalized_label / f"{sample_id}_mask.tif"
    write_patch_raster(image_path, stack, patch_raster_profile)
    write_mask_raster(mask_path, mask, patch_raster_profile)
    inventory_row = {
        "dataset": source.dataset,
        "scene_id": source.scene_id,
        "observation_id": properties.get("obs_id"),
        "area": properties.get("area"),
        "role": properties.get("role"),
        "source_shapefile_path": str(source.shapefile_path),
        "source_layer_type": source.layer_kind,
        "source_feature_id": properties.get("patch_id") or properties.get("id"),
        "raw_class_label": raw_label,
        "normalized_class_label": normalized_label,
        "sample_id": sample_id,
        "image_path": str(image_path),
        "mask_path": str(mask_path),
        "patch_width": patch_size,
        "patch_height": patch_size,
        "centroid_x": centroid.x,
        "centroid_y": centroid.y,
        "geometry_area": geometry.area,
        "edge_touch": window.touches_edge,
        "extraction_status": "ok",
    }
    library_row = dict(inventory_row)
    library_row.update(compute_band_statistics(stack, mask, BAND_ORDER))
    append_csv_row(library_root / "sar_patch_inventory.csv", inventory_row.keys(), inventory_row)
    append_csv_row(library_root / "sar_patch_library.csv", library_row.keys(), library_row)
    return inventory_row, library_row


def iter_source_features(shapefile_path: Path) -> Iterator[dict[str, object]]:
    import fiona

    with fiona.open(shapefile_path) as src:
        for feature in src:
            geometry = feature.get("geometry")
            if not geometry:
                continue
            geom = shape(geometry)
            if geom.is_empty:
                continue
            yield {
                "geometry": geometry,
                "properties": dict(feature.get("properties") or {}),
            }


def process_layer(source: LayerSource, patches_root: Path, library_root: Path, patch_size: int = PATCH_SIZE) -> int:
    manifest_path = manifest_path_for_scene(source.scene_dir)
    count = 0
    for feature in iter_source_features(source.shapefile_path):
        process_feature(source, feature, manifest_path, patches_root, library_root, patch_size=patch_size)
        count += 1
    return count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build SAR image patches and a feature library from digitised MERIA scenes.")
    parser.add_argument("--patch-size", type=int, default=PATCH_SIZE)
    parser.add_argument("--patches-root", type=Path, default=PATCHES_ROOT)
    parser.add_argument("--library-root", type=Path, default=LIBRARY_ROOT)
    parser.add_argument("--scene-root", type=Path, action="append", dest="scene_roots", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    scene_roots = tuple(args.scene_roots or SCENE_ROOTS)
    total_features = 0
    for source in discover_digitized_layers(scene_roots):
        try:
            total_features += process_layer(source, args.patches_root, args.library_root, patch_size=args.patch_size)
        except Exception as exc:
            logging.exception("Failed processing %s: %s", source.shapefile_path, exc)
    logging.info("Processed %s features", total_features)


if __name__ == "__main__":
    main()
