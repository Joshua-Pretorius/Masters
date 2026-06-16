import pathlib
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.shutil import copy as rio_copy  # for metadata cloning

# Sentinel‑2 central wavelengths (nm)
L_B4  = 665
L_B8  = 842
L_B11 = 1610
def read_band(path):
    with rasterio.open(path) as src:
        data = src.read(1).astype(np.float32)
        meta = src.meta.copy()
    return data, meta
def calc_fdi(b4, b6, b8, b11):
    # Intermediate term (Rrs′_NIR)
    rrs_nir_prime = b6 + (b11 - b6) * ((L_B8 - L_B4) / (L_B11 - L_B4)) * 10.0
    return b8 - rrs_nir_prime
def process_scene(scene_dir):
    # Expect files like S2_XXX_YYYY-MM-DD_B04.tif etc.
    patt = str(scene_dir / "*_B{}.tif")
    paths = {
        "B04": list(scene_dir.glob("*_B04.tif"))[0],
        "B06": list(scene_dir.glob("*_B06.tif"))[0],  # RE2
        "B08": list(scene_dir.glob("*_B08.tif"))[0],  # NIR
        "B11": list(scene_dir.glob("*_B11.tif"))[0],  # SWIR1
    }

    b4, meta = read_band(paths["B04"])
    b6, _    = read_band(paths["B06"])
    b8, _    = read_band(paths["B08"])
    b11,_    = read_band(paths["B11"])

    fdi = calc_fdi(b4, b6, b8, b11)

    # Write out
    out_path = scene_dir / (paths["B08"].stem.replace("_B08", "_FDI") + ".tif")
    meta.update(dtype="float32", count=1)
    with rasterio.open(out_path, "w", **meta) as dst:
        dst.write(fdi, 1)
    print(f"✓  FDI saved -> {out_path.relative_to(scene_dir.parent.parent)}")
root = pathlib.Path(r"D:\Masters\MARIDA\downloads")

for scene in root.rglob("optical"):
    # e.g., ...\16PCC\2017-01-12\optical
    try:
        process_scene(scene)
    except Exception as exc:
        print(f"⚠️  skipped {scene}: {exc}")
