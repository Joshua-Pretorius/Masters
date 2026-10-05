"""Build a cropped, georeferenced 16PCC FDI visualisation from Level-1C bands."""

from pathlib import Path
import math
import os
import xml.etree.ElementTree as ET
from zipfile import ZipFile

import numpy as np
from osgeo import gdal, osr

ROOT = Path(
    r"C:\Users\Joshua Pretorius\Desktop"
    r"\S2B_MSIL1C_20180830T160819_N0500_R140_T16PCC_20230730T125342.SAFE"
    r"\S2B_MSIL1C_20180830T160819_N0500_R140_T16PCC_20230730T125342.SAFE"
)
IMG = ROOT / "GRANULE" / "L1C_T16PCC_A007745_20180830T161630" / "IMG_DATA"
PROJECT = Path(
    r"D:\Joshua\golden_marida_16pcc_2018\digitising_batches"
    r"\golden_marida_16pcc_2018\batch.qgz"
)
OUTPUT = Path(
    r"D:\Masters\outputs\01a0eef4-348e-7101-a26b-9e5a892080ca"
    r"\16pcc_20180830_fdi_l1c_toa_10m.tif"
)
COEFFICIENT = ((842.0 - 665.0) / (1610.0 - 665.0)) * 10.0


def band_path(band):
    return IMG / f"T16PCC_20180830T160819_{band}.jp2"


def main():
    if OUTPUT.exists():
        raise RuntimeError(f"Output already exists: {OUTPUT}")
    metadata = ET.parse(ROOT / "MTD_MSIL1C.xml").getroot()
    quantification = [float(n.text) for n in metadata.iter() if n.tag.endswith("QUANTIFICATION_VALUE")]
    offsets = [float(n.text) for n in metadata.iter() if n.tag.endswith("RADIO_ADD_OFFSET")]
    if quantification != [10000.0] or len(offsets) != 13 or set(offsets) != {-1000.0}:
        raise RuntimeError("Unexpected Level-1C radiometric scale or offsets")
    for band in ("B06", "B08", "B11"):
        if not band_path(band).is_file():
            raise FileNotFoundError(band_path(band))

    with ZipFile(PROJECT) as archive:
        root = ET.fromstring(archive.read("batch.qgs"))
    extent = root.find("./ProjectViewSettings/DefaultViewExtent")
    if extent is None:
        raise RuntimeError("Project view extent missing")
    lon_min, lon_max = float(extent.attrib["xmin"]), float(extent.attrib["xmax"])
    lat_min, lat_max = float(extent.attrib["ymin"]), float(extent.attrib["ymax"])
    src_srs, dst_srs = osr.SpatialReference(), osr.SpatialReference()
    src_srs.ImportFromEPSG(4326)
    dst_srs.ImportFromEPSG(32616)
    src_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    dst_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    transform = osr.CoordinateTransformation(src_srs, dst_srs)
    xy = [transform.TransformPoint(lon, lat) for lon in (lon_min, lon_max) for lat in (lat_min, lat_max)]
    margin = 2000.0
    x_min, x_max = min(p[0] for p in xy) - margin, max(p[0] for p in xy) + margin
    y_min, y_max = min(p[1] for p in xy) - margin, max(p[1] for p in xy) + margin

    b08_src = gdal.Open(str(band_path("B08")))
    if b08_src is None or b08_src.RasterCount != 1:
        raise RuntimeError("Could not load Sentinel-2 B08")
    gt = b08_src.GetGeoTransform()
    if gt[1] != 10.0 or gt[5] != -10.0 or gt[2] != 0 or gt[4] != 0:
        raise RuntimeError(f"Unexpected B08 grid: {gt}")
    col0 = max(0, math.floor((x_min - gt[0]) / 10.0))
    col1 = min(b08_src.RasterXSize, math.ceil((x_max - gt[0]) / 10.0))
    row0 = max(0, math.floor((gt[3] - y_max) / 10.0))
    row1 = min(b08_src.RasterYSize, math.ceil((gt[3] - y_min) / 10.0))
    width, height = col1 - col0, row1 - row0
    if width <= 0 or height <= 0:
        raise RuntimeError("Project view does not intersect Sentinel-2 tile")
    bounds = (
        gt[0] + col0 * 10,
        gt[3] - row1 * 10,
        gt[0] + col1 * 10,
        gt[3] - row0 * 10,
    )
    b08_dn = b08_src.GetRasterBand(1).ReadAsArray(col0, row0, width, height).astype("float32")

    def warped_dn(band):
        ds = gdal.Warp(
            "",
            str(band_path(band)),
            format="MEM",
            dstSRS="EPSG:32616",
            outputBounds=bounds,
            width=width,
            height=height,
            resampleAlg="bilinear",
            srcNodata=0,
            dstNodata=0,
            outputType=gdal.GDT_Float32,
        )
        if ds is None:
            raise RuntimeError(f"Could not resample {band}")
        return ds.GetRasterBand(1).ReadAsArray().astype("float32")

    b06_dn = warped_dn("B06")
    b11_dn = warped_dn("B11")
    valid = (b06_dn > 0) & (b08_dn > 0) & (b11_dn > 0)
    b06 = (b06_dn - 1000.0) / 10000.0
    b08 = (b08_dn - 1000.0) / 10000.0
    b11 = (b11_dn - 1000.0) / 10000.0
    fdi = b08 - (b06 + (b11 - b06) * COEFFICIENT)
    fdi[~valid] = np.nan
    if valid.sum() < 1000:
        raise RuntimeError("Too few valid Sentinel-2 pixels in project view")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    driver = gdal.GetDriverByName("GTiff")
    dst = driver.Create(
        str(OUTPUT), width, height, 1, gdal.GDT_Float32,
        options=["TILED=YES", "COMPRESS=DEFLATE", "PREDICTOR=3", "BIGTIFF=IF_SAFER"],
    )
    if dst is None:
        raise RuntimeError("Could not create FDI GeoTIFF")
    dst.SetGeoTransform((bounds[0], 10.0, 0.0, bounds[3], 0.0, -10.0))
    dst.SetProjection(b08_src.GetProjection())
    dst.SetMetadata({
        "DESCRIPTION": "Floating Debris Index visualisation from Sentinel-2B Level-1C TOA reflectance",
        "SOURCE_PRODUCT": ROOT.name,
        "SOURCE_BANDS": "B06 B08 B11",
        "FORMULA": "B08 - (B06 + (B11-B06)*((842-665)/(1610-665))*10)",
        "REFLECTANCE": "(DN - 1000) / 10000; N0500 RADIO_ADD_OFFSET=-1000",
        "LIMITATION": "Uncorrected TOA diagnostic, not ACOLITE surface reflectance or plastic classification",
        "SOURCE_DOI": "10.1038/s41598-020-62298-z",
    })
    out_band = dst.GetRasterBand(1)
    out_band.SetNoDataValue(float("nan"))
    out_band.SetDescription("FDI (L1C TOA reflectance)")
    out_band.WriteArray(fdi)
    out_band.FlushCache()
    dst.FlushCache()
    dst = None
    values = fdi[valid]
    print("FDI:", OUTPUT)
    print("Shape:", width, height, "valid:", int(valid.sum()), "bounds:", bounds)
    print("Percentiles 1/2/50/98/99.5:", np.percentile(values, [1, 2, 50, 98, 99.5]))
    print("Size bytes:", OUTPUT.stat().st_size)


if __name__ == "__main__":
    main()
