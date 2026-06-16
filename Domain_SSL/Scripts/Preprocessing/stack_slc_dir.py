# stack_slc_dir.py
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import rasterio as rio
from rasterio.warp import reproject, Resampling

BIO = ["swh.tif","uo.tif","vo.tif","vsdx.tif","vsdy.tif"]

def reproject_to(path:Path, ref)->np.ndarray:
    with rio.open(path) as src:
        dst = np.zeros((ref.height, ref.width), dtype="float32")
        reproject(src.read(1).astype("float32"), dst,
                  src_transform=src.transform, src_crs=src.crs,
                  dst_transform=ref.transform,  dst_crs=ref.crs,
                  resampling=Resampling.bilinear)
        return dst

def add_from_dim(dim_path:Path, ref, layers:list[tuple[str,np.ndarray]]):
    with rio.open(dim_path) as ds:
        same_grid = (ds.crs==ref.crs and ds.transform==ref.transform and
                     ds.width==ref.width and ds.height==ref.height)
        for i in range(1, ds.count+1):
            name = ds.descriptions[i-1] or f"B{i}"
            arr  = ds.read(i).astype("float32")
            if not same_grid:
                arr2 = np.zeros((ref.height, ref.width), dtype="float32")
                reproject(arr, arr2, src_transform=ds.transform, src_crs=ds.crs,
                          dst_transform=ref.transform, dst_crs=ref.crs,
                          resampling=Resampling.bilinear)
                arr = arr2
            layers.append((name, arr))

def main():
    ap = argparse.ArgumentParser("Stack tex_tc + decomp_tc + sigma0_tc + biophysical into one GeoTIFF")
    ap.add_argument("--subswath_dir", required=True, help=r"...\PreProccess\aoi_2\2020-08-23\SLC\IW1")
    ap.add_argument("--bio_dir",      required=True, help=r"...\downloads_S1\aoi_2\2020-08-23\bio")
    ap.add_argument("--out",          required=True, help=r"...\PreProccess\aoi_2\2020-08-23\final\slc_IW1_stack.tif")
    args = ap.parse_args()

    d = Path(args.subswath_dir)
    tex_tc    = next((d.glob("*_tex_tc.dim")), None)
    sigma0_tc = next((d.glob("*_sigma0_tc.dim")), None)
    decomp_tc = next((d.glob("*_decomp_tc.dim")), None)

    if not tex_tc:
        raise FileNotFoundError("No *_tex_tc.dim found — that’s our reference grid.")
    with rio.open(tex_tc) as ref:
        layers: list[tuple[str,np.ndarray]] = []
        # 1) textures
        add_from_dim(tex_tc, ref, layers)
        # 2) sigma0 VV/VH (map space)
        if sigma0_tc: add_from_dim(sigma0_tc, ref, layers)
        # 3) decomposition (map space)
        if decomp_tc: add_from_dim(decomp_tc, ref, layers)
        # 4) biophysical
        bio = Path(args.bio_dir)
        for f in BIO:
            p = bio / f
            if p.exists():
                layers.append((f[:-4], reproject_to(p, ref)))

        # write (compressed, tiled, bigtiff-if-needed)
        prof = ref.profile.copy()
        prof.update(
            driver="GTiff", count=len(layers), dtype="float32", nodata=np.nan,
            tiled=True, blockxsize=512, blockysize=512,
            compress="deflate", predictor=2, zlevel=6, bigtiff="IF_SAFER"
        )
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        with rio.open(args.out, "w", **prof) as dst:
            for i,(nm,arr) in enumerate(layers, start=1):
                dst.write(arr, i); dst.set_band_description(i, nm)

        Path(str(Path(args.out).with_suffix("")) + "_channels.json") \
            .write_text(json.dumps([n for n,_ in layers], indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()