from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
