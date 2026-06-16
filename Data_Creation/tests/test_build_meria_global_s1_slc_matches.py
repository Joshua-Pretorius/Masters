from __future__ import annotations

import importlib.util
import math
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "build_meria_global_s1_slc_matches.py"
SPEC = importlib.util.spec_from_file_location("build_meria_global_s1_slc_matches", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Could not load module spec for {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class BuildMeriaGlobalMatchesTest(unittest.TestCase):
    def test_load_ghana_drift_observations_reads_shapefile_points(self) -> None:
        observations = {obs.obs_id: obs for obs in MODULE.load_ghana_drift_observations()}

        self.assertEqual(
            set(observations),
            {
                "57bbff03-21eb-54de-9d18-d8a65b256bd5",
                "91ea9edc-67b4-4211-8532-35deec4a3148",
                "cd77705c-782d-5b99-935f-405bfd905cbf",
                "d918b4e9-16ac-5c30-830f-6945943e1d9e",
                "d9db6dd4-4db8-5723-96ba-57d182cda0b7",
            },
        )

        split_candidate = observations["d9db6dd4-4db8-5723-96ba-57d182cda0b7"]
        point_records = MODULE.point_records_for_observation(split_candidate)
        self.assertEqual(len(point_records), 14)
        self.assertEqual(point_records[0].pt_id, "P01")
        self.assertEqual(point_records[-1].pt_id, "P14")

    def test_explicit_points_are_preserved(self) -> None:
        obs = MODULE.OBSERVATIONS_BY_ID["cabcd011-9d82-4124-9f9c-120bdc406cf3"]
        self.assertEqual(
            MODULE.observation_points(obs),
            obs.explicit_points,
        )

    def test_split_observation_by_scene_cover_creates_subset_rows(self) -> None:
        obs = MODULE.Observation(
            obs_id="ghana-test",
            area="Ghana",
            region="Ghana",
            date="2018-10-28",
            center_lat=5.0,
            center_lon=0.0,
            location_label="test",
            notes="example",
            point_records=(
                MODULE.PointRecord("P01", 5.0, -0.5),
                MODULE.PointRecord("P02", 5.1, -0.4),
                MODULE.PointRecord("P03", 5.2, 0.4),
                MODULE.PointRecord("P04", 5.3, 0.5),
            ),
            point_source="ghana_drift_points",
            match_strategy="contains_all_points",
            planet_acquired_start="2018-10-28T10:00:00Z",
            planet_acquired_end="2018-10-28T10:00:00Z",
        )
        before_matches = [
            {
                "name": "before-west.safe",
                "start": "2018-10-24T18:17:17Z",
                "coverage_ratio": "0.500",
                "candidate_count": 5,
                "rejection_reason": "-",
                "selected_point_ids": ["P01", "P02"],
            },
            {
                "name": "before-east.safe",
                "start": "2018-10-25T18:09:53Z",
                "coverage_ratio": "0.500",
                "candidate_count": 5,
                "rejection_reason": "-",
                "selected_point_ids": ["P03", "P04"],
            },
        ]
        after_matches = [
            {
                "name": "after-west.safe",
                "start": "2018-10-30T18:17:58Z",
                "coverage_ratio": "0.500",
                "candidate_count": 5,
                "rejection_reason": "-",
                "selected_point_ids": ["P01", "P02"],
            },
            {
                "name": "after-east.safe",
                "start": "2018-10-31T18:09:08Z",
                "coverage_ratio": "0.500",
                "candidate_count": 5,
                "rejection_reason": "-",
                "selected_point_ids": ["P03", "P04"],
            },
        ]

        parts = MODULE.split_observation_by_scene_cover(obs, before_matches, after_matches)

        self.assertEqual([part_obs.obs_id for part_obs, _, _ in parts], ["ghana-test_A", "ghana-test_B"])
        self.assertEqual(
            [record.pt_id for record in MODULE.point_records_for_observation(parts[0][0])],
            ["P01", "P02"],
        )
        self.assertEqual(parts[0][1]["name"], "before-west.safe")
        self.assertEqual(parts[0][2]["name"], "after-west.safe")
        self.assertEqual(
            [record.pt_id for record in MODULE.point_records_for_observation(parts[1][0])],
            ["P03", "P04"],
        )
        self.assertEqual(parts[1][1]["name"], "before-east.safe")
        self.assertEqual(parts[1][2]["name"], "after-east.safe")

    def test_synthetic_points_include_center_and_four_cardinal_offsets(self) -> None:
        obs = MODULE.OBSERVATIONS_BY_ID["05e7c3bc-2eac-4c4b-ba8a-6bf8aa4c0789"]
        points = MODULE.observation_points(obs)

        self.assertEqual(len(points), 5)
        center = MODULE.parse_decimal_cardinal(points[0])
        north = MODULE.parse_decimal_cardinal(points[1])
        south = MODULE.parse_decimal_cardinal(points[2])
        east = MODULE.parse_decimal_cardinal(points[3])
        west = MODULE.parse_decimal_cardinal(points[4])

        self.assertAlmostEqual(center[0], obs.center_lat, places=5)
        self.assertAlmostEqual(center[1], obs.center_lon, places=5)
        self.assertGreater(north[0], center[0])
        self.assertLess(south[0], center[0])
        self.assertGreater(east[1], center[1])
        self.assertLess(west[1], center[1])

        for candidate in (north, south, east, west):
            distance_km = MODULE.haversine_km(center[0], center[1], candidate[0], candidate[1])
            self.assertTrue(math.isclose(distance_km, 100.0, rel_tol=0.0, abs_tol=0.5), distance_km)

    def test_same_day_planet_time_is_used_for_before_after_deltas(self) -> None:
        obs = MODULE.OBSERVATIONS_BY_ID["cabcd011-9d82-4124-9f9c-120bdc406cf3"]
        lookup = MODULE.load_planet_lookup()
        row = MODULE.build_row(
            obs,
            {"name": "before.safe", "start": "2018-10-12T05:44:31Z", "coverage_ratio": "0.901"},
            {"name": "after.safe", "start": "2018-10-17T05:52:40Z", "coverage_ratio": "0.877"},
            lookup,
        )

        self.assertEqual(row["planet_acquired"], "2018-10-12 10:05:28 UTC")
        self.assertEqual(row["before_delta_h"], "-4.35")
        self.assertEqual(row["after_delta_h"], "+115.79")
        self.assertEqual(row["before_coverage_ratio"], "0.901")
        self.assertEqual(row["after_coverage_ratio"], "0.877")

    def test_lookup_includes_resolved_time_for_unavailable_global_download(self) -> None:
        obs = MODULE.OBSERVATIONS_BY_ID["9e17ce98-9eeb-40f6-989e-894dc2be72ea"]
        lookup = MODULE.load_planet_lookup()
        row = MODULE.build_row(obs, None, None, lookup)

        self.assertEqual(row["planet_acquired"], "2017-10-12 14:12:56 UTC")
        self.assertEqual(row["before_delta_h"], "-")
        self.assertEqual(row["after_delta_h"], "-")
        self.assertEqual(row["before_coverage_ratio"], "-")
        self.assertEqual(row["after_coverage_ratio"], "-")


if __name__ == "__main__":
    unittest.main()
