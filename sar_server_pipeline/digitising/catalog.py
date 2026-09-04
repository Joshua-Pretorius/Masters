from __future__ import annotations

import csv
import json
import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from .models import DigitisingTask, ProcessedScene, ReferencePoint
from .util import delta_label, iso_utc, parse_delta_hours, slug, strip_safe


LOG = logging.getLogger(__name__)

RASTER_KEYS = (
    "vv_refined_lee_db",
    "vv_refined_lee",
    "vv",
    "vh",
    "vv_glcm_mean",
    "vv_glcm_std",
    "vv_glcm_entropy",
    "decomp_entropy",
    "decomp_anisotropy",
    "decomp_alpha",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        LOG.warning("Catalog file is missing: %s", path)
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _existing_path(raw: object, scene_dir: Path) -> Path | None:
    if not raw:
        return None
    candidate = Path(str(raw))
    if candidate.exists():
        return candidate
    local = scene_dir / candidate.name
    return local if local.exists() else None


def _infer_output(scene_dir: Path, key: str) -> Path | None:
    suffixes = {
        "vv_refined_lee_db": ("_vv_refined_lee_db.tif",),
        "vv_refined_lee": ("_vv_refined_lee.tif",),
        "vv": ("_native_vv.tif", "_slc_vv.tif"),
        "vh": ("_native_vh.tif", "_slc_vh.tif"),
        "vv_glcm_mean": ("_vv_glcm_mean.tif",),
        "vv_glcm_std": ("_vv_glcm_std.tif",),
        "vv_glcm_entropy": ("_vv_glcm_entropy.tif",),
        "decomp_entropy": ("_decomp_entropy.tif",),
        "decomp_anisotropy": ("_decomp_anisotropy.tif",),
        "decomp_alpha": ("_decomp_alpha.tif",),
    }
    for candidate in sorted(scene_dir.glob("*.tif")):
        if candidate.name.endswith(suffixes[key]):
            return candidate
    return None


def discover_processed_scenes(processed_root: Path) -> list[ProcessedScene]:
    scenes: list[ProcessedScene] = []
    for manifest_path in sorted(processed_root.rglob("*_slc_manifest.json")):
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            LOG.warning("Ignoring unreadable processed manifest %s: %s", manifest_path, exc)
            continue
        scene_dir = manifest_path.parent
        outputs_raw = payload.get("outputs") or {}
        outputs: dict[str, Path] = {}
        for key in RASTER_KEYS:
            path = _existing_path(outputs_raw.get(key), scene_dir) or _infer_output(scene_dir, key)
            if path:
                outputs[key] = path
        reference_grid = _existing_path(payload.get("reference_grid"), scene_dir)
        if reference_grid is None:
            refs = sorted(scene_dir.glob("*_aoi_reference_*.tif"))
            reference_grid = refs[0] if refs else None
        granule = strip_safe(str((payload.get("slc") or {}).get("granule") or payload.get("download_group_key") or ""))
        if not granule:
            LOG.warning("Ignoring manifest without a granule key: %s", manifest_path)
            continue
        scenes.append(
            ProcessedScene(
                scene_id=str(payload.get("scene_id") or manifest_path.stem.removesuffix("_slc_manifest")),
                scene_dir=scene_dir,
                manifest_path=manifest_path,
                granule=granule,
                acquisition_start=iso_utc(str(payload.get("acquisition_start") or "")),
                outputs=outputs,
                reference_grid=reference_grid,
            )
        )
    return scenes


def _scene_lookup(scenes: Iterable[ProcessedScene]) -> dict[str, ProcessedScene]:
    lookup: dict[str, ProcessedScene] = {}
    for scene in scenes:
        lookup.setdefault(scene.granule, scene)
        download_key = scene.granule.removeprefix("S1_")
        lookup.setdefault(download_key, scene)
    return lookup


def _sa_points(catalog_root: Path) -> dict[str, tuple[ReferencePoint, ...]]:
    path = catalog_root / "meria_sa_plastic_s1_slc" / "MERIA_SA_plastic_points.csv"
    grouped: dict[str, list[ReferencePoint]] = defaultdict(list)
    for row in read_csv(path):
        grouped[row["obs_id"]].append(
            ReferencePoint(
                point_id=row["pt_id"],
                latitude=float(row["lat"]),
                longitude=float(row["lon"]),
                reference_kind="observed_plastic",
                seed_eligible=True,
                notes=row.get("notes", ""),
            )
        )
    return {key: tuple(value) for key, value in grouped.items()}


def _global_points(catalog_root: Path) -> dict[str, tuple[ReferencePoint, ...]]:
    path = catalog_root / "global_s1_slc_inventory" / "global_s1_slc_points.csv"
    grouped: dict[str, list[ReferencePoint]] = defaultdict(list)
    for row in read_csv(path):
        reference_kind = (row.get("reference_kind") or "aoi_proxy").strip()
        seed_eligible = str(row.get("seed_eligible") or "").strip().lower() in {"true", "1", "yes"}
        notes = (row.get("notes") or "").strip()
        if not notes and reference_kind == "aoi_proxy":
            notes = "Inventory AOI point; not used as a confirmed plastic drift seed."
        grouped[row["obs_id"]].append(
            ReferencePoint(
                point_id=row["point_id"],
                latitude=float(row["lat"]),
                longitude=float(row["lon"]),
                reference_kind=reference_kind,
                seed_eligible=seed_eligible,
                notes=notes,
            )
        )
    return {key: tuple(value) for key, value in grouped.items()}


def _planet_metadata(catalog_root: Path) -> dict[str, dict[str, object]]:
    path = catalog_root / "meria_planet_acquisitions.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    merged: dict[str, dict[str, object]] = {}
    for section in payload.values():
        if isinstance(section, dict):
            merged.update({str(key): value for key, value in section.items() if isinstance(value, dict)})
    return merged


def build_sa_tasks(catalog_root: Path, scenes: Iterable[ProcessedScene]) -> list[DigitisingTask]:
    matches = read_csv(catalog_root / "meria_sa_plastic_s1_slc" / "MERIA_SA_plastic_nearest_S1_SLC_before_after.csv")
    points = _sa_points(catalog_root)
    planet = _planet_metadata(catalog_root)
    scene_by_granule = _scene_lookup(scenes)
    tasks: list[DigitisingTask] = []
    for row in matches:
        obs_id = row["obs_id"]
        optical = planet.get(obs_id, {})
        optical_start, optical_end = _sa_optical_interval(row.get("planet_acquired", ""), optical)
        for role in ("before", "after"):
            granule = strip_safe(row.get(f"{role}_name", ""))
            if not granule or granule == "-":
                continue
            scene = scene_by_granule.get(granule)
            if scene is None:
                LOG.info("SA task %s/%s is not processed yet (%s)", obs_id, role, granule)
                continue
            sar_time = iso_utc(row.get(f"{role}_start", "")) or scene.acquisition_start
            if optical_start and sar_time:
                optical_midpoint = _midpoint(optical_start, optical_end or optical_start)
                delta = (_timestamp(sar_time) - _timestamp(optical_midpoint)).total_seconds() / 3600.0
                task_delta_label = _interval_delta_label(sar_time, optical_start, optical_end or optical_start)
            else:
                delta = parse_delta_hours(row.get(f"{role}_delta_h", ""))
                task_delta_label = delta_label(delta)
            acquisition_token = granule.split("_")[5]
            task_id = slug(f"{obs_id}_{role}_{acquisition_token}")
            tasks.append(
                DigitisingTask(
                    task_id=task_id,
                    dataset="sa",
                    observation_id=obs_id,
                    source_dataset="MERIA_SA",
                    source_group_id=obs_id,
                    area=row.get("area", ""),
                    role=role,
                    optical_time_start=optical_start,
                    optical_time_end=optical_end or optical_start,
                    sar_time=sar_time,
                    delta_hours=delta,
                    delta_label=task_delta_label,
                    scene=scene,
                    reference_points=points.get(obs_id, ()),
                    notes=row.get("notes", ""),
                    planet_item_ids=tuple(str(item) for item in optical.get("planet_item_ids", [])),
                )
            )
    return tasks


def _range_start(value: str) -> str:
    return (value or "").split(" to ", 1)[0].strip()


def _range_end(value: str) -> str:
    parts = (value or "").split(" to ", 1)
    return parts[-1].strip()


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _midpoint(start: str, end: str) -> str:
    start_time = _timestamp(start)
    end_time = _timestamp(end)
    return (start_time + (end_time - start_time) / 2).isoformat().replace("+00:00", "Z")


def _sa_optical_interval(raw_value: str, metadata: dict[str, object]) -> tuple[str, str]:
    metadata_start = str(metadata.get("planet_acquired_start") or "")
    metadata_end = str(metadata.get("planet_acquired_end") or metadata_start)
    if metadata_start:
        return iso_utc(metadata_start), iso_utc(metadata_end)
    raw = (raw_value or "").strip()
    day_match = re.search(r"\d{4}-\d{2}-\d{2}", raw)
    if "UTC day" in raw and day_match:
        day = datetime.fromisoformat(day_match.group(0)).replace(tzinfo=timezone.utc)
        return (
            day.isoformat().replace("+00:00", "Z"),
            (day + timedelta(days=1) - timedelta(microseconds=1)).isoformat().replace("+00:00", "Z"),
        )
    start = iso_utc(_range_start(raw))
    end = iso_utc(_range_end(raw))
    return start, end or start


def _interval_delta_label(sar_time: str, optical_start: str, optical_end: str) -> str:
    sar = _timestamp(sar_time)
    deltas = [
        (sar - _timestamp(optical_start)).total_seconds() / 3600.0,
        (sar - _timestamp(optical_end)).total_seconds() / 3600.0,
    ]
    if min(deltas) <= 0 <= max(deltas):
        return "SAR falls within optical acquisition interval"
    relation = "AFTER" if deltas[0] > 0 else "BEFORE"
    magnitudes = sorted(abs(value) for value in deltas)
    if abs(magnitudes[1] - magnitudes[0]) < 0.01:
        return f"SAR {magnitudes[0]:.2f} h {relation} optical"
    return f"SAR {magnitudes[0]:.2f}–{magnitudes[1]:.2f} h {relation} optical"


def build_global_tasks(catalog_root: Path, scenes: Iterable[ProcessedScene]) -> list[DigitisingTask]:
    rows = read_csv(catalog_root / "global_s1_slc_inventory" / "global_s1_slc_associations.csv")
    points = _global_points(catalog_root)
    scene_by_granule = _scene_lookup(scenes)
    tasks: list[DigitisingTask] = []
    for row in rows:
        if str(row.get("coverage_complete", "")).strip().lower() not in {"true", "1", "yes"}:
            continue
        granule = strip_safe(row.get("granule_name", ""))
        scene = scene_by_granule.get(granule)
        if scene is None:
            continue
        delta = parse_delta_hours(row.get("delta_h", ""))
        acquisition_token = granule.split("_")[5]
        rank = int(row.get("selection_rank") or 1)
        task_id = slug(f"{row['obs_id']}_{row['role']}_R{rank:02d}_{acquisition_token}")
        reference_time = iso_utc(row.get("reference_time", ""))
        tasks.append(
            DigitisingTask(
                task_id=task_id,
                dataset="global",
                observation_id=row["obs_id"],
                source_dataset=row.get("source_dataset", ""),
                source_group_id=row.get("source_group_id", ""),
                area=row.get("area", ""),
                role=row.get("role", ""),
                optical_time_start=reference_time,
                optical_time_end=reference_time,
                sar_time=iso_utc(row.get("acquisition_start", "")) or scene.acquisition_start,
                delta_hours=delta,
                delta_label=delta_label(delta),
                scene=scene,
                reference_points=points.get(row["obs_id"], ()),
                notes=(
                    f"Coverage set ratio {row.get('coverage_set_ratio', '')}; "
                    f"scene coverage ratio {row.get('scene_coverage_ratio', '')}."
                ),
            )
        )
    return tasks


def build_task_catalog(catalog_root: Path, processed_root: Path, dataset: str = "all") -> list[DigitisingTask]:
    scenes = discover_processed_scenes(processed_root)
    tasks: list[DigitisingTask] = []
    if dataset in {"all", "sa"}:
        tasks.extend(build_sa_tasks(catalog_root, scenes))
    if dataset in {"all", "global"}:
        tasks.extend(build_global_tasks(catalog_root, scenes))
    unique: dict[str, DigitisingTask] = {}
    for task in tasks:
        if task.task_id in unique and unique[task.task_id].scene.scene_id != task.scene.scene_id:
            raise ValueError(f"Task id collision: {task.task_id}")
        unique[task.task_id] = task
    return sorted(unique.values(), key=lambda task: (abs(task.delta_hours), task.dataset, task.task_id))
