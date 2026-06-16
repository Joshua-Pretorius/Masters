from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[2] / "Scripts" / "download_ghana_drift_planet.py"
SPEC = importlib.util.spec_from_file_location("download_ghana_drift_planet", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Could not load module spec for {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GhanaDriftPlanetDownloadTests(unittest.TestCase):
    def test_load_bounds_features_reads_dates_and_polygons_from_ogrinfo_json(self) -> None:
        payload = {
            "layers": [
                {
                    "features": [
                        {
                            "properties": {
                                "obs_id": "abc",
                                "obs_date": "2018/10/31",
                                "area": "Ghana",
                                "pt_count": 12,
                            },
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": [[[1.0, 2.0], [3.0, 2.0], [3.0, 4.0], [1.0, 2.0]]],
                            },
                        }
                    ]
                }
            ]
        }
        completed = mock.Mock(stdout=json.dumps(payload), returncode=0)
        with mock.patch.object(MODULE.subprocess, "run", return_value=completed) as run_mock:
            rows = MODULE.load_bounds_features(Path(r"D:\Masters\Ghana_Drift\ghana_drift_bounds.shp"))

        run_mock.assert_called_once()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["obs_id"], "abc")
        self.assertEqual(rows[0]["obs_date"], "2018-10-31")
        self.assertEqual(rows[0]["pt_count"], 12)
        self.assertEqual(rows[0]["geometry"]["type"], "Polygon")

    def test_build_quick_search_payload_limits_search_to_single_day_and_geometry(self) -> None:
        feature = {
            "obs_id": "abc",
            "obs_date": "2018-10-31",
            "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
        }

        payload = MODULE.build_quick_search_payload(feature, "PSScene")

        self.assertEqual(payload["item_types"], ["PSScene"])
        self.assertEqual(payload["geometry"], feature["geometry"])
        self.assertEqual(payload["filter"]["config"]["gte"], "2018-10-31T00:00:00Z")
        self.assertEqual(payload["filter"]["config"]["lte"], "2018-11-01T00:00:00Z")

    def test_build_order_payload_uses_all_item_ids_and_polygon_clip(self) -> None:
        geometry = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}

        payload = MODULE.build_order_payload(
            obs_id="abc",
            obs_date="2018-10-31",
            item_type="PSScene",
            item_ids=["item-1", "item-2"],
            geometry=geometry,
            product_bundle="analytic_udm2",
        )

        self.assertEqual(payload["name"], "ghana_drift_2018-10-31_abc")
        self.assertEqual(payload["products"][0]["item_ids"], ["item-1", "item-2"])
        self.assertEqual(payload["products"][0]["product_bundle"], "analytic_udm2")
        self.assertEqual(payload["tools"], [{"clip": {"aoi": geometry}}, {"composite": {}}])

    def test_output_directory_is_scoped_by_date_and_obs_id(self) -> None:
        out_dir = MODULE.output_dir_for_feature(Path(r"D:\Masters\Ghana_Drift"), "2018-10-31", "abc")

        self.assertEqual(out_dir, Path(r"D:\Masters\Ghana_Drift\2018-10-31_abc"))

    def test_existing_download_complete_detects_existing_raster(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir)
            (out_dir / "composite.tif").write_bytes(b"abc")

            self.assertTrue(MODULE.existing_download_complete(out_dir))

    def test_filter_requested_features_keeps_only_named_obs_ids(self) -> None:
        features = [
            {"obs_id": "a", "obs_date": "2018-10-20"},
            {"obs_id": "b", "obs_date": "2018-10-21"},
        ]

        filtered = MODULE.filter_requested_features(features, {"b"})

        self.assertEqual(filtered, [{"obs_id": "b", "obs_date": "2018-10-21"}])

    def test_select_covering_item_window_prefers_smallest_consecutive_range(self) -> None:
        aoi_geometry = {
            "type": "Polygon",
            "coordinates": [[[0.0, 0.0], [0.0, 1.0], [3.0, 1.0], [3.0, 0.0], [0.0, 0.0]]],
        }
        items = [
            {
                "id": "scene-early",
                "geometry": {"type": "Polygon", "coordinates": [[[0.0, 0.0], [0.0, 1.0], [0.8, 1.0], [0.8, 0.0], [0.0, 0.0]]]},
                "properties": {"acquired": "2018-10-28T09:45:00Z"},
            },
            {
                "id": "scene-a",
                "geometry": {"type": "Polygon", "coordinates": [[[0.0, 0.0], [0.0, 1.0], [1.6, 1.0], [1.6, 0.0], [0.0, 0.0]]]},
                "properties": {"acquired": "2018-10-28T10:01:00Z"},
            },
            {
                "id": "scene-b",
                "geometry": {"type": "Polygon", "coordinates": [[[1.4, 0.0], [1.4, 1.0], [3.0, 1.0], [3.0, 0.0], [1.4, 0.0]]]},
                "properties": {"acquired": "2018-10-28T10:03:00Z"},
            },
            {
                "id": "scene-late",
                "geometry": {"type": "Polygon", "coordinates": [[[2.6, 0.0], [2.6, 1.0], [3.0, 1.0], [3.0, 0.0], [2.6, 0.0]]]},
                "properties": {"acquired": "2018-10-28T10:18:00Z"},
            },
        ]

        selected = MODULE.select_covering_item_window(items, aoi_geometry)

        self.assertEqual([item["id"] for item in selected], ["scene-a", "scene-b"])

    def test_split_feature_geometry_halves_rectangular_bounds_along_long_axis(self) -> None:
        feature = {
            "obs_id": "abc",
            "obs_date": "2018-10-28",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[-1.0, 5.0], [-1.0, 6.0], [2.0, 6.0], [2.0, 5.0], [-1.0, 5.0]]],
            },
        }

        parts = MODULE.split_feature_geometry(feature, parts=2)

        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0]["part_index"], 1)
        self.assertEqual(parts[1]["part_index"], 2)
        self.assertEqual(parts[0]["part_total"], 2)
        self.assertEqual(parts[1]["part_total"], 2)
        self.assertEqual(parts[0]["geometry"]["coordinates"][0][0], [-1.0, 5.0])
        self.assertEqual(parts[0]["geometry"]["coordinates"][0][2], [0.5, 6.0])
        self.assertEqual(parts[1]["geometry"]["coordinates"][0][0], [0.5, 5.0])
        self.assertEqual(parts[1]["geometry"]["coordinates"][0][2], [2.0, 6.0])


if __name__ == "__main__":
    unittest.main()
