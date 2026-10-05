"""Add the supplied Sentinel-2 TCI to both 16PCC scene groups."""

import hashlib
import os
from pathlib import Path
import shutil
import sys
from datetime import datetime, timezone

QGIS_ROOT = Path(r"C:\Program Files\QGIS 3.40.4")
for subdir in ("bin", "apps/qt5/bin", "apps/qgis-ltr/bin", "apps/gdal/bin", "apps/Python312/DLLs"):
    directory = QGIS_ROOT / subdir
    if directory.is_dir():
        os.add_dll_directory(str(directory))
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from qgis.core import QgsApplication, QgsMultiBandColorRenderer, QgsProject, QgsRasterLayer


PROJECT = Path(
    r"D:\Joshua\golden_marida_16pcc_2018\digitising_batches"
    r"\golden_marida_16pcc_2018\batch.qgz"
)
TCI = Path(
    r"C:\Users\Joshua Pretorius\Desktop"
    r"\S2B_MSIL1C_20180830T160819_N0500_R140_T16PCC_20230730T125342.SAFE"
    r"\S2B_MSIL1C_20180830T160819_N0500_R140_T16PCC_20230730T125342.SAFE"
    r"\GRANULE\L1C_T16PCC_A007745_20180830T161630\IMG_DATA"
    r"\T16PCC_20180830T160819_TCI.jp2"
)
GROUP_NAME = "Sentinel-2 optical — 2018-08-30 16:08 UTC"
LAYER_NAME = "True colour RGB — B04 red / B03 green / B02 blue (10 m TCI)"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def optical_nodes(project):
    scene_groups = [
        group
        for group in project.layerTreeRoot().findGroups()
        if "marida_16PCC_2018_08_30_before_R0" in group.name()
    ]
    if len(scene_groups) != 2:
        raise RuntimeError(f"Expected two 16PCC SAR scene groups, found {len(scene_groups)}")
    found = []
    for scene_group in scene_groups:
        subgroups = [g for g in scene_group.findGroups() if g.name() == GROUP_NAME]
        if len(subgroups) != 1:
            raise RuntimeError(f"Optical group missing or duplicated in {scene_group.name()}")
        layers = [n.layer() for n in subgroups[0].findLayers()]
        if len(layers) != 1 or not layers[0] or not layers[0].isValid():
            raise RuntimeError(f"Optical layer invalid in {scene_group.name()}")
        if Path(layers[0].source()) != TCI:
            raise RuntimeError(f"Unexpected optical source in {scene_group.name()}")
        found.append(scene_group.name())
    return found


def main():
    if not TCI.is_file() or not PROJECT.is_file():
        raise FileNotFoundError("16PCC project or Sentinel-2 TCI is missing")
    original_hash = digest(PROJECT)
    app = QgsApplication([], False)
    app.initQgis()
    project = QgsProject.instance()
    if not project.read(str(PROJECT)):
        raise RuntimeError("QGIS could not read the existing batch project")
    scene_groups = [
        group
        for group in project.layerTreeRoot().findGroups()
        if "marida_16PCC_2018_08_30_before_R0" in group.name()
    ]
    if len(scene_groups) != 2:
        raise RuntimeError(f"Expected two 16PCC SAR scene groups, found {len(scene_groups)}")
    for scene_group in scene_groups:
        if any(g.name() == GROUP_NAME for g in scene_group.findGroups()):
            raise RuntimeError(f"Optical group already exists in {scene_group.name()}")
        layer = QgsRasterLayer(str(TCI), LAYER_NAME, "gdal")
        if not layer.isValid() or layer.bandCount() != 3:
            raise RuntimeError("TCI did not load as a valid three-band raster")
        layer.setRenderer(QgsMultiBandColorRenderer(layer.dataProvider(), 1, 2, 3))
        project.addMapLayer(layer, False)
        sar_group_index = next(
            (i for i, child in enumerate(scene_group.children()) if child.name() == "SAR rasters"),
            len(scene_group.children()),
        )
        optical_group = scene_group.insertGroup(sar_group_index, GROUP_NAME)
        node = optical_group.addLayer(layer)
        node.setItemVisibilityChecked(False)
        optical_group.setItemVisibilityChecked(False)
        optical_group.setExpanded(False)
        print(f"Added {LAYER_NAME} under {scene_group.name()}")

    if "--dry-run" in sys.argv:
        print("Dry run: valid RGB layers added in memory; project not written")
        return

    stage = PROJECT.with_name("batch.true_colour_staging.qgz")
    if stage.exists():
        raise RuntimeError(f"Staging file already exists: {stage}")
    project.setFileName(str(stage))
    if not project.write():
        raise RuntimeError("QGIS could not write the staged project")
    project.clear()
    if not project.read(str(stage)):
        raise RuntimeError("QGIS could not reopen the staged project")
    print("Verified:", " | ".join(optical_nodes(project)))
    if digest(PROJECT) != original_hash:
        raise RuntimeError("Project changed during edit; original was not replaced")
    backup = PROJECT.with_name(
        "batch.before_true_colour_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".qgz"
    )
    shutil.copy2(PROJECT, backup)
    os.replace(stage, PROJECT)
    print("Project:", PROJECT)
    print("Backup:", backup)


if __name__ == "__main__":
    main()
