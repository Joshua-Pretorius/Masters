from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

from .geopackage import CLASSES, CONFIDENCE_LEVELS
from .models import DigitisingTask


LOG = logging.getLogger(__name__)

RASTER_LABELS = {
    "vv_refined_lee_db": "VV refined Lee (dB)",
    "vv_refined_lee": "VV refined Lee",
    "vv": "VV native",
    "vh": "VH native",
    "vv_glcm_mean": "VV GLCM mean",
    "vv_glcm_std": "VV GLCM standard deviation",
    "vv_glcm_entropy": "VV GLCM entropy",
    "decomp_entropy": "Decomposition entropy",
    "decomp_anisotropy": "Decomposition anisotropy",
    "decomp_alpha": "Decomposition alpha",
}


def _qgis():
    try:
        from qgis.PyQt.QtGui import QColor
        from qgis.core import (
            Qgis,
            QgsApplication,
            QgsCategorizedSymbolRenderer,
            QgsDefaultValue,
            QgsEditorWidgetSetup,
            QgsPalLayerSettings,
            QgsProject,
            QgsRasterLayer,
            QgsReferencedRectangle,
            QgsRendererCategory,
            QgsSymbol,
            QgsTextFormat,
            QgsVectorLayer,
            QgsVectorLayerSimpleLabeling,
        )
    except ImportError as exc:
        raise RuntimeError(
            "PyQGIS is required to generate .qgz projects. Run this command through the digitising Docker service."
        ) from exc
    return locals()


def _configure_annotations(layer, task: DigitisingTask, q: dict[str, object]) -> None:
    QgsDefaultValue = q["QgsDefaultValue"]
    QgsEditorWidgetSetup = q["QgsEditorWidgetSetup"]
    QgsSymbol = q["QgsSymbol"]
    QgsRendererCategory = q["QgsRendererCategory"]
    QgsCategorizedSymbolRenderer = q["QgsCategorizedSymbolRenderer"]
    QColor = q["QColor"]

    class_index = layer.fields().indexOf("Class")
    confidence_index = layer.fields().indexOf("confidence")
    layer.setEditorWidgetSetup(class_index, QgsEditorWidgetSetup("ValueMap", {"map": [{v: v} for v in CLASSES]}))
    layer.setEditorWidgetSetup(
        confidence_index,
        QgsEditorWidgetSetup("ValueMap", {"map": [{v: v} for v in CONFIDENCE_LEVELS]}),
    )
    defaults = {
        "task_id": task.task_id,
        "obs_id": task.observation_id,
        "dataset": task.dataset,
        "role": task.role,
        "scene_id": task.scene.scene_id,
        "area": task.area,
        "optical_utc": task.optical_time_representative,
        "sar_utc": task.sar_time,
        "delta_h": task.delta_hours,
    }
    form = layer.editFormConfig()
    read_only = {"feature_uuid", "patch_id", *defaults.keys()}
    for field_name, value in defaults.items():
        index = layer.fields().indexOf(field_name)
        expression = str(value) if isinstance(value, (float, int)) else "'" + str(value).replace("'", "''") + "'"
        layer.setDefaultValueDefinition(index, QgsDefaultValue(expression, True))
    for field_name in read_only:
        index = layer.fields().indexOf(field_name)
        if index >= 0:
            form.setReadOnly(index, True)
    layer.setEditFormConfig(form)

    colours = {
        "plastic": "#e31a1c",
        "ship": "#ff7f00",
        "wake": "#fdbf6f",
        "slick": "#6a3d9a",
        "calm_water": "#1f78b4",
        "open_ocean": "#33a02c",
        "other": "#b15928",
        "uncertain": "#bdbdbd",
    }
    categories = []
    for class_name in CLASSES:
        symbol = QgsSymbol.defaultSymbol(layer.geometryType())
        colour = QColor(colours[class_name])
        colour.setAlpha(90)
        symbol.setColor(colour)
        categories.append(QgsRendererCategory(class_name, symbol, class_name))
    layer.setRenderer(QgsCategorizedSymbolRenderer("Class", categories))


def _configure_reference_labels(layer, q: dict[str, object]) -> None:
    QgsPalLayerSettings = q["QgsPalLayerSettings"]
    QgsTextFormat = q["QgsTextFormat"]
    QgsVectorLayerSimpleLabeling = q["QgsVectorLayerSimpleLabeling"]
    settings = QgsPalLayerSettings()
    settings.fieldName = "delta_lbl"
    settings.enabled = True
    text_format = QgsTextFormat()
    text_format.setSize(9)
    settings.setFormat(text_format)
    layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
    layer.setLabelsEnabled(True)


def _configure_metadata_links(layer, q: dict[str, object]) -> None:
    QgsEditorWidgetSetup = q["QgsEditorWidgetSetup"]
    for field_name in ("planet_url", "s2_url"):
        index = layer.fields().indexOf(field_name)
        if index >= 0:
            layer.setEditorWidgetSetup(index, QgsEditorWidgetSetup("TextEdit", {"UseLink": True, "IsMultiline": False}))


def _add_task(project, parent_group, task: DigitisingTask, q: dict[str, object]):
    QgsVectorLayer = q["QgsVectorLayer"]
    QgsRasterLayer = q["QgsRasterLayer"]
    group = parent_group.addGroup(f"{task.task_id} — {task.delta_label}")
    gpkg = task.task_dir / "task.gpkg"

    annotation = QgsVectorLayer(f"{gpkg}|layername=annotations", "Annotations (EDIT THIS)", "ogr")
    if not annotation.isValid():
        raise RuntimeError(f"Could not load annotations from {gpkg}")
    _configure_annotations(annotation, task, q)
    project.addMapLayer(annotation, False)
    group.addLayer(annotation)

    reference = QgsVectorLayer(f"{gpkg}|layername=reference_points", "Optical reference points", "ogr")
    if reference.isValid():
        _configure_reference_labels(reference, q)
        project.addMapLayer(reference, False)
        group.addLayer(reference)

    predicted = QgsVectorLayer(f"{gpkg}|layername=predicted_points", "Drift-predicted points", "ogr")
    if predicted.isValid():
        project.addMapLayer(predicted, False)
        group.addLayer(predicted)

    envelopes = QgsVectorLayer(f"{gpkg}|layername=prediction_envelopes", "Prediction uncertainty", "ogr")
    if envelopes.isValid():
        project.addMapLayer(envelopes, False)
        group.addLayer(envelopes)

    metadata = QgsVectorLayer(f"{gpkg}|layername=task_metadata", "Task metadata and optical links", "ogr")
    if metadata.isValid():
        _configure_metadata_links(metadata, q)
        project.addMapLayer(metadata, False)
        group.addLayer(metadata)

    raster_group = group.addGroup("SAR rasters")
    ordered = list(RASTER_LABELS)
    if task.scene.reference_grid:
        raster = QgsRasterLayer(str(task.scene.reference_grid), "AOI reference")
        if raster.isValid():
            project.addMapLayer(raster, False)
            raster_group.addLayer(raster)
    visible_raster_selected = False
    for key in ordered:
        path = task.scene.outputs.get(key)
        if not path:
            continue
        raster = QgsRasterLayer(str(path), RASTER_LABELS[key])
        if raster.isValid():
            project.addMapLayer(raster, False)
            node = raster_group.addLayer(raster)
            visible = key == "vv_refined_lee_db" or not visible_raster_selected
            node.setItemVisibilityChecked(visible)
            visible_raster_selected = visible_raster_selected or visible
    return annotation, reference if reference.isValid() and not reference.extent().isEmpty() else annotation


def build_qgis_project(path: Path, tasks: Iterable[DigitisingTask], *, title: str) -> None:
    q = _qgis()
    QgsApplication = q["QgsApplication"]
    QgsProject = q["QgsProject"]
    Qgis = q["Qgis"]
    owns_application = QgsApplication.instance() is None
    application = None
    if owns_application:
        application = QgsApplication([], False)
        application.initQgis()
    try:
        project = QgsProject()
        project.setTitle(title)
        project.setPresetHomePath(str(path.parent))
        if hasattr(project, "setFilePathStorage"):
            project.setFilePathStorage(Qgis.FilePathType.Relative)
        root = project.layerTreeRoot()
        first_annotation = None
        first_view_layer = None
        for task in tasks:
            annotation, view_layer = _add_task(project, root, task, q)
            first_annotation = first_annotation or annotation
            first_view_layer = first_view_layer or view_layer
        if first_annotation is not None:
            project.setCrs(first_annotation.crs())
            if hasattr(project, "viewSettings") and first_view_layer is not None and not first_view_layer.extent().isEmpty():
                project.viewSettings().setDefaultViewExtent(
                    q["QgsReferencedRectangle"](first_view_layer.extent(), first_view_layer.crs())
                )
        path.parent.mkdir(parents=True, exist_ok=True)
        if not project.write(str(path)):
            raise RuntimeError(f"QGIS could not write project {path}")
    finally:
        if application is not None:
            application.exitQgis()
