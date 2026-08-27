from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

import fiona
import rasterio
from pyproj import CRS, Transformer
from shapely.geometry import box, mapping, shape
from shapely.ops import transform

from .models import DigitisingTask


CLASSES = (
    "plastic",
    "ship",
    "wake",
    "slick",
    "calm_water",
    "open_ocean",
    "other",
    "uncertain",
)
CONFIDENCE_LEVELS = ("high", "medium", "low")

ANNOTATION_SCHEMA = {
    "geometry": "MultiPolygon",
    "properties": {
        "feature_uuid": "str:36",
        "patch_id": "str:96",
        "Class": "str:32",
        "confidence": "str:16",
        "task_id": "str:128",
        "obs_id": "str:96",
        "dataset": "str:16",
        "role": "str:16",
        "scene_id": "str:160",
        "area": "str:96",
        "optical_utc": "str:32",
        "sar_utc": "str:32",
        "delta_h": "float",
        "notes": "str",
    },
}

REFERENCE_SCHEMA = {
    "geometry": "Point",
    "properties": {
        "point_id": "str:128",
        "task_id": "str:128",
        "obs_id": "str:96",
        "ref_kind": "str:32",
        "seed_ok": "int",
        "delta_h": "float",
        "delta_lbl": "str:64",
        "notes": "str",
    },
}

PREDICTION_POINT_SCHEMA = {
    "geometry": "Point",
    "properties": {
        "seed_id": "str:128",
        "task_id": "str:128",
        "delta_h": "float",
        "status": "str:32",
    },
}

PREDICTION_ENVELOPE_SCHEMA = {
    "geometry": "Unknown",
    "properties": {
        "seed_id": "str:128",
        "task_id": "str:128",
        "delta_h": "float",
        "status": "str:32",
    },
}

METADATA_SCHEMA = {
    "geometry": "None",
    "properties": {
        "task_id": "str:128",
        "dataset": "str:16",
        "obs_id": "str:96",
        "source_ds": "str:64",
        "source_grp": "str:128",
        "area": "str:96",
        "role": "str:16",
        "scene_id": "str:160",
        "opt_start": "str:32",
        "opt_end": "str:32",
        "sar_utc": "str:32",
        "delta_h": "float",
        "delta_lbl": "str:64",
        "planet_ids": "str",
        "planet_url": "str",
        "s2_url": "str",
        "pred_status": "str:32",
        "pred_detail": "str",
        "notes": "str",
    },
}


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    feature_count: int
    errors: tuple[str, ...]


def primary_raster(task: DigitisingTask) -> Path:
    for key in ("vv_refined_lee_db", "vv_refined_lee", "vv", "vh"):
        if key in task.scene.outputs:
            return task.scene.outputs[key]
    if task.scene.reference_grid:
        return task.scene.reference_grid
    raise FileNotFoundError(f"{task.task_id}: no usable processed raster")


def raster_crs(path: Path) -> CRS:
    with rasterio.open(path) as source:
        if source.crs is None:
            raise ValueError(f"Raster has no CRS: {path}")
        return CRS.from_user_input(source.crs)


def _delete_layer(path: Path, layer: str) -> None:
    if path.exists() and layer in fiona.listlayers(path):
        fiona.remove(path, layer=layer, driver="GPKG")


def _write_layer(
    path: Path,
    layer: str,
    schema: Mapping[str, object],
    features: Iterable[Mapping[str, object]],
    *,
    crs: CRS | str | None,
    replace: bool = True,
) -> None:
    if replace:
        _delete_layer(path, layer)
    kwargs: dict[str, object] = {
        "driver": "GPKG",
        "layer": layer,
        "schema": dict(schema),
    }
    if crs is not None:
        kwargs["crs_wkt"] = CRS.from_user_input(crs).to_wkt()
    with fiona.open(path, mode="w", **kwargs) as sink:
        for feature in features:
            sink.write(dict(feature))


def _sql(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, (float, int)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _install_annotation_triggers(path: Path, task: DigitisingTask) -> None:
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
    assignments = [
        "feature_uuid = COALESCE(NULLIF(NEW.feature_uuid, ''), "
        "lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-4' || "
        "substr(lower(hex(randomblob(2))),2) || '-' || substr('89ab',abs(random()) % 4 + 1,1) || "
        "substr(lower(hex(randomblob(2))),2) || '-' || lower(hex(randomblob(6))))",
        f"patch_id = COALESCE(NULLIF(NEW.patch_id, ''), {_sql(task.task_id + '-P')} || printf('%04d', NEW.fid))",
    ]
    assignments.extend(
        f'"{name}" = COALESCE(NULLIF(NEW."{name}", \'\'), {_sql(value)})'
        for name, value in defaults.items()
        if not isinstance(value, (float, int))
    )
    assignments.append(f'"delta_h" = COALESCE(NEW."delta_h", {_sql(task.delta_hours)})')
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            "DROP TRIGGER IF EXISTS annotations_autofill;\n"
            "DROP TRIGGER IF EXISTS annotations_uuid_immutable;\n"
            "CREATE TRIGGER annotations_autofill AFTER INSERT ON annotations BEGIN\n"
            "  UPDATE annotations SET\n    "
            + ",\n    ".join(assignments)
            + "\n  WHERE fid = NEW.fid;\nEND;\n"
            "CREATE TRIGGER annotations_uuid_immutable BEFORE UPDATE OF feature_uuid ON annotations\n"
            "WHEN OLD.feature_uuid IS NOT NULL AND NEW.feature_uuid <> OLD.feature_uuid BEGIN\n"
            "  SELECT RAISE(ABORT, 'feature_uuid is immutable');\nEND;"
        )
        connection.commit()
    finally:
        connection.close()


def create_or_refresh_task_geopackage(
    path: Path,
    task: DigitisingTask,
    *,
    prediction_status: str = "not_run",
    prediction_detail: str = "",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    annotation_crs = raster_crs(primary_raster(task))
    layers = fiona.listlayers(path) if path.exists() else []
    if "annotations" not in layers:
        _write_layer(path, "annotations", ANNOTATION_SCHEMA, (), crs=annotation_crs, replace=False)
    _install_annotation_triggers(path, task)

    reference_features = (
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": (point.longitude, point.latitude)},
            "properties": {
                "point_id": point.point_id,
                "task_id": task.task_id,
                "obs_id": task.observation_id,
                "ref_kind": point.reference_kind,
                "seed_ok": int(point.seed_eligible),
                "delta_h": task.delta_hours,
                "delta_lbl": task.delta_label,
                "notes": point.notes,
            },
        }
        for point in task.reference_points
    )
    _write_layer(path, "reference_points", REFERENCE_SCHEMA, reference_features, crs="EPSG:4326")
    current_layers = fiona.listlayers(path)
    if "predicted_points" not in current_layers:
        _write_layer(path, "predicted_points", PREDICTION_POINT_SCHEMA, (), crs="EPSG:4326", replace=False)
    if "prediction_envelopes" not in current_layers:
        _write_layer(path, "prediction_envelopes", PREDICTION_ENVELOPE_SCHEMA, (), crs="EPSG:4326", replace=False)
    update_task_metadata(path, task, prediction_status=prediction_status, prediction_detail=prediction_detail)


def update_task_metadata(
    path: Path,
    task: DigitisingTask,
    *,
    prediction_status: str,
    prediction_detail: str,
) -> None:
    metadata = {
        "type": "Feature",
        "geometry": None,
        "properties": {
            "task_id": task.task_id,
            "dataset": task.dataset,
            "obs_id": task.observation_id,
            "source_ds": task.source_dataset,
            "source_grp": task.source_group_id,
            "area": task.area,
            "role": task.role,
            "scene_id": task.scene.scene_id,
            "opt_start": task.optical_time_start,
            "opt_end": task.optical_time_end,
            "sar_utc": task.sar_time,
            "delta_h": task.delta_hours,
            "delta_lbl": task.delta_label,
            "planet_ids": json.dumps(task.planet_item_ids),
            "planet_url": "https://www.planet.com/explorer/",
            "s2_url": "https://browser.dataspace.copernicus.eu/",
            "pred_status": prediction_status,
            "pred_detail": prediction_detail,
            "notes": task.notes,
        },
    }
    _write_layer(path, "task_metadata", METADATA_SCHEMA, (metadata,), crs=None)


def replace_prediction_layers(
    path: Path,
    task: DigitisingTask,
    predicted_points: Iterable[Mapping[str, object]],
    prediction_envelopes: Iterable[Mapping[str, object]],
) -> None:
    _write_layer(path, "predicted_points", PREDICTION_POINT_SCHEMA, predicted_points, crs="EPSG:4326")
    _write_layer(path, "prediction_envelopes", PREDICTION_ENVELOPE_SCHEMA, prediction_envelopes, crs="EPSG:4326")


def annotation_feature_count(path: Path) -> int:
    if not path.exists() or "annotations" not in fiona.listlayers(path):
        return 0
    with fiona.open(path, layer="annotations") as source:
        return len(source)


def validate_annotations(path: Path, task: DigitisingTask) -> ValidationResult:
    errors: list[str] = []
    if not path.exists():
        return ValidationResult(False, 0, (f"GeoPackage does not exist: {path}",))
    if "annotations" not in fiona.listlayers(path):
        return ValidationResult(False, 0, ("Missing annotations layer",))
    expected = {
        "task_id": task.task_id,
        "obs_id": task.observation_id,
        "dataset": task.dataset,
        "role": task.role,
        "scene_id": task.scene.scene_id,
    }
    seen_uuid: set[str] = set()
    seen_patch: set[str] = set()
    raster_path = primary_raster(task)
    with rasterio.open(raster_path) as raster:
        raster_bounds = box(*raster.bounds)
        raster_projection = CRS.from_user_input(raster.crs) if raster.crs else None
    with fiona.open(path, layer="annotations") as source:
        source_projection = CRS.from_user_input(source.crs_wkt or source.crs) if (source.crs_wkt or source.crs) else None
        projector = None
        if source_projection and raster_projection and source_projection != raster_projection:
            projector = Transformer.from_crs(source_projection, raster_projection, always_xy=True).transform
        features = list(source)
        for index, feature in enumerate(features, start=1):
            prefix = f"feature {index}"
            geometry_data = feature.get("geometry")
            if not geometry_data:
                errors.append(f"{prefix}: missing geometry")
                continue
            geometry = shape(geometry_data)
            if geometry.geom_type not in {"Polygon", "MultiPolygon"}:
                errors.append(f"{prefix}: expected polygon geometry, got {geometry.geom_type}")
            if geometry.is_empty or not geometry.is_valid:
                errors.append(f"{prefix}: geometry is empty or invalid")
            raster_geometry = transform(projector, geometry) if projector else geometry
            if not raster_geometry.intersects(raster_bounds):
                errors.append(f"{prefix}: geometry does not intersect the SAR raster")
            properties = dict(feature.get("properties") or {})
            for field, value in expected.items():
                if str(properties.get(field) or "") != str(value):
                    errors.append(f"{prefix}: {field} does not match {value}")
            class_name = str(properties.get("Class") or "")
            confidence = str(properties.get("confidence") or "")
            if class_name not in CLASSES:
                errors.append(f"{prefix}: invalid Class {class_name!r}")
            if confidence not in CONFIDENCE_LEVELS:
                errors.append(f"{prefix}: invalid confidence {confidence!r}")
            uuid = str(properties.get("feature_uuid") or "")
            patch_id = str(properties.get("patch_id") or "")
            if not uuid or uuid in seen_uuid:
                errors.append(f"{prefix}: feature_uuid is missing or duplicated")
            if not patch_id or patch_id in seen_patch:
                errors.append(f"{prefix}: patch_id is missing or duplicated")
            seen_uuid.add(uuid)
            seen_patch.add(patch_id)
    if not features:
        errors.append("annotations layer is empty")
    return ValidationResult(not errors, len(features), tuple(errors))


def export_annotations(path: Path, output: Path) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    with fiona.open(path, layer="annotations") as source:
        schema = source.schema.copy()
        crs_wkt = source.crs_wkt
        with fiona.open(temporary, "w", driver="GeoJSON", schema=schema, crs_wkt=crs_wkt) as sink:
            count = 0
            for feature in source:
                sink.write(feature)
                count += 1
    temporary.replace(output)
    return count
