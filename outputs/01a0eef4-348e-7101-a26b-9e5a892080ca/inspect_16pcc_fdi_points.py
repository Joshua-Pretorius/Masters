from pathlib import Path
import numpy as np
from osgeo import gdal, ogr, osr

raster = gdal.Open(r"D:\Masters\outputs\01a0eef4-348e-7101-a26b-9e5a892080ca\16pcc_20180830_fdi_l1c_toa_10m.tif")
arr = raster.GetRasterBand(1).ReadAsArray()
gt = raster.GetGeoTransform()
gpkg = next(Path(r"D:\Joshua\golden_marida_16pcc_2018\processed").glob("**/task.gpkg"))
src = ogr.Open(str(gpkg))
layer = src.GetLayerByName("reference_points")
dst_srs = osr.SpatialReference()
dst_srs.ImportFromWkt(raster.GetProjection())
layer_srs = layer.GetSpatialRef()
layer_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
dst_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
transform = osr.CoordinateTransformation(layer_srs, dst_srs)
centres = []
print("Source features:", layer.GetFeatureCount(), "fields:", [f.name for f in layer.schema])
for feature in layer:
    point = feature.GetGeometryRef().Centroid()
    point.Transform(transform)
    col = int((point.GetX() - gt[0]) / gt[1])
    row = int((point.GetY() - gt[3]) / gt[5])
    if 0 <= col < arr.shape[1] and 0 <= row < arr.shape[0]:
        centres.append((row, col, float(arr[row, col])))
print("Class 1 centroids in FDI:", len(centres))
print("Sample values:", [round(v, 5) for _, _, v in centres[:30]])
pixels = []
for row, col, value in centres:
    chip = arr[max(0, row-20):row+21, max(0,col-20):col+21]
    pixels.append(chip[np.isfinite(chip)])
if pixels:
    all_pixels = np.concatenate(pixels)
    print("41x41-pixel local percentiles:", np.percentile(all_pixels, [1,2,10,25,50,75,90,98,99]))
