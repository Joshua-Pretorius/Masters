#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import rasterio
from scipy.ndimage import uniform_filter


def weak_boxcar3x3(arr: np.ma.MaskedArray) -> np.ndarray:
    data = arr.filled(np.nan).astype("float32")
    valid = np.isfinite(data)
    values = np.where(valid, data, 0.0).astype("float32")
    weights = valid.astype("float32")

    summed = uniform_filter(values, size=3, mode="nearest") * 9.0
    counts = uniform_filter(weights, size=3, mode="nearest") * 9.0
    out = np.full(data.shape, np.nan, dtype="float32")
    np.divide(summed, counts, out=out, where=counts > 0)
    out[~valid] = np.nan
    return out


def filtered_path(src: Path, suffix: str) -> Path:
    return src.with_name(src.stem + f"_{suffix}" + src.suffix)


def filter_raster(src: Path, suffix: str, overwrite: bool = False) -> Path:
    dst = filtered_path(src, suffix)
    if dst.exists() and not overwrite:
        print(f"[skip] {dst}")
        return dst

    with rasterio.open(src) as ds:
        profile = ds.profile.copy()
        profile.update(
            dtype="float32",
            compress="deflate",
            predictor=2,
            tiled=True,
            blockxsize=min(512, ds.width),
            blockysize=min(512, ds.height),
            bigtiff="IF_SAFER",
        )
        descriptions = ds.descriptions
        tags = ds.tags()

        with rasterio.open(dst, "w", **profile) as out_ds:
            out_ds.update_tags(**tags)
            out_ds.update_tags(speckle_filter=suffix, source_product=str(src))
            for band in range(1, ds.count + 1):
                filtered = weak_boxcar3x3(ds.read(band, masked=True))
                out_ds.write(filtered, band)
                desc = descriptions[band - 1] or f"band_{band}"
                out_ds.set_band_description(band, f"{desc}_{suffix}")

    print(f"[ok] {dst}")
    return dst


def main() -> None:
    parser = argparse.ArgumentParser(description="Create weak 3x3 boxcar-filtered sigma0 GeoTIFF products.")
    parser.add_argument(
        "--root",
        default="/mnt/d/Masters/Domain_SSL/PreProccess/ocean_scan_2017",
        help="Root containing final SLC outputs.",
    )
    parser.add_argument("--pattern", default="aoi_*/2017-*/final/slc_IW*_sigma0_tc.tif")
    parser.add_argument("--suffix", default="weak_boxcar3x3")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    sources = sorted(root.glob(args.pattern))
    sources = [src for src in sources if not src.stem.endswith(f"_{args.suffix}")]
    if not sources:
        raise RuntimeError(f"No sigma0 products matched {root / args.pattern}")

    for src in sources:
        filter_raster(src, args.suffix, overwrite=args.overwrite)


if __name__ == "__main__":
    main()
