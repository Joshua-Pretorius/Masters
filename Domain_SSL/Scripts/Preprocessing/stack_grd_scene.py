# stack_grd_scene.py
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np, rasterio as rio
from rasterio.warp import reproject, Resampling

BIO = ["swh.tif","uo.tif","vo.tif","vsdx.tif","vsdy.tif"]

def reproject_to(path:Path, ref):
    with rio.open(path) as s:
        dst = np.zeros((ref.height, ref.width), dtype="float32")
        reproject(s.read(1).astype("float32"), dst,
                  src_transform=s.transform, src_crs=s.crs,
                  dst_transform=ref.transform, dst_crs=ref.crs, resampling=Resampling.bilinear)
        return dst

def main():
    ap = argparse.ArgumentParser("Stack GRD TC (VV/VH) + biophysical")
    ap.add_argument("--grd_tc", required=True)
    ap.add_argument("--bio_dir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    with rio.open(a.grd_tc) as ref:
        names = list(ref.descriptions or [f"B{i}" for i in range(1, ref.count+1)])
        layers = [(names[i-1], ref.read(i).astype("float32")) for i in range(1, ref.count+1)]
        # add biophysical
        for f in BIO:
            p = Path(a.bio_dir)/f
            if p.exists():
                layers.append((f[:-4], reproject_to(p, ref)))

        meta = ref.meta.copy(); meta.update(count=len(layers), dtype="float32", nodata=np.nan)
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        with rio.open(a.out, "w", **meta) as dst:
            for i,(nm,arr) in enumerate(layers, start=1):
                dst.write(arr, i); dst.set_band_description(i, nm)

        Path(str(Path(a.out).with_suffix("")) + "_channels.json").write_text(json.dumps([n for n,_ in layers], indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()