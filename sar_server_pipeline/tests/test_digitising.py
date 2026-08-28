from __future__ import annotations

import csv
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import fiona
import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import MultiPolygon, box, mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
WORKSPACE_ROOT = REPO_ROOT.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

RASTERIO_ROOT = Path(rasterio.__file__).resolve().parent
os.environ["PROJ_LIB"] = str(RASTERIO_ROOT / "proj_data")
os.environ["GDAL_DATA"] = str(RASTERIO_ROOT / "gdal_data")

from digitising.catalog import _sa_optical_interval, build_task_catalog
from digitising.drift import _forcing_directory, prepare_prediction
from digitising.geopackage import ANNOTATION_SCHEMA, create_or_refresh_task_geopackage, validate_annotations
from digitising import project as qgis_project
from digitising.util import relative_to_root
from digitising.workflow import Environment, import_batch, prepare_batch
from Domain_SSL.Scripts.Preprocessing.fetch_drift_forcing import month_chunks


SHARED_GRANULE = "S1B_IW_SLC__1SDV_20190425T031055_20190425T031122_015957_01DFC7_4905"


class QgisApplicationLifecycleTests(unittest.TestCase):
    def test_one_application_is_reused_for_all_projects_in_a_batch(self) -> None:
        class FakeApplication:
            current = None
            initialised = 0

            @classmethod
            def instance(cls):
                return cls.current

            def __init__(self, _args, _gui_enabled):
                type(self).current = self

            def initQgis(self):
                type(self).initialised += 1

        prior = qgis_project._QGIS_APPLICATION
        qgis_project._QGIS_APPLICATION = None
        try:
            first = qgis_project._ensure_qgis_application(FakeApplication)
            second = qgis_project._ensure_qgis_application(FakeApplication)
        finally:
            qgis_project._QGIS_APPLICATION = prior

        self.assertIs(first, second)
        self.assertEqual(FakeApplication.initialised, 1)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def build_fixture(root: Path) -> tuple[Environment, Path]:
    data_root = root / "sar-data"
    catalog_root = root / "catalog"
    scene_dir = data_root / "processed" / "MERIA_SA_001_Durban" / "after_20190425T031055"
    scene_dir.mkdir(parents=True)
    raster_path = scene_dir / "MERIA_SA_001_Durban_after_20190425T031055_slc_utm_vv_refined_lee_db.tif"
    with rasterio.open(
        raster_path,
        "w",
        driver="GTiff",
        width=100,
        height=100,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(30.0, -29.0, 0.02, 0.02),
    ) as sink:
        sink.write(np.ones((1, 100, 100), dtype="float32"))
    reference_path = scene_dir / "MERIA_SA_001_Durban_after_20190425T031055_aoi_reference_utm10m.tif"
    shutil.copy2(raster_path, reference_path)
    manifest_path = scene_dir / "MERIA_SA_001_Durban_after_20190425T031055_slc_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "observation_id": "MERIA_SA_001",
                "area": "Durban",
                "role": "after",
                "acquisition_start": "2019-04-25 03:10:55 UTC",
                "scene_id": "MERIA_SA_001_Durban_after_20190425T031055",
                "download_group_key": SHARED_GRANULE,
                "slc": {"granule": SHARED_GRANULE},
                "reference_grid": str(reference_path),
                "outputs": {"vv_refined_lee_db": str(raster_path)},
                "status": "processed",
            }
        ),
        encoding="utf-8",
    )

    sa_dir = catalog_root / "meria_sa_plastic_s1_slc"
    write_csv(
        sa_dir / "MERIA_SA_plastic_points.csv",
        [
            {
                "obs_id": "MERIA_SA_001",
                "obs_date": "2019-04-24",
                "area": "Durban",
                "pt_id": "MERIA_SA_001_P01",
                "lat": -30.0,
                "lon": 31.0,
                "dms": "",
                "notes": "first observation",
            },
            {
                "obs_id": "MERIA_SA_002",
                "obs_date": "2019-04-25",
                "area": "Durban",
                "pt_id": "MERIA_SA_002_P01",
                "lat": -30.1,
                "lon": 31.1,
                "dms": "",
                "notes": "second observation",
            },
        ],
    )
    write_csv(
        sa_dir / "MERIA_SA_plastic_nearest_S1_SLC_before_after.csv",
        [
            {
                "obs_id": "MERIA_SA_001",
                "area": "Durban",
                "date": "2019-04-24",
                "planet_acquired": "2019-04-24 07:38:41 UTC",
                "before_name": "-",
                "before_start": "",
                "before_delta_h": "",
                "after_name": SHARED_GRANULE + ".SAFE",
                "after_start": "2019-04-25 03:10:55 UTC",
                "after_delta_h": "+19.12",
                "notes": "after task",
            },
            {
                "obs_id": "MERIA_SA_002",
                "area": "Durban",
                "date": "2019-04-25",
                "planet_acquired": "2019-04-25 07:36:26 UTC",
                "before_name": SHARED_GRANULE + ".SAFE",
                "before_start": "2019-04-25 03:10:55 UTC",
                "before_delta_h": "-4.43",
                "after_name": "-",
                "after_start": "",
                "after_delta_h": "",
                "notes": "before task",
            },
        ],
    )
    (catalog_root / "meria_planet_acquisitions.json").write_text(
        json.dumps(
            {
                "sa": {
                    "MERIA_SA_001": {
                        "planet_acquired_start": "2019-04-24T07:38:41Z",
                        "planet_acquired_end": "2019-04-24T07:38:41Z",
                        "planet_item_ids": ["planet-001"],
                    },
                    "MERIA_SA_002": {
                        "planet_acquired_start": "2019-04-25T07:36:26Z",
                        "planet_acquired_end": "2019-04-25T07:36:26Z",
                        "planet_item_ids": ["planet-002"],
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    environment = Environment(
        data_root=data_root,
        catalog_root=catalog_root,
        drift_tools_root=root / "drift-tools",
        remote="bolelang@146.64.214.137",
        remote_data_root="/mnt/storage/bolelang_mount/Joshua/sar-data",
        desktop_root="/home/bsibolla/Desktop/Joshua",
        cmems_credentials=root / "missing-cmems",
        cdsapirc=root / "missing-cds",
    )
    return environment, raster_path


def add_valid_annotation(gpkg: Path, task) -> None:
    properties = {field: None for field in ANNOTATION_SCHEMA["properties"]}
    properties.update({"Class": "plastic", "confidence": "high", "notes": "visible patch"})
    geometry = mapping(MultiPolygon([box(30.9, -30.1, 31.1, -29.9)]))
    with fiona.open(gpkg, "a", layer="annotations") as sink:
        sink.write({"type": "Feature", "geometry": geometry, "properties": properties})


def fake_project(path: Path, tasks, *, title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(title + "\n" + "\n".join(task.task_id for task in tasks), encoding="utf-8")


class CatalogTests(unittest.TestCase):
    def test_day_only_optical_reference_is_preserved_as_an_interval(self) -> None:
        start, end = _sa_optical_interval("2026-05-09 UTC day", {})

        self.assertEqual(start, "2026-05-09T00:00:00Z")
        self.assertEqual(end, "2026-05-09T23:59:59.999999Z")

    def test_shared_sar_acquisition_produces_independent_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            environment, _ = build_fixture(Path(temporary))
            tasks = build_task_catalog(environment.catalog_root, environment.processed_root, "sa")

        self.assertEqual(len(tasks), 2)
        self.assertNotEqual(tasks[0].task_id, tasks[1].task_id)
        self.assertEqual(tasks[0].scene.scene_id, tasks[1].scene.scene_id)
        self.assertEqual([task.observation_id for task in tasks], ["MERIA_SA_002", "MERIA_SA_001"])

    def test_global_catalog_uses_only_complete_associations_and_marks_proxy_points(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            environment, _ = build_fixture(Path(temporary))
            global_dir = environment.catalog_root / "global_s1_slc_inventory"
            base = {
                "target_id": "marida_scene:before:01",
                "obs_id": "marida_scene",
                "source_dataset": "MARIDA",
                "source_group_id": "tile/date",
                "area": "tile",
                "date": "2019-04-25",
                "reference_time": "2019-04-25T07:36:26Z",
                "timestamp_source": "catalogue",
                "role": "before",
                "selection_rank": "1",
                "granule_name": SHARED_GRANULE + ".SAFE",
                "acquisition_start": "2019-04-25T03:10:55Z",
                "delta_h": "-4.43",
                "scene_coverage_ratio": "1",
                "coverage_set_ratio": "1",
                "coverage_complete": "True",
                "download_group_key": SHARED_GRANULE,
                "aoi_buffer_km": "30",
            }
            incomplete = dict(base, obs_id="incomplete_scene", target_id="incomplete_scene:before:01", coverage_complete="False")
            write_csv(global_dir / "global_s1_slc_associations.csv", [base, incomplete])
            write_csv(
                global_dir / "global_s1_slc_points.csv",
                [{"obs_id": "marida_scene", "point_id": "bbox-1", "lat": -30.0, "lon": 31.0}],
            )

            tasks = build_task_catalog(environment.catalog_root, environment.processed_root, "global")

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].observation_id, "marida_scene")
        self.assertEqual(tasks[0].reference_points[0].reference_kind, "aoi_proxy")
        self.assertFalse(tasks[0].reference_points[0].seed_eligible)


class GeoPackageTests(unittest.TestCase):
    def test_database_triggers_populate_ids_and_task_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            environment, _ = build_fixture(Path(temporary))
            task = build_task_catalog(environment.catalog_root, environment.processed_root, "sa")[0]
            gpkg = task.task_dir / "task.gpkg"
            create_or_refresh_task_geopackage(gpkg, task)
            add_valid_annotation(gpkg, task)

            validation = validate_annotations(gpkg, task)
            with fiona.open(gpkg, layer="annotations") as source:
                properties = dict(next(iter(source))["properties"])

        self.assertTrue(validation.valid, validation.errors)
        self.assertTrue(properties["feature_uuid"])
        self.assertEqual(properties["patch_id"], f"{task.task_id}-P0001")
        self.assertEqual(properties["task_id"], task.task_id)
        self.assertEqual(properties["scene_id"], task.scene.scene_id)


class PredictionTests(unittest.TestCase):
    def test_forcing_dates_are_split_safely_across_month_boundaries(self) -> None:
        chunks = month_chunks("2024-01-30", "2024-03-02")

        self.assertEqual(
            [(start.isoformat(), end.isoformat()) for start, end in chunks],
            [
                ("2024-01-30", "2024-01-31"),
                ("2024-02-01", "2024-02-29"),
                ("2024-03-01", "2024-03-02"),
            ],
        )

    def test_forward_and_backward_tasks_run_toward_the_sar_time_from_cached_forcing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            environment, _ = build_fixture(Path(temporary))
            environment.drift_tools_root.mkdir(parents=True)
            (environment.drift_tools_root / "fetch_drift_forcing.py").write_text("", encoding="utf-8")
            (environment.drift_tools_root / "run_planet_to_sar_opendrift.py").write_text("", encoding="utf-8")
            tasks = build_task_catalog(environment.catalog_root, environment.processed_root, "sa")
            for task in tasks:
                forcing = _forcing_directory(environment.forcing_cache, task)
                forcing.mkdir(parents=True)
                (forcing / "cmems_currents_test.nc").write_text("cached", encoding="utf-8")
                (forcing / "cmems_waves_test.nc").write_text("cached", encoding="utf-8")
                (forcing / "era5_wind_test.nc").write_text("cached", encoding="utf-8")
                create_or_refresh_task_geopackage(task.task_dir / "task.gpkg", task)

            with mock.patch("digitising.drift.subprocess.run") as run_mock, mock.patch(
                "digitising.drift._load_predictions"
            ):
                results = [
                    prepare_prediction(
                        task,
                        task.task_dir / "task.gpkg",
                        forcing_cache=environment.forcing_cache,
                        tools_root=environment.drift_tools_root,
                        cmems_credentials=environment.cmems_credentials,
                        cdsapirc=environment.cdsapirc,
                    )
                    for task in tasks
                ]

        self.assertEqual([result.status for result in results], ["complete", "complete"])
        commands = [call.args[0] for call in run_mock.call_args_list]
        self.assertEqual(len(commands), 2)
        for task, command in zip(tasks, commands):
            self.assertEqual(command[command.index("--planet-time") + 1], task.optical_time_representative)
            self.assertEqual(command[command.index("--target-time") + 1], task.sar_time)

    def test_missing_forcing_credentials_does_not_block_scaffolding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            environment, _ = build_fixture(Path(temporary))
            environment.drift_tools_root.mkdir(parents=True)
            (environment.drift_tools_root / "fetch_drift_forcing.py").write_text("", encoding="utf-8")
            (environment.drift_tools_root / "run_planet_to_sar_opendrift.py").write_text("", encoding="utf-8")
            task = build_task_catalog(environment.catalog_root, environment.processed_root, "sa")[0]
            gpkg = task.task_dir / "task.gpkg"
            create_or_refresh_task_geopackage(gpkg, task)

            result = prepare_prediction(
                task,
                gpkg,
                forcing_cache=environment.forcing_cache,
                tools_root=environment.drift_tools_root,
                cmems_credentials=environment.cmems_credentials,
                cdsapirc=environment.cdsapirc,
            )

        self.assertEqual(result.status, "forcing_unavailable")


class PreparationTests(unittest.TestCase):
    def test_limit_is_applied_after_populated_task_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            environment, _ = build_fixture(Path(temporary))
            tasks = build_task_catalog(environment.catalog_root, environment.processed_root, "sa")
            create_or_refresh_task_geopackage(tasks[0].task_dir / "task.gpkg", tasks[0])
            add_valid_annotation(tasks[0].task_dir / "task.gpkg", tasks[0])

            result = prepare_batch(
                environment,
                dataset="sa",
                limit=1,
                batch_name="dry",
                prediction_mode="skip",
                dry_run=True,
                project_builder=fake_project,
            )

        self.assertEqual(result.skipped_complete, (tasks[0].task_id,))
        self.assertEqual(result.selected, (tasks[1].task_id,))

    def test_prepare_writes_portable_transfer_and_return_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            environment, raster_path = build_fixture(Path(temporary))
            result = prepare_batch(
                environment,
                dataset="sa",
                limit=1,
                batch_name="batch_001",
                prediction_mode="skip",
                project_builder=fake_project,
            )
            batch_dir = environment.data_root / "digitising_batches" / "batch_001"
            transfer = (batch_dir / "transfer_files.txt").read_text(encoding="utf-8").splitlines()
            returned = (batch_dir / "return_files.txt").read_text(encoding="utf-8").splitlines()

        self.assertEqual(len(result.selected), 1)
        self.assertIn(relative_to_root(raster_path, environment.data_root), transfer)
        self.assertTrue(any(path.endswith("task.gpkg") for path in transfer))
        self.assertTrue(any(path.endswith("batch.qgz") for path in transfer))
        self.assertEqual(len(returned), 1)
        self.assertTrue(returned[0].endswith("task.gpkg"))
        self.assertNotIn("/SLC/", "\n".join(transfer))
        self.assertIn("rsync -av --relative", result.pull_command)


class ImportTests(unittest.TestCase):
    def test_valid_return_is_imported_and_only_annotations_are_exported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            environment, _ = build_fixture(Path(temporary))
            prepared = prepare_batch(
                environment,
                dataset="sa",
                limit=1,
                batch_name="batch_001",
                prediction_mode="skip",
                project_builder=fake_project,
            )
            task = {task.task_id: task for task in build_task_catalog(environment.catalog_root, environment.processed_root)}[
                prepared.selected[0]
            ]
            incoming = (
                environment.data_root
                / "digitising_returns"
                / "batch_001"
                / relative_to_root(task.task_dir / "task.gpkg", environment.data_root)
            )
            incoming.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(task.task_dir / "task.gpkg", incoming)
            add_valid_annotation(incoming, task)

            report = import_batch(environment, "batch_001")
            exported = environment.data_root / "shapefiles" / task.scene.scene_id / f"{task.task_id}_annotations.geojson"
            with fiona.open(exported) as source:
                exported_features = list(source)

        self.assertEqual(report["invalid"], {})
        self.assertEqual(report["conflicts"], {})
        self.assertEqual(report["imported"][0]["feature_count"], 1)
        self.assertEqual(len(exported_features), 1)
        self.assertEqual(exported_features[0]["properties"]["Class"], "plastic")

    def test_empty_return_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            environment, _ = build_fixture(Path(temporary))
            prepared = prepare_batch(
                environment,
                dataset="sa",
                limit=1,
                batch_name="batch_empty",
                prediction_mode="skip",
                project_builder=fake_project,
            )
            task = {task.task_id: task for task in build_task_catalog(environment.catalog_root, environment.processed_root)}[
                prepared.selected[0]
            ]
            incoming = (
                environment.data_root
                / "digitising_returns"
                / "batch_empty"
                / relative_to_root(task.task_dir / "task.gpkg", environment.data_root)
            )
            incoming.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(task.task_dir / "task.gpkg", incoming)

            report = import_batch(environment, "batch_empty")

        self.assertIn(task.task_id, report["invalid"])
        self.assertEqual(report["imported"], [])


if __name__ == "__main__":
    unittest.main()
