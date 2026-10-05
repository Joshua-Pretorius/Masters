from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

from .geopackage import CLASSES, CONFIDENCE_LEVELS, TRAINING_STATUSES
from .models import DigitisingTask
from .scene import SceneGroup


LOG = logging.getLogger(__name__)

# A QgsApplication cannot be repeatedly torn down and safely re-created in the
# same Python process. Batch preparation writes many projects, so keep one
# off-screen application alive until the short-lived container exits.
_QGIS_APPLICATION = None

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


def _ensure_qgis_application(QgsApplication):
    global _QGIS_APPLICATION
    if _QGIS_APPLICATION is not None:
        return _QGIS_APPLICATION
    application = QgsApplication.instance()
    if application is None:
        application = QgsApplication([], False)
        application.initQgis()
    _QGIS_APPLICATION = application
    return application


def _configure_annotations(layer, task: DigitisingTask, q: dict[str, object]) -> None:
    QgsDefaultValue = q["QgsDefaultValue"]
    QgsEditorWidgetSetup = q["QgsEditorWidgetSetup"]
    QgsSymbol = q["QgsSymbol"]
    QgsRendererCategory = q["QgsRendererCategory"]
    QgsCategorizedSymbolRenderer = q["QgsCategorizedSymbolRenderer"]
    QColor = q["QColor"]

    class_index = layer.fields().indexOf("Class")
    layer.setEditorWidgetSetup(class_index, QgsEditorWidgetSetup("ValueMap", {"map": [{v: v} for v in CLASSES]}))
    for field_name in ("feature_confidence", "correspondence_confidence"):
        index = layer.fields().indexOf(field_name)
        if index >= 0:
            layer.setEditorWidgetSetup(
                index,
                QgsEditorWidgetSetup("ValueMap", {"map": [{v: v} for v in CONFIDENCE_LEVELS]}),
            )
    training_status_index = layer.fields().indexOf("training_status")
    if training_status_index >= 0:
        layer.setEditorWidgetSetup(
            training_status_index,
            QgsEditorWidgetSetup("ValueMap", {"map": [{v: v} for v in TRAINING_STATUSES]}),
        )
    legacy_confidence_index = layer.fields().indexOf("confidence")
    if legacy_confidence_index >= 0:
        layer.setEditorWidgetSetup(legacy_confidence_index, QgsEditorWidgetSetup("Hidden", {}))
    aliases = {
        "feature_confidence": "Feature confidence",
        "correspondence_confidence": "Correspondence confidence",
        "training_status": "Training status",
        "evidence_obs_ids": "Supporting optical observation IDs (comma separated)",
    }
    for field_name, alias in aliases.items():
        index = layer.fields().indexOf(field_name)
        if index >= 0:
            layer.setFieldAlias(index, alias)
    immutable_defaults = {
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
    review_defaults = {
        "feature_confidence": "not_assessed",
        "correspondence_confidence": "not_assessed",
        "training_status": "candidate",
    }
    form = layer.editFormConfig()
    read_only = {"feature_uuid", "patch_id", *immutable_defaults.keys()}
    for field_name, value in immutable_defaults.items():
        index = layer.fields().indexOf(field_name)
        if index < 0:
            continue
        expression = str(value) if isinstance(value, (float, int)) else "'" + str(value).replace("'", "''") + "'"
        layer.setDefaultValueDefinition(index, QgsDefaultValue(expression, True))
    for field_name, value in review_defaults.items():
        index = layer.fields().indexOf(field_name)
        if index >= 0:
            expression = "'" + value.replace("'", "''") + "'"
            layer.setDefaultValueDefinition(index, QgsDefaultValue(expression, False))
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
    QgsCategorizedSymbolRenderer = q["QgsCategorizedSymbolRenderer"]
    QgsRendererCategory = q["QgsRendererCategory"]
    QgsSymbol = q["QgsSymbol"]
    QgsTextFormat = q["QgsTextFormat"]
    QgsVectorLayerSimpleLabeling = q["QgsVectorLayerSimpleLabeling"]
    QColor = q["QColor"]

    categories = []
    for value, colour_name, label, opacity in (
        (1, "#e31a1c", "Label-derived OpenDrift seed", 255),
        (0, "#808080", "AOI context (not a drift seed)", 90),
    ):
        symbol = QgsSymbol.defaultSymbol(layer.geometryType())
        colour = QColor(colour_name)
        colour.setAlpha(opacity)
        symbol.setColor(colour)
        categories.append(QgsRendererCategory(value, symbol, label))
    layer.setRenderer(QgsCategorizedSymbolRenderer("seed_ok", categories))

    settings = QgsPalLayerSettings()
    settings.fieldName = 'CASE WHEN "seed_ok" = 1 THEN "point_id" || \'\\n\' || "delta_lbl" END'
    settings.isExpression = True
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


def _add_rasters(project, group, task: DigitisingTask, q: dict[str, object]) -> None:
    QgsRasterLayer = q["QgsRasterLayer"]
    raster_group = group.addGroup("SAR rasters")
    if task.scene.reference_grid:
        raster = QgsRasterLayer(str(task.scene.reference_grid), "AOI reference")
        if raster.isValid():
            project.addMapLayer(raster, False)
            raster_group.addLayer(raster)
    visible_raster_selected = False
    for key in RASTER_LABELS:
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


def _add_task(project, parent_group, task: DigitisingTask, q: dict[str, object], *,
              add_annotation: bool = True, add_rasters: bool = True):
    QgsVectorLayer = q["QgsVectorLayer"]
    group = parent_group.addGroup(
        f"{task.observation_id} | {task.optical_time_start[:10]} | {task.role} | {task.delta_label}"
    )
    gpkg = task.task_dir / "task.gpkg"

    annotation = None
    if add_annotation:
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

    if add_rasters:
        _add_rasters(project, group, task, q)
    return annotation, reference if reference.isValid() and not reference.extent().isEmpty() else annotation


def build_qgis_project(path: Path, tasks: Iterable[DigitisingTask], *, title: str) -> None:
    q = _qgis()
    QgsApplication = q["QgsApplication"]
    QgsProject = q["QgsProject"]
    Qgis = q["Qgis"]
    _ensure_qgis_application(QgsApplication)
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


def build_scene_qgis_project(path: Path, groups: Iterable[SceneGroup], *, title: str) -> None:
    """Render each physical acquisition once with all of its optical comparisons."""
    q = _qgis()
    _ensure_qgis_application(q["QgsApplication"])
    project = q["QgsProject"]()
    project.setTitle(title)
    project.setPresetHomePath(str(path.parent))
    if hasattr(project, "setFilePathStorage"):
        project.setFilePathStorage(q["Qgis"].FilePathType.Relative)
    first_annotation = None
    first_view_layer = None
    for scene_group in groups:
        task = scene_group.anchor_task
        group = project.layerTreeRoot().addGroup(
            f"SAR {scene_group.scene.acquisition_start[:19]} | {scene_group.scene.scene_id}"
        )
        annotation = q["QgsVectorLayer"](
            f"{scene_group.path}|layername=annotations", "Scene annotations (EDIT THIS)", "ogr"
        )
        if not annotation.isValid():
            raise RuntimeError(f"Could not load scene annotations from {scene_group.path}")
        _configure_annotations(annotation, task, q)
        project.addMapLayer(annotation, False)
        group.addLayer(annotation)
        first_annotation = first_annotation or annotation
        _add_rasters(project, group, task, q)
        optical_group = group.addGroup("Optical observations — original points on before and after SAR")
        for linked_task in scene_group.tasks:
            _, view = _add_task(
                project, optical_group, linked_task, q, add_annotation=False, add_rasters=False
            )
            first_view_layer = first_view_layer or view
    if first_annotation is not None:
        project.setCrs(first_annotation.crs())
        if hasattr(project, "viewSettings") and first_view_layer is not None and not first_view_layer.extent().isEmpty():
            project.viewSettings().setDefaultViewExtent(
                q["QgsReferencedRectangle"](first_view_layer.extent(), first_view_layer.crs())
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    if not project.write(str(path)):
        raise RuntimeError(f"QGIS could not write project {path}")
