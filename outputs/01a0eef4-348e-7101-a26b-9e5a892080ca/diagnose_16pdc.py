"""Read-only validation of 16PDC QGIS raster sources and first TIFF blocks."""

import math
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile

import numpy as np
from osgeo import gdal

PROJECT = Path(r"D:\Joshua\golden_marida_16pdc_2018\digitising_batches\golden_marida_16pdc_2018\batch.qgz")
gdal.UseExceptions()

with ZipFile(PROJECT) as archive:
    root = ET.fromstring(archive.read("batch.qgs"))
view = root.find("./ProjectViewSettings/DefaultViewExtent")
print("VIEW", view.attrib)
rasters = [layer for layer in root.findall("./projectlayers/maplayer") if layer.attrib.get("type") == "raster"]
print("RASTER_COUNT", len(rasters))
for layer in rasters:
    name = layer.findtext("layername")
    source = layer.findtext("datasource")
    path = (PROJECT.parent / source).resolve()
    if not path.is_file():
        print("MISSING", name, source)
        continue
    try:
        ds = gdal.Open(str(path))
        if ds is None:
            print("CANNOT_OPEN", name, path.name)
            continue
        band = ds.GetRasterBand(1)
        gt = ds.GetGeoTransform()
        centre_lon, centre_lat = -87.2, 15.85
        col = int((centre_lon - gt[0]) / gt[1])
        row = int((centre_lat - gt[3]) / gt[5])
        sample = band.ReadAsArray(0, 0, min(512, ds.RasterXSize), min(512, ds.RasterYSize))
        first_finite = int(np.isfinite(sample).sum())
        if 0 <= col < ds.RasterXSize and 0 <= row < ds.RasterYSize:
            local = band.ReadAsArray(max(0, col-128), max(0, row-128), 256, 256)
            centre_finite = int(np.isfinite(local).sum())
            centre_min = float(np.nanmin(local)) if centre_finite else math.nan
            centre_max = float(np.nanmax(local)) if centre_finite else math.nan
        else:
            centre_finite, centre_min, centre_max = -1, math.nan, math.nan
        print("OK", name, path.parent.name, path.name[-34:], path.stat().st_size,
              ds.RasterXSize, ds.RasterYSize, "first_finite", first_finite,
              "centre_finite", centre_finite, "centre_range", centre_min, centre_max)
    except Exception as error:
        print("READ_ERROR", name, path.name, repr(error))
