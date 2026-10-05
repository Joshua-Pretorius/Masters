#!/usr/bin/env python3
"""Build aligned, scene-tuned SAR display rasters for a prepared QGIS batch."""

from __future__ import annotations

import argparse
import json
from contextlib import ExitStack
from pathlib import Path

from analyze_sar_visual_discrimination import (
    SCENE_RULES,
    gaussian_target_margin,
    raster_map,
    rule_vote,
    safe_db,
    target_rgb,
)

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from rasterio.windows import Window


def output_profile(reference, *, count: int, dtype: str, nodata: float | int, predictor: int) -> dict:
    return {
        "driver": "GTiff",
        "width": reference.width,
        "height": reference.height,
        "count": count,
        "crs": reference.crs,
        "transform": reference.transform,
        "dtype": dtype,
        "nodata": nodata,
        "tiled": True,
        "blockxsize": 512,
        "blockysize": 512,
        "compress": "DEFLATE",
        "predictor": predictor,
        "bigtiff": "IF_SAFER",
    }


def warped(stack: ExitStack, path: Path, reference) -> WarpedVRT:
    source = stack.enter_context(rasterio.open(path))
    return stack.enter_context(
        WarpedVRT(
            source,
            crs=reference.crs,
            transform=reference.transform,
            width=reference.width,
            height=reference.height,
            src_nodata=source.nodata,
            nodata=np.nan,
            resampling=Resampling.bilinear,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-root", type=Path, required=True)
    parser.add_argument("--analysis-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--block-size", type=int, default=512)
    args = parser.parse_args()

    batch_root = args.batch_root.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    report = json.loads(args.analysis_report.read_text(encoding="utf-8"))
    scene_dir = batch_root / "processed" / "MERIA_SA_001_Durban" / "after_20190425T031055"
    mapping = raster_map(scene_dir)
    gaussian_names = tuple(report["gaussian_target_margin"]["band_order"])
    gaussian_model = {
        int(code): parameters for code, parameters in report["gaussian_target_margin"]["model"].items()
    }

    final_paths = {
        "vh_db": output_dir / "S1_20190425_vh_db_aligned_utm10m.tif",
        "ratio": output_dir / "S1_20190425_vv_minus_vh_db_aligned_utm10m.tif",
        "rgb": output_dir / "S1_20190425_target_contrast_rgb.tif",
        "margin": output_dir / "S1_20190425_target_margin.tif",
        "votes": output_dir / "S1_20190425_target_rule_votes.tif",
    }
    partial_paths = {name: path.with_suffix(".partial.tif") for name, path in final_paths.items()}
    for path in partial_paths.values():
        if path.exists():
            path.unlink()

    with ExitStack() as stack:
        reference = stack.enter_context(rasterio.open(mapping["vv_db"][0]))
        vh_source = warped(stack, mapping["vh_db"][0], reference)
        entropy_source = warped(stack, mapping["decomp_entropy"][0], reference)
        anisotropy_source = warped(stack, mapping["decomp_anisotropy"][0], reference)
        alpha_source = warped(stack, mapping["decomp_alpha"][0], reference)
        outputs = {
            "vh_db": stack.enter_context(
                rasterio.open(partial_paths["vh_db"], "w", **output_profile(reference, count=1, dtype="float32", nodata=-9999.0, predictor=3))
            ),
            "ratio": stack.enter_context(
                rasterio.open(partial_paths["ratio"], "w", **output_profile(reference, count=1, dtype="float32", nodata=-9999.0, predictor=3))
            ),
            "rgb": stack.enter_context(
                rasterio.open(partial_paths["rgb"], "w", **output_profile(reference, count=3, dtype="uint8", nodata=0, predictor=2))
            ),
            "margin": stack.enter_context(
                rasterio.open(partial_paths["margin"], "w", **output_profile(reference, count=1, dtype="float32", nodata=-9999.0, predictor=3))
            ),
            "votes": stack.enter_context(
                rasterio.open(partial_paths["votes"], "w", **output_profile(reference, count=1, dtype="uint8", nodata=255, predictor=2))
            ),
        }
        outputs["vh_db"].set_band_description(1, "VH sigma0 dB aligned to the 10 m VV AOI grid")
        outputs["ratio"].set_band_description(1, "VV dB minus VH dB")
        for index, description in enumerate(
            ("decomposition entropy", "inverted decomposition anisotropy", "VH dB band-pass"), start=1
        ):
            outputs["rgb"].set_band_description(index, description)
        outputs["margin"].set_band_description(1, "Five-band scene-tuned target margin")
        outputs["votes"].set_band_description(1, "Count of scene-tuned target rules satisfied (0-6)")
        common_tags = {
            "scene": "Sentinel-1 2019-04-25T03:10:55Z",
            "optical_task": "Optical 2019-04-25 | MERIA_SA_002 | backward to SAR",
            "purpose": "visual inspection aid; not a validated material classifier",
            "rules": json.dumps(SCENE_RULES, sort_keys=True),
        }
        for dataset in outputs.values():
            dataset.update_tags(**common_tags)

        block = max(128, int(args.block_size))
        for row_off in range(0, reference.height, block):
            height = min(block, reference.height - row_off)
            for col_off in range(0, reference.width, block):
                width = min(block, reference.width - col_off)
                window = Window(col_off, row_off, width, height)
                vv_db = reference.read(1, window=window, masked=False).astype("float32", copy=False)
                vh_db = safe_db(vh_source.read(1, window=window, masked=False))
                entropy = entropy_source.read(1, window=window, masked=False).astype("float32", copy=False)
                anisotropy = anisotropy_source.read(1, window=window, masked=False).astype("float32", copy=False)
                alpha = alpha_source.read(1, window=window, masked=False).astype("float32", copy=False)
                ratio = vv_db - vh_db
                arrays = {
                    "vv_db": vv_db,
                    "vh_db": vh_db,
                    "vv_minus_vh_db": ratio,
                    "decomp_entropy": entropy,
                    "decomp_anisotropy": anisotropy,
                    "decomp_alpha": alpha,
                }
                valid = np.logical_and.reduce([np.isfinite(arrays[name]) for name in gaussian_names])
                rgb_float = target_rgb(arrays)
                rgb = np.where(valid[..., None], np.clip(np.rint(rgb_float * 254.0) + 1, 1, 255), 0).astype("uint8")
                margin = gaussian_target_margin(arrays, gaussian_names, gaussian_model).astype("float32")
                votes = rule_vote(arrays).astype("uint8")
                outputs["vh_db"].write(np.where(valid, vh_db, -9999.0).astype("float32"), 1, window=window)
                outputs["ratio"].write(np.where(valid, ratio, -9999.0).astype("float32"), 1, window=window)
                outputs["rgb"].write(np.moveaxis(rgb, -1, 0), window=window)
                outputs["margin"].write(np.where(valid, margin, -9999.0).astype("float32"), 1, window=window)
                outputs["votes"].write(np.where(valid, votes, 255).astype("uint8"), 1, window=window)

    for name, partial in partial_paths.items():
        partial.replace(final_paths[name])

    manifest = {
        "purpose": "Scene-specific visual inspection aid; not a validated plastic classifier.",
        "reference_grid": str(mapping["vv_db"][0]),
        "analysis_report": str(args.analysis_report.resolve()),
        "outputs": {name: str(path) for name, path in final_paths.items()},
        "scene_rules": SCENE_RULES,
        "gaussian_model": gaussian_model,
    }
    manifest_path = output_dir / "visualisation_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "outputs": manifest["outputs"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
