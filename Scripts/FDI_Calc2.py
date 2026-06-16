import pathlib
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.errors import RasterioIOError

ROOT = pathlib.Path(r"D:\Masters\MARIDA\downloads")   # <— adjust if needed
S2_SCALE = 10_000.0                                   # SR scale factor
L_B4, L_B8, L_B11 = 665, 842, 1610                   # wavelengths (nm)
def load_band(path):
    with rasterio.open(path) as src:
        return src.read(1).astype(np.float32) / S2_SCALE, src.profile

def resample_to_ref(src_arr, src_prof, ref_prof):
    dst = np.empty((ref_prof["height"], ref_prof["width"]), np.float32)
    reproject(
        src_arr, dst,
        src_transform=src_prof["transform"],  src_crs=src_prof["crs"],
        dst_transform=ref_prof["transform"],  dst_crs=ref_prof["crs"],
        resampling=Resampling.bilinear,
    )
    return dst
def calc_fdi(b4, b6, b8, b11):
    rrs_nir_p = b6 + (b11 - b6) * ((L_B8 - L_B4) / (L_B11 - L_B4)) * 10.0
    return b8 - rrs_nir_p
import time
import os

def fdi_path(opt_dir):
    """Return expected *_FDI.tif path based on B08 name, or None if no B08."""
    b08 = next(opt_dir.glob("*_B08.tif"), None)
    return b08.with_name(b08.name.replace("_B08", "_FDI")) if b08 else None

def already_done(out_path):
    """True if file exists and is > 0 bytes."""
    return out_path.exists() and os.path.getsize(out_path) > 0

def process(opt_dir):
    def band_path(code):
        p = list(opt_dir.glob(f"*_{code}.tif"))
        if not p:
            raise FileNotFoundError(f"missing {code}")
        return p[0]

    p04, p06, p08, p11 = map(band_path, ("B04", "B06", "B08", "B11"))

    b4, ref_prof = load_band(p04)           # 10 m grid = reference
    b8, _       = load_band(p08)

    # resample 20 m bands to 10 m grid
    b6, prof6   = load_band(p06)
    b6          = resample_to_ref(b6, prof6, ref_prof)

    b11, prof11 = load_band(p11)
    b11         = resample_to_ref(b11, prof11, ref_prof)

    # ----- crop to common window (handles 1‑px edge diffs) ------------
    h = min(b.shape[0] for b in (b4, b6, b8, b11))
    w = min(b.shape[1] for b in (b4, b6, b8, b11))
    b4, b6, b8, b11 = (a[:h, :w] for a in (b4, b6, b8, b11))

    fdi = calc_fdi(b4, b6, b8, b11)

    out = p08.with_name(p08.name.replace("_B08", "_FDI"))
    ref_prof.update(dtype="float32", count=1, height=h, width=w)
    with rasterio.open(out, "w", **ref_prof) as dst:
        dst.write(fdi, 1)

    print("✓", out.relative_to(opt_dir.parent.parent))

if __name__ == "__main__":
    for opt in ROOT.rglob("optical"):
        out = fdi_path(opt)
        if not out:
            print("MISS ", opt)             # no B08 found
            continue
        if already_done(out):
            print("SKIP ", out.relative_to(ROOT))
            continue

        print("MAKE ", out.relative_to(ROOT))
        t0 = time.time()
        try:
            process(opt)
            dt = time.time() - t0
            print(f"DONE ", out.name, f"({dt:.1f}s)")
        except (RasterioIOError, FileNotFoundError, ValueError) as err:
            print("FAIL ", opt, "→", err)
