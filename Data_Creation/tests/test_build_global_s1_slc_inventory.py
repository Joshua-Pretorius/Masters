from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box


SCRIPT = Path(__file__).resolve().parents[1] / "build_global_s1_slc_inventory.py"
SPEC = importlib.util.spec_from_file_location("build_global_s1_slc_inventory", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GlobalInventoryTests(unittest.TestCase):
    def test_jamila_uses_26_nominal_timestamp_groups(self) -> None:
        groups = MODULE.load_jamila_groups()

        self.assertEqual(len(groups), 26)
        self.assertEqual(sum(group.feature_count for group in groups), 3378)
        self.assertEqual({group.timestamp_source for group in groups}, {"nominal"})

    def test_two_adjacent_frames_can_complete_one_coverage_set(self) -> None:
        reference = datetime(2020, 1, 1, 12, tzinfo=timezone.utc)
        aoi = box(0, 0, 2, 1)
        scenes = [
            MODULE.S1Scene("left.SAFE", reference - timedelta(hours=2), box(0, 0, 1, 1)),
            MODULE.S1Scene("right.SAFE", reference - timedelta(hours=1), box(1, 0, 2, 1)),
        ]

        selected, ratio = MODULE.select_scene_set(aoi, scenes, reference, "before")

        self.assertEqual({scene.name for scene in selected}, {"left.SAFE", "right.SAFE"})
        self.assertGreaterEqual(ratio, MODULE.COVERAGE_THRESHOLD)

    def test_frames_more_than_12_hours_apart_are_not_combined(self) -> None:
        reference = datetime(2020, 1, 1, 12, tzinfo=timezone.utc)
        aoi = box(0, 0, 2, 1)
        scenes = [
            MODULE.S1Scene("left.SAFE", reference - timedelta(hours=1), box(0, 0, 1, 1)),
            MODULE.S1Scene("right.SAFE", reference - timedelta(hours=14), box(1, 0, 2, 1)),
        ]

        selected, ratio = MODULE.select_scene_set(aoi, scenes, reference, "before")

        self.assertLess(ratio, MODULE.COVERAGE_THRESHOLD)
        self.assertEqual(len(selected), 1)

    def test_marida_seed_rows_use_only_connected_marine_debris_components(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            patches_root = Path(temporary)
            folder = patches_root / "S2_30-8-18_16PCC"
            folder.mkdir()
            class_path = folder / "S2_30-8-18_16PCC_0_cl.tif"
            confidence_path = folder / "S2_30-8-18_16PCC_0_conf.tif"
            classes = np.array(
                [
                    [1, 1, 0, 0],
                    [0, 0, 0, 5],
                    [0, 0, 1, 0],
                    [0, 0, 0, 0],
                ],
                dtype="float32",
            )
            confidence = np.array(
                [
                    [1, 1, 0, 0],
                    [0, 0, 0, 2],
                    [0, 0, 3, 0],
                    [0, 0, 0, 0],
                ],
                dtype="float32",
            )
            profile = {
                "driver": "GTiff",
                "height": 4,
                "width": 4,
                "count": 1,
                "dtype": "float32",
                "crs": "EPSG:4326",
                "transform": from_origin(30.0, -29.0, 0.01, 0.01),
            }
            for path, values in ((class_path, classes), (confidence_path, confidence)):
                with rasterio.open(path, "w", **profile) as destination:
                    destination.write(values, 1)

            obs_id = "marida_16PCC_2018-08-30"
            rows = MODULE.marida_seed_rows({obs_id}, patches_root=patches_root)

        self.assertEqual(len(rows), 2)
        self.assertEqual({row["reference_kind"] for row in rows}, {"marida_debris_mask"})
        self.assertEqual({row["seed_eligible"] for row in rows}, {"true"})
        self.assertEqual({row["confidence"] for row in rows}, {"high", "low"})
        self.assertTrue(all("class DN=1" in row["notes"] for row in rows))

    def test_jamila_seed_rows_use_non_absence_geometry_midpoints(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            observations_path = Path(temporary) / "jamila.json"
            observations_path.write_text(
                json.dumps(
                    {
                        "observations": [
                            {
                                "id": "positive-line",
                                "geometry": {"type": "LineString", "coordinates": [[31.0, -30.0], [31.2, -30.0]]},
                                "isAbsence": False,
                                "extra": {"_sourceId": "durban_20200101.shp/1"},
                            },
                            {
                                "id": "absence-line",
                                "geometry": {"type": "LineString", "coordinates": [[32.0, -30.0], [32.2, -30.0]]},
                                "isAbsence": True,
                                "extra": {"_sourceId": "durban_20200101.shp/2"},
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            obs_id = "jamila_floating_debris_durban_20200101"
            rows = MODULE.jamila_seed_rows({obs_id}, observations_path=observations_path)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_feature_id"], "positive-line")
        self.assertAlmostEqual(rows[0]["lon"], 31.1)
        self.assertAlmostEqual(rows[0]["lat"], -30.0)
        self.assertEqual(rows[0]["seed_eligible"], "true")


if __name__ == "__main__":
    unittest.main()
