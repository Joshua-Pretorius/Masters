"""Fixed-bin VV texture on the native grid. No scene-dependent statistics."""
from contextlib import ExitStack
from pathlib import Path

import numpy as np
import rasterio as rio
from numpy.lib.stride_tricks import sliding_window_view
from rasterio.windows import Window

VERSION = "vv-db-fixed32-5x5-v1"
KEYS = ("vv_glcm_mean", "vv_glcm_std", "vv_glcm_entropy")
DESCRIPTIONS = ("VV GLCM marginal mean (bin index)", "VV GLCM marginal SD (bin index)",
                "VV GLCM symmetric joint entropy (bits)")
DIRECTIONS = ((0, 1), (1, 0), (1, 1), (1, -1))
# Each 5x5 neighbourhood contains 72 undirected pairs, 144 directed pairs.
COUNT_LOG = np.zeros(73)
COUNT_LOG[1:] = np.arange(1, 73) * np.log2(np.arange(1, 73))


def grid(dataset):
    return dataset.crs, dataset.transform, dataset.width, dataset.height


def texture_tile(db, valid, owner=None):
    """Inputs include a two-pixel halo. Return NaN for incomplete/mixed windows."""
    good = sliding_window_view(valid, (5, 5)).all(axis=(-2, -1))
    if owner is not None:
        tiles = sliding_window_view(owner, (5, 5))
        good &= (tiles.min(axis=(-2, -1)) == tiles.max(axis=(-2, -1))) & (owner[2:-2, 2:-2] > 0)
    result = np.full((3, *good.shape), np.nan, dtype="float32")
    if not good.any():
        return result
    bins = np.floor(np.where(valid, db, -32) + 32).clip(0, 31).astype("uint16")
    pixels = sliding_window_view(bins, (5, 5))[good]
    codes = np.empty((len(pixels), 72), dtype="uint16")
    count = 0
    total = np.zeros(len(pixels), dtype="uint32")
    squares = np.zeros_like(total)
    off_diagonal = np.zeros(len(pixels), dtype="uint8")
    for dy, dx in DIRECTIONS:
        for y in range(5 - dy):
            for x in range(max(0, -dx), min(5, 5 - dx)):
                a, b = pixels[:, y, x], pixels[:, y + dy, x + dx]
                total += a + b
                squares += a*a + b*b
                codes[:, count] = np.minimum(a, b)*32 + np.maximum(a, b)
                off_diagonal += a != b
                count += 1
    mean = total / 144
    result[0, good] = mean
    result[1, good] = np.sqrt(np.maximum(0, squares / 144 - mean*mean))
    # Sorting unordered pair keys gives their counts. Splitting each off-diagonal
    # pair equally between (i,j) and (j,i) adds its probability to entropy in bits.
    codes.sort(axis=1)
    run = np.ones(len(pixels), dtype="uint8")
    cost = np.zeros(len(pixels))
    for i in range(1, count):
        changed = codes[:, i] != codes[:, i-1]
        cost += np.where(changed, COUNT_LOG[run], 0)
        run = np.where(changed, 1, run + 1)
    result[2, good] = np.log2(count) + (off_diagonal - cost - COUNT_LOG[run]) / count
    return result


def generate(source, owner, destinations, signature, policy):
    with ExitStack() as stack:
        src = stack.enter_context(rio.open(source))
        ownership = stack.enter_context(rio.open(owner)) if owner else None
        profile = dict(driver="GTiff", width=src.width, height=src.height, crs=src.crs,
                       transform=src.transform, count=1, dtype="float32", nodata=np.nan,
                       tiled=True, blockxsize=128, blockysize=128, compress="deflate",
                       predictor=3, BIGTIFF="IF_SAFER")
        outputs = [stack.enter_context(rio.open(p, "w", **profile)) for p in destinations]
        for dst, key, description in zip(outputs, KEYS, DESCRIPTIONS):
            dst.set_band_description(1, description)
            dst.update_tags(glcm_version=VERSION, glcm_metric=key, input_signature=signature,
                            source=Path(source).name, seam_policy=policy,
                            quantization="32 fixed 1 dB bins, clipped at -32 and 0 dB",
                            neighbourhood="5x5 native pixels, pooled symmetric 1-pixel pairs in 4 directions")
        valid_pixels = 0
        for _, w in outputs[0].block_windows(1):
            halo = Window(w.col_off-2, w.row_off-2, w.width+4, w.height+4)
            raw = src.read(1, window=halo, boundless=True, masked=True)
            valid = ~np.ma.getmaskarray(raw) & np.isfinite(raw.data)
            owners = None
            if ownership:
                owners = ownership.read(1, window=halo, boundless=True, fill_value=0)
                if np.any(valid & ((owners < 1) | (owners > 3))):
                    raise ValueError(f"Missing/invalid sub-swath ownership for valid VV: {source}, {w}")
            tile = texture_tile(raw.data, valid, owners)
            valid_pixels += np.isfinite(tile[0]).sum()
            for dst, band in zip(outputs, tile):
                dst.write(band, 1, window=w)
        if not valid_pixels:
            raise ValueError(f"No valid full 5x5 texture windows: {source}")

