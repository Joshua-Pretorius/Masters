"""Open the 16PDC batch project on the SAR frame containing its target points."""

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import shutil
import sys

QGIS_ROOT = Path(r"C:\Program Files\QGIS 3.40.4")
for subdir in ("bin", "apps/qt5/bin", "apps/qgis-ltr/bin", "apps/Python312/DLLs"):
    directory = QGIS_ROOT / subdir
    if directory.is_dir():
        os.add_dll_directory(str(directory))
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from qgis.PyQt.QtGui import QColor, QFont
from qgis.core import (
    QgsApplication, QgsProject, QgsRectangle, QgsReferencedRectangle,
    QgsVectorLayerSimpleLabeling,
)

PROJECT = Path(r"D:\Joshua\golden_marida_16pdc_2018\digitising_batches\golden_marida_16pdc_2018\batch.qgz")
TARGET_EXTENT = QgsRectangle(-87.40, 15.82, -87.27, 15.91)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def groups(project):
    all_groups = project.layerTreeRoot().findGroups()
    r01 = [g for g in all_groups if "16PDC" in g.name() and "R01_20181024T113716" in g.name()]
    r02 = [g for g in all_groups if "16PDC" in g.name() and "R02_20181024T113744" in g.name()]
    if len(r01) != 1 or len(r02) != 1:
        raise RuntimeError(f"Expected one R01 and one R02 group; found {len(r01)}, {len(r02)}")
    return r01[0], r02[0]


def verify(project):
    r01, r02 = groups(project)
    if not r01.itemVisibilityChecked() or r02.itemVisibilityChecked():
        raise RuntimeError("R01/R02 group visibility incorrect")
    target = project.viewSettings().defaultViewExtent()
    if abs(target.xMinimum() - TARGET_EXTENT.xMinimum()) > 1e-9:
        raise RuntimeError("Default view extent was not saved")
    raster_layers = [layer for layer in project.mapLayers().values() if layer.type() == layer.RasterLayer]
    if len(raster_layers) != 20 or not all(layer.isValid() for layer in raster_layers):
        raise RuntimeError("Raster layer count or validity changed")
    references = [layer for layer in project.mapLayers().values() if layer.name() == "Optical reference points"]
    if len(references) != 2 or not all(layer.isValid() for layer in references):
        raise RuntimeError("Optical reference layers missing")
    if any("right(\"point_id\", 4)" not in layer.labeling().settings().fieldName for layer in references):
        raise RuntimeError("Short point labels missing")
    print("Verified: R01 visible, R02 off, 20 valid rasters, short labels, target extent saved")


def shorten_point_labels(project):
    for layer in project.mapLayers().values():
        if layer.name() != "Optical reference points":
            continue
        settings = layer.labeling().settings()
        settings.isExpression = True
        settings.fieldName = "CASE WHEN \"seed_ok\" = 1 THEN 'MD-' || right(\"point_id\", 4) END"
        text_format = settings.format()
        font = QFont("Arial")
        font.setPointSizeF(8.0)
        text_format.setFont(font)
        text_format.setSize(8.0)
        text_format.setColor(QColor("#202020"))
        buffer = text_format.buffer()
        buffer.setEnabled(True)
        buffer.setSize(0.5)
        buffer.setColor(QColor("white"))
        text_format.setBuffer(buffer)
        settings.setFormat(text_format)
        layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
        layer.setLabelsEnabled(True)


def main():
    dry_run = "--dry-run" in sys.argv
    before = sha256(PROJECT)
    app = QgsApplication([], False)
    app.initQgis()
    project = QgsProject.instance()
    if not project.read(str(PROJECT)):
        raise RuntimeError("Cannot read batch QGIS project")
    r01, r02 = groups(project)
    r01.setItemVisibilityChecked(True)
    r01.setExpanded(True)
    r02.setItemVisibilityChecked(False)
    r02.setExpanded(False)
    project.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(TARGET_EXTENT, project.crs()))
    shorten_point_labels(project)
    verify(project)
    if dry_run:
        print("Dry run: project not written")
        return
    stage = PROJECT.with_name("batch.r01_focus_staging.qgz")
    if stage.exists():
        raise RuntimeError(f"Staging file exists: {stage}")
    project.setFileName(str(stage))
    if not project.write():
        raise RuntimeError("Cannot write staged project")
    project.clear()
    if not project.read(str(stage)):
        raise RuntimeError("Cannot reopen staged project")
    verify(project)
    if sha256(PROJECT) != before:
        raise RuntimeError("Project changed during save")
    backup = PROJECT.with_name(
        "batch.before_r01_focus_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".qgz"
    )
    shutil.copy2(PROJECT, backup)
    os.replace(stage, PROJECT)
    print("Project:", PROJECT)
    print("Backup:", backup)


if __name__ == "__main__":
    main()
