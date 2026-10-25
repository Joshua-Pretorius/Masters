"""Offline numerical, coverage and resumability tests for the four views."""

import json
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin
from pyproj import Transformer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from digitising.water_contrast import calculate, coverage, generate, window_sizes
from digitising.water_contrast import prepare_scene, transfer_paths, VERSION


class ContrastTests(unittest.TestCase):
    def test_preparation_combines_references_and_transfers_products(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            scene = SimpleNamespace(scene_dir=root, scene_id="scene", outputs={})
            tasks = [
                SimpleNamespace(
                    task_dir=root / "task1",
                    reference_points=[
                        SimpleNamespace(
                            longitude=26.5, latitude=39.0, reference_kind="aoi_proxy"
                        )
                    ],
                ),
                SimpleNamespace(
                    task_dir=root / "task2",
                    reference_points=[
                        SimpleNamespace(
                            longitude=26.6, latitude=39.1, reference_kind="label"
                        )
                    ],
                ),
            ]
            with mock.patch(
                "digitising.water_contrast.generate",
                return_value={"status": "complete"},
            ) as create:
                prepare_scene(scene, tasks)
                self.assertEqual(create.call_args.args[1], [(26.5, 39.0), (26.6, 39.1)])
                self.assertEqual(create.call_args.args[2], root / VERSION)
            destination = root / VERSION
            destination.mkdir()
            for name in (
                "water_contrast.tif",
                "water_contrast.json",
                "coverage.geojson",
            ):
                (destination / name).touch()
            self.assertEqual(len(transfer_paths(scene)), 3)

    def test_known_ratios_sign_and_scale_invariance(self):
        vv = np.ones((151, 151))
        vh = vv.copy()
        lee = np.zeros_like(vv)
        water = np.ones_like(vv, dtype=bool)
        vv[72:79, 72:79] = 2
        vh[72:79, 72:79] = 0.5
        lee[75, 75] = 3
        result = calculate(vv, vh, lee, water, (10, 10))
        np.testing.assert_allclose(
            result[:, 75, 75],
            [3, 10 * np.log10(2), -10 * np.log10(2), 10 * np.log10(2)],
            atol=1e-6,
        )
        scaled = calculate(vv * 4, vh * 4, lee + 10 * np.log10(4), water, (10, 10))
        np.testing.assert_allclose(result, scaled, atol=1e-5, equal_nan=True)

    def test_water_and_missing_data_are_not_zero(self):
        a = np.ones((151, 151))
        water = np.ones_like(a, dtype=bool)
        result = calculate(a, a, np.zeros_like(a), water, (10, 10))
        np.testing.assert_allclose(result[:, 75, 75], 0)
        water[75, 75] = False
        self.assertTrue(
            np.isnan(
                calculate(a, a, np.zeros_like(a), water, (10, 10))[:, 75, 75]
            ).all()
        )
        water[:] = False
        self.assertTrue(
            np.isnan(calculate(a, a, np.zeros_like(a), water, (10, 10))).all()
        )

    def test_native_window_sizes(self):
        sizes = window_sizes((13.24, 13.93))
        self.assertEqual(sizes["patch30"], (3, 3))
        self.assertEqual(sizes["patch60"], (5, 5))
        self.assertEqual(sizes["outer"], (45, 47))
        self.assertEqual(sizes["guard"], (15, 17))

    def test_guard_excludes_nearby_bright_return(self):
        vv = np.ones((151, 151))
        water = np.ones_like(vv, dtype=bool)
        vv[75, 83] = 1000  # outside both central patches, inside the 100 m guard
        result = calculate(vv, np.ones_like(vv), np.zeros_like(vv), water, (10, 10))
        np.testing.assert_allclose(result[:, 75, 75], 0, atol=1e-6)

    def test_missing_vh_does_not_remove_vv(self):
        vv = np.ones((151, 151))
        water = np.ones_like(vv, dtype=bool)
        result = calculate(
            vv, np.full_like(vv, np.nan), np.zeros_like(vv), water, (10, 10)
        )
        self.assertTrue(np.isnan(result[2]).all())
        np.testing.assert_allclose(result[[0, 1, 3], 75, 75], 0)

    def test_tiled_generation_coverage_and_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            outputs = {}
            rng = np.random.default_rng(42)
            vv = np.exp(rng.normal(-3, 0.3, (180, 180))).astype("float32")
            vh = vv * 0.4
            lee = (10 * np.log10(vv)).astype("float32")
            for key, array in [("vv", vv), ("vh", vh), ("vv_refined_lee_db", lee)]:
                path = root / (key + ".tif")
                outputs[key] = path
                with rasterio.open(
                    path,
                    "w",
                    driver="GTiff",
                    width=180,
                    height=180,
                    count=1,
                    dtype="float32",
                    crs="EPSG:32618",
                    transform=from_origin(500000, 2100000, 10, 10),
                    nodata=-9999,
                ) as dst:
                    dst.write(array, 1)
            lon, lat = Transformer.from_crs(32618, 4326, always_xy=True).transform(
                500900, 2099100
            )
            with rasterio.open(outputs["vv"]) as src:
                area, win, points = coverage(src, [(lon, lat), (0, 0)], 100000)
                self.assertEqual(len(points), 1)
                self.assertEqual((win.width, win.height), (180, 180))
                self.assertIsNone(coverage(src, [(0, 0)])[0])
            reader = lambda src, win, px: np.ones(
                (int(win.height), int(win.width)), dtype=bool
            )
            result = generate(
                outputs, [(lon, lat)], root / "result", block=61, water_reader=reader
            )
            expected = calculate(vv, vh, lee, np.ones_like(vv, dtype=bool), (10, 10))
            with rasterio.open(result["path"]) as src:
                np.testing.assert_allclose(
                    src.read(), expected, atol=1e-5, equal_nan=True
                )
                self.assertEqual(src.transform, from_origin(500000, 2100000, 10, 10))
            stamp = Path(result["path"]).stat().st_mtime_ns
            cached = generate(
                outputs,
                [(lon, lat)],
                root / "result",
                water_reader=lambda *a: self.fail("cache should skip calculation"),
            )
            self.assertEqual(cached["fingerprint"], result["fingerprint"])
            self.assertEqual(Path(result["path"]).stat().st_mtime_ns, stamp)
            changed = generate(
                outputs,
                [(lon, lat)],
                root / "result",
                buffer_m=500,
                water_reader=reader,
            )
            self.assertNotEqual(changed["fingerprint"], result["fingerprint"])


if __name__ == "__main__":
    unittest.main()
