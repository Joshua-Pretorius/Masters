#!/usr/bin/env python3
"""Add styled experimental SAR visualisation rasters to one closed QGIS project."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from qgis.PyQt.QtGui import QColor
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsColorRampShader,
    QgsContrastEnhancement,
    QgsMultiBandColorRenderer,
    QgsProject,
    QgsRasterLayer,
    QgsRasterShader,
    QgsSingleBandGrayRenderer,
    QgsSingleBandPseudoColorRenderer,
)


SAR_GROUP = "SAR 2019-04-25 03:10:55 UTC"
RASTER_GROUP = "SAR rasters"
VIS_GROUP = "Experimental target contrast | MERIA_SA_002 backward"


def find_direct_group(parent, name: str):
    for child in parent.children():
        if child.nodeType() == child.NodeGroup and child.name() == name:
            return child
    return None


def set_gray(layer: QgsRasterLayer, minimum: float, maximum: float) -> None:
    renderer = QgsSingleBandGrayRenderer(layer.dataProvider(), 1)
    enhancement = QgsContrastEnhancement(layer.dataProvider().dataType(1))
    enhancement.setMinimumValue(minimum)
    enhancement.setMaximumValue(maximum)
    enhancement.setContrastEnhancementAlgorithm(QgsContrastEnhancement.StretchToMinimumMaximum)
    renderer.setContrastEnhancement(enhancement)
    layer.setRenderer(renderer)


def set_pseudocolor(layer: QgsRasterLayer, items: list[tuple[float, str, str]], discrete: bool) -> None:
    function = QgsColorRampShader()
    function.setColorRampType(QgsColorRampShader.Discrete if discrete else QgsColorRampShader.Interpolated)
    function.setColorRampItemList(
        [QgsColorRampShader.ColorRampItem(value, QColor(color), label) for value, color, label in items]
    )
    shader = QgsRasterShader()
    shader.setRasterShaderFunction(function)
    layer.setRenderer(QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, shader))


def add_layer(project: QgsProject, group, path: Path, name: str, abstract: str) -> tuple[QgsRasterLayer, object]:
    layer = QgsRasterLayer(str(path), name)
    if not layer.isValid():
        raise RuntimeError(f"Could not load derived raster: {path}")
    metadata = layer.metadata()
    metadata.setAbstract(abstract)
    layer.setMetadata(metadata)
    layer.setCustomProperty("experimental/scene_specific", True)
    layer.setCustomProperty("experimental/not_material_classifier", True)
    project.addMapLayer(layer, False)
    node = group.addLayer(layer)
    return layer, node


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--visualisation-dir", type=Path, required=True)
    parser.add_argument("--analysis-report", type=Path, required=True)
    args = parser.parse_args()

    project_path = args.project.resolve()
    visualisation_dir = args.visualisation_dir.resolve()
    report = json.loads(args.analysis_report.read_text(encoding="utf-8"))
    paths = {
        "rgb": visualisation_dir / "S1_20190425_target_contrast_rgb.tif",
        "margin": visualisation_dir / "S1_20190425_target_margin.tif",
        "votes": visualisation_dir / "S1_20190425_target_rule_votes.tif",
        "vh": visualisation_dir / "S1_20190425_vh_db_aligned_utm10m.tif",
        "ratio": visualisation_dir / "S1_20190425_vv_minus_vh_db_aligned_utm10m.tif",
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing derived rasters: {missing}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    batch_root = project_path.parents[2]
    backup = batch_root / "project_visualisation_backups" / stamp / project_path.relative_to(batch_root)
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(project_path, backup)

    application = QgsApplication([], False)
    application.initQgis()
    project = None
    verification = None
    try:
        project = QgsProject()
        if not project.read(str(project_path)):
            raise RuntimeError(f"Could not read QGIS project: {project_path}")
        root = project.layerTreeRoot()
        sar_group = find_direct_group(root, SAR_GROUP)
        if sar_group is None:
            raise RuntimeError(f"Missing project group: {SAR_GROUP}")
        raster_group = find_direct_group(sar_group, RASTER_GROUP)
        if raster_group is None:
            raise RuntimeError(f"Missing project group: {SAR_GROUP} / {RASTER_GROUP}")
        previous = find_direct_group(raster_group, VIS_GROUP)
        if previous is not None:
            for layer_node in previous.findLayers():
                project.removeMapLayer(layer_node.layerId())
            raster_group.removeChildNode(previous)
        group = raster_group.insertGroup(0, VIS_GROUP)
        group.setItemVisibilityChecked(True)
        group.setCustomProperty(
            "experimental/note",
            "Tuned from local MERIA_SA_002 backward annotations for visual inspection only; not a validated plastic classifier.",
        )
        warning = (
            "Scene-specific visual inspection aid tuned from six plastic-proxy, three ship, two water, "
            "and one other annotation polygons. The highlight shapefile is not part of this display. "
            "Do not treat coloured pixels as automatic plastic labels."
        )

        rgb, rgb_node = add_layer(
            project,
            group,
            paths["rgb"],
            "01 Target contrast RGB | H / low A / VH band-pass",
            warning + " RGB: red=decomposition entropy, green=inverted anisotropy, blue=intermediate VH dB.",
        )
        rgb.setRenderer(QgsMultiBandColorRenderer(rgb.dataProvider(), 1, 2, 3))
        rgb_node.setItemVisibilityChecked(True)

        margin, margin_node = add_layer(
            project,
            group,
            paths["margin"],
            "02 Five-band target margin | experimental",
            warning + " Higher values are more similar to the target proxy distribution than to the labelled distractors.",
        )
        margin_range = report["gaussian_target_margin"]
        distractor_low = float(margin_range["distractor_percentiles_p02_p25_p50_p75_p98"][0])
        target_high = float(margin_range["target_percentiles_p02_p25_p50_p75_p98"][4])
        threshold = float(margin_range["threshold"]["threshold"])
        set_pseudocolor(
            margin,
            [
                (distractor_low, "#231151", "low target similarity"),
                (threshold, "#cc4778", f"descriptive threshold {threshold:.2f}"),
                (target_high, "#f0f921", "high target similarity"),
            ],
            discrete=False,
        )
        margin_node.setItemVisibilityChecked(False)

        votes, votes_node = add_layer(
            project,
            group,
            paths["votes"],
            "03 Target-rule votes | 0 to 6",
            warning + " Each pixel records how many of the six documented band thresholds it satisfies.",
        )
        set_pseudocolor(
            votes,
            [
                (0, "#20114b", "0"),
                (1, "#3b0f70", "1"),
                (2, "#8c2981", "2"),
                (3, "#de4968", "3"),
                (4, "#fe9f6d", "4"),
                (5, "#fcfdbf", "5"),
                (6, "#ffffff", "6"),
            ],
            discrete=True,
        )
        votes_node.setItemVisibilityChecked(False)

        vh, vh_node = add_layer(
            project,
            group,
            paths["vh"],
            "04 VH dB | aligned UTM 10 m",
            warning + " VH was converted with 10 log10 and resampled to the exact VV UTM grid before comparison.",
        )
        set_gray(vh, -34.06, -24.78)
        vh_node.setItemVisibilityChecked(False)

        ratio, ratio_node = add_layer(
            project,
            group,
            paths["ratio"],
            "05 VV dB minus VH dB | aligned UTM 10 m",
            warning + " This is subtraction in dB space, equivalent to a VV/VH ratio in linear power.",
        )
        set_gray(ratio, 3.65, 15.49)
        ratio_node.setItemVisibilityChecked(False)

        try:
            project.setFilePathStorage(Qgis.FilePathType.Relative)
        except AttributeError:
            project.writeEntry("Paths", "Absolute", False)
        if not project.write(str(project_path)):
            raise RuntimeError(f"Could not save QGIS project: {project_path}")

        verification = QgsProject()
        if not verification.read(str(project_path)):
            raise RuntimeError("Saved project could not be reopened")
        verify_sar = find_direct_group(verification.layerTreeRoot(), SAR_GROUP)
        verify_rasters = find_direct_group(verify_sar, RASTER_GROUP) if verify_sar else None
        verify_group = find_direct_group(verify_rasters, VIS_GROUP) if verify_rasters else None
        if verify_group is None:
            raise RuntimeError("Saved visualisation group is missing")
        verified_layers = [node.layer() for node in verify_group.findLayers()]
        if len(verified_layers) != 5 or not all(layer and layer.isValid() for layer in verified_layers):
            raise RuntimeError("One or more saved visualisation layers are invalid")
        print(
            json.dumps(
                {
                    "project": str(project_path),
                    "backup": str(backup),
                    "group": f"{SAR_GROUP} / {RASTER_GROUP} / {VIS_GROUP}",
                    "layers": [layer.name() for layer in verified_layers],
                },
                indent=2,
            ),
            flush=True,
        )
        return 0
    except Exception:
        shutil.copy2(backup, project_path)
        raise
    finally:
        if verification is not None:
            verification.clear()
        if project is not None:
            project.clear()
        application.exitQgis()


if __name__ == "__main__":
    raise SystemExit(main())
