"""Render 16PDC SAR layers headlessly to reproduce QGIS display errors."""

import os
from pathlib import Path

QGIS_ROOT = Path(r"C:\Program Files\QGIS 3.40.4")
for subdir in ("bin", "apps/qt5/bin", "apps/qgis-ltr/bin", "apps/Python312/DLLs"):
    directory = QGIS_ROOT / subdir
    if directory.is_dir():
        os.add_dll_directory(str(directory))
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from qgis.PyQt.QtCore import QSize
from qgis.core import QgsApplication, QgsMapRendererSequentialJob, QgsMapSettings, QgsProject, QgsRectangle

PROJECT = Path(r"D:\Joshua\golden_marida_16pdc_2018\digitising_batches\golden_marida_16pdc_2018\batch.qgz")
OUT = Path(r"D:\Masters\outputs\01a0eef4-348e-7101-a26b-9e5a892080ca\16pdc_qgis_diagnostic.png")

app = QgsApplication([], False)
app.initQgis()
project = QgsProject.instance()
print("READ", project.read(str(PROJECT)), flush=True)
for layer in project.mapLayers().values():
    if layer.type() == layer.RasterLayer:
        node = project.layerTreeRoot().findLayer(layer.id())
        print("RASTER", layer.name(), "valid", layer.isValid(), "visible", node.isVisible() if node else None,
              "extent", layer.extent().toString(), flush=True)
    else:
        print("VECTOR", layer.name(), "valid", layer.isValid(),
              "features", layer.featureCount() if layer.isValid() else None, flush=True)
layers = [
    layer for layer in project.mapLayers().values()
    if layer.name() == "VV refined Lee (dB)" and layer.isValid()
    and project.layerTreeRoot().findLayer(layer.id()).isVisible()
]
reference = [
    layer for layer in project.mapLayers().values()
    if layer.name() == "Optical reference points" and layer.isValid()
    and "20181024T113716" in layer.source()
]
layers = layers
print("RENDER", [layer.source() for layer in layers], flush=True)
settings = QgsMapSettings()
settings.setLayers(layers)
settings.setDestinationCrs(project.crs())
settings.setExtent(QgsRectangle(-87.40, 15.82, -87.27, 15.91))
settings.setOutputSize(QSize(1200, 900))
job = QgsMapRendererSequentialJob(settings)
job.start()
job.waitForFinished()
print("ERRORS", [(e.layerID, e.message) for e in job.errors()], flush=True)
image = job.renderedImage()
print("IMAGE", image.width(), image.height(), "saved", image.save(str(OUT)), OUT, flush=True)
