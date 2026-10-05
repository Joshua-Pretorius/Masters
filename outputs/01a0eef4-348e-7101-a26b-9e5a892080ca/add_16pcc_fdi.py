"""Add the 16PCC Level-1C FDI visualisation to both SAR scene groups."""

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

from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsApplication,
    QgsColorRampShader,
    QgsProject,
    QgsRasterLayer,
    QgsRasterShader,
    QgsSingleBandPseudoColorRenderer,
)

PROJECT = Path(
    r"D:\Joshua\golden_marida_16pcc_2018\digitising_batches"
    r"\golden_marida_16pcc_2018\batch.qgz"
)
FDI_SOURCE = Path(
    r"D:\Masters\outputs\01a0eef4-348e-7101-a26b-9e5a892080ca"
    r"\16pcc_20180830_fdi_l1c_toa_10m.tif"
)
FDI_DEST = Path(
    r"D:\Joshua\golden_marida_16pcc_2018\optical"
    r"\16pcc_20180830_fdi_l1c_toa_10m.tif"
)
GROUP_NAME = "Sentinel-2 optical — 2018-08-30 16:08 UTC"
LAYER_NAME = "FDI — B08/B06/B11 (L1C TOA, diagnostic)"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fdi_layers(project, expected_path):
    found = []
    scene_groups = [
        group for group in project.layerTreeRoot().findGroups()
        if "marida_16PCC_2018_08_30_before_R0" in group.name()
    ]
    if len(scene_groups) != 2:
        raise RuntimeError(f"Expected two SAR groups, found {len(scene_groups)}")
    for scene_group in scene_groups:
        optical = [g for g in scene_group.findGroups() if g.name() == GROUP_NAME]
        if len(optical) != 1:
            raise RuntimeError(f"Missing optical subgroup: {scene_group.name()}")
        candidates = [n.layer() for n in optical[0].findLayers() if n.name() == LAYER_NAME]
        if len(candidates) != 1 or not candidates[0] or not candidates[0].isValid():
            raise RuntimeError(f"FDI layer missing or invalid: {scene_group.name()}")
        if Path(candidates[0].source()) != expected_path:
            raise RuntimeError(f"Wrong FDI source: {scene_group.name()}")
        if not isinstance(candidates[0].renderer(), QgsSingleBandPseudoColorRenderer):
            raise RuntimeError(f"FDI pseudocolor style missing: {scene_group.name()}")
        found.append(scene_group.name())
    return found


def make_renderer(layer):
    ramp = QgsColorRampShader(0.018, 0.08)
    ramp.setColorRampType(QgsColorRampShader.Interpolated)
    ramp.setColorRampItemList([
        QgsColorRampShader.ColorRampItem(-0.02, QColor("#082567"), "Below local background"),
        QgsColorRampShader.ColorRampItem(0.020, QColor("#225ea8"), "Low"),
        QgsColorRampShader.ColorRampItem(0.025, QColor("#41b6c4"), "Nearby water background"),
        QgsColorRampShader.ColorRampItem(0.030, QColor("#ffffbf"), "Elevated"),
        QgsColorRampShader.ColorRampItem(0.045, QColor("#fdae61"), "High"),
        QgsColorRampShader.ColorRampItem(0.080, QColor("#d7191c"), "Very high"),
    ])
    shader = QgsRasterShader()
    shader.setRasterShaderFunction(ramp)
    renderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, shader)
    renderer.setClassificationMin(0.018)
    renderer.setClassificationMax(0.08)
    return renderer


def main():
    dry_run = "--dry-run" in sys.argv
    if not PROJECT.is_file() or not FDI_SOURCE.is_file():
        raise FileNotFoundError("16PCC project or staged FDI raster missing")
    original_hash = digest(PROJECT)
    fdi_hash = digest(FDI_SOURCE)
    if dry_run:
        layer_path = FDI_SOURCE
    else:
        FDI_DEST.parent.mkdir(parents=True, exist_ok=True)
        if FDI_DEST.exists():
            if digest(FDI_DEST) != fdi_hash:
                raise RuntimeError(f"Existing destination has different data: {FDI_DEST}")
        else:
            temp_raster = FDI_DEST.with_suffix(".copying.tif")
            if temp_raster.exists():
                raise RuntimeError(f"Copy staging file already exists: {temp_raster}")
            shutil.copy2(FDI_SOURCE, temp_raster)
            if digest(temp_raster) != fdi_hash:
                raise RuntimeError("FDI copy hash mismatch")
            os.replace(temp_raster, FDI_DEST)
        layer_path = FDI_DEST

    app = QgsApplication([], False)
    app.initQgis()
    project = QgsProject.instance()
    if not project.read(str(PROJECT)):
        raise RuntimeError("QGIS could not read the 16PCC batch project")
    scene_groups = [
        group for group in project.layerTreeRoot().findGroups()
        if "marida_16PCC_2018_08_30_before_R0" in group.name()
    ]
    if len(scene_groups) != 2:
        raise RuntimeError(f"Expected two SAR groups, found {len(scene_groups)}")
    for scene_group in scene_groups:
        optical = [g for g in scene_group.findGroups() if g.name() == GROUP_NAME]
        if len(optical) != 1:
            raise RuntimeError(f"Missing optical subgroup: {scene_group.name()}")
        if any(n.name() == LAYER_NAME for n in optical[0].findLayers()):
            raise RuntimeError(f"FDI already present in {scene_group.name()}")
        layer = QgsRasterLayer(str(layer_path), LAYER_NAME, "gdal")
        if not layer.isValid() or layer.bandCount() != 1:
            raise RuntimeError("FDI raster did not load as a valid single-band raster")
        layer.setRenderer(make_renderer(layer))
        project.addMapLayer(layer, False)
        node = optical[0].addLayer(layer)
        node.setItemVisibilityChecked(False)
        print("Added FDI under", scene_group.name())
    if dry_run:
        print("Dry run: valid FDI layers and pseudocolor renderers created in memory")
        return

    stage = PROJECT.with_name("batch.fdi_staging.qgz")
    if stage.exists():
        raise RuntimeError(f"Project staging file already exists: {stage}")
    project.setFileName(str(stage))
    if not project.write():
        raise RuntimeError("QGIS could not write staged project")
    project.clear()
    if not project.read(str(stage)):
        raise RuntimeError("QGIS could not reopen staged project")
    print("Verified:", " | ".join(fdi_layers(project, FDI_DEST)))
    if digest(PROJECT) != original_hash:
        raise RuntimeError("Project changed during edit; original not replaced")
    backup = PROJECT.with_name(
        "batch.before_fdi_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".qgz"
    )
    shutil.copy2(PROJECT, backup)
    os.replace(stage, PROJECT)
    print("Project:", PROJECT)
    print("FDI raster:", FDI_DEST)
    print("Backup:", backup)


if __name__ == "__main__":
    main()
