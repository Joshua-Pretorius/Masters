from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "slc_match_aoi.py"
SPEC = importlib.util.spec_from_file_location("slc_match_aoi", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Could not load module spec for {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class SlcMatchAoiTest(unittest.TestCase):
    def test_scene_coverage_ratio_distinguishes_full_and_sliver_coverage(self) -> None:
        points = [(0.0, 0.0)]
        full_cover = {
            "type": "Polygon",
            "coordinates": [[
                (-0.2, -0.2),
                (-0.2, 0.2),
                (0.2, 0.2),
                (0.2, -0.2),
                (-0.2, -0.2),
            ]],
        }
        sliver_cover = {
            "type": "Polygon",
            "coordinates": [[
                (0.043, -0.02),
                (0.043, 0.02),
                (0.047, 0.02),
                (0.047, -0.02),
                (0.043, -0.02),
            ]],
        }

        full_ratio = MODULE.coverage_ratio_for_scene(points, full_cover, buffer_km=5.0)
        sliver_ratio = MODULE.coverage_ratio_for_scene(points, sliver_cover, buffer_km=5.0)

        self.assertGreater(full_ratio, 0.95)
        self.assertLess(sliver_ratio, 0.15)


if __name__ == "__main__":
    unittest.main()
