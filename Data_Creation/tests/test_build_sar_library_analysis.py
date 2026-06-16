from __future__ import annotations

import importlib.util
import csv
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio as rio
from rasterio.transform import from_origin


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "build_sar_library_analysis.py"
SPEC = importlib.util.spec_from_file_location("build_sar_library_analysis", SCRIPT_PATH)
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
        "transform": from_origin(0.0, float(data.shape[0]), 1.0, 1.0),
        "tiled": False,
        "nodata": None,
    }
    with rio.open(path, "w", **profile) as dst:
        dst.write(data.astype("float32"), 1)


def create_analysis_fixture(library_csv: Path, inventory_csv: Path, patches_root: Path) -> None:
    patches_root.mkdir(parents=True, exist_ok=True)
    patch_dir = patches_root / "meria_global" / "before_20181030T181758" / "plastic"
    patch_dir.mkdir(parents=True, exist_ok=True)
    plastic_patch = patch_dir / "before_20181030T181758_1_image.tif"
    ship_patch = patches_root / "meria_global" / "before_20181030T181758" / "ship" / "before_20181030T181758_2_image.tif"
    ship_patch.parent.mkdir(parents=True, exist_ok=True)
    write_raster(plastic_patch, np.array([[1, 2], [3, 4]], dtype="float32"))
    write_raster(ship_patch, np.array([[4, 3], [2, 1]], dtype="float32"))
    headers = [
        "scene_id",
        "normalized_class_label",
        "extraction_status",
        "image_path",
        "sample_id",
        "vv_db_mean",
        "vh_db_mean",
        "vv_vh_ratio_db_mean",
        "vv_glcm_mean_mean",
        "vv_glcm_entropy_mean",
        "decomp_entropy_mean",
        "decomp_alpha_mean",
    ]
    rows = [
        {
            "scene_id": "before_20181030T181758",
            "normalized_class_label": "plastic",
            "extraction_status": "ok",
            "image_path": str(plastic_patch),
            "sample_id": "before_20181030T181758_1",
            "vv_db_mean": "1.0",
            "vh_db_mean": "0.5",
            "vv_vh_ratio_db_mean": "0.5",
            "vv_glcm_mean_mean": "2.0",
            "vv_glcm_entropy_mean": "3.0",
            "decomp_entropy_mean": "0.3",
            "decomp_alpha_mean": "0.4",
        },
        {
            "scene_id": "before_20181030T181758",
            "normalized_class_label": "ship",
            "extraction_status": "ok",
            "image_path": str(ship_patch),
            "sample_id": "before_20181030T181758_2",
            "vv_db_mean": "4.0",
            "vh_db_mean": "2.0",
            "vv_vh_ratio_db_mean": "2.0",
            "vv_glcm_mean_mean": "4.0",
            "vv_glcm_entropy_mean": "1.0",
            "decomp_entropy_mean": "0.8",
            "decomp_alpha_mean": "0.9",
        },
    ]
    with library_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    with inventory_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sample_id", "image_path"])
        writer.writeheader()
        for row in rows:
            writer.writerow({"sample_id": row["sample_id"], "image_path": row["image_path"]})


class LibraryFilteringTests(unittest.TestCase):
    def test_load_library_rows_reads_csv_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "library.csv"
            csv_path.write_text(
                "\n".join(
                    [
                        "scene_id,normalized_class_label,extraction_status,vv_db_mean,vh_db_mean,image_path",
                        "before_20181030T181758,plastic,ok,1.5,0.5,D:/patch1.tif",
                        "before_20181030T181758,ship,ok,2.0,0.7,D:/patch2.tif",
                    ]
                ),
                encoding="utf-8",
            )

            rows = MODULE.load_library_rows(csv_path)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["normalized_class_label"], "plastic")

    def test_filter_valid_plastic_rows_keeps_only_ok_rows_with_numeric_features(self) -> None:
        rows = [
            {"normalized_class_label": "plastic", "extraction_status": "ok", "vv_db_mean": "1.2", "vh_db_mean": "0.3"},
            {"normalized_class_label": "plastic", "extraction_status": "ok", "vv_db_mean": "nan", "vh_db_mean": "0.4"},
            {"normalized_class_label": "ship", "extraction_status": "ok", "vv_db_mean": "1.4", "vh_db_mean": "0.5"},
        ]

        filtered = MODULE.filter_valid_plastic_rows(rows, ["vv_db_mean", "vh_db_mean"])

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["normalized_class_label"], "plastic")

    def test_filter_valid_ghana_rows_keeps_expected_classes_only(self) -> None:
        rows = [
            {"scene_id": "before_20181030T181758", "normalized_class_label": "plastic", "extraction_status": "ok", "vv_db_mean": "1.0"},
            {"scene_id": "before_20181030T181758", "normalized_class_label": "ship", "extraction_status": "ok", "vv_db_mean": "2.0"},
            {"scene_id": "before_20181012T054431", "normalized_class_label": "plastic", "extraction_status": "ok", "vv_db_mean": "3.0"},
        ]

        filtered = MODULE.filter_valid_ghana_rows(rows, ["vv_db_mean"])

        self.assertEqual(len(filtered), 2)
        self.assertEqual({row["normalized_class_label"] for row in filtered}, {"plastic", "ship"})


class FeatureRankingTests(unittest.TestCase):
    def test_build_plastic_vs_other_labels_marks_plastic_as_one(self) -> None:
        rows = [
            {"normalized_class_label": "plastic"},
            {"normalized_class_label": "ship"},
            {"normalized_class_label": "wake"},
        ]

        labels = MODULE.build_plastic_vs_other_labels(rows)

        np.testing.assert_array_equal(labels, np.array([1, 0, 0], dtype="int32"))

    def test_compute_effect_size_ranking_orders_more_separable_feature_first(self) -> None:
        matrix = np.array(
            [
                [10.0, 1.0],
                [11.0, 1.1],
                [2.0, 1.2],
                [3.0, 1.1],
            ],
            dtype="float32",
        )
        labels = np.array([1, 1, 0, 0], dtype="int32")
        feature_names = ["strong_feature", "weak_feature"]

        ranking = MODULE.compute_effect_size_ranking(matrix, labels, feature_names)

        self.assertEqual(ranking[0]["feature_name"], "strong_feature")
        self.assertGreater(ranking[0]["effect_size"], ranking[1]["effect_size"])


class OutputGenerationTests(unittest.TestCase):
    def test_write_feature_importance_csv_creates_expected_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir) / "importance.csv"
            ranking = [
                {"feature_name": "vv_db_mean", "effect_size": 1.5},
                {"feature_name": "vh_db_mean", "effect_size": 0.5},
            ]

            MODULE.write_feature_importance_csv(out_path, ranking)

            text = out_path.read_text(encoding="utf-8")

        self.assertIn("feature_name,effect_size", text)
        self.assertIn("vv_db_mean", text)

    def test_plot_class_counts_creates_png(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir) / "class_counts.png"
            rows = [
                {"normalized_class_label": "plastic"},
                {"normalized_class_label": "plastic"},
                {"normalized_class_label": "ship"},
            ]

            MODULE.plot_class_counts(rows, out_path)

            self.assertTrue(out_path.exists())
            self.assertGreater(out_path.stat().st_size, 0)


class EndToEndAnalysisTests(unittest.TestCase):
    def test_run_analysis_writes_key_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            library_csv = tmp / "sar_patch_library.csv"
            inventory_csv = tmp / "sar_patch_inventory.csv"
            patches_root = tmp / "Patches"
            analysis_root = tmp / "Analysis"
            create_analysis_fixture(library_csv, inventory_csv, patches_root)

            MODULE.run_analysis(
                library_csv=library_csv,
                inventory_csv=inventory_csv,
                patches_root=patches_root,
                analysis_root=analysis_root,
            )

            self.assertTrue((analysis_root / "ghana_class_counts.png").exists())
            self.assertTrue((analysis_root / "ghana_plastic_vs_other_feature_importance.csv").exists())
            self.assertTrue((analysis_root / "analysis_run_note.md").exists())


if __name__ == "__main__":
    unittest.main()
