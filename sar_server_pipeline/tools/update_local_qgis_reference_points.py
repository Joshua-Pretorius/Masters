#!/usr/bin/env python3
"""Safely refresh reference points in a prepared local QGIS digitising batch."""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from osgeo import ogr, osr
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsCategorizedSymbolRenderer,
    QgsMarkerSymbol,
    QgsPalLayerSettings,
    QgsProject,
    QgsRendererCategory,
    QgsTextFormat,
    QgsVectorLayer,
    QgsVectorLayerSimpleLabeling,
)


ogr.UseExceptions()


SUPPLEMENTARY_LAYER = "Supplementary PlanetScope points (NO DRIFT)"
SUPPLEMENTARY_GROUP = "Supplementary reference - NO DRIFT"


def read_operational_points(path: Path) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if row["obs_id"] in {"MERIA_SA_001", "MERIA_SA_002"}:
                grouped[row["obs_id"]].append(row)
    expected = {"MERIA_SA_001": 3, "MERIA_SA_002": 11}
    actual = {key: len(grouped[key]) for key in expected}
    if actual != expected:
        raise RuntimeError(f"Unexpected operational point counts: {actual}; expected {expected}")
    return grouped


def read_supplementary_points(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row["observation_date"]] += 1
        if row["seed_eligible"].lower() != "false" or row["status"] != "reference_only":
            raise RuntimeError(f"Supplementary point is not safely marked reference-only: {row}")
    if dict(counts) != {"2019-04-26": 8, "2019-04-27": 3}:
        raise RuntimeError(f"Unexpected supplementary point counts: {dict(counts)}")
    return rows


def layer_by_name(dataset: ogr.DataSource, name: str) -> ogr.Layer:
    layer = dataset.GetLayerByName(name)
    if layer is None:
        raise RuntimeError(f"GeoPackage layer is missing: {name}")
    return layer


def clear_layer(layer: ogr.Layer) -> None:
    fids = [feature.GetFID() for feature in layer]
    layer.ResetReading()
    for fid in fids:
        if layer.DeleteFeature(fid) != ogr.OGRERR_NONE:
            raise RuntimeError(f"Could not delete feature {fid} from {layer.GetName()}")


def annotation_count(path: Path) -> int:
    dataset = ogr.Open(str(path), 0)
    if dataset is None:
        raise RuntimeError(f"Could not open GeoPackage: {path}")
    count = layer_by_name(dataset, "annotations").GetFeatureCount()
    dataset = None
    return count


def update_task_geopackage(path: Path, points: dict[str, list[dict[str, str]]]) -> tuple[str, int]:
    dataset = ogr.Open(str(path), 1)
    if dataset is None:
        raise RuntimeError(f"Could not open GeoPackage for update: {path}")

    metadata = layer_by_name(dataset, "task_metadata")
    metadata_feature = metadata.GetNextFeature()
    if metadata_feature is None:
        raise RuntimeError(f"No task metadata exists in {path}")
    task_id = metadata_feature.GetFieldAsString("task_id")
    obs_id = metadata_feature.GetFieldAsString("obs_id")
    if obs_id not in points:
        raise RuntimeError(f"Unexpected observation {obs_id} in {path}")
    delta_h = metadata_feature.GetField("delta_h")
    delta_label = metadata_feature.GetFieldAsString("delta_lbl")
    note = f"User-verified PlanetScope debris locations for {24 if obs_id == 'MERIA_SA_001' else 25} April 2019."

    reference = layer_by_name(dataset, "reference_points")
    if reference.StartTransaction() != ogr.OGRERR_NONE:
        raise RuntimeError(f"Could not start reference-point transaction in {path}")
    try:
        clear_layer(reference)
        definition = reference.GetLayerDefn()
        for row in points[obs_id]:
            feature = ogr.Feature(definition)
            feature.SetField("point_id", row["pt_id"])
            feature.SetField("task_id", task_id)
            feature.SetField("obs_id", obs_id)
            feature.SetField("ref_kind", "observed_plastic")
            feature.SetField("seed_ok", 1)
            feature.SetField("delta_h", float(delta_h))
            feature.SetField("delta_lbl", delta_label)
            feature.SetField("notes", row["notes"])
            geometry = ogr.Geometry(ogr.wkbPoint)
            geometry.AddPoint_2D(float(row["lon"]), float(row["lat"]))
            feature.SetGeometry(geometry)
            if reference.CreateFeature(feature) != ogr.OGRERR_NONE:
                raise RuntimeError(f"Could not create {row['pt_id']} in {path}")
        if reference.CommitTransaction() != ogr.OGRERR_NONE:
            raise RuntimeError(f"Could not commit reference-point transaction in {path}")
    except Exception:
        reference.RollbackTransaction()
        raise
    dataset.ExecuteSQL(
        "UPDATE gpkg_geometry_columns SET z = 0 WHERE table_name = 'reference_points'"
    )

    # The old predictions were generated from the replaced coordinates. Keeping
    # them visible would falsely imply that they correspond to the new points.
    clear_layer(layer_by_name(dataset, "predicted_points"))
    clear_layer(layer_by_name(dataset, "prediction_envelopes"))
    metadata_feature.SetField("pred_status", "not_run")
    metadata_feature.SetField(
        "pred_detail",
        "Reference points corrected in the local QGIS copy; old predictions removed and OpenDrift not rerun.",
    )
    metadata_feature.SetField("notes", note)
    if metadata.SetFeature(metadata_feature) != ogr.OGRERR_NONE:
        raise RuntimeError(f"Could not update task metadata in {path}")
    dataset = None
    return obs_id, len(points[obs_id])


def create_supplementary_geopackage(path: Path, rows: list[dict[str, str]]) -> None:
    driver = ogr.GetDriverByName("GPKG")
    if path.exists() and driver.DeleteDataSource(str(path)) != ogr.OGRERR_NONE:
        raise RuntimeError(f"Could not replace {path}")
    dataset = driver.CreateDataSource(str(path))
    if dataset is None:
        raise RuntimeError(f"Could not create {path}")
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    layer = dataset.CreateLayer("supplementary_reference_points", srs=srs, geom_type=ogr.wkbPoint)
    for name, field_type, width in (
        ("point_id", ogr.OFTString, 64),
        ("obs_date", ogr.OFTString, 10),
        ("source", ogr.OFTString, 32),
        ("seed_ok", ogr.OFTInteger, 0),
        ("status", ogr.OFTString, 32),
        ("notes", ogr.OFTString, 254),
    ):
        field = ogr.FieldDefn(name, field_type)
        if width:
            field.SetWidth(width)
        if layer.CreateField(field) != ogr.OGRERR_NONE:
            raise RuntimeError(f"Could not create field {name} in {path}")
    definition = layer.GetLayerDefn()
    for row in rows:
        feature = ogr.Feature(definition)
        feature.SetField("point_id", row["temporary_point_id"])
        feature.SetField("obs_date", row["observation_date"])
        feature.SetField("source", row["source"])
        feature.SetField("seed_ok", 0)
        feature.SetField("status", "reference_only")
        feature.SetField("notes", row["notes"])
        geometry = ogr.Geometry(ogr.wkbPoint)
        geometry.AddPoint_2D(float(row["lon"]), float(row["lat"]))
        feature.SetGeometry(geometry)
        if layer.CreateFeature(feature) != ogr.OGRERR_NONE:
            raise RuntimeError(f"Could not create supplementary point {row['temporary_point_id']}")
    dataset = None


def style_supplementary_layer(layer: QgsVectorLayer) -> None:
    categories = []
    for date, label, color, shape in (
        ("2019-04-26", "26 April 2019 - reference only", "255,140,0,230", "circle"),
        ("2019-04-27", "27 April 2019 - reference only", "213,0,249,230", "triangle"),
    ):
        symbol = QgsMarkerSymbol.createSimple(
            {
                "name": shape,
                "color": color,
                "size": "3.2",
                "outline_color": "255,255,255,255",
                "outline_width": "0.5",
            }
        )
        categories.append(QgsRendererCategory(date, symbol, label))
    layer.setRenderer(QgsCategorizedSymbolRenderer("obs_date", categories))
    label_settings = QgsPalLayerSettings()
    label_settings.enabled = True
    label_settings.fieldName = '"obs_date" || \'  \' || "point_id"'
    label_settings.isExpression = True
    text_format = QgsTextFormat()
    text_format.setSize(8)
    label_settings.setFormat(text_format)
    layer.setLabeling(QgsVectorLayerSimpleLabeling(label_settings))
    layer.setLabelsEnabled(True)
    layer.setReadOnly(True)
    layer.setCustomProperty("digitising/reference_only", True)
    layer.setAbstract(
        "User-recorded PlanetScope reference points for 26 and 27 April 2019. "
        "These points are not attached to a digitising task and were not used by OpenDrift."
    )


def update_project(project_path: Path, supplementary_gpkg: Path) -> None:
    project = QgsProject()
    if not project.read(str(project_path)):
        raise RuntimeError(f"Could not read QGIS project: {project_path}")
    for layer in list(project.mapLayers().values()):
        if layer.name() == SUPPLEMENTARY_LAYER:
            project.removeMapLayer(layer.id())
    root = project.layerTreeRoot()
    old_group = root.findGroup(SUPPLEMENTARY_GROUP)
    if old_group is not None:
        root.removeChildNode(old_group)
    layer = QgsVectorLayer(
        f"{supplementary_gpkg}|layername=supplementary_reference_points",
        SUPPLEMENTARY_LAYER,
        "ogr",
    )
    if not layer.isValid():
        raise RuntimeError(f"Could not load supplementary layer from {supplementary_gpkg}")
    style_supplementary_layer(layer)
    project.addMapLayer(layer, False)
    group = root.insertGroup(0, SUPPLEMENTARY_GROUP)
    group.addLayer(layer)
    try:
        project.setFilePathStorage(Qgis.FilePathType.Relative)
    except AttributeError:
        project.writeEntry("Paths", "Absolute", False)
    if not project.write(str(project_path)):
        raise RuntimeError(f"Could not save QGIS project: {project_path}")


def copy_backup(batch_root: Path, targets: list[Path]) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = batch_root / "point_update_backups" / stamp
    for target in targets:
        relative = target.relative_to(batch_root)
        destination = backup_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, destination)
    return backup_root


def restore_backup(batch_root: Path, backup_root: Path, targets: list[Path]) -> None:
    for target in targets:
        backup = backup_root / target.relative_to(batch_root)
        if backup.exists():
            shutil.copy2(backup, target)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-root", type=Path, required=True)
    parser.add_argument("--operational-points", type=Path, required=True)
    parser.add_argument("--supplementary-points", type=Path, required=True)
    args = parser.parse_args()

    batch_root = args.batch_root.resolve()
    task_geopackages = sorted(
        path for path in batch_root.rglob("task.gpkg") if "point_update_backups" not in path.parts
    )
    projects = sorted(
        path for path in batch_root.rglob("*.qgz") if "point_update_backups" not in path.parts
    )
    if len(task_geopackages) != 4 or len(projects) != 5:
        raise RuntimeError(
            f"Expected four task GeoPackages and five projects; found "
            f"{len(task_geopackages)} and {len(projects)}"
        )
    sidecars = [Path(f"{path}{suffix}") for path in task_geopackages for suffix in ("-wal", "-shm")]
    live_sidecars = [path for path in sidecars if path.exists()]
    if live_sidecars:
        raise RuntimeError(f"QGIS/SQLite sidecar files still exist; close QGIS first: {live_sidecars}")

    operational = read_operational_points(args.operational_points.resolve())
    supplementary = read_supplementary_points(args.supplementary_points.resolve())
    supplementary_gpkg = (
        batch_root
        / "digitising_batches"
        / "sa_durban_2019_apr"
        / "supplementary_planetscope_points.gpkg"
    )
    targets = task_geopackages + projects
    if supplementary_gpkg.exists():
        targets.append(supplementary_gpkg)
    annotation_counts_before = {path: annotation_count(path) for path in task_geopackages}
    backup_root = copy_backup(batch_root, targets)
    created_supplementary = not supplementary_gpkg.exists()

    qgs = QgsApplication([], False)
    qgs.initQgis()
    try:
        updates = [update_task_geopackage(path, operational) for path in task_geopackages]
        create_supplementary_geopackage(supplementary_gpkg, supplementary)
        for project in projects:
            update_project(project, supplementary_gpkg)
        annotation_counts_after = {path: annotation_count(path) for path in task_geopackages}
        if annotation_counts_after != annotation_counts_before:
            raise RuntimeError(
                f"Annotation counts changed unexpectedly: before={annotation_counts_before}, "
                f"after={annotation_counts_after}"
            )
        print(f"Backup: {backup_root}")
        for path, (obs_id, count) in zip(task_geopackages, updates):
            print(f"Updated {path}: {obs_id} -> {count} reference points; predictions cleared")
        print(f"Created {supplementary_gpkg}: {len(supplementary)} reference-only points")
        print(f"Updated {len(projects)} QGIS projects; annotations preserved: {annotation_counts_after}")
        return 0
    except Exception:
        restore_backup(batch_root, backup_root, targets)
        if created_supplementary and supplementary_gpkg.exists():
            supplementary_gpkg.unlink()
        raise
    finally:
        qgs.exitQgis()


if __name__ == "__main__":
    sys.exit(main())
