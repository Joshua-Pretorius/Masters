#!/usr/bin/env python3
"""Rank SAR display bands against local annotation classes and render previews.

The annotations are used only to tune a scene-specific visualisation.  This
script does not alter annotation geometry or claim material classification.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from collections import Counter
from pathlib import Path


RASTERIO_PACKAGE = Path(
    r"C:\Users\Joshua Pretorius\AppData\Local\Programs\Python\Python311"
    r"\Lib\site-packages\rasterio"
)
os.environ["PROJ_DATA"] = str(RASTERIO_PACKAGE / "proj_data")
os.environ["PROJ_LIB"] = str(RASTERIO_PACKAGE / "proj_data")
os.environ["GDAL_DATA"] = str(RASTERIO_PACKAGE / "gdal_data")

import fiona
import matplotlib
import numpy as np
import rasterio
from matplotlib import pyplot as plt
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.vrt import WarpedVRT
from rasterio.windows import Window, from_bounds
from shapely.geometry import shape
from shapely.ops import transform, unary_union
from pyproj import Transformer


matplotlib.use("Agg")


CLASS_CODES = {
    "plastic": 1,
    "ship": 2,
    "calm_water": 3,
    "open_ocean": 3,
    "other": 4,
}

SCENE_RULES = {
    "vh_db_min": -29.32,
    "vh_db_max": -24.50,
    "decomp_entropy_min": 0.46,
    "decomp_anisotropy_max": 0.81,
    "decomp_alpha_min": 13.40,
    "vv_minus_vh_db_max": 9.50,
}


def rounded_window(bounds: tuple[float, float, float, float], dataset, pad_m: float) -> Window:
    left, bottom, right, top = bounds
    raw = from_bounds(left - pad_m, bottom - pad_m, right + pad_m, top + pad_m, dataset.transform)
    col0 = max(0, math.floor(raw.col_off))
    row0 = max(0, math.floor(raw.row_off))
    col1 = min(dataset.width, math.ceil(raw.col_off + raw.width))
    row1 = min(dataset.height, math.ceil(raw.row_off + raw.height))
    return Window(col0, row0, col1 - col0, row1 - row0)


def read_annotations(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with fiona.open(path, layer="annotations") as source:
        for feature in source:
            class_name = feature["properties"].get("Class")
            if class_name not in CLASS_CODES or not feature["geometry"]:
                continue
            rows.append(
                {
                    "fid": str(feature.id),
                    "patch_id": feature["properties"].get("patch_id"),
                    "class_name": class_name,
                    "geometry": shape(feature["geometry"]),
                }
            )
    return rows


def read_highlights(path: Path) -> list[object]:
    transformer = Transformer.from_crs(4326, 32736, always_xy=True).transform
    with fiona.open(path) as source:
        return [transform(transformer, shape(feature["geometry"])) for feature in source]


def raster_map(scene_dir: Path) -> dict[str, tuple[Path, str]]:
    prefix = "MERIA_SA_001_Durban_after_20190425T031055"
    mapping = {
        "vv_db": (scene_dir / f"{prefix}_slc_utm_vv_refined_lee_db.tif", "identity"),
        "vh_db": (scene_dir / f"{prefix}_slc_native_vh.tif", "db"),
        "vv_minus_vh_db": (scene_dir / f"{prefix}_slc_native_vh.tif", "derived_ratio"),
        "vv_glcm_mean_db": (scene_dir / f"{prefix}_slc_native_vv_glcm_mean.tif", "db"),
        "vv_glcm_std_db": (scene_dir / f"{prefix}_slc_native_vv_glcm_std.tif", "db"),
        "vv_glcm_entropy": (scene_dir / f"{prefix}_slc_native_vv_glcm_entropy.tif", "identity"),
        "decomp_entropy": (scene_dir / f"{prefix}_slc_native_decomp_entropy.tif", "identity"),
        "decomp_anisotropy": (scene_dir / f"{prefix}_slc_native_decomp_anisotropy.tif", "identity"),
        "decomp_alpha": (scene_dir / f"{prefix}_slc_native_decomp_alpha.tif", "identity"),
    }
    missing = [str(path) for path, _ in mapping.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing input rasters: {missing}")
    return mapping


def read_aligned(path: Path, reference, window: Window, resampling=Resampling.bilinear) -> np.ndarray:
    with rasterio.open(path) as source:
        same_grid = (
            source.crs == reference.crs
            and source.transform == reference.transform
            and source.width == reference.width
            and source.height == reference.height
        )
        if same_grid:
            return source.read(1, window=window, masked=False).astype("float32", copy=False)
        with WarpedVRT(
            source,
            crs=reference.crs,
            transform=reference.transform,
            width=reference.width,
            height=reference.height,
            src_nodata=source.nodata,
            nodata=np.nan,
            resampling=resampling,
        ) as vrt:
            return vrt.read(1, window=window, masked=False).astype("float32", copy=False)


def safe_db(values: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(values > 0, 10.0 * np.log10(values), np.nan).astype("float32")


def finite_percentiles(values: np.ndarray, percentiles: tuple[float, ...]) -> list[float | None]:
    finite = values[np.isfinite(values)]
    if not finite.size:
        return [None for _ in percentiles]
    return [float(value) for value in np.percentile(finite, percentiles)]


def auc_greater(target: np.ndarray, background: np.ndarray) -> float | None:
    target = target[np.isfinite(target)]
    background = background[np.isfinite(background)]
    if not target.size or not background.size:
        return None
    values = np.concatenate([target, background])
    labels = np.concatenate([np.ones(target.size, dtype=np.uint8), np.zeros(background.size, dtype=np.uint8)])
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(values.size, dtype=np.float64)
    sorted_values = values[order]
    start = 0
    while start < values.size:
        end = start + 1
        while end < values.size and sorted_values[end] == sorted_values[start]:
            end += 1
        ranks[order[start:end]] = 0.5 * (start + 1 + end)
        start = end
    rank_sum = ranks[labels == 1].sum()
    return float((rank_sum - target.size * (target.size + 1) / 2.0) / (target.size * background.size))


def best_threshold(target: np.ndarray, background: np.ndarray) -> dict[str, float | str] | None:
    target = target[np.isfinite(target)]
    background = background[np.isfinite(background)]
    if not target.size or not background.size:
        return None
    combined = np.concatenate([target, background])
    candidates = np.unique(np.percentile(combined, np.linspace(1, 99, 199)))
    best: dict[str, float | str] | None = None
    for direction in ("greater", "less"):
        for threshold in candidates:
            if direction == "greater":
                tpr = float(np.mean(target >= threshold))
                fpr = float(np.mean(background >= threshold))
            else:
                tpr = float(np.mean(target <= threshold))
                fpr = float(np.mean(background <= threshold))
            youden = tpr - fpr
            if best is None or youden > float(best["youden_j"]):
                best = {
                    "direction": direction,
                    "threshold": float(threshold),
                    "target_recall": tpr,
                    "background_false_positive_rate": fpr,
                    "youden_j": youden,
                }
    return best


def stratified_indices(labels: np.ndarray, max_per_class: int, seed: int) -> dict[int, tuple[np.ndarray, np.ndarray]]:
    rng = np.random.default_rng(seed)
    indices: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    for code in sorted(set(CLASS_CODES.values())):
        rows, cols = np.where(labels == code)
        if rows.size > max_per_class:
            selected = rng.choice(rows.size, max_per_class, replace=False)
            rows, cols = rows[selected], cols[selected]
        indices[code] = (rows, cols)
    return indices


def stretch(values: np.ndarray, low: float, high: float, invert: bool = False) -> np.ndarray:
    if not np.isfinite(low) or not np.isfinite(high) or high <= low:
        return np.zeros(values.shape, dtype="float32")
    scaled = np.clip((values - low) / (high - low), 0, 1)
    scaled[~np.isfinite(values)] = 0
    return (1.0 - scaled if invert else scaled).astype("float32")


def rule_vote(arrays: dict[str, np.ndarray]) -> np.ndarray:
    return (
        (arrays["vh_db"] >= SCENE_RULES["vh_db_min"]).astype("uint8")
        + (arrays["vh_db"] <= SCENE_RULES["vh_db_max"]).astype("uint8")
        + (arrays["decomp_entropy"] >= SCENE_RULES["decomp_entropy_min"]).astype("uint8")
        + (arrays["decomp_anisotropy"] <= SCENE_RULES["decomp_anisotropy_max"]).astype("uint8")
        + (arrays["decomp_alpha"] >= SCENE_RULES["decomp_alpha_min"]).astype("uint8")
        + (arrays["vv_minus_vh_db"] <= SCENE_RULES["vv_minus_vh_db_max"]).astype("uint8")
    )


def fit_diagonal_gaussian(
    sampled: dict[str, dict[int, np.ndarray]], names: tuple[str, ...]
) -> dict[int, dict[str, list[float]]]:
    model: dict[int, dict[str, list[float]]] = {}
    for code in sorted(set(CLASS_CODES.values())):
        matrix = np.column_stack([sampled[name][code] for name in names]).astype("float64")
        valid = np.all(np.isfinite(matrix), axis=1)
        matrix = matrix[valid]
        if not matrix.size:
            raise RuntimeError(f"No finite samples for class code {code}")
        lower = np.percentile(matrix, 2, axis=0)
        upper = np.percentile(matrix, 98, axis=0)
        clipped = np.clip(matrix, lower, upper)
        center = np.median(clipped, axis=0)
        q25, q75 = np.percentile(clipped, [25, 75], axis=0)
        scale = np.maximum((q75 - q25) / 1.349, 1e-4)
        model[code] = {"center": center.tolist(), "scale": scale.tolist()}
    return model


def gaussian_target_margin(
    arrays: dict[str, np.ndarray], names: tuple[str, ...], model: dict[int, dict[str, list[float]]]
) -> np.ndarray:
    stack = np.stack([arrays[name] for name in names], axis=-1).astype("float32")
    likelihoods: dict[int, np.ndarray] = {}
    for code, parameters in model.items():
        center = np.asarray(parameters["center"], dtype="float32")
        scale = np.asarray(parameters["scale"], dtype="float32")
        z = (stack - center) / scale
        likelihoods[code] = -0.5 * np.sum(z * z, axis=-1) - float(np.sum(np.log(scale)))
    return likelihoods[1] - np.maximum.reduce([likelihoods[2], likelihoods[3], likelihoods[4]])


def read_selected_arrays(
    mapping: dict[str, tuple[Path, str]], reference, window: Window
) -> dict[str, np.ndarray]:
    result: dict[str, np.ndarray] = {}
    result["vv_db"] = read_aligned(mapping["vv_db"][0], reference, window)
    vh_linear = read_aligned(mapping["vh_db"][0], reference, window)
    result["vh_db"] = safe_db(vh_linear)
    result["vv_minus_vh_db"] = result["vv_db"] - result["vh_db"]
    for name in ("decomp_entropy", "decomp_anisotropy", "decomp_alpha"):
        result[name] = read_aligned(mapping[name][0], reference, window)
    return result


def target_rgb(arrays: dict[str, np.ndarray]) -> np.ndarray:
    entropy = stretch(arrays["decomp_entropy"], 0.30, 0.72)
    low_anisotropy = stretch(arrays["decomp_anisotropy"], 0.58, 0.91, invert=True)
    vh = arrays["vh_db"]
    vh_low = stretch(vh, SCENE_RULES["vh_db_min"] - 2.0, SCENE_RULES["vh_db_min"] + 2.0)
    vh_high_reject = stretch(vh, SCENE_RULES["vh_db_max"] - 2.0, SCENE_RULES["vh_db_max"] + 2.0, invert=True)
    vh_bandpass = np.minimum(vh_low, vh_high_reject)
    return np.dstack([entropy, low_anisotropy, vh_bandpass])


def render_composite_sheet(
    output_path: Path,
    reference,
    highlights: list[object],
    annotations: list[dict[str, object]],
    mapping: dict[str, tuple[Path, str]],
    threshold: int,
    gaussian_names: tuple[str, ...],
    gaussian_model: dict[int, dict[str, list[float]]],
    gaussian_threshold: float,
) -> None:
    regions: list[tuple[str, object]] = [
        (f"highlight corridor {index + 1}", geometry) for index, geometry in enumerate(highlights)
    ]
    for class_name in ("ship", "calm_water", "open_ocean", "other"):
        geometries = [row["geometry"] for row in annotations if row["class_name"] == class_name]
        if geometries:
            regions.append((class_name.replace("_", " "), unary_union(geometries)))
    fig, axes = plt.subplots(len(regions), 4, figsize=(15, 3.4 * len(regions)))
    for row_index, (region_name, geometry) in enumerate(regions):
        window = rounded_window(geometry.bounds, reference, pad_m=350)
        arrays = read_selected_arrays(mapping, reference, window)
        rgb = target_rgb(arrays)
        vote = rule_vote(arrays)
        mask = vote >= threshold
        gaussian_score = gaussian_target_margin(arrays, gaussian_names, gaussian_model)
        base = stretch(arrays["vv_db"], -24.0, -15.0)
        overlay = np.dstack([base, base, base])
        overlay[mask] = 0.35 * overlay[mask] + 0.65 * np.array([1.0, 0.1, 0.8], dtype="float32")
        axes[row_index, 0].imshow(rgb)
        axes[row_index, 1].imshow(vote, cmap="magma", vmin=0, vmax=6)
        axes[row_index, 2].imshow(gaussian_score, cmap="magma", vmin=gaussian_threshold - 8, vmax=gaussian_threshold + 8)
        axes[row_index, 3].imshow(overlay)
        for col_index, title in enumerate((
            "RGB target contrast",
            "rule votes (0-6)",
            "Gaussian target margin",
            f"automatic candidates >= {threshold}",
        )):
            axes[row_index, col_index].set_axis_off()
            if row_index == 0:
                axes[row_index, col_index].set_title(title, fontsize=10)
        axes[row_index, 0].text(
            0.01,
            0.98,
            region_name,
            transform=axes[row_index, 0].transAxes,
            va="top",
            ha="left",
            fontsize=9,
            color="white",
            bbox={"facecolor": "black", "alpha": 0.65, "pad": 2},
        )
    fig.suptitle("25 Apr 2019 scene-tuned visualisations — highlight geometry not displayed", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.985))
    fig.savefig(output_path, dpi=180, facecolor="white")
    plt.close(fig)


def render_contact_sheet(
    output_path: Path,
    reference,
    highlights: list[object],
    annotations: list[dict[str, object]],
    mapping: dict[str, tuple[Path, str]],
    display_ranges: dict[str, list[float | None]],
    ranked_names: list[str],
) -> None:
    regions: list[tuple[str, object]] = [
        (f"highlight corridor {index + 1}", geometry) for index, geometry in enumerate(highlights)
    ]
    for class_name in ("ship", "calm_water", "open_ocean", "other"):
        geometries = [row["geometry"] for row in annotations if row["class_name"] == class_name]
        if geometries:
            regions.append((class_name.replace("_", " "), unary_union(geometries)))
    names = ranked_names[:6]
    fig, axes = plt.subplots(len(regions), len(names), figsize=(3.0 * len(names), 2.8 * len(regions)))
    if len(regions) == 1:
        axes = np.asarray([axes])
    vv_cache: dict[tuple[int, int, int, int], np.ndarray] = {}
    for row_index, (region_name, geometry) in enumerate(regions):
        window = rounded_window(geometry.bounds, reference, pad_m=600)
        cache_key = (int(window.col_off), int(window.row_off), int(window.width), int(window.height))
        for col_index, name in enumerate(names):
            path, mode = mapping[name]
            values = read_aligned(path, reference, window)
            if mode == "db":
                values = safe_db(values)
            elif mode == "derived_ratio":
                if cache_key not in vv_cache:
                    vv_cache[cache_key] = read_aligned(mapping["vv_db"][0], reference, window)
                values = vv_cache[cache_key] - safe_db(values)
            low, high = display_ranges[name][0], display_ranges[name][-1]
            image = stretch(values, float(low), float(high)) if low is not None and high is not None else np.zeros(values.shape)
            axes[row_index, col_index].imshow(image, cmap="gray", vmin=0, vmax=1)
            axes[row_index, col_index].set_axis_off()
            if row_index == 0:
                axes[row_index, col_index].set_title(name.replace("_", "\n"), fontsize=9)
            if col_index == 0:
                axes[row_index, col_index].text(
                    0.01,
                    0.98,
                    region_name,
                    transform=axes[row_index, col_index].transAxes,
                    va="top",
                    ha="left",
                    fontsize=9,
                    color="white",
                    bbox={"facecolor": "black", "alpha": 0.65, "pad": 2},
                )
    fig.suptitle("25 Apr 2019 Sentinel-1 candidate displays — no annotation overlay", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.98))
    fig.savefig(output_path, dpi=160, facecolor="white")
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-per-class", type=int, default=60_000)
    parser.add_argument("--seed", type=int, default=20260915)
    args = parser.parse_args()

    batch_root = args.batch_root.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    scene_dir = batch_root / "processed" / "MERIA_SA_001_Durban" / "after_20190425T031055"
    annotations_path = (
        scene_dir
        / "digitising"
        / "MERIA_SA_002_before_20190425T031055"
        / "task.gpkg"
    )
    highlight_path = batch_root / "highlight.shp"
    mapping = raster_map(scene_dir)
    annotations = read_annotations(annotations_path)
    highlights = read_highlights(highlight_path)
    class_counts = Counter(row["class_name"] for row in annotations)

    with rasterio.open(mapping["vv_db"][0]) as reference:
        analysis_geometry = unary_union([row["geometry"] for row in annotations])
        window = rounded_window(analysis_geometry.bounds, reference, pad_m=300)
        window_transform = reference.window_transform(window)
        labels = rasterize(
            [(row["geometry"], CLASS_CODES[row["class_name"]]) for row in annotations],
            out_shape=(int(window.height), int(window.width)),
            transform=window_transform,
            fill=0,
            dtype="uint8",
        )
        indices = stratified_indices(labels, args.max_per_class, args.seed)
        sampled: dict[str, dict[int, np.ndarray]] = {}
        display_ranges: dict[str, list[float | None]] = {}
        vv_window: np.ndarray | None = None
        for name, (path, mode) in mapping.items():
            values = read_aligned(path, reference, window)
            if name == "vv_db":
                vv_window = values
            if mode == "db":
                values = safe_db(values)
            elif mode == "derived_ratio":
                if vv_window is None:
                    vv_window = read_aligned(mapping["vv_db"][0], reference, window)
                values = vv_window - safe_db(values)
            sampled[name] = {code: values[rows, cols] for code, (rows, cols) in indices.items()}
            pooled = np.concatenate([part for part in sampled[name].values() if part.size])
            display_ranges[name] = finite_percentiles(pooled, (2, 25, 50, 75, 98))
            del values

        report_bands: dict[str, object] = {}
        for name, by_code in sampled.items():
            target = by_code[1]
            distractors = np.concatenate([by_code[code] for code in (2, 3, 4) if by_code[code].size])
            aucs: dict[str, float | None] = {}
            for label, code in (("ship", 2), ("water", 3), ("other", 4), ("all_distractors", 0)):
                background = distractors if code == 0 else by_code[code]
                auc = auc_greater(target, background)
                aucs[label] = None if auc is None else max(auc, 1.0 - auc)
            direction_auc = auc_greater(target, distractors)
            report_bands[name] = {
                "display_percentiles_p02_p25_p50_p75_p98": display_ranges[name],
                "target_percentiles_p05_p25_p50_p75_p95": finite_percentiles(target, (5, 25, 50, 75, 95)),
                "ship_percentiles_p05_p25_p50_p75_p95": finite_percentiles(by_code[2], (5, 25, 50, 75, 95)),
                "water_percentiles_p05_p25_p50_p75_p95": finite_percentiles(by_code[3], (5, 25, 50, 75, 95)),
                "other_percentiles_p05_p25_p50_p75_p95": finite_percentiles(by_code[4], (5, 25, 50, 75, 95)),
                "absolute_auc": aucs,
                "target_is_brighter": None if direction_auc is None else direction_auc >= 0.5,
                "best_balanced_threshold_vs_all_distractors": best_threshold(target, distractors),
            }

        ranked = sorted(
            report_bands,
            key=lambda name: (
                report_bands[name]["absolute_auc"]["all_distractors"] or 0,
                min(
                    value or 0
                    for key, value in report_bands[name]["absolute_auc"].items()
                    if key != "all_distractors"
                ),
            ),
            reverse=True,
        )
        vote_by_code = {
            code: rule_vote({name: sampled[name][code] for name in (
                "vh_db",
                "decomp_entropy",
                "decomp_anisotropy",
                "decomp_alpha",
                "vv_minus_vh_db",
            )})
            for code in sorted(set(CLASS_CODES.values()))
        }
        distractor_votes = np.concatenate([vote_by_code[code] for code in (2, 3, 4)])
        vote_thresholds = []
        for threshold in range(1, 7):
            target_recall = float(np.mean(vote_by_code[1] >= threshold))
            false_positive_rate = float(np.mean(distractor_votes >= threshold))
            vote_thresholds.append(
                {
                    "threshold": threshold,
                    "target_recall": target_recall,
                    "background_false_positive_rate": false_positive_rate,
                    "youden_j": target_recall - false_positive_rate,
                    "ship_false_positive_rate": float(np.mean(vote_by_code[2] >= threshold)),
                    "water_false_positive_rate": float(np.mean(vote_by_code[3] >= threshold)),
                    "other_false_positive_rate": float(np.mean(vote_by_code[4] >= threshold)),
                }
            )
        selected_vote = max(vote_thresholds, key=lambda row: row["youden_j"])
        gaussian_names = (
            "vh_db",
            "decomp_entropy",
            "decomp_anisotropy",
            "decomp_alpha",
            "vv_minus_vh_db",
        )
        gaussian_model = fit_diagonal_gaussian(sampled, gaussian_names)
        gaussian_by_code = {
            code: gaussian_target_margin(
                {name: sampled[name][code] for name in gaussian_names},
                gaussian_names,
                gaussian_model,
            )
            for code in sorted(set(CLASS_CODES.values()))
        }
        gaussian_distractors = np.concatenate([gaussian_by_code[code] for code in (2, 3, 4)])
        gaussian_threshold = best_threshold(gaussian_by_code[1], gaussian_distractors)
        gaussian_auc = auc_greater(gaussian_by_code[1], gaussian_distractors)
        report = {
            "purpose": "Scene-specific visual discrimination only; not a validated plastic classifier.",
            "scene": "Sentinel-1 2019-04-25T03:10:55Z",
            "optical_task": "Optical 2019-04-25 | MERIA_SA_002 | backward to SAR",
            "reference_grid": {
                "crs": str(reference.crs),
                "pixel_size_m": [reference.transform.a, abs(reference.transform.e)],
                "shape": [reference.height, reference.width],
            },
            "annotation_feature_counts": dict(class_counts),
            "sampled_pixel_counts": {str(code): int(rows.size) for code, (rows, _) in indices.items()},
            "ranking": ranked,
            "bands": report_bands,
            "scene_rule": {
                "rules": SCENE_RULES,
                "vote_thresholds": vote_thresholds,
                "selected": selected_vote,
            },
            "gaussian_target_margin": {
                "band_order": gaussian_names,
                "model": gaussian_model,
                "auc_target_greater_than_all_distractors": gaussian_auc,
                "threshold": gaussian_threshold,
                "target_percentiles_p02_p25_p50_p75_p98": finite_percentiles(
                    gaussian_by_code[1], (2, 25, 50, 75, 98)
                ),
                "distractor_percentiles_p02_p25_p50_p75_p98": finite_percentiles(
                    gaussian_distractors, (2, 25, 50, 75, 98)
                ),
                "warning": "Descriptive in-sample scene tuning; not an independent accuracy estimate.",
            },
        }
        report_path = output_dir / "sar_visual_discrimination_report.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        render_contact_sheet(
            output_dir / "sar_candidate_contact_sheet.png",
            reference,
            highlights,
            annotations,
            mapping,
            display_ranges,
            ranked,
        )
        render_composite_sheet(
            output_dir / "sar_composite_contact_sheet.png",
            reference,
            highlights,
            annotations,
            mapping,
            int(selected_vote["threshold"]),
            gaussian_names,
            gaussian_model,
            float(gaussian_threshold["threshold"]),
        )

    print(json.dumps({"report": str(report_path), "ranking": ranked, "class_counts": dict(class_counts)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
