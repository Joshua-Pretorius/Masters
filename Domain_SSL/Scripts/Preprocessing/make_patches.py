# make_patches.py
import argparse, os, numpy as np, rasterio as rio
from rasterio.windows import Window

def save_patch(arr, out_dir, base, r, c):
    np.save(os.path.join(out_dir, f"{base}_r{r:05d}_c{c:05d}.npy"), arr)

def main():
    ap = argparse.ArgumentParser("Tile a stack into patches")
    ap.add_argument("--stack", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--patch", type=int, default=256)
    ap.add_argument("--stride", type=int, default=256)   # set <patch for overlap
    ap.add_argument("--min-coverage", type=float, default=0.85)  # valid-pixel fraction
    a = ap.parse_args()

    os.makedirs(a.out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(a.stack))[0]

    with rio.open(a.stack) as ds:
        H, W = ds.height, ds.width
        for r in range(0, H - a.patch + 1, a.stride):
            for c in range(0, W - a.patch + 1, a.stride):
                win = Window(c, r, a.patch, a.patch)
                arr = ds.read(window=win).astype("float32")  # (bands, h, w)
                if np.isfinite(arr).mean() >= a.min_coverage:
                    save_patch(arr, a.out_dir, base, r, c)

if __name__ == "__main__":
    main()