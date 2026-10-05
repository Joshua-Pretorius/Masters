from __future__ import annotations

import json
import logging
import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

import fiona

from .catalog import RASTER_KEYS, build_task_catalog
from .drift import PredictionResult, prepare_prediction
from .geopackage import (
    ValidationResult,
    create_or_refresh_task_geopackage,
    export_annotations,
    primary_raster,
    update_task_metadata,
    validate_annotations,
)
from .models import DigitisingTask
from .project import build_qgis_project, build_scene_qgis_project
from .scene import SceneGroup, create_scene_geopackage, group_by_scene, validate_scene_annotations
from .util import relative_to_root, write_json


LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class Environment:
    data_root: Path
    catalog_root: Path
    drift_tools_root: Path
    remote: str
    remote_data_root: str
    desktop_root: str
    cmems_credentials: Path
    cdsapirc: Path

    @property
    def processed_root(self) -> Path:
        return self.data_root / "processed"

    @property
    def forcing_cache(self) -> Path:
        return self.data_root / "biophysical" / "forcing_cache"


@dataclass(frozen=True)
class PrepareResult:
    batch_name: str
    selected: tuple[str, ...]
    skipped_complete: tuple[str, ...]
    unavailable: tuple[str, ...]
    pull_command: str
    return_command: str


def task_manifest(task: DigitisingTask, prediction: PredictionResult) -> dict[str, object]:
    return {
        "schema_version": 1,
        "task_id": task.task_id,
        "dataset": task.dataset,
        "observation_id": task.observation_id,
        "source_dataset": task.source_dataset,
        "source_group_id": task.source_group_id,
        "area": task.area,
        "role": task.role,
        "optical_time_start": task.optical_time_start,
        "optical_time_end": task.optical_time_end,
        "optical_time_representative": task.optical_time_representative,
        "sar_time": task.sar_time,
        "delta_hours": task.delta_hours,
        "delta_label": task.delta_label,
        "physical_scene_id": task.scene.scene_id,
        "physical_scene_manifest": str(task.scene.manifest_path),
        "sentinel1_granule": task.scene.granule,
        "reference_points": [asdict(point) for point in task.reference_points],
        "planet_item_ids": list(task.planet_item_ids),
        "optical_links": {
            "planet_explorer": "https://www.planet.com/explorer/",
            "copernicus_browser": "https://browser.dataspace.copernicus.eu/",
        },
        "prediction": {"status": prediction.status, "detail": prediction.detail},
        "editable_layer": "annotations",
        "editable_geopackage": str(task.task_dir / "task.gpkg"),
    }


def canonical_export_path(environment: Environment, task: DigitisingTask) -> Path:
    return environment.data_root / "shapefiles" / task.scene.scene_id / f"{task.task_id}_annotations.geojson"


def reconcile_task(environment: Environment, task: DigitisingTask, *, write_export: bool = True) -> ValidationResult:
    primary_raster(task)
    gpkg = task.task_dir / "task.gpkg"
    result = validate_annotations(gpkg, task)
    if result.valid and write_export:
        export_annotations(gpkg, canonical_export_path(environment, task))
    return result


def _task_transfer_paths(environment: Environment, task: DigitisingTask) -> list[Path]:
    paths = [
        task.scene.manifest_path,
        task.task_dir / "task.gpkg",
        task.task_dir / "task.qgz",
        task.task_dir / "task_manifest.json",
    ]
    if task.scene.reference_grid:
        paths.append(task.scene.reference_grid)
    paths.extend(task.scene.outputs[key] for key in RASTER_KEYS if key in task.scene.outputs)
    return [path for path in paths if path.exists()]


def _commands(environment: Environment, batch_name: str) -> tuple[str, str]:
    remote_batch = f"{environment.remote_data_root.rstrip('/')}/digitising_batches/{batch_name}"
    remote_root = environment.remote_data_root.rstrip("/") + "/"
    local_root = f"{environment.desktop_root.rstrip('/')}/{batch_name}"
    pull = (
        "rsync -av --relative "
        f"--files-from=:{remote_batch}/transfer_files.txt "
        f"{environment.remote}:{remote_root} {local_root}/"
    )
    return_list = f"{local_root}/digitising_batches/{batch_name}/return_files.txt"
    returned_root = f"{remote_root}digitising_returns/{batch_name}/"
    push = (
        "rsync -av --relative "
        f"--files-from={return_list} "
        f"{local_root}/ {environment.remote}:{returned_root}"
    )
    return pull, push


def _write_batch_files(
    environment: Environment,
    batch_name: str,
    tasks: Sequence[DigitisingTask],
    completed: Sequence[str],
    prediction_results: dict[str, PredictionResult],
    *,
    include_partial: bool = False,
) -> tuple[str, str]:
    batch_dir = environment.data_root / "digitising_batches" / batch_name
    transfer_paths: set[Path] = {
        batch_dir / "batch.qgz",
        batch_dir / "batch_manifest.json",
        batch_dir / "transfer_files.txt",
        batch_dir / "return_files.txt",
        batch_dir / "README.txt",
    }
    for task in tasks:
        transfer_paths.update(_task_transfer_paths(environment, task))
    transfer_lines = sorted(relative_to_root(path, environment.data_root) for path in transfer_paths if path.exists())
    return_lines = sorted(relative_to_root(task.task_dir / "task.gpkg", environment.data_root) for task in tasks)
    (batch_dir / "transfer_files.txt").write_text("\n".join(transfer_lines) + "\n", encoding="utf-8")
    (batch_dir / "return_files.txt").write_text("\n".join(return_lines) + "\n", encoding="utf-8")
    pull, push = _commands(environment, batch_name)
    batch_payload = {
        "schema_version": 1,
        "batch_name": batch_name,
        "task_ids": [task.task_id for task in tasks],
        "datasets": sorted({task.dataset for task in tasks}),
        "include_partial": include_partial,
        "skipped_complete": list(completed),
        "ordering": "absolute optical-to-SAR delta hours, then dataset and task id",
        "prediction_status": {
            task_id: {"status": result.status, "detail": result.detail}
            for task_id, result in prediction_results.items()
        },
        "pull_command": pull,
        "return_command": push,
    }
    write_json(batch_dir / "batch_manifest.json", batch_payload)
    readme = (
        f"MERIA digitisation batch: {batch_name}\n\n"
        "1. Pull this batch onto the QGIS work machine:\n"
        f"   {pull}\n\n"
        "2. Open digitising_batches/"
        f"{batch_name}/batch.qgz in QGIS and edit only the Annotations layers.\n\n"
        "3. Return only the edited GeoPackages:\n"
        f"   {push}\n\n"
        "4. On Skua run:\n"
        f"   docker compose run --rm digitising import --batch {batch_name}\n"
    )
    (batch_dir / "README.txt").write_text(readme, encoding="utf-8")
    # Regenerate now that the manifests themselves exist, so they are included in the transfer list.
    transfer_paths.update({batch_dir / "batch_manifest.json", batch_dir / "README.txt"})
    transfer_lines = sorted(relative_to_root(path, environment.data_root) for path in transfer_paths if path.exists())
    (batch_dir / "transfer_files.txt").write_text("\n".join(transfer_lines) + "\n", encoding="utf-8")
    return pull, push


def prepare_batch(
    environment: Environment,
    *,
    dataset: str,
    limit: int,
    batch_name: str,
    task_ids: Sequence[str] = (),
    prediction_mode: str = "auto",
    dry_run: bool = False,
    include_partial: bool = False,
    project_builder: Callable[..., None] = build_qgis_project,
    grouping: str = "scene",
    scene_project_builder: Callable[..., None] = build_scene_qgis_project,
) -> PrepareResult:
    if grouping == "scene":
        return _prepare_scene_batch(
            environment, dataset=dataset, limit=limit, batch_name=batch_name,
            task_ids=task_ids, prediction_mode=prediction_mode, dry_run=dry_run,
            include_partial=include_partial, project_builder=scene_project_builder,
        )
    if grouping != "observation":
        raise ValueError("grouping must be 'scene' or 'observation'")
    if limit < 1:
        raise ValueError("--limit must be at least 1")
    catalog = build_task_catalog(
        environment.catalog_root,
        environment.processed_root,
        dataset,
        include_partial=include_partial,
    )
    requested = set(task_ids)
    if requested:
        known = {task.task_id for task in catalog}
        missing = sorted(requested - known)
        if missing:
            raise ValueError("Unknown or unprocessed task id(s): " + ", ".join(missing))
        catalog = [task for task in catalog if task.task_id in requested]

    complete: list[str] = []
    candidates: list[DigitisingTask] = []
    unavailable: list[str] = []
    for task in catalog:
        try:
            result = reconcile_task(environment, task, write_export=not dry_run)
        except (FileNotFoundError, ValueError, OSError) as exc:
            LOG.warning("Task %s is unavailable: %s", task.task_id, exc)
            unavailable.append(task.task_id)
            continue
        if result.valid:
            complete.append(task.task_id)
        else:
            candidates.append(task)
    selected = candidates[:limit]
    pull, push = _commands(environment, batch_name)
    if dry_run:
        return PrepareResult(batch_name, tuple(task.task_id for task in selected), tuple(complete), tuple(unavailable), pull, push)
    if not selected:
        raise RuntimeError("No pending processed digitisation tasks matched the request.")

    batch_dir = environment.data_root / "digitising_batches" / batch_name
    batch_dir.mkdir(parents=True, exist_ok=True)
    prediction_results: dict[str, PredictionResult] = {}
    for task in selected:
        gpkg = task.task_dir / "task.gpkg"
        create_or_refresh_task_geopackage(gpkg, task)
        prediction = prepare_prediction(
            task,
            gpkg,
            forcing_cache=environment.forcing_cache,
            tools_root=environment.drift_tools_root,
            cmems_credentials=environment.cmems_credentials,
            cdsapirc=environment.cdsapirc,
            mode=prediction_mode,
        )
        prediction_results[task.task_id] = prediction
        update_task_metadata(
            gpkg,
            task,
            prediction_status=prediction.status,
            prediction_detail=prediction.detail,
        )
        write_json(task.task_dir / "task_manifest.json", task_manifest(task, prediction))
        project_builder(task.task_dir / "task.qgz", (task,), title=task.task_id)
    project_builder(batch_dir / "batch.qgz", selected, title=f"MERIA digitisation — {batch_name}")
    pull, push = _write_batch_files(
        environment,
        batch_name,
        selected,
        complete,
        prediction_results,
        include_partial=include_partial,
    )
    return PrepareResult(
        batch_name,
        tuple(task.task_id for task in selected),
        tuple(complete),
        tuple(unavailable),
        pull,
        push,
    )


def _scene_export_path(environment: Environment, group: SceneGroup) -> Path:
    return environment.data_root / "shapefiles" / group.scene.scene_id / "scene_annotations.geojson"


def _prepare_scene_batch(
    environment: Environment, *, dataset: str, limit: int, batch_name: str,
    task_ids: Sequence[str], prediction_mode: str, dry_run: bool,
    include_partial: bool, project_builder: Callable[..., None],
) -> PrepareResult:
    if limit < 1:
        raise ValueError("--limit must be at least 1")
    catalog = build_task_catalog(
        environment.catalog_root, environment.processed_root, dataset,
        include_partial=include_partial,
    )
    requested = set(task_ids)
    if requested:
        known = {task.task_id: task.scene.granule for task in catalog}
        missing = sorted(requested - known.keys())
        if missing:
            raise ValueError("Unknown or unprocessed task id(s): " + ", ".join(missing))
        chosen_granules = {known[task_id] for task_id in requested}
        catalog = [task for task in catalog if task.scene.granule in chosen_granules]
    complete: list[str] = []
    candidates: list[SceneGroup] = []
    unavailable: list[str] = []
    for group in group_by_scene(catalog):
        try:
            primary_raster(group.anchor_task)
            validation = validate_scene_annotations(group.path, group)
        except (FileNotFoundError, ValueError, OSError) as exc:
            LOG.warning("Scene %s is unavailable: %s", group.scene.scene_id, exc)
            unavailable.append(group.scene.scene_id)
            continue
        if validation.valid:
            complete.append(group.scene.scene_id)
            if not dry_run:
                export_annotations(group.path, _scene_export_path(environment, group))
        else:
            candidates.append(group)
    selected = candidates[:limit]
    pull, push = _commands(environment, batch_name)
    if dry_run:
        return PrepareResult(batch_name, tuple(group.scene.scene_id for group in selected),
                             tuple(complete), tuple(unavailable), pull, push)
    if not selected:
        raise RuntimeError("No pending processed SAR scenes matched the request.")
    batch_dir = environment.data_root / "digitising_batches" / batch_name
    batch_dir.mkdir(parents=True, exist_ok=True)
    prediction_results: dict[str, PredictionResult] = {}
    transfer_paths: set[Path] = {batch_dir / "batch.qgz", batch_dir / "batch_manifest.json",
                                 batch_dir / "transfer_files.txt", batch_dir / "return_files.txt",
                                 batch_dir / "README.txt"}
    for group in selected:
        create_scene_geopackage(group)
        transfer_paths.update({group.path, group.project_path, group.manifest_path,
                               group.scene.manifest_path})
        if group.scene.reference_grid:
            transfer_paths.add(group.scene.reference_grid)
        transfer_paths.update(group.scene.outputs.values())
        for task in group.tasks:
            gpkg = task.task_dir / "task.gpkg"
            create_or_refresh_task_geopackage(gpkg, task)
            prediction = prepare_prediction(
                task, gpkg, forcing_cache=environment.forcing_cache,
                tools_root=environment.drift_tools_root,
                cmems_credentials=environment.cmems_credentials,
                cdsapirc=environment.cdsapirc, mode=prediction_mode,
            )
            prediction_results[task.task_id] = prediction
            update_task_metadata(gpkg, task, prediction_status=prediction.status,
                                 prediction_detail=prediction.detail)
            write_json(task.task_dir / "task_manifest.json", task_manifest(task, prediction))
            transfer_paths.update({gpkg, task.task_dir / "task_manifest.json"})
        write_json(group.manifest_path, {
            "schema_version": 2,
            "physical_scene_id": group.scene.scene_id,
            "sentinel1_granule": group.scene.granule,
            "sar_time": group.scene.acquisition_start,
            "editable_geopackage": str(group.path),
            "optical_associations": [
                {"task_id": task.task_id, "observation_id": task.observation_id,
                 "source_dataset": task.source_dataset, "role": task.role,
                 "optical_time_start": task.optical_time_start,
                 "optical_time_end": task.optical_time_end,
                 "delta_label": task.delta_label,
                 "reference_point_count": len(task.reference_points)}
                for task in group.tasks
            ],
        })
        project_builder(group.project_path, (group,), title=group.scene.scene_id)
    project_builder(batch_dir / "batch.qgz", selected, title=f"SAR scene digitisation — {batch_name}")
    batch_payload = {
        "schema_version": 2, "grouping": "physical_sar_scene",
        "batch_name": batch_name,
        "scene_groups": [{"scene_id": group.scene.scene_id, "granule": group.scene.granule,
                          "task_ids": [task.task_id for task in group.tasks]} for group in selected],
        "datasets": sorted({task.dataset for group in selected for task in group.tasks}),
        "include_partial": include_partial, "skipped_complete": complete,
        "prediction_status": {task_id: {"status": result.status, "detail": result.detail}
                              for task_id, result in prediction_results.items()},
        "pull_command": pull, "return_command": push,
    }
    write_json(batch_dir / "batch_manifest.json", batch_payload)
    readme = (
        f"SAR scene digitisation batch: {batch_name}\n\n"
        f"1. Pull: {pull}\n"
        f"2. Open digitising_batches/{batch_name}/batch.qgz. Edit only each Scene annotations layer.\n"
        "   Optical points are repeated on their before and after SAR scenes.\n"
        "   For accepted_proxy polygons, enter comma-separated linked observation IDs in evidence_obs_ids.\n"
        f"3. Return the edited scene GeoPackages: {push}\n"
        f"4. On Skua: docker compose run --rm digitising import --batch {batch_name}\n"
    )
    (batch_dir / "README.txt").write_text(readme, encoding="utf-8")
    (batch_dir / "transfer_files.txt").write_text(
        "\n".join(sorted(relative_to_root(path, environment.data_root)
                         for path in transfer_paths if path.exists())) + "\n", encoding="utf-8"
    )
    (batch_dir / "return_files.txt").write_text(
        "\n".join(sorted(relative_to_root(group.path, environment.data_root)
                         for group in selected)) + "\n", encoding="utf-8"
    )
    return PrepareResult(batch_name, tuple(group.scene.scene_id for group in selected),
                         tuple(complete), tuple(unavailable), pull, push)


def _annotation_ids(path: Path) -> set[str]:
    if not path.exists() or "annotations" not in fiona.listlayers(path):
        return set()
    with fiona.open(path, layer="annotations") as source:
        return {str((feature.get("properties") or {}).get("feature_uuid") or "") for feature in source}


def import_batch(environment: Environment, batch_name: str) -> dict[str, object]:
    batch_dir = environment.data_root / "digitising_batches" / batch_name
    batch_manifest_path = batch_dir / "batch_manifest.json"
    if not batch_manifest_path.exists():
        raise FileNotFoundError(f"Unknown batch: {batch_name}")
    batch = json.loads(batch_manifest_path.read_text(encoding="utf-8"))
    if batch.get("grouping") == "physical_sar_scene":
        return _import_scene_batch(environment, batch_name, batch)
    datasets = set(batch.get("datasets") or ())
    dataset_filter = next(iter(datasets)) if len(datasets) == 1 else "all"
    catalog = {
        task.task_id: task
        for task in build_task_catalog(
            environment.catalog_root,
            environment.processed_root,
            dataset_filter,
            include_partial=bool(batch.get("include_partial", False)),
        )
    }
    incoming_root = environment.data_root / "digitising_returns" / batch_name
    report: dict[str, object] = {"batch_name": batch_name, "imported": [], "invalid": {}, "conflicts": {}}
    for task_id in batch.get("task_ids", []):
        task = catalog.get(task_id)
        if task is None:
            report["invalid"][task_id] = ["Task is no longer present in the current catalog"]
            continue
        relative_gpkg = Path(relative_to_root(task.task_dir / "task.gpkg", environment.data_root))
        returned = incoming_root / relative_gpkg
        validation = validate_annotations(returned, task)
        if not validation.valid:
            report["invalid"][task_id] = list(validation.errors)
            continue
        canonical = task.task_dir / "task.gpkg"
        canonical_validation = validate_annotations(canonical, task)
        if canonical_validation.valid and _annotation_ids(canonical) != _annotation_ids(returned):
            report["conflicts"][task_id] = "Server and returned GeoPackages contain different completed annotation UUIDs."
            continue
        canonical.parent.mkdir(parents=True, exist_ok=True)
        if canonical.exists():
            backup = batch_dir / "import_backups" / f"{task_id}.gpkg"
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(canonical, backup)
        temporary = canonical.with_suffix(".gpkg.importing")
        shutil.copy2(returned, temporary)
        os.replace(temporary, canonical)
        count = export_annotations(canonical, canonical_export_path(environment, task))
        report["imported"].append({"task_id": task_id, "feature_count": count})
    write_json(batch_dir / "import_report.json", report)
    return report


def _import_scene_batch(environment: Environment, batch_name: str,
                        batch: dict[str, object]) -> dict[str, object]:
    datasets = set(batch.get("datasets") or ())
    dataset_filter = next(iter(datasets)) if len(datasets) == 1 else "all"
    catalog = build_task_catalog(
        environment.catalog_root, environment.processed_root, dataset_filter,
        include_partial=bool(batch.get("include_partial", False)),
    )
    groups = {group.scene.granule: group for group in group_by_scene(catalog)}
    incoming_root = environment.data_root / "digitising_returns" / batch_name
    batch_dir = environment.data_root / "digitising_batches" / batch_name
    report: dict[str, object] = {"batch_name": batch_name, "imported": [], "invalid": {}, "conflicts": {}}
    for entry in batch.get("scene_groups", []):
        scene_id = entry["scene_id"]
        group = groups.get(entry["granule"])
        if group is None or group.scene.scene_id != scene_id:
            report["invalid"][scene_id] = ["Scene is no longer present in the current catalog"]
            continue
        if {task.task_id for task in group.tasks} != set(entry["task_ids"]):
            report["invalid"][scene_id] = ["Optical associations changed since batch preparation"]
            continue
        relative_gpkg = Path(relative_to_root(group.path, environment.data_root))
        returned = incoming_root / relative_gpkg
        validation = validate_scene_annotations(returned, group)
        if not validation.valid:
            report["invalid"][scene_id] = list(validation.errors)
            continue
        canonical_validation = validate_scene_annotations(group.path, group)
        if canonical_validation.valid and _annotation_ids(group.path) != _annotation_ids(returned):
            report["conflicts"][scene_id] = "Server and returned scene annotations contain different completed UUIDs."
            continue
        if group.path.exists():
            backup = batch_dir / "import_backups" / f"{scene_id}.gpkg"
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(group.path, backup)
        temporary = group.path.with_suffix(".gpkg.importing")
        shutil.copy2(returned, temporary)
        os.replace(temporary, group.path)
        count = export_annotations(group.path, _scene_export_path(environment, group))
        report["imported"].append({"scene_id": scene_id, "feature_count": count})
    write_json(batch_dir / "import_report.json", report)
    return report
