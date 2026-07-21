from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "add_meria_sa_observation.py"
SPEC = importlib.util.spec_from_file_location("add_meria_sa_observation", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Could not load module spec for {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class AddMeriaObservationTests(unittest.TestCase):
    def test_parse_point_accepts_decimal_lat_lon(self) -> None:
        self.assertEqual(MODULE.parse_point("-29.8258,31.2519"), (-29.8258, 31.2519))

    def test_query_direction_uses_requested_window_and_selection_settings(self) -> None:
        selected = {
            "name": "S1A_IW_SLC__1SDV_20240101T000000_20240101T000027_000000_000000_0001.SAFE",
            "start": "2024-01-01T00:00:00Z",
            "coverage_ratio": "0.900",
            "candidate_count": 3,
            "rejection_reason": "-",
        }
        with (
            mock.patch.object(MODULE.resolver, "request_json", return_value={"value": []}) as request,
            mock.patch.object(MODULE.resolver, "select_candidate", return_value=selected) as select,
        ):
            result = MODULE.query_direction(
                [(-29.8, 31.2)],
                MODULE.parse_date("2024-01-15"),
                "before",
                window_days=10,
                buffer_km=3.0,
                coverage_threshold=0.8,
            )

        self.assertEqual(result["name"], selected["name"])
        request.assert_called_once()
        select.assert_called_once_with(
            [],
            "before",
            [(-29.8, 31.2)],
            buffer_km=3.0,
            coverage_threshold=0.8,
        )
        self.assertEqual(result["window_end"], MODULE.parse_date("2024-01-15"))

    def test_update_csvs_adds_one_match_row_and_multiple_point_rows(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            match_csv = root / "matches.csv"
            points_csv = root / "points.csv"
            row = {field: "" for field in MODULE.MATCH_FIELDS}
            row.update({"obs_id": "MERIA_SA_009", "date": "2024-01-15", "before_name": "before.SAFE", "after_name": "after.SAFE"})

            MODULE.update_csvs(
                match_row=row,
                points=[(-29.8, 31.2), (-29.9, 31.3)],
                area="Durban",
                notes="test",
                replace=False,
                match_csv=match_csv,
                points_csv=points_csv,
            )

            self.assertEqual(len(MODULE.load_rows(match_csv)), 1)
            point_rows = MODULE.load_rows(points_csv)
            self.assertEqual(len(point_rows), 2)
            self.assertEqual(point_rows[1]["pt_id"], "MERIA_SA_009_P02")

    def test_union_coverage_can_accept_a_partial_second_scene(self) -> None:
        full = {
            "footprint": {
                "type": "Polygon",
                "coordinates": [[(31.0, -30.0), (31.0, -29.0), (32.0, -29.0), (32.0, -30.0), (31.0, -30.0)]],
            }
        }
        partial = {
            "footprint": {
                "type": "Polygon",
                "coordinates": [[(31.0, -30.0), (31.0, -29.5), (31.5, -29.5), (31.5, -30.0), (31.0, -30.0)]],
            }
        }
        self.assertEqual(MODULE.union_coverage([(-29.8, 31.2)], [full, partial], 5.0), 1.0)

    def test_select_best_partial_prefers_spatial_coverage_over_catalogue_order(self) -> None:
        low = {
            "Name": "low.SAFE",
            "ContentDate": {"Start": "2026-05-05T17:00:54Z"},
            "GeoFootprint": {
                "type": "Polygon",
                "coordinates": [[(31.0, -30.0), (31.0, -29.5), (31.5, -29.5), (31.5, -30.0), (31.0, -30.0)]],
            },
        }
        high = {
            "Name": "high.SAFE",
            "ContentDate": {"Start": "2026-05-05T17:01:21Z"},
            "GeoFootprint": {
                "type": "Polygon",
                "coordinates": [[(31.0, -30.0), (31.0, -29.0), (32.0, -29.0), (32.0, -30.0), (31.0, -30.0)]],
            },
        }
        result = MODULE.select_best_partial([low, high], "before", [(-29.8, 31.2)], 5.0)
        self.assertEqual(result["name"], "high.SAFE")
        self.assertEqual(result["coverage_ratio"], "1.000")


if __name__ == "__main__":
    unittest.main()
