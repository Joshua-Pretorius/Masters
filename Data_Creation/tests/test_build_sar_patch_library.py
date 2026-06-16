from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio as rio
import fiona
from rasterio.transform import from_origin
from shapely.geometry import mapping
from shapely.geometry import box


RASTERIO_ROOT = Path(rio.__file__).resolve().parent
os.environ["PROJ_LIB"] = str(RASTERIO_ROOT / "proj_data")
os.environ["GDAL_DATA"] = str(RASTERIO_ROOT / "gdal_data")


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "build_sar_patch_library.py"
SPEC = importlib.util.spec_from_file_location("build_sar_patch_library", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def write_raster(path: Path, data: np.ndarray, pixel_size: float = 1.0) -> None:
    profile = {
        "driver": "GTiff",
        "width": int(data.shape[1]),
        "height": int(data.shape[0]),
        "count": 1,
        "dtype": "float32",
        "crs": "EPSG:4326",
        "transform": from_origin(0.0, float(data.shape[0]) * pixel_size, pixel_size, pixel_size),
        "tiled": False,
        "nodata": None,
    }
    with rio.open(path, "w", **profile) as dst:
        dst.write(data.astype("float32"), 1)


def create_manifest_and_rasters(scene_dir: Path, manifest_path: Path) -> None:
    raster_names = {
        "vv": "scene_slc_native_vv.tif",
        "vh": "scene_slc_native_vh.tif",
        "vv_refined_lee_db": "scene_slc_utm_vv_refined_lee_db.tif",
        "vv_glcm_mean": "scene_slc_native_vv_glcm_mean.tif",
        "vv_glcm_std": "scene_slc_native_vv_glcm_std.tif",
        "vv_glcm_entropy": "scene_slc_native_vv_glcm_entropy.tif",
        "decomp_entropy": "scene_slc_native_decomp_entropy.tif",
        "decomp_anisotropy": "scene_slc_native_decomp_anisotropy.tif",
        "decomp_alpha": "scene_slc_native_decomp_alpha.tif",
    }
    outputs: dict[str, str] = {}
    base = np.ones((512, 512), dtype="float32")
    for index, (key, filename) in enumerate(raster_names.items(), start=1):
        raster_path = scene_dir / filename
        write_raster(raster_path, base * index, pixel_size=10.0)
        outputs[key] = str(raster_path)
    manifest_path.write_text(json.dumps({"scene_id": "Scene_001", "outputs": outputs}), encoding="utf-8")


def sample_feature_record() -> dict[str, object]:
    return {
        "geometry": mapping(box(1200.0, 1200.0, 1400.0, 1400.0)),
        "properties": {
            "patch_id": "patch-001",
            "obs_id": "obs-001",
            "area": "Test Area",
            "role": "after",
        },
    }


class DiscoveryAndLabelTests(unittest.TestCase):
    def test_discover_digitized_layers_finds_standard_and_case_variant_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            standard = root / "processed_slc" / "Scene_A" / "digitised_patches" / "scene_a_digitised_patches.shp"
            case_variant = root / "processed_slc" / "Scene_B" / "Digitised_patches" / "scene_b_digitised_patches.shp"
            standard.parent.mkdir(parents=True)
            case_variant.parent.mkdir(parents=True)
            for shp_path in (standard, case_variant):
                shp_path.write_bytes(b"")

            results = MODULE.discover_digitized_layers((root / "processed_slc",))

        self.assertEqual([item.shapefile_path for item in results], [standard, case_variant])

    def test_resolve_feature_class_defaults_standard_digitised_patches_to_plastic(self) -> None:
        source = MODULE.LayerSource(
            dataset="meria_sa",
            scene_id="MERIA_SA_001_Durban_after_20190425T031055",
            scene_dir=Path("D:/scene"),
            shapefile_path=Path("D:/scene/digitised_patches/sample_digitised_patches.shp"),
            layer_kind="digitised_patches",
        )

        raw_label, normalized = MODULE.resolve_feature_class(source, {"patch_id": "patch-01"})

        self.assertIsNone(raw_label)
        self.assertEqual(normalized, "plastic")

    def test_resolve_feature_class_reads_and_normalizes_explicit_class_field(self) -> None:
        source = MODULE.LayerSource(
            dataset="meria_global",
            scene_id="91ea9edc-67b4-4211-8532-35deec4a3148_Ghana_before_20181030T181758",
            scene_dir=Path("D:/scene"),
            shapefile_path=Path("D:/scene/digitised_patches/sample_digitised_other_features.shp"),
            layer_kind="digitised_other_features",
        )

        raw_label, normalized = MODULE.resolve_feature_class(source, {"Class": " Calm Water "})

        self.assertEqual(raw_label, " Calm Water ")
        self.assertEqual(normalized, "calm_water")


class RasterLookupAndWindowTests(unittest.TestCase):
    def test_build_scene_raster_map_reads_existing_outputs_and_derives_vh_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            scene_dir = Path(tmp_dir)
            manifest_path = scene_dir / "scene_slc_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "scene_id": "Scene_001",
                        "outputs": {
                            "vv": str(scene_dir / "scene_slc_native_vv.tif"),
                            "vh": str(scene_dir / "scene_slc_native_vh.tif"),
                            "vv_refined_lee_db": str(scene_dir / "scene_slc_utm_vv_refined_lee_db.tif"),
                            "vv_glcm_mean": str(scene_dir / "scene_slc_native_vv_glcm_mean.tif"),
                            "vv_glcm_std": str(scene_dir / "scene_slc_native_vv_glcm_std.tif"),
                            "vv_glcm_entropy": str(scene_dir / "scene_slc_native_vv_glcm_entropy.tif"),
                            "decomp_entropy": str(scene_dir / "scene_slc_native_decomp_entropy.tif"),
                            "decomp_anisotropy": str(scene_dir / "scene_slc_native_decomp_anisotropy.tif"),
                            "decomp_alpha": str(scene_dir / "scene_slc_native_decomp_alpha.tif"),
                        },
                    }
                ),
                encoding="utf-8",
            )

            raster_map = MODULE.build_scene_raster_map(manifest_path)

        self.assertEqual(raster_map["vv_db"].key, "vv_refined_lee_db")
        self.assertEqual(raster_map["vh_db"].key, "vh")
        self.assertEqual(raster_map["vv_glcm_mean"].key, "vv_glcm_mean")

    def test_build_scene_raster_map_falls_back_to_subswath_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            scene_dir = Path(tmp_dir)
            manifest_path = scene_dir / "scene_slc_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "scene_id": "Scene_002",
                        "outputs": {
                            "vv": None,
                            "vh": None,
                            "vv_refined_lee_db": None,
                            "vv_glcm_mean": None,
                            "vv_glcm_std": None,
                            "vv_glcm_entropy": None,
                            "decomp_entropy": None,
                            "decomp_anisotropy": None,
                            "decomp_alpha": None,
                        },
                        "subswath_outputs": {
                            "IW1": {
                                "vv": str(scene_dir / "iw1_vv.tif"),
                                "vh": str(scene_dir / "iw1_vh.tif"),
                                "vv_refined_lee_db": str(scene_dir / "iw1_vv_db.tif"),
                                "vv_glcm_mean": str(scene_dir / "iw1_glcm_mean.tif"),
                                "vv_glcm_std": str(scene_dir / "iw1_glcm_std.tif"),
                                "vv_glcm_entropy": str(scene_dir / "iw1_glcm_entropy.tif"),
                                "decomp_entropy": str(scene_dir / "iw1_decomp_entropy.tif"),
                                "decomp_anisotropy": str(scene_dir / "iw1_decomp_anisotropy.tif"),
                                "decomp_alpha": str(scene_dir / "iw1_decomp_alpha.tif"),
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            raster_map = MODULE.build_scene_raster_map(manifest_path)

        self.assertEqual(raster_map["vv_db"].path.name, "iw1_vv_db.tif")
        self.assertEqual(raster_map["vh_db"].path.name, "iw1_vh.tif")

    def test_build_scene_raster_map_falls_back_to_scene_tifs_when_manifest_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            scene_dir = Path(tmp_dir)
            manifest_path = scene_dir / "scene_slc_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "scene_id": "Scene_003",
                        "outputs": {
                            "vv": None,
                            "vh": None,
                            "vv_refined_lee_db": None,
                            "vv_glcm_mean": None,
                            "vv_glcm_std": None,
                            "vv_glcm_entropy": None,
                            "decomp_entropy": None,
                            "decomp_anisotropy": None,
                            "decomp_alpha": None,
                        }
                    }
                ),
                encoding="utf-8",
            )
            for filename in (
                "scene_slc_native_vv.tif",
                "scene_slc_native_vh.tif",
                "scene_slc_native_vv_refined_lee_db.tif",
                "scene_slc_native_vv_glcm_mean.tif",
                "scene_slc_native_vv_glcm_std.tif",
                "scene_slc_native_vv_glcm_entropy.tif",
                "scene_slc_native_decomp_entropy.tif",
                "scene_slc_native_decomp_anisotropy.tif",
                "scene_slc_native_decomp_alpha.tif",
            ):
                (scene_dir / filename).write_bytes(b"")

            raster_map = MODULE.build_scene_raster_map(manifest_path)

        self.assertEqual(raster_map["vv_db"].path.name, "scene_slc_native_vv_refined_lee_db.tif")
        self.assertEqual(raster_map["vh_db"].path.name, "scene_slc_native_vh.tif")

    def test_centroid_window_is_fixed_256_by_256_and_marks_edge_overlap(self) -> None:
        transform = from_origin(0.0, 5120.0, 10.0, 10.0)
        profile = {"width": 512, "height": 512, "transform": transform}

        window = MODULE.centroid_patch_window(profile, centroid_x=20.0, centroid_y=5000.0, patch_size=256)

        self.assertEqual(window.width, 256)
        self.assertEqual(window.height, 256)
        self.assertTrue(window.touches_edge)


class PatchExtractionTests(unittest.TestCase):
    def test_extract_patch_stack_pads_beyond_raster_bounds_with_nan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            raster_path = tmp / "vv_db.tif"
            write_raster(raster_path, np.arange(16, dtype="float32").reshape(4, 4), pixel_size=10.0)
            band = MODULE.RasterBandSpec(name="vv_db", key="vv_refined_lee_db", path=raster_path, mode="identity")
            profile = MODULE.load_reference_profile(raster_path)
            window = MODULE.PatchWindow(row_off=-1, col_off=-1, width=4, height=4, touches_edge=True)

            stack, out_profile = MODULE.extract_patch_stack({"vv_db": band}, profile, window)

        self.assertEqual(stack.shape, (1, 4, 4))
        self.assertTrue(np.isnan(stack[0, 0, 0]))
        self.assertEqual(out_profile["width"], 4)

    def test_rasterize_geometry_mask_aligns_with_patch_grid(self) -> None:
        profile = MODULE.patch_profile(from_origin(0.0, 40.0, 10.0, 10.0), width=4, height=4, count=1)
        geometry = {
            "type": "Polygon",
            "coordinates": [[(10.0, 30.0), (30.0, 30.0), (30.0, 10.0), (10.0, 10.0), (10.0, 30.0)]],
        }

        mask = MODULE.rasterize_feature_mask(geometry, profile)

        self.assertEqual(mask.shape, (4, 4))
        self.assertEqual(int(mask.sum()), 4)

    def test_compute_band_statistics_uses_labeled_pixels_only(self) -> None:
        stack = np.array([[[1.0, 2.0], [3.0, np.nan]]], dtype="float32")
        mask = np.array([[1, 0], [1, 0]], dtype="uint8")

        stats = MODULE.compute_band_statistics(stack, mask, ["vv_db"])

        self.assertEqual(stats["vv_db_valid_pixel_count"], 2)
        self.assertAlmostEqual(stats["vv_db_mean"], 2.0)
        self.assertAlmostEqual(stats["vv_db_min"], 1.0)
        self.assertAlmostEqual(stats["vv_db_max"], 3.0)


class EndToEndExtractionTests(unittest.TestCase):
    def test_process_feature_writes_image_mask_and_library_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            patches_dir = tmp / "Patches"
            library_dir = tmp / "Library"
            scene_dir = tmp / "scene"
            manifest_path = scene_dir / "scene_slc_manifest.json"
            scene_dir.mkdir(parents=True)
            create_manifest_and_rasters(scene_dir, manifest_path)

            source = MODULE.LayerSource(
                dataset="meria_global",
                scene_id="Scene_001",
                scene_dir=scene_dir,
                shapefile_path=scene_dir / "digitised_patches" / "scene_digitised_patches.shp",
                layer_kind="digitised_patches",
            )
            feature = sample_feature_record()

            inventory_row, library_row = MODULE.process_feature(
                source=source,
                feature=feature,
                manifest_path=manifest_path,
                patches_root=patches_dir,
                library_root=library_dir,
                patch_size=256,
            )

            self.assertEqual(inventory_row["normalized_class_label"], "plastic")
            self.assertTrue(Path(inventory_row["image_path"]).exists())
            self.assertTrue(Path(inventory_row["mask_path"]).exists())
            self.assertIn("vv_db_mean", library_row)


class FeatureReaderTests(unittest.TestCase):
    def test_iter_source_features_reads_shapefile_without_geopandas(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            shp_path = tmp / "digitised_patches.shp"
            schema = {"geometry": "Polygon", "properties": {"patch_id": "str:32", "Class": "str:32"}}
            with fiona.open(
                shp_path,
                "w",
                driver="ESRI Shapefile",
                schema=schema,
                crs="EPSG:4326",
            ) as sink:
                sink.write(
                    {
                        "geometry": mapping(box(0.0, 0.0, 1.0, 1.0)),
                        "properties": {"patch_id": "patch-001", "Class": "Ship"},
                    }
                )

            features = list(MODULE.iter_source_features(shp_path))

        self.assertEqual(len(features), 1)
        self.assertEqual(features[0]["properties"]["patch_id"], "patch-001")
        self.assertEqual(features[0]["properties"]["Class"], "Ship")


class CommandLineTests(unittest.TestCase):
    def test_parse_args_uses_data_creation_patch_and_library_defaults(self) -> None:
        original_argv = sys.argv[:]
        try:
            sys.argv = ["build_sar_patch_library.py"]
            args = MODULE.parse_args()
        finally:
            sys.argv = original_argv

        self.assertEqual(args.patch_size, 256)
        self.assertEqual(args.patches_root, MODULE.REPO_ROOT / "Data_Creation" / "Patches")
        self.assertEqual(args.library_root, MODULE.REPO_ROOT / "Data_Creation" / "Library")


if __name__ == "__main__":
    unittest.main()
