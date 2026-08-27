from __future__ import annotations

import json
import logging
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import fiona
from shapely.geometry import mapping, shape

from .geopackage import replace_prediction_layers
from .models import DigitisingTask
from .util import stable_hash, write_json


LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class PredictionResult:
    status: str
    detail: str


def _datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _seed_geojson(path: Path, task: DigitisingTask) -> None:
    features = []
    for index, point in enumerate(point for point in task.reference_points if point.seed_eligible):
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [point.longitude, point.latitude]},
                "properties": {"rand_point_id": index, "point_id": point.point_id},
            }
        )
    write_json(path, {"type": "FeatureCollection", "features": features})


def _forcing_directory(root: Path, task: DigitisingTask) -> Path:
    points = [point for point in task.reference_points if point.seed_eligible]
    west = min(point.longitude for point in points) - 0.2
    east = max(point.longitude for point in points) + 0.2
    south = min(point.latitude for point in points) - 0.2
    north = max(point.latitude for point in points) + 0.2
    start = min(_datetime(task.optical_time_start), _datetime(task.sar_time)) - timedelta(days=1)
    end = max(_datetime(task.optical_time_end or task.optical_time_start), _datetime(task.sar_time)) + timedelta(days=1)
    key = stable_hash(start.date(), end.date(), round(west, 3), round(south, 3), round(east, 3), round(north, 3))
    return root / f"{start:%Y%m%d}_{end:%Y%m%d}_{key}"


def _forcing_present(path: Path) -> bool:
    return (
        bool(list(path.glob("cmems_currents_*.nc")))
        and bool(list(path.glob("cmems_waves_*.nc")))
        and bool(list(path.glob("era5_wind_*.nc")))
    )


def _fetch_forcing(
    task: DigitisingTask,
    forcing_dir: Path,
    fetch_script: Path,
    cmems_credentials: Path,
    cdsapirc: Path,
) -> None:
    points = [point for point in task.reference_points if point.seed_eligible]
    start = min(_datetime(task.optical_time_start), _datetime(task.sar_time)) - timedelta(days=1)
    end = max(_datetime(task.optical_time_end or task.optical_time_start), _datetime(task.sar_time)) + timedelta(days=1)
    command = [
        sys.executable,
        str(fetch_script),
        "--out-dir",
        str(forcing_dir),
        "--start-date",
        start.date().isoformat(),
        "--end-date",
        end.date().isoformat(),
        "--west",
        str(min(point.longitude for point in points) - 0.2),
        "--south",
        str(min(point.latitude for point in points) - 0.2),
        "--east",
        str(max(point.longitude for point in points) + 0.2),
        "--north",
        str(max(point.latitude for point in points) + 0.2),
        "--cmems-credentials",
        str(cmems_credentials),
        "--cdsapirc",
        str(cdsapirc),
    ]
    subprocess.run(command, check=True)


def _load_predictions(task: DigitisingTask, gpkg: Path, output_dir: Path) -> None:
    eligible_points = [point for point in task.reference_points if point.seed_eligible]
    point_rows = []
    predicted_path = output_dir / "predicted_seed_polygons.geojson"
    if predicted_path.exists():
        with fiona.open(predicted_path) as source:
            for feature in source:
                properties = dict(feature.get("properties") or {})
                seed_index = int(properties.get("seed_idx") or 0)
                seed_id = eligible_points[seed_index].point_id if seed_index < len(eligible_points) else str(seed_index)
                centroid = shape(feature["geometry"]).centroid
                point_rows.append(
                    {
                        "type": "Feature",
                        "geometry": mapping(centroid),
                        "properties": {
                            "seed_id": seed_id,
                            "task_id": task.task_id,
                            "delta_h": task.delta_hours,
                            "status": "complete",
                        },
                    }
                )
    envelope_rows = []
    envelopes_path = output_dir / "search_boxes_1km.geojson"
    if envelopes_path.exists():
        with fiona.open(envelopes_path) as source:
            for feature in source:
                properties = dict(feature.get("properties") or {})
                seed_index = int(properties.get("seed_idx") or 0)
                seed_id = eligible_points[seed_index].point_id if seed_index < len(eligible_points) else str(seed_index)
                envelope_rows.append(
                    {
                        "type": "Feature",
                        "geometry": mapping(shape(feature["geometry"])),
                        "properties": {
                            "seed_id": seed_id,
                            "task_id": task.task_id,
                            "delta_h": task.delta_hours,
                            "status": "complete",
                        },
                    }
                )
    replace_prediction_layers(gpkg, task, point_rows, envelope_rows)


def prepare_prediction(
    task: DigitisingTask,
    gpkg: Path,
    *,
    forcing_cache: Path,
    tools_root: Path,
    cmems_credentials: Path,
    cdsapirc: Path,
    mode: str = "auto",
) -> PredictionResult:
    eligible = [point for point in task.reference_points if point.seed_eligible]
    if not eligible:
        return PredictionResult("no_valid_seed", "No confirmed observation point is available; AOI proxies were not advected.")
    if mode == "skip":
        return PredictionResult("not_run", "Prediction was disabled for this preparation run.")

    output_dir = task.task_dir / "drift"
    manifest_path = output_dir / "opendrift_manifest.json"
    if manifest_path.exists():
        try:
            _load_predictions(task, gpkg, output_dir)
            return PredictionResult("complete", "Reused the existing task-specific OpenDrift result.")
        except Exception as exc:
            LOG.warning("Could not reuse drift result for %s: %s", task.task_id, exc)

    fetch_script = tools_root / "fetch_drift_forcing.py"
    run_script = tools_root / "run_planet_to_sar_opendrift.py"
    if not fetch_script.exists() or not run_script.exists():
        return PredictionResult("failed", f"Drift tools are missing under {tools_root}")
    forcing_dir = _forcing_directory(forcing_cache, task)
    forcing_dir.mkdir(parents=True, exist_ok=True)
    if not _forcing_present(forcing_dir):
        if mode == "cached-only":
            return PredictionResult("forcing_unavailable", f"No cached forcing exists at {forcing_dir}")
        if not cmems_credentials.exists() or not cdsapirc.exists():
            return PredictionResult("forcing_unavailable", "CMEMS or CDS credentials are not mounted in the container.")
        try:
            _fetch_forcing(task, forcing_dir, fetch_script, cmems_credentials, cdsapirc)
        except Exception as exc:
            LOG.exception("Forcing retrieval failed for %s", task.task_id)
            return PredictionResult("forcing_unavailable", str(exc))

    output_dir.mkdir(parents=True, exist_ok=True)
    seeds = output_dir / "seeds.geojson"
    _seed_geojson(seeds, task)
    try:
        subprocess.run(
            [
                sys.executable,
                str(run_script),
                "--seeds",
                str(seeds),
                "--planet-time",
                task.optical_time_representative,
                "--target-time",
                task.sar_time,
                "--forcing-dir",
                str(forcing_dir),
                "--out-dir",
                str(output_dir),
                "--target-raster",
                str(next(iter(task.scene.outputs.values()))),
                "--landmask-source",
                "none",
            ],
            check=True,
        )
        _load_predictions(task, gpkg, output_dir)
    except Exception as exc:
        LOG.exception("OpenDrift failed for %s", task.task_id)
        return PredictionResult("failed", str(exc))
    return PredictionResult("complete", "OpenDrift completed using cached or newly fetched CMEMS/ERA5 forcing.")
