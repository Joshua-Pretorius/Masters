from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
import rasterio as rio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT

from pipeline.manifest import Manifest


@dataclass(frozen=True)
class PatchStackResult:
    processed_patches: int


def append_csv_row(csv_path: Path, fieldnames: Sequence[str], row: dict[str, object]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    exists = csv_path.exists()
    with csv_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        if not exists:
            writer.writeheader()
        writer.writerow({name: row.get(name) for name in fieldnames})


def reproject_band_to_patch(source_path: Path, reference: rio.DatasetReader) -> np.ndarray:
    with rio.open(source_path) as src:
        with WarpedVRT(
            src,
            crs=reference.crs,
            transform=reference.transform,
            width=reference.width,
            height=reference.height,
            resampling=Resampling.bilinear,
        ) as vrt:
            return vrt.read(1).astype("float32")


def write_stack(out_path: Path, stack: np.ndarray, reference: rio.DatasetReader) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    profile = reference.profile.copy()
    profile.update(driver="GTiff", dtype="float32", count=int(stack.shape[0]), nodata=np.nan)
    with rio.open(out_path, "w", **profile) as dst:
        dst.write(stack.astype("float32"))


def run_patch_stack(manifest: Manifest) -> PatchStackResult:
    inventory_csv = manifest.outputs.patches_root / "sar_patch_inventory.csv"
    if not inventory_csv.exists():
        raise FileNotFoundError(f"Missing patch inventory: {inventory_csv}")

    catalog_csv = manifest.outputs.stacks_root / "stack_catalog.csv"
    processed = 0
    channels = list(manifest.processing.sar_band_order) + list(manifest.processing.biophysical_bands)

    with inventory_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            image_path = Path(row["image_path"])
            scene_id = row["scene_id"]
            label = row["normalized_class_label"]
            sample_id = row["sample_id"]
            stack_path = manifest.outputs.stacks_root / row["dataset"] / scene_id / label / f"{sample_id}_stack.tif"
            channels_path = manifest.outputs.stacks_root / row["dataset"] / scene_id / label / f"{sample_id}_channels.json"
            with rio.open(image_path) as sar_patch:
                sar_arrays = sar_patch.read().astype("float32")
                if sar_arrays.shape[0] != len(manifest.processing.sar_band_order):
                    raise ValueError(f"Unexpected SAR band count for {image_path}")
                bio_arrays = []
                for band_name in manifest.processing.biophysical_bands:
                    band_path = Path(manifest.inputs.biophysical_root or "") / scene_id / f"{band_name}.tif"
                    if not band_path.exists():
                        raise FileNotFoundError(f"Missing biophysical raster for {scene_id}: {band_path}")
                    bio_arrays.append(reproject_band_to_patch(band_path, sar_patch))
                full_stack = np.concatenate([sar_arrays, np.stack(bio_arrays, axis=0)], axis=0)
                write_stack(stack_path, full_stack, sar_patch)
            channels_path.write_text(json.dumps(channels, indent=2), encoding="utf-8")
            catalog_row = {
                "scene_id": scene_id,
                "sample_id": sample_id,
                "stack_path": str(stack_path),
                "channels_path": str(channels_path),
            }
            append_csv_row(catalog_csv, catalog_row.keys(), catalog_row)
            processed += 1

    (manifest.outputs.stacks_root / "stack_dataset_manifest.json").write_text(
        json.dumps(
            {
                "run_id": manifest.run_id,
                "channels": channels,
                "processed_patches": processed,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return PatchStackResult(processed_patches=processed)
