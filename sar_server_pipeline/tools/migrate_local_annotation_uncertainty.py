from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from qgis.core import QgsApplication, QgsDefaultValue, QgsEditorWidgetSetup, QgsProject, QgsVectorLayer


CONFIDENCE_LEVELS = ("high", "medium", "low", "not_assessed")
TRAINING_STATUSES = ("candidate", "accepted_proxy", "excluded")
SKIP_PARTS = {"point_update_backups", "schema_migration_backups"}


def active_files(root: Path, pattern: str) -> list[Path]:
    return sorted(
        path
        for path in root.rglob(pattern)
        if path.is_file() and not SKIP_PARTS.intersection(path.parts)
    )


def backup(path: Path, root: Path, backup_root: Path) -> None:
    destination = backup_root / path.relative_to(root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destination)


def suspend_generic_rtree_updates(connection: sqlite3.Connection) -> list[tuple[str, str]]:
    triggers = [
        (str(name), str(sql))
        for name, sql in connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'trigger' "
            "AND tbl_name = 'annotations' "
            "AND name IN ('rtree_annotations_geom_update3', 'rtree_annotations_geom_update4')"
        )
    ]
    for name, _sql in triggers:
        connection.execute(f'DROP TRIGGER "{name}"')
    return triggers


def restore_triggers(connection: sqlite3.Connection, triggers: list[tuple[str, str]]) -> None:
    for _name, sql in triggers:
        connection.execute(sql)


def migrate_geopackage(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        layer = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'annotations'"
        ).fetchone()
        if layer is None:
            raise RuntimeError("missing annotations table")
        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(annotations)")}
        for name in ("feature_confidence", "correspondence_confidence", "training_status"):
            if name not in columns:
                connection.execute(f'ALTER TABLE annotations ADD COLUMN "{name}" TEXT')

        triggers = suspend_generic_rtree_updates(connection)
        try:
            connection.execute(
                "UPDATE annotations SET feature_confidence = "
                "CASE WHEN lower(COALESCE(confidence, '')) IN ('high', 'medium', 'low') "
                "THEN lower(confidence) ELSE 'not_assessed' END "
                "WHERE feature_confidence IS NULL OR feature_confidence = ''"
            )
            connection.execute(
                "UPDATE annotations SET correspondence_confidence = 'not_assessed' "
                "WHERE correspondence_confidence IS NULL OR correspondence_confidence = ''"
            )
            connection.execute(
                "UPDATE annotations SET training_status = 'candidate' "
                "WHERE training_status IS NULL OR training_status = ''"
            )
        finally:
            restore_triggers(connection, triggers)

        connection.execute("DROP TRIGGER IF EXISTS annotations_uncertainty_defaults")
        connection.executescript(
            "CREATE TRIGGER annotations_uncertainty_defaults AFTER INSERT ON annotations BEGIN\n"
            "  UPDATE annotations SET\n"
            "    feature_confidence = COALESCE(NULLIF(NEW.feature_confidence, ''), "
            "NULLIF(NEW.confidence, ''), 'not_assessed'),\n"
            "    correspondence_confidence = COALESCE(NULLIF(NEW.correspondence_confidence, ''), "
            "'not_assessed'),\n"
            "    training_status = COALESCE(NULLIF(NEW.training_status, ''), 'candidate')\n"
            "  WHERE fid = NEW.fid;\n"
            "END;"
        )
        connection.commit()
    finally:
        connection.close()


def value_map(values: tuple[str, ...]) -> QgsEditorWidgetSetup:
    return QgsEditorWidgetSetup("ValueMap", {"map": [{value: value} for value in values]})


def configure_annotation_layer(layer: QgsVectorLayer) -> None:
    confidence_map = value_map(CONFIDENCE_LEVELS)
    for field_name in ("feature_confidence", "correspondence_confidence"):
        index = layer.fields().indexOf(field_name)
        if index >= 0:
            layer.setEditorWidgetSetup(index, confidence_map)
    status_index = layer.fields().indexOf("training_status")
    if status_index >= 0:
        layer.setEditorWidgetSetup(status_index, value_map(TRAINING_STATUSES))

    aliases = {
        "feature_confidence": "Feature confidence",
        "correspondence_confidence": "Correspondence confidence",
        "training_status": "Training status",
    }
    for field_name, alias in aliases.items():
        index = layer.fields().indexOf(field_name)
        if index >= 0:
            layer.setFieldAlias(index, alias)

    defaults = {
        "feature_confidence": "'not_assessed'",
        "correspondence_confidence": "'not_assessed'",
        "training_status": "'candidate'",
    }
    for field_name, expression in defaults.items():
        index = layer.fields().indexOf(field_name)
        if index >= 0:
            layer.setDefaultValueDefinition(index, QgsDefaultValue(expression, False))

    legacy_index = layer.fields().indexOf("confidence")
    if legacy_index >= 0:
        layer.setEditorWidgetSetup(legacy_index, QgsEditorWidgetSetup("Hidden", {}))
        form = layer.editFormConfig()
        form.setReadOnly(legacy_index, True)
        layer.setEditFormConfig(form)


def migrate_project(path: Path) -> int:
    project = QgsProject()
    if not project.read(str(path)):
        raise RuntimeError("QGIS could not read the project")
    updated = 0
    for layer in project.mapLayers().values():
        if not isinstance(layer, QgsVectorLayer):
            continue
        source = layer.source().lower()
        if "layername=annotations" not in source and layer.name() != "Annotations (EDIT THIS)":
            continue
        if not layer.isValid():
            raise RuntimeError(f"invalid annotations layer: {layer.source()}")
        configure_annotation_layer(layer)
        updated += 1
    if updated and not project.write(str(path)):
        raise RuntimeError("QGIS could not write the project")
    project.clear()
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate local MERIA QGIS tasks to split uncertainty fields.")
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)

    geopackages = active_files(root, "task.gpkg")
    projects = active_files(root, "*.qgz")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = root / "schema_migration_backups" / timestamp
    for path in (*geopackages, *projects):
        backup(path, root, backup_root)

    application = QgsApplication.instance()
    owns_application = application is None
    if application is None:
        application = QgsApplication([], False)
        application.initQgis()
    errors: list[str] = []
    migrated_gpkg = 0
    migrated_projects = 0
    configured_layers = 0
    try:
        for path in geopackages:
            try:
                migrate_geopackage(path)
                migrated_gpkg += 1
            except Exception as exc:
                errors.append(f"GeoPackage {path}: {exc}")
        for path in projects:
            try:
                count = migrate_project(path)
                migrated_projects += 1
                configured_layers += count
            except Exception as exc:
                errors.append(f"Project {path}: {exc}")
    finally:
        if owns_application:
            application.exitQgis()

    print(f"Backup: {backup_root}")
    print(f"GeoPackages migrated: {migrated_gpkg}/{len(geopackages)}")
    print(f"Projects rewritten: {migrated_projects}/{len(projects)}")
    print(f"Annotation layers configured: {configured_layers}")
    if errors:
        print("Errors:")
        for error in errors:
            print(f"- {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
