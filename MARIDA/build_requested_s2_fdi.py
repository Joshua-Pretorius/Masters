"""Build georeferenced FDI rasters from the three requested CDSE SAFE ZIPs."""

from __future__ import annotations

import importlib.util
import json
import os
from contextlib import ExitStack
from pathlib import Path
import re
from zipfile import ZipFile
from xml.etree import ElementTree as ET

# The workstation has an older SNAP PROJ_LIB in its environment. Use the
# projection database bundled with this rasterio installation.
_rasterio_package = Path(importlib.util.find_spec("rasterio").origin).parent
os.environ["PROJ_LIB"] = str(_rasterio_package / "proj_data")

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT


ROOT = Path(r"D:\Masters\MARIDA\downloads\16PDC\2018-10-24\copernicus_products")
OUTPUT = ROOT / "fdi"
PRODUCTS = (
    "S2A_MSIL1C_20181024T161331_N0500_R140_T16PCC_20230728T071849.SAFE",
    "S2A_MSIL1C_20181024T161331_N0500_R140_T16PDC_20230728T071849.SAFE",
    "S2A_MSIL2A_20181024T161331_N0500_R140_T16PEC_20230729T044439.SAFE",
)
BAND_ID = {"B06": "5", "B08": "7", "B11": "11"}
FACTOR = (842.0 - 665.0) / (1610.0 - 665.0) * 10.0
NODATA = -9999.0


def local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def single_text(root: ET.Element, tag: str) -> str:
    values = [e.text.strip() for e in root.iter() if local_name(e) == tag and e.text]
    if len(values) != 1:
        raise ValueError(f"Expected one {tag}; found {len(values)}")
    return values[0]


def metadata(archive: ZipFile, product: str) -> tuple[str, float, dict[str, float]]:
    names = archive.namelist()
    level = "L2A" if "MSIL2A" in product else "L1C"
    meta_name = next(n for n in names if n.endswith(f"/MTD_MSI{level}.xml"))
    tile_name = next(n for n in names if n.endswith("/MTD_TL.xml"))
    root = ET.fromstring(archive.read(meta_name))
    tile = ET.fromstring(archive.read(tile_name))
    crs = single_text(tile, "HORIZONTAL_CS_CODE")
    quant_tag = "BOA_QUANTIFICATION_VALUE" if level == "L2A" else "QUANTIFICATION_VALUE"
    offset_tag = "BOA_ADD_OFFSET" if level == "L2A" else "RADIO_ADD_OFFSET"
    quant = float(single_text(root, quant_tag))
    offsets_by_id = {
        e.attrib["band_id"]: float(e.text)
        for e in root.iter()
        if local_name(e) == offset_tag and e.text and "band_id" in e.attrib
    }
    offsets = {band: offsets_by_id[BAND_ID[band]] for band in BAND_ID}
    return crs, quant, offsets


def band_name(archive: ZipFile, band: str) -> str:
    match = re.compile(rf"_{band}(?:_(?:10|20)m)?\.jp2$")
    found = [n for n in archive.namelist() if "/IMG_DATA/" in n and match.search(n)]
    if len(found) != 1:
        raise ValueError(f"Expected one IMG_DATA {band}, found {len(found)}")
    return found[0]


def build(product: str) -> dict:
    zip_path = ROOT / f"{product}.zip"
    if not zip_path.exists():
        raise FileNotFoundError(zip_path)
    tile = re.search(r"_T(\d{2}[A-Z]{3})_", product).group(1)
    level = "L2A" if "MSIL2A" in product else "L1C"
    destination = OUTPUT / f"S2A_20181024T161331_T{tile}_{level}_FDI.tif"
    if destination.exists():
        with rasterio.open(destination) as src:
            if src.count == 1 and src.crs and src.width > 1000:
                print(f"SKIP {destination}", flush=True)
                return {"product": product, "fdi": str(destination), "status": "already_exists"}

    with ZipFile(zip_path) as archive:
        crs, quant, offsets = metadata(archive, product)
        band_paths = {
            band: f"/vsizip/{zip_path.as_posix()}/{band_name(archive, band)}"
            for band in BAND_ID
        }
    print(f"START {tile} {level} {crs} offsets={offsets} quant={quant}", flush=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(".partial.tif")
    with rasterio.Env(GDAL_CACHEMAX=256), ExitStack() as stack:
        b8 = stack.enter_context(rasterio.open(band_paths["B08"]))
        b6 = stack.enter_context(rasterio.open(band_paths["B06"]))
        b11 = stack.enter_context(rasterio.open(band_paths["B11"]))
        if b8.width <= b6.width or b8.width <= b11.width:
            raise ValueError("Expected 10 m B08 and 20 m B06/B11")
        vrt_options = dict(
            src_crs=crs, crs=crs, transform=b8.transform,
            width=b8.width, height=b8.height,
            resampling=Resampling.bilinear, src_nodata=0, nodata=0,
        )
        b6_10m = stack.enter_context(WarpedVRT(b6, **vrt_options))
        b11_10m = stack.enter_context(WarpedVRT(b11, **vrt_options))
        profile = b8.profile.copy()
        profile.update(
            driver="GTiff", dtype="float32", count=1, crs=crs,
            nodata=NODATA, tiled=True, blockxsize=512, blockysize=512,
            compress="deflate", predictor=3, zlevel=4, BIGTIFF="IF_SAFER",
        )
        with rasterio.open(partial, "w", **profile) as output:
            output.update_tags(
                source_product=product, source_level=level,
                input_reflectance="BOA" if level == "L2A" else "TOA",
                fdi_formula="B08 - (B06 + (B11-B06)*((842-665)/(1610-665))*10)",
                band_quantification=str(quant), band_offsets=json.dumps(offsets),
                source="Copernicus Data Space Ecosystem SAFE",
            )
            windows = list(output.block_windows(1))
            for index, (_, window) in enumerate(windows, 1):
                dn8 = b8.read(1, window=window)
                dn6 = b6_10m.read(1, window=window)
                dn11 = b11_10m.read(1, window=window)
                valid = (dn8 > 0) & (dn6 > 0) & (dn11 > 0)
                r8 = (dn8.astype(np.float32) + offsets["B08"]) / quant
                r6 = (dn6.astype(np.float32) + offsets["B06"]) / quant
                r11 = (dn11.astype(np.float32) + offsets["B11"]) / quant
                fdi = r8 - (r6 + (r11 - r6) * FACTOR)
                fdi[~valid] = NODATA
                output.write(fdi.astype(np.float32), 1, window=window)
                if index % 100 == 0:
                    print(f"PROGRESS {tile} {level} {index}/{len(windows)} blocks", flush=True)
    partial.replace(destination)
    with rasterio.open(destination) as src:
        sample = src.read(1, out_shape=(1200, 1200), resampling=Resampling.average)
        valid_sample = sample[np.isfinite(sample) & (sample != NODATA)]
        percentiles = np.percentile(valid_sample, [2, 50, 98]).tolist()
        result = {
            "product": product, "fdi": str(destination), "status": "created",
            "level": level, "crs": str(src.crs), "width": src.width,
            "height": src.height, "bounds": list(src.bounds),
            "sample_p02_p50_p98": percentiles,
            "valid_sample_pixels": int(valid_sample.size),
        }
    print(f"DONE {destination} p02/p50/p98={percentiles}", flush=True)
    return result


if __name__ == "__main__":
    results = [build(product) for product in PRODUCTS]
    (OUTPUT / "manifest.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
