"""One editable annotation set per physical SAR acquisition.

Optical/SAR associations remain separate tasks because their observation times,
before/after roles and drift predictions differ. They share this scene review.
"""

from __future__ import annotations

import sqlite3
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import fiona
import rasterio
from pyproj import CRS, Transformer
from shapely.geometry import box, shape
from shapely.ops import transform

from .geopackage import CLASSES, CONFIDENCE_LEVELS, TRAINING_STATUSES, ValidationResult, primary_raster
from .models import DigitisingTask, ProcessedScene


SCENE_ANNOTATION_SCHEMA = {
    "geometry": "MultiPolygon",
    "properties": {
        "feature_uuid": "str:36",
        "patch_id": "str:96",
        "Class": "str:32",
        "feature_confidence": "str:16",
        "correspondence_confidence": "str:16",
        "training_status": "str:24",
        "scene_id": "str:160",
        "sar_utc": "str:32",
        "evidence_obs_ids": "str",
        "notes": "str",
    },
}


@dataclass(frozen=True)
class SceneGroup:
    scene: ProcessedScene
    tasks: tuple[DigitisingTask, ...]

    @property
    def anchor_task(self) -> DigitisingTask:
        return next(task for task in self.tasks if task.scene == self.scene)

    @property
    def path(self) -> Path:
        return self.scene.scene_dir / "digitising" / "scene_annotations.gpkg"

    @property
    def project_path(self) -> Path:
        return self.scene.scene_dir / "digitising" / "scene.qgz"

    @property
    def manifest_path(self) -> Path:
        return self.scene.scene_dir / "digitising" / "scene_manifest.json"

    @property
    def observation_ids(self) -> set[str]:
        return {task.observation_id for task in self.tasks}


def group_by_scene(tasks: Sequence[DigitisingTask]) -> list[SceneGroup]:
    grouped: dict[str, list[DigitisingTask]] = {}
    for task in tasks:
        grouped.setdefault(task.scene.granule, []).append(task)
    return [
        SceneGroup(min(items, key=lambda task: (task.scene.scene_id, str(task.scene.manifest_path))).scene,
                   tuple(items))
        for items in grouped.values()
    ]


def create_scene_geopackage(group: SceneGroup) -> None:
    """Create once; never replace existing scene annotations on re-preparation."""
    path = group.path
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and "annotations" in fiona.listlayers(path):
        return
    with rasterio.open(primary_raster(group.anchor_task)) as raster:
        crs_wkt = raster.crs.to_wkt()
    with fiona.open(path, "w", driver="GPKG", layer="annotations", schema=SCENE_ANNOTATION_SCHEMA, crs_wkt=crs_wkt):
        pass
    # Fill stable identifiers and the immutable SAR identity, while leaving
    # optical provenance for the reviewer to select from the dated subgroups.
    connection = sqlite3.connect(path)
    try:
        scene_id = group.scene.scene_id.replace("'", "''")
        sar_time = group.scene.acquisition_start.replace("'", "''")
        patch_prefix = "SAR-" + hashlib.sha256(group.scene.granule.encode("utf-8")).hexdigest()[:16] + "-P"
        connection.executescript(
            "CREATE TRIGGER scene_annotations_autofill AFTER INSERT ON annotations BEGIN\n"
            "UPDATE annotations SET "
            "feature_uuid = COALESCE(NULLIF(NEW.feature_uuid, ''), lower(hex(randomblob(4))) || '-' || "
            "lower(hex(randomblob(2))) || '-4' || substr(lower(hex(randomblob(2))),2) || '-' || "
            "substr('89ab',abs(random()) % 4 + 1,1) || substr(lower(hex(randomblob(2))),2) || '-' || "
            "lower(hex(randomblob(6)))), "
            f"patch_id = COALESCE(NULLIF(NEW.patch_id, ''), '{patch_prefix}' || printf('%04d', NEW.fid)), "
            "feature_confidence = COALESCE(NULLIF(NEW.feature_confidence, ''), 'not_assessed'), "
            "correspondence_confidence = COALESCE(NULLIF(NEW.correspondence_confidence, ''), 'not_assessed'), "
            "training_status = COALESCE(NULLIF(NEW.training_status, ''), 'candidate'), "
            f"scene_id = '{scene_id}', sar_utc = '{sar_time}' WHERE fid = NEW.fid; END;"
        )
        connection.commit()
    finally:
        connection.close()


def validate_scene_annotations(path: Path, group: SceneGroup) -> ValidationResult:
    if not path.exists() or "annotations" not in fiona.listlayers(path):
        return ValidationResult(False, 0, ("Missing scene annotations layer",))
    errors: list[str] = []
    seen_uuid: set[str] = set()
    seen_patch: set[str] = set()
    with rasterio.open(primary_raster(group.anchor_task)) as raster:
        bounds = box(*raster.bounds)
        raster_crs = CRS.from_user_input(raster.crs)
    with fiona.open(path, layer="annotations") as source:
        source_crs = CRS.from_user_input(source.crs_wkt or source.crs)
        projector = None if source_crs == raster_crs else Transformer.from_crs(source_crs, raster_crs, always_xy=True).transform
        features = list(source)
        for index, feature in enumerate(features, 1):
            props = dict(feature["properties"])
            prefix = f"feature {index}"
            for field, values in (("Class", CLASSES), ("feature_confidence", CONFIDENCE_LEVELS),
                                  ("correspondence_confidence", CONFIDENCE_LEVELS),
                                  ("training_status", TRAINING_STATUSES)):
                if props.get(field) not in values:
                    errors.append(f"{prefix}: invalid {field} {props.get(field)!r}")
            if props.get("scene_id") != group.scene.scene_id:
                errors.append(f"{prefix}: scene_id does not match")
            if props.get("sar_utc") != group.scene.acquisition_start:
                errors.append(f"{prefix}: sar_utc does not match")
            for field, seen in (("feature_uuid", seen_uuid), ("patch_id", seen_patch)):
                value = str(props.get(field) or "")
                if not value or value in seen:
                    errors.append(f"{prefix}: missing or duplicate {field}")
                seen.add(value)
            status = props.get("training_status")
            if status == "candidate":
                errors.append(f"{prefix}: candidate has not been accepted or excluded")
            if status == "accepted_proxy":
                if "not_assessed" in (props.get("feature_confidence"), props.get("correspondence_confidence")):
                    errors.append(f"{prefix}: accepted_proxy requires assessed confidence")
                linked = {value.strip() for value in str(props.get("evidence_obs_ids") or "").split(",") if value.strip()}
                if not linked or not linked <= group.observation_ids:
                    errors.append(f"{prefix}: evidence_obs_ids must name linked optical observation IDs")
            if not feature.get("geometry"):
                errors.append(f"{prefix}: missing geometry")
            else:
                geometry = shape(feature["geometry"])
                if projector:
                    geometry = transform(projector, geometry)
                if geometry.is_empty or not geometry.is_valid or not geometry.intersects(bounds):
                    errors.append(f"{prefix}: invalid geometry or outside SAR raster bounds")
    if not features:
        errors.append("No annotation polygons")
    return ValidationResult(not errors, len(features), tuple(errors))
