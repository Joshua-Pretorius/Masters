from __future__ import annotations

import csv
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import rasterio as rio
from rasterio.transform import from_origin
from shapely.geometry import mapping, box


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

RASTERIO_ROOT = Path(rio.__file__).resolve().parent
os.environ["PROJ_LIB"] = str(RASTERIO_ROOT / "proj_data")
os.environ["GDAL_DATA"] = str(RASTERIO_ROOT / "gdal_data")

from pipeline.cli import main
from pipeline.manifest import load_manifest
from pipeline.runner import STAGE_ORDER, run_stage, run_workflow
from stages.patch_extract import run_patch_extract, select_output_bundle
from stages.patch_stack import run_patch_stack
from stages.slc_process import _default_processor_script, _load_module, run_slc_process


SAR_BANDS = [
    "vv_db",
    "vh_db",
    "vv_vh_ratio_db",
    "vv_minus_vh_db",
    "vv_glcm_mean",
    "vv_glcm_std",
    "vv_glcm_entropy",
    "decomp_entropy",
    "decomp_anisotropy",
    "decomp_alpha",
]


def write_raster(path: Path, data: np.ndarray, *, crs: str = "EPSG:4326") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "width": int(data.shape[1]),
        "height": int(data.shape[0]),
        "count": 1,
        "dtype": "float32",
        "crs": crs,
        "transform": from_origin(0.0, float(data.shape[0]), 1.0, 1.0),
        "nodata": np.nan,
    }
    with rio.open(path, "w", **profile) as dst:
        dst.write(data.astype("float32"), 1)


def write_feature_file(path: Path, *, scene_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    feature_collection = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": mapping(box(1.0, 1.0, 3.0, 3.0)),
                "properties": {
                    "scene_id": scene_id,
                    "patch_id": "001",
                    "Class": "Plastic",
                },
            }
        ],
    }
    path.write_text(json.dumps(feature_collection), encoding="utf-8")


def write_scene_manifest(scene_dir: Path, scene_id: str, outputs: dict[str, str]) -> Path:
    scene_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = scene_dir / f"{scene_id}_slc_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "scene_id": scene_id,
                "outputs": outputs,
                "processing": {"subswath_grids": {}},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return manifest_path


def build_manifest(temp_root: Path, *, scene_id: str = "SCENE_001") -> Path:
    raw_root = temp_root / "raw"
    shapefiles_root = temp_root / "shapefiles"
    processed_root = temp_root / "processed"
    patches_root = temp_root / "patches"
    stacks_root = temp_root / "stacks"
    logs_root = temp_root / "logs"
    manifests_root = temp_root / "manifests"
    biophysical_root = temp_root / "biophysical"

    scene_dir = processed_root / "durban" / scene_id
    outputs: dict[str, str] = {}
    band_arrays = {
        "vv": np.full((4, 4), 10.0, dtype="float32"),
        "vh": np.full((4, 4), 10.0, dtype="float32"),
        "vv_refined_lee_db": np.full((4, 4), 5.0, dtype="float32"),
        "vv_glcm_mean": np.full((4, 4), 2.0, dtype="float32"),
        "vv_glcm_std": np.full((4, 4), 3.0, dtype="float32"),
        "vv_glcm_entropy": np.full((4, 4), 4.0, dtype="float32"),
        "decomp_entropy": np.full((4, 4), 6.0, dtype="float32"),
        "decomp_anisotropy": np.full((4, 4), 7.0, dtype="float32"),
        "decomp_alpha": np.full((4, 4), 8.0, dtype="float32"),
    }
    for key, array in band_arrays.items():
        tif_path = scene_dir / f"{scene_id}_{key}.tif"
        write_raster(tif_path, array)
        outputs[key] = str(tif_path)
    write_scene_manifest(scene_dir, scene_id, outputs)
    write_feature_file(shapefiles_root / scene_id / "patches.geojson", scene_id=scene_id)

    for band_name, fill_value in {"uo": 11.0, "vo": 12.0, "swh": 13.0}.items():
        write_raster(biophysical_root / scene_id / f"{band_name}.tif", np.full((4, 4), fill_value, dtype="float32"))

    manifest_path = temp_root / "job.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "run-001",
                "dataset_mode": "sa",
                "targets": ["MERIA_SA_001:after"],
                "inputs": {
                    "match_csv": str(raw_root / "matches.csv"),
                    "points_csv": str(raw_root / "points.csv"),
                    "raw_slc_root": str(raw_root / "slc"),
                    "shapefiles_root": str(shapefiles_root),
                    "biophysical_root": str(biophysical_root),
                },
                "outputs": {
                    "processed_root": str(processed_root),
                    "patches_root": str(patches_root),
                    "stacks_root": str(stacks_root),
                    "logs_root": str(logs_root),
                    "manifests_root": str(manifests_root),
                },
                "stages": {
                    "slc_process": {"enabled": True, "overwrite": False},
                    "patch_extract": {"enabled": True, "overwrite": False},
                    "patch_stack": {"enabled": True, "overwrite": False},
                },
                "processing": {
                    "subset_mode": "aoi",
                    "subswaths": ["IW1", "IW2", "IW3"],
                    "workers": 1,
                    "cache_gb": 8,
                    "patch_size": 4,
                    "sar_band_order": SAR_BANDS,
                    "biophysical_bands": ["uo", "vo", "swh"],
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return manifest_path


class ManifestLoadingTests(unittest.TestCase):
    def test_load_manifest_resolves_absolute_paths_and_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest_path = build_manifest(Path(tmp_dir))

            manifest = load_manifest(manifest_path)

        self.assertEqual(manifest.schema_version, 1)
        self.assertEqual(manifest.run_id, "run-001")
        self.assertEqual(manifest.dataset_mode, "sa")
        self.assertEqual(manifest.processing.resolution_policy, "snap-native")
        self.assertEqual(manifest.processing.output_mode, "scene")
        self.assertEqual(manifest.processing.patch_size, 4)
        self.assertEqual(manifest.processing.biophysical_bands, ("uo", "vo", "swh"))
        self.assertTrue(manifest.outputs.processed_root.is_absolute())


class SceneBundleSelectionTests(unittest.TestCase):
    def test_select_output_bundle_falls_back_to_matching_subswath(self) -> None:
        manifest = {
            "scene_id": "SCENE_001",
            "outputs": {"vv": None},
            "subswath_outputs": {
                "IW2": {
                    "vv": "vv.tif",
                    "vh": "vh.tif",
                    "vv_refined_lee_db": "vv_refined_lee_db.tif",
                    "vv_glcm_mean": "vv_glcm_mean.tif",
                    "vv_glcm_std": "vv_glcm_std.tif",
                    "vv_glcm_entropy": "vv_glcm_entropy.tif",
                    "decomp_entropy": "decomp_entropy.tif",
                    "decomp_anisotropy": "decomp_anisotropy.tif",
                    "decomp_alpha": "decomp_alpha.tif",
                }
            },
            "processing": {
                "subswath_grids": {
                    "IW2": {"bounds": [0.0, 0.0, 10.0, 10.0]},
                }
            },
        }

        selected = select_output_bundle(manifest, centroid_x=5.0, centroid_y=5.0)

        self.assertEqual(selected["vv"], "vv.tif")


class PatchExtractStageTests(unittest.TestCase):
    def test_patch_extract_writes_inventory_and_patch_rasters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest_path = build_manifest(Path(tmp_dir))
            manifest = load_manifest(manifest_path)

            result = run_patch_extract(manifest)

            inventory_csv = manifest.outputs.patches_root / "sar_patch_inventory.csv"
            library_csv = manifest.outputs.patches_root / "sar_patch_library.csv"
            self.assertEqual(result.processed_features, 1)
            self.assertTrue(inventory_csv.exists())
            self.assertTrue(library_csv.exists())
            with inventory_csv.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertTrue(Path(rows[0]["image_path"]).exists())
            self.assertTrue(Path(rows[0]["mask_path"]).exists())

    def test_patch_extract_deduplicates_the_same_stable_feature(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest_path = build_manifest(Path(tmp_dir))
            manifest = load_manifest(manifest_path)
            original = manifest.inputs.shapefiles_root / "SCENE_001" / "patches.geojson"
            payload = json.loads(original.read_text(encoding="utf-8"))
            payload["features"][0]["properties"]["feature_uuid"] = "3d591f50-451d-46d5-a45e-e9341cd2f9dd"
            original.write_text(json.dumps(payload), encoding="utf-8")
            duplicate = original.with_name("duplicate.geojson")
            duplicate.write_text(json.dumps(payload), encoding="utf-8")

            result = run_patch_extract(manifest)

        self.assertEqual(result.processed_features, 1)


class PatchStackStageTests(unittest.TestCase):
    def test_patch_stack_combines_sar_and_biophysical_channels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest_path = build_manifest(Path(tmp_dir))
            manifest = load_manifest(manifest_path)
            run_patch_extract(manifest)

            result = run_patch_stack(manifest)

            catalog_csv = manifest.outputs.stacks_root / "stack_catalog.csv"
            self.assertEqual(result.processed_patches, 1)
            with catalog_csv.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            stack_path = Path(rows[0]["stack_path"])
            channels_path = Path(rows[0]["channels_path"])
            self.assertTrue(stack_path.exists())
            self.assertTrue(channels_path.exists())
            with rio.open(stack_path) as src:
                self.assertEqual(src.count, len(SAR_BANDS) + 3)
            channels = json.loads(channels_path.read_text(encoding="utf-8"))
            self.assertEqual(channels[: len(SAR_BANDS)], SAR_BANDS)
            self.assertEqual(channels[-3:], ["uo", "vo", "swh"])


class RunnerAndCliTests(unittest.TestCase):
    def test_default_slc_processor_is_vendored_in_server_repo(self) -> None:
        sa_script = _default_processor_script("sa")
        global_script = _default_processor_script("global")

        self.assertIn("sar_server_pipeline", str(sa_script))
        self.assertTrue(sa_script.exists())
        self.assertTrue(global_script.exists())

    def test_global_slc_processor_loads_its_vendored_sa_sibling(self) -> None:
        global_script = _default_processor_script("global")

        module = _load_module(global_script)

        self.assertEqual(
            Path(module.sa.__file__).resolve(),
            global_script.with_name("process_sa_slc_targets.py").resolve(),
        )

    def test_slc_stage_routes_shared_download_cache_to_manifest_raw_root(self) -> None:
        source = (REPO_ROOT / "stages" / "slc_process.py").read_text(encoding="utf-8")
        self.assertIn("module.DATA_DIR = manifest.inputs.raw_slc_root", source)

    def test_slc_stage_forwards_scene_and_resolution_options(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest = load_manifest(build_manifest(Path(tmp_dir)))
            fake_module = mock.Mock()
            captured_argv: list[str] = []

            def capture_argv() -> None:
                captured_argv.extend(sys.argv)

            fake_module.main.side_effect = capture_argv

            with mock.patch("stages.slc_process._load_module", return_value=fake_module):
                run_slc_process(manifest)

            self.assertIn("--resolution-policy", captured_argv)
            self.assertEqual(captured_argv[captured_argv.index("--resolution-policy") + 1], "snap-native")
            self.assertIn("--output-mode", captured_argv)
            self.assertEqual(captured_argv[captured_argv.index("--output-mode") + 1], "scene")

    def test_run_workflow_stops_on_failure_and_preserves_completed_stage_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest = load_manifest(build_manifest(Path(tmp_dir)))
            calls: list[str] = []

            def ok_stage(current_manifest):
                calls.append("ok")
                return {"status": "ok"}

            def failing_stage(current_manifest):
                calls.append("fail")
                raise RuntimeError("boom")

            registry = {
                "slc_process": ok_stage,
                "patch_extract": failing_stage,
                "patch_stack": ok_stage,
            }

            with self.assertRaises(RuntimeError):
                run_workflow(manifest, stage_names=STAGE_ORDER, stage_registry=registry)

            marker = manifest.outputs.manifests_root / manifest.run_id / "stages" / "slc_process.json"
            self.assertEqual(calls, ["ok", "fail"])
            self.assertTrue(marker.exists())
            self.assertFalse((manifest.outputs.manifests_root / manifest.run_id / "stages" / "patch_stack.json").exists())

    def test_run_stage_skips_completed_stage_when_marker_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest = load_manifest(build_manifest(Path(tmp_dir)))
            calls: list[str] = []

            def ok_stage(current_manifest):
                calls.append("called")
                return {"status": "ok"}

            run_stage(manifest, "patch_extract", ok_stage)
            result = run_stage(manifest, "patch_extract", ok_stage)

            self.assertEqual(calls, ["called"])
            self.assertTrue(result.skipped)

    def test_cli_dispatches_named_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest_path = build_manifest(Path(tmp_dir))

            with mock.patch("pipeline.cli.run_workflow") as run_workflow_mock:
                exit_code = main(["patch_extract", "--manifest", str(manifest_path)])

            self.assertEqual(exit_code, 0)
            self.assertTrue(run_workflow_mock.called)
            kwargs = run_workflow_mock.call_args.kwargs
            self.assertEqual(kwargs["stage_names"], ("patch_extract",))


class DockerPackagingTests(unittest.TestCase):
    def test_pipeline_uses_native_snap_runtime_without_host_mount(self) -> None:
        dockerfile = (REPO_ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")
        compose = (REPO_ROOT / "compose.yml").read_text(encoding="utf-8")

        self.assertIn("ARG SNAP_IMAGE=mundialis/esa-snap:latest", dockerfile)
        self.assertIn("FROM ${SNAP_IMAGE}", dockerfile)
        self.assertIn("apk add --no-cache", dockerfile)
        self.assertNotIn("FROM python:3.11-slim-bullseye", dockerfile)
        self.assertNotIn("COPY --from=snap-runtime", dockerfile)
        self.assertIn('SNAP_GPT=/usr/local/snap/bin/gpt', dockerfile)
        self.assertIn("ARG SNAP_INITIAL_HEAP=4G", dockerfile)
        self.assertIn("ARG SNAP_MAX_HEAP=64G", dockerfile)
        self.assertIn('"-Xms${SNAP_INITIAL_HEAP}"', dockerfile)
        self.assertIn('"-Xmx${SNAP_MAX_HEAP}"', dockerfile)
        self.assertIn('"${SNAP_GPT}" -h', dockerfile)
        self.assertIn('UnsatisfiedLinkError', dockerfile)
        self.assertNotIn("SNAP_HOST_DIR", compose)
        self.assertNotIn("/opt/snap", compose)
        self.assertIn("/usr/local/snap/bin/gpt", compose)

    def test_digitising_service_is_headless_and_separate_from_snap(self) -> None:
        dockerfile = (REPO_ROOT / "docker" / "Dockerfile.digitising").read_text(encoding="utf-8")
        compose = (REPO_ROOT / "compose.yml").read_text(encoding="utf-8")

        self.assertIn("ARG QGIS_IMAGE=qgis/qgis:3.44.13-noble", dockerfile)
        self.assertIn("QT_QPA_PLATFORM=offscreen", dockerfile)
        self.assertIn('ENTRYPOINT ["python3", "-m", "digitising"]', dockerfile)
        requirements = (REPO_ROOT / "digitising-requirements.txt").read_text(encoding="utf-8")
        self.assertIn("h5py<4", requirements)
        self.assertIn("digitising:", compose)
        self.assertIn("read_only: true", compose)
        self.assertIn("/run/secrets", compose)


if __name__ == "__main__":
    unittest.main()
