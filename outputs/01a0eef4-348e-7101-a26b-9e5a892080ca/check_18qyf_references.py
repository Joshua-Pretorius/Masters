"""Read-only source and prepared-point check for MARIDA 18QYF, 2021-01-23."""

from collections import Counter
from pathlib import Path
import numpy as np
from osgeo import gdal, ogr

MASK_ROOT = Path(r"D:\Masters\MARIDA\MARIDA\patches\S2_23-1-21_18QYF")
for path in sorted(MASK_ROOT.glob("*_cl.tif")):
    ds = gdal.Open(str(path))
    data = ds.GetRasterBand(1).ReadAsArray()
    values, counts = np.unique(data, return_counts=True)
    print(path.name, "classes", dict(zip(map(int, values), map(int, counts))),
          "marine_debris_DN1", int(np.count_nonzero(data == 1)))

gpkg = next(Path(r"D:\Joshua\golden_marida_18qyf_2021\processed").glob("**/task.gpkg"))
db = ogr.Open(str(gpkg))
for layer_name in ("reference_points", "predicted_points", "prediction_envelopes", "annotations"):
    layer = db.GetLayerByName(layer_name)
    print(layer_name, "count", layer.GetFeatureCount())
    if layer_name == "reference_points":
        print("reference_types", dict(Counter((f.GetField("ref_kind"), f.GetField("seed_ok")) for f in layer)))
