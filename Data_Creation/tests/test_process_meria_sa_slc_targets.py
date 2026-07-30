from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import rasterio as rio
from rasterio.transform import from_origin


RASTERIO_ROOT = Path(rio.__file__).resolve().parent
os.environ["PROJ_LIB"] = str(RASTERIO_ROOT / "proj_data")
os.environ["GDAL_DATA"] = str(RASTERIO_ROOT / "gdal_data")


PROCESS_DRIFT_SLC_STUB = types.ModuleType("process_drift_slc")
PROCESS_DRIFT_SLC_STUB.cleanup_dim_product = lambda *args, **kwargs: None
PROCESS_DRIFT_SLC_STUB.edl_auth = lambda *args, **kwargs: ("", "")
PROCESS_DRIFT_SLC_STUB.find_gpt = lambda *args, **kwargs: None
PROCESS_DRIFT_SLC_STUB.polarizations_for_granule = lambda *args, **kwargs: ["VV", "VH"]
PROCESS_DRIFT_SLC_STUB.setup_logging = lambda *args, **kwargs: None
PROCESS_DRIFT_SLC_STUB.unzip_safe = lambda *args, **kwargs: None
sys.modules.setdefault("process_drift_slc", PROCESS_DRIFT_SLC_STUB)

SNAP_UTILS_STUB = types.ModuleType("snap_utils")
SNAP_UTILS_STUB.export_to_geotiff = lambda *args, **kwargs: None
SNAP_UTILS_STUB.graph_has_operator = lambda *args, **kwargs: False
SNAP_UTILS_STUB.patch_graph_io = lambda *args, **kwargs: None
SNAP_UTILS_STUB.patch_graph_params = lambda *args, **kwargs: None
SNAP_UTILS_STUB.run_graph = lambda *args, **kwargs: None
SNAP_UTILS_STUB.uses_windows_paths = lambda *args, **kwargs: False
sys.modules.setdefault("snap_utils", SNAP_UTILS_STUB)


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "process_sa_slc_targets.py"
SPEC = importlib.util.spec_from_file_location("process_sa_slc_targets", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def write_raster(path: Path, data: np.ndarray) -> None:
    profile = {
        "driver": "GTiff",
        "width": int(data.shape[1]),
        "height": int(data.shape[0]),
        "count": 1,
        "dtype": "float32",
        "crs": "EPSG:4326",
        "transform": from_origin(0, float(data.shape[0]), 1.0, 1.0),
        "tiled": False,
        "nodata": None,
    }
    with rio.open(path, "w", **profile) as dst:
        dst.write(data.astype("float32"), 1)


def write_multiband_raster(path: Path, count: int) -> None:
    profile = {
        "driver": "GTiff",
        "width": 2,
        "height": 2,
        "count": count,
        "dtype": "float32",
        "crs": "EPSG:4326",
        "transform": from_origin(0, 2, 1.0, 1.0),
        "tiled": False,
        "nodata": None,
    }
    with rio.open(path, "w", **profile) as dst:
        for band in range(1, count + 1):
            dst.write(np.full((2, 2), float(band), dtype="float32"), band)


def load_module(script_path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class CompatibilityEntrypointTests(unittest.TestCase):
    def test_neutral_sa_entrypoint_exists_and_exposes_main(self) -> None:
        script_path = Path(__file__).resolve().parents[1] / "process_sa_slc_targets.py"
        module_name = "process_sa_slc_targets_entrypoint_test"

        try:
            module = load_module(script_path, module_name)
            self.assertTrue(callable(module.main))
            self.assertTrue(callable(module.resolve_graphs_dir))
        finally:
            sys.modules.pop(module_name, None)

    def test_legacy_sa_entrypoint_delegates_to_neutral_main(self) -> None:
        neutral = types.ModuleType("process_sa_slc_targets")
        calls: list[str] = []
        neutral.main = lambda: calls.append("called")

        script_path = Path(__file__).resolve().parents[1] / "process_meria_sa_slc_targets.py"
        module_name = "legacy_meria_sa_entrypoint_test"
        original = sys.modules.get("process_sa_slc_targets")
        sys.modules["process_sa_slc_targets"] = neutral

        try:
            module = load_module(script_path, module_name)
            module.main()
        finally:
            sys.modules.pop(module_name, None)
            if original is None:
                sys.modules.pop("process_sa_slc_targets", None)
            else:
                sys.modules["process_sa_slc_targets"] = original

        self.assertEqual(calls, ["called"])


class SceneMosaicSupportMaskTests(unittest.TestCase):
    def test_resolve_graphs_dir_prefers_sar_pp_graphs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            (repo_root / "SAR_PP" / "graphs").mkdir(parents=True)
            (repo_root / "sar_ml_pipeline" / "graphs").mkdir(parents=True)

            resolved = MODULE.resolve_graphs_dir(repo_root)

        self.assertEqual(resolved, repo_root / "SAR_PP" / "graphs")

    def test_resolve_graphs_dir_falls_back_to_legacy_locations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            (repo_root / "sar_ml_pipeline_legacy" / "graphs").mkdir(parents=True)

            resolved = MODULE.resolve_graphs_dir(repo_root)

        self.assertEqual(resolved, repo_root / "sar_ml_pipeline_legacy" / "graphs")

    def test_parse_args_defaults_to_resolved_graphs_dir(self) -> None:
        graphs_dir = Path("D:/Masters/SAR_PP/graphs")

        with (
            mock.patch.object(MODULE, "resolve_graphs_dir", return_value=graphs_dir),
            mock.patch.object(sys, "argv", ["process_sa_slc_targets.py"]),
        ):
            args = MODULE.parse_args()

        self.assertEqual(Path(args.graphs_dir), graphs_dir)

    def test_load_matches_reads_role_specific_download_group_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            match_csv = Path(tmp_dir) / "matches.csv"
            match_csv.write_text(
                "\n".join(
                    [
                        "obs_id,area,date,before_name,before_start,before_delta_h,before_download_group_key,after_name,after_start,after_delta_h,after_download_group_key",
                        "MERIA_SA_999,Test Area,2024-06-01,before.safe,2024-06-01 00:00:00 UTC,-4.0,before-group,after.safe,2024-06-02 00:00:00 UTC,+20.0,after-group",
                    ]
                ),
                encoding="utf-8",
            )

            with mock.patch.object(MODULE, "MATCH_CSV", match_csv):
                rows = MODULE.load_matches({("MERIA_SA_999", "before"), ("MERIA_SA_999", "after")})

        before = next(item for item in rows if item.role == "before")
        after = next(item for item in rows if item.role == "after")
        self.assertEqual(before.download_group_key, "before-group")
        self.assertEqual(after.download_group_key, "after-group")

    def test_download_only_reuses_shared_zip_for_same_download_group(self) -> None:
        target1 = MODULE.Target(
            obs_id="MERIA_SA_999",
            area="Test Area",
            role="before",
            obs_date="2024-06-01",
            granule_safe="S1A_IW_SLC__1SDV_20240601T000000_20240601T000027_054321_069999_1234.SAFE",
            acquisition_start="2024-06-01T00:00:00Z",
            delta_h="0.0",
            download_group_key="shared-granule",
        )
        target2 = MODULE.Target(
            obs_id="MERIA_SA_998",
            area="Nearby Area",
            role="before",
            obs_date="2024-06-01",
            granule_safe="S1A_IW_SLC__1SDV_20240601T000000_20240601T000027_054321_069999_1234.SAFE",
            acquisition_start="2024-06-01T00:00:00Z",
            delta_h="0.0",
            download_group_key="shared-granule",
        )

        def fake_download(_url: str, out_path: Path, _auth: tuple[str, str]) -> None:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(b"zip-data")

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            out_root = tmp / "out"
            work_root = tmp / "work"
            data_dir = tmp / "data"
            with (
                mock.patch.object(MODULE, "DATA_DIR", data_dir),
                mock.patch.object(MODULE, "polarizations_for_granule", return_value=["VV"]),
                mock.patch.object(MODULE, "expected_product_keys", return_value=set()),
                mock.patch.object(MODULE, "target_bounds_wgs84", return_value=(0.0, 0.0, 1.0, 1.0)),
                mock.patch.object(MODULE, "needs_reference_grid", return_value=False),
                mock.patch.object(MODULE, "outputs_complete", return_value=False),
                mock.patch.object(MODULE, "processing_metadata", return_value={}),
                mock.patch.object(MODULE, "stream_download_asf", side_effect=fake_download) as download_mock,
            ):
                for target in (target1, target2):
                    MODULE.process_target(
                        target=target,
                        auth=("user", "pass"),
                        out_root=out_root,
                        work_root=work_root,
                        graphs=None,
                        gpt=None,
                        requested_subswaths=("IW1",),
                        output_mode="scene",
                        subset_mode="aoi",
                        resolution_policy="snap-native",
                        resolution_m=10.0,
                        pad_deg=0.25,
                        cache_gb=8,
                        workers=1,
                        download_only=True,
                        prepare_only=False,
                        keep_zip=True,
                        keep_safe=False,
                        force=False,
                    )

        self.assertEqual(download_mock.call_count, 1)

    def test_default_pad_deg_is_tight_standardized_value(self) -> None:
        with mock.patch.object(sys, "argv", ["process_sa_slc_targets.py"]):
            args = MODULE.parse_args()
        self.assertEqual(args.pad_deg, 0.25)
        self.assertEqual(args.subset_mode, "aoi")

    def test_subset_mode_accepts_full_swath(self) -> None:
        with mock.patch.object(sys, "argv", ["process_sa_slc_targets.py", "--subset-mode", "full-swath"]):
            args = MODULE.parse_args()
        self.assertEqual(args.subset_mode, "full-swath")

    def test_raster_band_indexes_infers_dual_pol_sigma0_order_without_descriptions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "IW1_sigma0_tc.tif"
            write_multiband_raster(path, count=2)
            self.assertEqual(MODULE.raster_band_indexes(path), {"sigma0vh": 1, "sigma0vv": 2})

    def test_raster_band_indexes_infers_texture_order_without_descriptions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "IW1_tex_tc.tif"
            write_multiband_raster(path, count=20)
            band_map = MODULE.raster_band_indexes(path)
        self.assertEqual(band_map["sigma0vventropy"], 17)
        self.assertEqual(band_map["sigma0vvglcmmean"], 18)
        self.assertEqual(band_map["sigma0vvglcmvariance"], 19)

    def test_raster_band_indexes_infers_decomp_order_without_descriptions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "IW1_decomp_tc.tif"
            write_multiband_raster(path, count=3)
            self.assertEqual(MODULE.raster_band_indexes(path), {"entropy": 1, "anisotropy": 2, "alpha": 3})

    def test_filtered_db_product_uses_full_scene_native_path(self) -> None:
        target = MODULE.Target(
            obs_id="MERIA_SA_999",
            area="Test Area",
            role="after",
            obs_date="2024-06-01",
            granule_safe="S1A_IW_SLC__1SDV_20240601T000000_20240601T000027_054321_069999_1234.SAFE",
            acquisition_start="2024-06-01T00:00:00Z",
            delta_h="0.0",
        )
        paths = MODULE.product_output_paths(target, Path("D:/tmp/out"), "snap-native")
        self.assertTrue(str(paths["vv"]).endswith("_slc_native_vv.tif"))
        self.assertTrue(str(paths["vv_refined_lee_db"]).endswith("_slc_native_vv_refined_lee_db.tif"))

    def test_folder_key_defaults_to_obs_first(self) -> None:
        target = MODULE.Target(
            obs_id="MERIA_SA_999",
            area="Test Area",
            role="after",
            obs_date="2024-06-01",
            granule_safe="S1A_IW_SLC__1SDV_20240601T000000_20240601T000027_054321_069999_1234.SAFE",
            acquisition_start="2024-06-01T00:00:00Z",
            delta_h="0.0",
        )
        self.assertEqual(target.folder_key, "MERIA_SA_999_Test_Area")

    def test_folder_key_can_prefix_area_name(self) -> None:
        target = MODULE.Target(
            obs_id="abc123",
            area="Palma de Mallorca",
            role="before",
            obs_date="2024-06-01",
            granule_safe="S1A_IW_SLC__1SDV_20240601T000000_20240601T000027_054321_069999_1234.SAFE",
            acquisition_start="2024-06-01T00:00:00Z",
            delta_h="0.0",
        )
        with mock.patch.object(MODULE, "FOLDER_NAME_STYLE", "area-first"):
            self.assertEqual(target.folder_key, "Palma_de_Mallorca_abc123")

    def test_glcm_mosaic_ignores_zero_background_from_first_swath(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            sigma0_1 = tmp / "iw1_sigma0.tif"
            sigma0_2 = tmp / "iw2_sigma0.tif"
            tex_1 = tmp / "iw1_tex.tif"
            tex_2 = tmp / "iw2_tex.tif"
            out_path = tmp / "mosaic_glcm_mean.tif"

            write_raster(sigma0_1, np.array([[1, 1, 0, 0]], dtype="float32"))
            write_raster(sigma0_2, np.array([[0, 0, 1, 1]], dtype="float32"))
            write_raster(tex_1, np.array([[5, 6, 0, 0]], dtype="float32"))
            write_raster(tex_2, np.array([[0, 0, 7, 8]], dtype="float32"))

            final_profile = MODULE.final_raster_profile(
                {
                    "driver": "GTiff",
                    "width": 4,
                    "height": 1,
                    "crs": "EPSG:4326",
                    "transform": from_origin(0, 1, 1.0, 1.0),
                }
            )
            spec = next(item for item in MODULE.PRODUCT_SPECS if item.key == "vv_glcm_mean")
            MODULE.write_mosaic_product(
                final_profile=final_profile,
                sources=[(tex_1, 1), (tex_2, 1)],
                out_path=out_path,
                spec=spec,
                support_sources=[(sigma0_1, 1), (sigma0_2, 1)],
            )

            with rio.open(out_path) as ds:
                arr = ds.read(1)

            np.testing.assert_array_equal(arr, np.array([[5, 6, 7, 8]], dtype="float32"))

    def test_decomp_mosaic_ignores_zero_background_from_first_swath(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            sigma0_1 = tmp / "iw1_sigma0.tif"
            sigma0_2 = tmp / "iw2_sigma0.tif"
            decomp_1 = tmp / "iw1_decomp.tif"
            decomp_2 = tmp / "iw2_decomp.tif"
            out_path = tmp / "mosaic_decomp_entropy.tif"

            write_raster(sigma0_1, np.array([[1, 1, 0, 0]], dtype="float32"))
            write_raster(sigma0_2, np.array([[0, 0, 1, 1]], dtype="float32"))
            write_raster(decomp_1, np.array([[0.3, 0.4, 0.0, 0.0]], dtype="float32"))
            write_raster(decomp_2, np.array([[0.0, 0.0, 0.6, 0.7]], dtype="float32"))

            final_profile = MODULE.final_raster_profile(
                {
                    "driver": "GTiff",
                    "width": 4,
                    "height": 1,
                    "crs": "EPSG:4326",
                    "transform": from_origin(0, 1, 1.0, 1.0),
                }
            )
            spec = next(item for item in MODULE.PRODUCT_SPECS if item.key == "decomp_entropy")
            MODULE.write_mosaic_product(
                final_profile=final_profile,
                sources=[(decomp_1, 1), (decomp_2, 1)],
                out_path=out_path,
                spec=spec,
                support_sources=[(sigma0_1, 1), (sigma0_2, 1)],
            )

            with rio.open(out_path) as ds:
                arr = ds.read(1)

            np.testing.assert_array_equal(arr, np.array([[0.3, 0.4, 0.6, 0.7]], dtype="float32"))

    def test_db_mosaic_converts_positive_values_and_masks_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            sigma0 = tmp / "iw1_sigma0.tif"
            filtered = tmp / "iw1_filtered.tif"
            out_path = tmp / "mosaic_vv_refined_lee_db.tif"

            write_raster(sigma0, np.array([[1.0, 10.0, 0.0]], dtype="float32"))
            write_raster(filtered, np.array([[1.0, 10.0, 0.0]], dtype="float32"))

            final_profile = MODULE.final_raster_profile(
                {
                    "driver": "GTiff",
                    "width": 3,
                    "height": 1,
                    "crs": "EPSG:4326",
                    "transform": from_origin(0, 1, 1.0, 1.0),
                }
            )
            spec = next(item for item in MODULE.PRODUCT_SPECS if item.key == "vv_refined_lee_db")
            MODULE.write_mosaic_product(
                final_profile=final_profile,
                sources=[(filtered, 1)],
                out_path=out_path,
                spec=spec,
                support_sources=[(sigma0, 1)],
            )

            with rio.open(out_path) as ds:
                arr = ds.read(1)

            self.assertAlmostEqual(float(arr[0, 0]), 0.0, places=5)
            self.assertAlmostEqual(float(arr[0, 1]), 10.0, places=5)
            self.assertTrue(np.isnan(arr[0, 2]))

    def test_full_swath_subswath_run_skips_subset_graphs(self) -> None:
        graphs = {
            "split": Path("01_split.xml"),
            "orbit": Path("02_orbit_apply.xml"),
            "calibration": Path("03_calibration.xml"),
            "deburst": Path("04_deburst.xml"),
            "subset": Path("05_subset.xml"),
            "c2": Path("06_polarimetric_matrix.xml"),
            "speckle": Path("07_speckle_filter.xml"),
            "terrain": Path("08_terrain_correction.xml"),
            "decomp": Path("09_polarimetric_decomposition.xml"),
            "texture": Path("10_feature_extraction.xml"),
        }
        graph_calls: list[str] = []

        def record_graph_call(*args, **kwargs):
            graph_calls.append(args[1].name)

        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = Path(tmp_dir) / "IW1"
            with (
                mock.patch.object(MODULE, "run_graph_with_io", side_effect=record_graph_call),
                mock.patch.object(MODULE, "cleanup_dim_product"),
                mock.patch.object(MODULE, "dim_band_indexes", return_value={"vv": 1, "vh": 2}),
                mock.patch.object(MODULE, "export_to_geotiff"),
                mock.patch.object(MODULE, "graph_has_operator", return_value=True),
            ):
                result = MODULE.run_enhanced_subswath(
                    gpt="gpt",
                    graphs=graphs,
                    slc_input=Path("input.SAFE"),
                    work_dir=work_dir,
                    subswath="IW1",
                    selected_pols=["VV", "VH"],
                    aoi_wkt="POLYGON((0 0,1 0,1 1,0 1,0 0))",
                    subset_mode="full-swath",
                    cache_gb=8,
                    workers=1,
                )

        self.assertIsNotNone(result)
        self.assertNotIn("05_subset.xml", graph_calls)

    def test_run_enhanced_subswath_reuses_completed_outputs(self) -> None:
        graphs = {
            "split": Path("01_split.xml"),
            "orbit": Path("02_orbit_apply.xml"),
            "calibration": Path("03_calibration.xml"),
            "deburst": Path("04_deburst.xml"),
            "subset": Path("05_subset.xml"),
            "c2": Path("06_polarimetric_matrix.xml"),
            "speckle": Path("07_speckle_filter.xml"),
            "terrain": Path("08_terrain_correction.xml"),
            "decomp": Path("09_polarimetric_decomposition.xml"),
            "texture": Path("10_feature_extraction.xml"),
        }

        def fake_band_indexes(path: Path) -> dict[str, int]:
            if path.name.endswith("sigma0_tc.tif"):
                return {"sigma0vv": 1, "sigma0vh": 2}
            if path.name.endswith("filtered_tc.tif"):
                return {"sigma0vv": 1, "sigma0vh": 2}
            if path.name.endswith("tex_tc.tif"):
                return {"sigma0vvglcmmean": 1, "sigma0vvglcmvariance": 2, "sigma0vventropy": 3}
            if path.name.endswith("decomp_tc.tif"):
                return {"entropy": 1, "anisotropy": 2, "alpha": 3}
            raise AssertionError(path)

        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = Path(tmp_dir) / "IW1"
            work_dir.mkdir(parents=True, exist_ok=True)
            for name in ("IW1_sigma0_tc.tif", "IW1_filtered_tc.tif", "IW1_tex_tc.tif", "IW1_decomp_tc.tif"):
                (work_dir / name).write_bytes(b"ready")

            with (
                mock.patch.object(MODULE, "load_band_indexes", side_effect=fake_band_indexes),
                mock.patch.object(MODULE, "run_graph_with_io") as run_graph_mock,
                mock.patch.object(MODULE, "export_to_geotiff") as export_mock,
                mock.patch.object(MODULE, "cleanup_dim_product") as cleanup_mock,
            ):
                result = MODULE.run_enhanced_subswath(
                    gpt="gpt",
                    graphs=graphs,
                    slc_input=Path("input.SAFE"),
                    work_dir=work_dir,
                    subswath="IW1",
                    selected_pols=["VV", "VH"],
                    aoi_wkt="POLYGON((0 0,1 0,1 1,0 1,0 0))",
                    subset_mode="aoi",
                    cache_gb=8,
                    workers=1,
                )

        self.assertIsNotNone(result)
        self.assertEqual(result.paths["sigma0"].name, "IW1_sigma0_tc.tif")
        self.assertEqual(result.paths["filtered"].name, "IW1_filtered_tc.tif")
        self.assertEqual(result.paths["texture"].name, "IW1_tex_tc.tif")
        self.assertEqual(result.paths["decomp"].name, "IW1_decomp_tc.tif")
        self.assertEqual(result.bands["sigma0"], {"sigma0vv": 1, "sigma0vh": 2})
        run_graph_mock.assert_not_called()
        export_mock.assert_not_called()
        cleanup_mock.assert_not_called()

    def test_run_enhanced_subswath_resumes_from_texture_tc_and_orbit(self) -> None:
        graphs = {
            "split": Path("01_split.xml"),
            "orbit": Path("02_orbit_apply.xml"),
            "calibration": Path("03_calibration.xml"),
            "deburst": Path("04_deburst.xml"),
            "subset": Path("05_subset.xml"),
            "c2": Path("06_polarimetric_matrix.xml"),
            "speckle": Path("07_speckle_filter.xml"),
            "terrain": Path("08_terrain_correction.xml"),
            "decomp": Path("09_polarimetric_decomposition.xml"),
            "texture": Path("10_feature_extraction.xml"),
        }
        graph_calls: list[str] = []
        export_calls: list[str] = []

        def make_snap_product(path: Path) -> None:
            path.write_text("dim", encoding="utf-8")
            path.with_suffix(".data").mkdir(parents=True, exist_ok=True)

        def fake_band_indexes(path: Path) -> dict[str, int]:
            if path.name.endswith("sigma0_tc.tif"):
                return {"sigma0vv": 1, "sigma0vh": 2}
            if path.name.endswith("filtered_tc.tif"):
                return {"sigma0vv": 1, "sigma0vh": 2}
            if path.name.endswith("orbit.dim"):
                return {"orbitvv": 1, "orbitvh": 2}
            if path.name.endswith("tex_tc.dim") or path.name.endswith("tex_tc.tif"):
                return {"sigma0vvglcmmean": 1, "sigma0vvglcmvariance": 2, "sigma0vventropy": 3}
            if path.name.endswith("c2.dim") or path.name.endswith("c2_subset.dim"):
                return {"c211": 1, "c212": 2, "c222": 3}
            if path.name.endswith("decomp.dim"):
                return {"entropy": 1, "anisotropy": 2, "alpha": 3}
            if path.name.endswith("decomp_tc.dim") or path.name.endswith("decomp_tc.tif"):
                return {"entropy": 1, "anisotropy": 2, "alpha": 3}
            raise AssertionError(path)

        def fake_run_graph_with_io(_gpt, graph, _src, dst, *_args, **_kwargs):
            graph_calls.append(graph.name)
            make_snap_product(dst)

        def fake_export_to_geotiff(_gpt, in_path, out_path, **_kwargs):
            export_calls.append(in_path.name)
            out_path.write_bytes(b"tif")

        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = Path(tmp_dir) / "IW3"
            work_dir.mkdir(parents=True, exist_ok=True)
            (work_dir / "IW3_sigma0_tc.tif").write_bytes(b"sigma0")
            (work_dir / "IW3_filtered_tc.tif").write_bytes(b"filtered")
            make_snap_product(work_dir / "IW3_orbit.dim")
            make_snap_product(work_dir / "IW3_tex_tc.dim")

            with (
                mock.patch.object(MODULE, "load_band_indexes", side_effect=fake_band_indexes),
                mock.patch.object(MODULE, "run_graph_with_io", side_effect=fake_run_graph_with_io),
                mock.patch.object(MODULE, "export_to_geotiff", side_effect=fake_export_to_geotiff),
                mock.patch.object(MODULE, "cleanup_dim_product"),
                mock.patch.object(MODULE, "graph_has_operator", return_value=True),
            ):
                result = MODULE.run_enhanced_subswath(
                    gpt="gpt",
                    graphs=graphs,
                    slc_input=Path("input.SAFE"),
                    work_dir=work_dir,
                    subswath="IW3",
                    selected_pols=["VV", "VH"],
                    aoi_wkt="POLYGON((0 0,1 0,1 1,0 1,0 0))",
                    subset_mode="aoi",
                    cache_gb=8,
                    workers=1,
                )

        self.assertIsNotNone(result)
        self.assertEqual(graph_calls, ["06_polarimetric_matrix.xml", "05_subset.xml", "09_polarimetric_decomposition.xml", "08_terrain_correction.xml"])
        self.assertEqual(export_calls, ["IW3_tex_tc.dim", "IW3_decomp_tc.dim"])
        self.assertEqual(result.paths["texture"].name, "IW3_tex_tc.tif")
        self.assertEqual(result.paths["decomp"].name, "IW3_decomp_tc.tif")

    def test_native_scene_profile_uses_source_union_for_full_swath_scene(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            left = tmp / "left.tif"
            right = tmp / "right.tif"

            profile = {
                "driver": "GTiff",
                "width": 2,
                "height": 2,
                "count": 1,
                "dtype": "float32",
                "crs": "EPSG:4326",
                "tiled": False,
                "nodata": None,
            }
            with rio.open(left, "w", **(profile | {"transform": from_origin(0, 2, 1.0, 1.0)})) as dst:
                dst.write(np.ones((1, 2, 2), dtype="float32"))
            with rio.open(right, "w", **(profile | {"transform": from_origin(2, 2, 1.0, 1.0)})) as dst:
                dst.write(np.ones((1, 2, 2), dtype="float32"))

            result = MODULE.native_scene_profile(
                aoi_bounds_wgs84=(0.0, 0.0, 0.5, 0.5),
                source_paths=[left, right],
                use_source_bounds=True,
            )

        self.assertEqual(result["width"], 4)
        self.assertEqual(result["height"], 2)
        self.assertEqual(tuple(result["transform"])[:6], (1.0, 0.0, 0.0, 0.0, -1.0, 2.0))


if __name__ == "__main__":
    unittest.main()
