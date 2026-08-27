from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Mapping, Sequence

import numpy as np
import rasterio as rio
from affine import Affine
from rasterio import features
from rasterio.windows import Window
from shapely.geometry import shape

from pipeline.manifest import Manifest


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


@dataclass(frozen=True)
class PatchExtractResult:
    processed_features: int


def outputs_complete(outputs: Mapping[str, object] | None) -> bool:
    return bool(outputs) and all(outputs.get(key) for key in REQUIRED_OUTPUT_KEYS)


def infer_outputs_from_scene_dir(scene_dir: Path) -> dict[str, str | None]:
    outputs: dict[str, str | None] = {key: None for key in REQUIRED_OUTPUT_KEYS}
    for tif_path in scene_dir.glob("*.tif"):
        for key, suffixes in SCENE_TIF_PATTERNS.items():
            if tif_path.name.endswith(suffixes):
                outputs[key] = str(tif_path)
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

    for candidate in subswath_outputs.values():
        if outputs_complete(candidate):
            return candidate

    if manifest_path is not None:
        inferred = infer_outputs_from_scene_dir(manifest_path.parent)
        if outputs_complete(inferred):
            return inferred

    scene_id = manifest.get("scene_id", "<unknown>")
    raise ValueError(f"No complete raster output bundle found for {scene_id}")


def discover_scene_manifests(processed_root: Path) -> dict[str, Path]:
    manifests: dict[str, Path] = {}
    for manifest_path in sorted(processed_root.rglob("*_slc_manifest.json")):
        payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        scene_id = payload.get("scene_id")
        if scene_id:
            manifests[str(scene_id)] = manifest_path
    return manifests


def feature_files(root: Path) -> Iterator[Path]:
    patterns = ("*.geojson", "*.json", "*.shp")
    for pattern in patterns:
        for path in sorted(root.rglob(pattern)):
            if path.is_file():
                yield path


def iter_features(path: Path) -> Iterator[dict[str, object]]:
    suffix = path.suffix.lower()
    if suffix in {".geojson", ".json"}:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("type") == "FeatureCollection":
            for feature in payload.get("features", []):
                yield feature
            return
        yield payload
        return
    if suffix == ".shp":
        try:
            import fiona  # type: ignore
        except ImportError as exc:
            raise RuntimeError("Shapefile support requires fiona in the runtime image.") from exc
        with fiona.open(path) as src:
            for feature in src:
                yield {
                    "type": "Feature",
                    "geometry": feature.get("geometry"),
                    "properties": dict(feature.get("properties") or {}),
                }
        return
    raise ValueError(f"Unsupported feature file: {path}")


def scene_id_for_feature_file(root: Path, path: Path) -> str:
    relative = path.relative_to(root)
    if len(relative.parts) > 1:
        return relative.parts[0]
    return path.stem


def build_scene_raster_map(manifest_path: Path, centroid_x: float, centroid_y: float) -> dict[str, RasterBandSpec]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    outputs = select_output_bundle(manifest, centroid_x=centroid_x, centroid_y=centroid_y, manifest_path=manifest_path)
    return {
        "vv_db": RasterBandSpec("vv_db", "vv_refined_lee_db", Path(outputs["vv_refined_lee_db"]), "identity"),
        "vh_db": RasterBandSpec("vh_db", "vh", Path(outputs["vh"]), "db"),
        "vv_glcm_mean": RasterBandSpec("vv_glcm_mean", "vv_glcm_mean", Path(outputs["vv_glcm_mean"]), "identity"),
        "vv_glcm_std": RasterBandSpec("vv_glcm_std", "vv_glcm_std", Path(outputs["vv_glcm_std"]), "identity"),
        "vv_glcm_entropy": RasterBandSpec("vv_glcm_entropy", "vv_glcm_entropy", Path(outputs["vv_glcm_entropy"]), "identity"),
        "decomp_entropy": RasterBandSpec("decomp_entropy", "decomp_entropy", Path(outputs["decomp_entropy"]), "identity"),
        "decomp_anisotropy": RasterBandSpec("decomp_anisotropy", "decomp_anisotropy", Path(outputs["decomp_anisotropy"]), "identity"),
        "decomp_alpha": RasterBandSpec("decomp_alpha", "decomp_alpha", Path(outputs["decomp_alpha"]), "identity"),
    }


def load_reference_profile(raster_path: Path) -> dict[str, object]:
    with rio.open(raster_path) as src:
        return src.profile.copy()


def centroid_patch_window(profile: Mapping[str, object], centroid_x: float, centroid_y: float, patch_size: int) -> PatchWindow:
    transform = profile["transform"]
    if not isinstance(transform, Affine):
        transform = Affine(*transform[:6])
    col_f, row_f = ~transform * (centroid_x, centroid_y)
    half = patch_size // 2
    col_off = int(round(col_f)) - half
    row_off = int(round(row_f)) - half
    width = int(profile["width"])
    height = int(profile["height"])
    touches_edge = col_off < 0 or row_off < 0 or col_off + patch_size > width or row_off + patch_size > height
    return PatchWindow(row_off=row_off, col_off=col_off, width=patch_size, height=patch_size, touches_edge=touches_edge)


def patch_profile(transform: Affine, width: int, height: int, count: int, crs: object) -> dict[str, object]:
    return {
        "driver": "GTiff",
        "width": width,
        "height": height,
        "count": count,
        "dtype": "float32",
        "transform": transform,
        "crs": crs,
        "nodata": np.nan,
    }


def extract_patch_stack(raster_map: Mapping[str, RasterBandSpec], reference_profile: Mapping[str, object], window: PatchWindow) -> tuple[np.ndarray, dict[str, object]]:
    band_names = list(raster_map.keys())
    stack = np.full((len(band_names), window.height, window.width), np.nan, dtype="float32")
    for band_index, band_name in enumerate(band_names):
        with rio.open(raster_map[band_name].path) as src:
            read_col_off = max(window.col_off, 0)
            read_row_off = max(window.row_off, 0)
            read_width = max(0, min(window.col_off + window.width, src.width) - read_col_off)
            read_height = max(0, min(window.row_off + window.height, src.height) - read_row_off)
            if read_width == 0 or read_height == 0:
                continue
            data = src.read(1, window=Window(read_col_off, read_row_off, read_width, read_height)).astype("float32")
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
    return stack, patch_profile(out_transform, window.width, window.height, len(band_names), reference_profile.get("crs"))


def safe_log10(data: np.ndarray) -> np.ndarray:
    out = np.full(data.shape, np.nan, dtype="float32")
    valid = data > 0
    out[valid] = 10.0 * np.log10(data[valid])
    return out


def derived_patch_stack(
    raster_map: Mapping[str, RasterBandSpec],
    reference_profile: Mapping[str, object],
    window: PatchWindow,
    band_order: Sequence[str],
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
    base_stack, profile = extract_patch_stack({name: raster_map[name] for name in base_names}, reference_profile, window)
    name_to_array = {name: base_stack[index] for index, name in enumerate(base_names)}
    vv_db = name_to_array["vv_db"]
    vh_db = safe_log10(name_to_array["vh_db"])
    derived = {
        "vv_db": vv_db,
        "vh_db": vh_db,
        "vv_vh_ratio_db": vv_db - vh_db,
        "vv_minus_vh_db": vv_db - vh_db,
        "vv_glcm_mean": name_to_array["vv_glcm_mean"],
        "vv_glcm_std": name_to_array["vv_glcm_std"],
        "vv_glcm_entropy": name_to_array["vv_glcm_entropy"],
        "decomp_entropy": name_to_array["decomp_entropy"],
        "decomp_anisotropy": name_to_array["decomp_anisotropy"],
        "decomp_alpha": name_to_array["decomp_alpha"],
    }
    stack = np.stack([derived[name] for name in band_order], axis=0).astype("float32")
    profile["count"] = len(band_order)
    return stack, profile


def rasterize_feature_mask(geometry: Mapping[str, object], profile: Mapping[str, object]) -> np.ndarray:
    return features.rasterize(
        [(geometry, 1)],
        out_shape=(int(profile["height"]), int(profile["width"])),
        transform=profile["transform"],
        fill=0,
        dtype="uint8",
    )


def compute_band_statistics(stack: np.ndarray, mask: np.ndarray, band_names: Sequence[str]) -> dict[str, float | int]:
    stats: dict[str, float | int] = {}
    labeled = mask == 1
    for index, band_name in enumerate(band_names):
        values = stack[index][labeled]
        values = values[np.isfinite(values)]
        stats[f"{band_name}_valid_pixel_count"] = int(values.size)
        stats[f"{band_name}_mean"] = float(np.mean(values)) if values.size else np.nan
    return stats


def write_raster(out_path: Path, data: np.ndarray, profile: Mapping[str, object], *, dtype: str) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_profile = dict(profile)
    out_profile["driver"] = "GTiff"
    out_profile["dtype"] = dtype
    out_profile["count"] = int(data.shape[0]) if data.ndim == 3 else 1
    if dtype == "uint8":
        out_profile["nodata"] = 0
    with rio.open(out_path, "w", **out_profile) as dst:
        if data.ndim == 3:
            dst.write(data.astype(dtype))
        else:
            dst.write(data.astype(dtype), 1)


def append_csv_row(csv_path: Path, fieldnames: Sequence[str], row: Mapping[str, object]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    exists = csv_path.exists()
    with csv_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        if not exists:
            writer.writeheader()
        writer.writerow({name: row.get(name) for name in fieldnames})


def run_patch_extract(manifest: Manifest) -> PatchExtractResult:
    scene_manifests = discover_scene_manifests(manifest.outputs.processed_root)
    inventory_csv = manifest.outputs.patches_root / "sar_patch_inventory.csv"
    library_csv = manifest.outputs.patches_root / "sar_patch_library.csv"
    processed = 0
    seen_feature_ids: set[tuple[str, str]] = set()

    for feature_file in feature_files(manifest.inputs.shapefiles_root):
        scene_id = scene_id_for_feature_file(manifest.inputs.shapefiles_root, feature_file)
        if scene_id not in scene_manifests:
            raise FileNotFoundError(f"No processed scene manifest found for scene_id {scene_id}")
        scene_manifest_path = scene_manifests[scene_id]

        for feature in iter_features(feature_file):
            properties = dict(feature.get("properties") or {})
            stable_feature_id = properties.get("feature_uuid") or properties.get("patch_id")
            if stable_feature_id:
                dedup_key = (scene_id, str(stable_feature_id))
                if dedup_key in seen_feature_ids:
                    continue
                seen_feature_ids.add(dedup_key)
            geometry_mapping = feature["geometry"]
            geometry = shape(geometry_mapping)
            centroid = geometry.centroid
            raster_map = build_scene_raster_map(scene_manifest_path, centroid.x, centroid.y)
            reference_profile = load_reference_profile(raster_map["vv_db"].path)
            window = centroid_patch_window(reference_profile, centroid.x, centroid.y, manifest.processing.patch_size)
            stack, patch_profile_data = derived_patch_stack(
                raster_map,
                reference_profile,
                window,
                manifest.processing.sar_band_order,
            )
            mask = rasterize_feature_mask(geometry_mapping, patch_profile_data)
            normalized_class = "_".join(str(properties.get("Class", "plastic")).strip().lower().split())
            sample_id = f"{scene_id}_{properties.get('patch_id', processed + 1)}"
            image_path = manifest.outputs.patches_root / manifest.dataset_mode / scene_id / normalized_class / f"{sample_id}_image.tif"
            mask_path = manifest.outputs.patches_root / manifest.dataset_mode / scene_id / normalized_class / f"{sample_id}_mask.tif"
            write_raster(image_path, stack, patch_profile_data, dtype="float32")
            write_raster(mask_path, mask, patch_profile_data, dtype="uint8")

            inventory_row = {
                "dataset": manifest.dataset_mode,
                "scene_id": scene_id,
                "normalized_class_label": normalized_class,
                "sample_id": sample_id,
                "image_path": str(image_path),
                "mask_path": str(mask_path),
                "source_feature_file": str(feature_file),
                "edge_touch": window.touches_edge,
            }
            library_row = dict(inventory_row)
            library_row.update(compute_band_statistics(stack, mask, manifest.processing.sar_band_order))
            append_csv_row(inventory_csv, inventory_row.keys(), inventory_row)
            append_csv_row(library_csv, library_row.keys(), library_row)
            processed += 1

    return PatchExtractResult(processed_features=processed)
