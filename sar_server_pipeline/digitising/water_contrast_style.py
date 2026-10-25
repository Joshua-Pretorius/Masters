"""QGIS styling, kept independent of rasterio for desktop migration."""

from __future__ import annotations

VERSION = "water_contrast_v1"
LABELS = (
    "Refined Lee VV | signed contrast (dB)",
    "VV 30 m patch | signed contrast (dB)",
    "VH 30 m patch | signed contrast (dB)",
    "VV 60 m patch | signed contrast (dB)",
)


def add_qgis_layers(project, group, result):
    """Use one multiband source directly; relative project paths remain portable."""
    from qgis.core import (
        QgsRasterLayer,
        QgsColorRampShader,
        QgsRasterShader,
        QgsSingleBandPseudoColorRenderer,
    )
    from qgis.PyQt.QtGui import QColor

    if result.get("status") != "complete":
        return []
    layers = []
    for band, label in enumerate(LABELS, 1):
        options = QgsRasterLayer.LayerOptions()
        options.loadDefaultStyle = False
        layer = QgsRasterLayer(result["path"], label, "gdal", options)
        if not layer.isValid():
            raise RuntimeError(f'Cannot load {result["path"]}')
        ramp = QgsColorRampShader()
        ramp.setColorRampType(QgsColorRampShader.Interpolated)
        ramp.setMinimumValue(-6)
        ramp.setMaximumValue(6)
        ramp.setClip(False)
        ramp.setColorRampItemList(
            [
                QgsColorRampShader.ColorRampItem(v, QColor(c), str(v))
                for v, c in [(-6, "#2166ac"), (0, "#f7f7f7"), (6, "#b2182b")]
            ]
        )
        shader = QgsRasterShader(-6, 6)
        shader.setRasterShaderFunction(ramp)
        renderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(), band, shader)
        renderer.setClassificationMin(-6)
        renderer.setClassificationMax(6)
        layer.setRenderer(renderer)
        layer.setCustomProperty("water_contrast/version", VERSION)
        metadata = layer.metadata()
        metadata.setAbstract(
            "Signed water-relative backscatter contrast. Points convex hull + 100 km, clipped to existing SAR. Native grid; nominal patch sizes rounded to odd cell windows. Fixed blue/white/red -6/0/+6 dB. WorldCover 2021 permanent water + 30 m margin. No target fitting or significance calibration. VH instrument noise unassessed. Exact method and windows: water_contrast.json beside raster."
        )
        layer.setMetadata(metadata)
        project.addMapLayer(layer, False)
        node = group.insertLayer(band - 1, layer)
        node.setItemVisibilityChecked(False)
        node.setExpanded(False)
        layers.append(layer)
    return layers
