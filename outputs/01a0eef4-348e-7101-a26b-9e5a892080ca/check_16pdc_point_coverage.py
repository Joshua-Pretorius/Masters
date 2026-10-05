"""Check whether 16PDC reference points intersect valid SAR pixels."""

from pathlib import Path
import math
from osgeo import gdal, ogr, osr

BASE = Path(r"D:\Joshua\golden_marida_16pdc_2018\processed")
for scene in sorted(BASE.glob("*/scene_*")):
    task = next(scene.glob("digitising/*/task.gpkg"))
    tif = next(scene.glob("*vv_refined_lee_db.tif"))
    dataset = gdal.Open(str(tif))
    band = dataset.GetRasterBand(1)
    gt = dataset.GetGeoTransform()
    vector = ogr.Open(str(task))
    reference_layer = vector.GetLayerByName("reference_points")
    source_crs = reference_layer.GetSpatialRef()
    raster_crs = osr.SpatialReference()
    raster_crs.ImportFromWkt(dataset.GetProjection())
    source_crs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    raster_crs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    transform = osr.CoordinateTransformation(source_crs, raster_crs)
    for layer_name in ("reference_points", "predicted_points"):
        layer = vector.GetLayerByName(layer_name)
        print(scene.name, layer_name, "count", layer.GetFeatureCount(),
              "fields", [f.name for f in layer.schema])
        for feature in layer:
            point = feature.GetGeometryRef().Clone()
            point.Transform(transform)
            col = int((point.GetX() - gt[0]) / gt[1])
            row = int((point.GetY() - gt[3]) / gt[5])
            if col < 0 or row < 0 or col >= dataset.RasterXSize or row >= dataset.RasterYSize:
                status = "OUTSIDE_TIFF"
            else:
                value = float(band.ReadAsArray(col, row, 1, 1)[0, 0])
                status = f"VALID {value:.2f} dB" if math.isfinite(value) else "NODATA"
            print(feature.GetField("point_id" if layer_name == "reference_points" else "seed_id"),
                  f"{point.GetX():.5f}", f"{point.GetY():.5f}", status)
