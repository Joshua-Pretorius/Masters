"""Render a quick inspection image for the requested Sentinel-2 FDI tiles."""

import importlib.util
import json
import os
from pathlib import Path

package = Path(importlib.util.find_spec("rasterio").origin).parent
os.environ["PROJ_LIB"] = str(package / "proj_data")
os.environ["MPLBACKEND"] = "Agg"

import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
import numpy as np
import rasterio
from rasterio.enums import Resampling


ROOT = Path(r"D:\Masters\MARIDA\downloads\16PDC\2018-10-24\copernicus_products\fdi")
manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
cmap = LinearSegmentedColormap.from_list(
    "fdi_water", ["#15315b", "#4f8dae", "#f6f5ea", "#f5a340", "#b71930"]
)
cmap.set_bad("#d5d9dc")
normalizer = TwoSlopeNorm(vmin=-0.05, vcenter=0.0, vmax=0.10)
fig, axes = plt.subplots(1, 3, figsize=(15, 5.1), constrained_layout=True)
for axis, item in zip(axes, manifest):
    with rasterio.open(item["fdi"]) as raster:
        data = raster.read(
            1, out_shape=(700, 700), masked=True, resampling=Resampling.average
        )
        axis.imshow(data, cmap=cmap, norm=normalizer, origin="upper")
    tile = item["product"].split("_T")[1][:5]
    level = item["level"]
    axis.set_title(f"{tile}  |  {level} {'surface' if level == 'L2A' else 'top of atmosphere'}")
    axis.set_xticks([])
    axis.set_yticks([])
fig.suptitle("Sentinel-2 FDI  ·  24 October 2018, 16:13 UTC")
bar = fig.colorbar(
    plt.cm.ScalarMappable(norm=normalizer, cmap=cmap),
    ax=axes, location="bottom", fraction=0.055, pad=0.025, shrink=0.65,
    extend="both",
)
bar.set_label("Floating Debris Index (reflectance units; saturated outside −0.05 to +0.10)")
output = ROOT / "requested_fdi_overview.png"
fig.savefig(output, dpi=160, facecolor="white")
print(output)
