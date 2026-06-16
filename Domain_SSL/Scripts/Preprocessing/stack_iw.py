# stack_iw.py
import argparse
from pathlib import Path
import numpy as np
import rasterio as rio
from rasterio.warp import reproject, Resampling

BIO = ["swh.tif", "uo.tif", "vo.tif", "vsdx.tif", "vsdy.tif"]

# ---------- helpers ----------
def find_product(dirpath: Path, suffix: str):
    """
    Look for slc_*_{suffix}.tif first, else slc_*_{suffix}.data (ENVI set).
    Returns (kind, path) where kind in {"tif","data"} or (None,None).
    """
    tifs = sorted(dirpath.glob(f"slc_*_{suffix}.tif"))
    if tifs:
        return "tif", tifs[0]
    datas = sorted(dirpath.glob(f"slc_*_{suffix}.data"))
    if datas:
        return "data", datas[0]
    return None, None

def list_envi_imgs(data_dir: Path):
    """All .img files in a SNAP .data folder (ignore vector_data)."""
    return sorted([p for p in data_dir.glob("*.img") if p.name.lower() != "vector_data"])

def expand_sources(kind, src):
    """
    Expand a source into a list of (kind, path, band_index, band_name).
    - GeoTIFF: one tuple per band (keeps descriptions if present)
    - ENVI set: one tuple per .img file (band_index=1)
    """
    out = []
    if not src:
        return out
    if kind == "tif":
        with rio.open(src) as ds:
            for i in range(1, ds.count + 1):
                name = ds.descriptions[i - 1] or f"{src.stem}_B{i}"
                out.append(("tif", src, i, name))
    else:  # .data folder
        for p in list_envi_imgs(src):
            out.append(("img", p, 1, p.stem))
    return out

def same_grid(ds, ref):
    return (ds.crs == ref["crs"] and
            ds.transform == ref["transform"] and
            ds.width == ref["width"] and ds.height == ref["height"])

def read_to_ref(kind, path, band_idx, ref_meta):
    """Read a band and reproject/resample to the reference grid if needed."""
    with rio.open(path) as ds:
        arr = ds.read(band_idx).astype("float32")
        # If grids match (or at least size+transform match with missing CRS), just return
        if (ds.width, ds.height) == (ref_meta["width"], ref_meta["height"]) and (
            ds.transform == ref_meta["transform"] or ds.crs is None or ref_meta["crs"] is None
        ):
            if ds.crs == ref_meta["crs"] and ds.transform == ref_meta["transform"]:
                return arr
        # Otherwise reproject to reference
        out = np.zeros((ref_meta["height"], ref_meta["width"]), dtype="float32")
        reproject(
            arr, out,
            src_transform=ds.transform, src_crs=ds.crs,
            dst_transform=ref_meta["transform"], dst_crs=ref_meta["crs"],
            resampling=Resampling.bilinear,
        )
        return out

# ---------- main ----------
def main():
    ap = argparse.ArgumentParser(
        "Stack sigma0_tc + tex_tc + decomp_tc + biophysical for one IW (GeoTIFF or ENVI .img inputs)."
    )
    ap.add_argument("--iw-dir", required=True, help=r"...\PreProccess\aoi_X\DATE\SLC\IW1  (or ...\final)")
    ap.add_argument("--bio-dir", required=True, help=r"...\downloads_S1\aoi_X\DATE\bio")
    ap.add_argument("--out",     required=True, help=r"...\final\slc_IW1_stack.tif")
    args = ap.parse_args()

    d = Path(args.iw_dir)
    # locate the three products (prefer .tif, else .data/)
    tex_kind, tex_src = find_product(d, "tex_tc")
    sig_kind, sig_src = find_product(d, "sigma0_tc")
    dec_kind, dec_src = find_product(d, "decomp_tc")
    assert tex_src, f"No *_tex_tc found as .tif or .data in {d}"

    # expand to explicit file/band list (order = tex → sigma0 → decomp → bio)
    tex_files = expand_sources(tex_kind, tex_src);  assert tex_files
    sig_files = expand_sources(sig_kind, sig_src)
    dec_files = expand_sources(dec_kind, dec_src)
    bio_paths = [Path(args.bio_dir)/nm for nm in BIO if (Path(args.bio_dir)/nm).exists()]
    bio_files = [("tif", p, 1, p.stem) for p in bio_paths]

    all_files = tex_files + sig_files + dec_files + bio_files

    # reference grid from the very first textures band
    ref_path = tex_files[0][1]
    ref_band = tex_files[0][2]
    with rio.open(ref_path) as ref:
        ref_meta = {
            "crs": ref.crs,
            "transform": ref.transform,
            "width": ref.width,
            "height": ref.height,
            "dtype": "float32",
            "driver": "GTiff",
        }
        out_profile = ref.profile.copy()
    out_profile.update(
        driver="GTiff",
        count=len(all_files),
        dtype="float32",
        tiled=True, blockxsize=512, blockysize=512,
        compress="deflate", predictor=2, zlevel=6,
        bigtiff="IF_SAFER",
        nodata=np.nan,
    )

    # write in one pass
    out_path = Path(args.out); out_path.parent.mkdir(parents=True, exist_ok=True)
    with rio.open(out_path, "w", **out_profile) as dst:
        for b, (kind, path, band_idx, name) in enumerate(all_files, start=1):
            arr = read_to_ref(kind, path, band_idx, ref_meta)
            dst.write(arr, b)
            dst.set_band_description(b, name)

if __name__ == "__main__":
    main()