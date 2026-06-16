from __future__ import annotations

import importlib.util
import sys
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "build_meria_sa_s1_slc_matches.py"
SPEC = importlib.util.spec_from_file_location("build_meria_sa_s1_slc_matches", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Could not load module spec for {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class BuildMeriaSAMatchesTest(unittest.TestCase):
    def test_after_match_skips_nearer_sliver_scene_when_coverage_is_too_low(self) -> None:
        obs = next(item for item in MODULE.OBSERVATIONS if item.obs_id == "MERIA_SA_002")
        lookup = {
            obs.obs_id: {
                "planet_acquired_start": "2019-04-25T07:36:26Z",
                "planet_acquired_end": "2019-04-25T08:02:15Z",
            }
        }
        products = [
            {
                "Name": "S1A_IW_SLC__1SDV_20190425T081000_20190425T081027_000000_000000_0001.SAFE",
                "ContentDate": {"Start": "2019-04-25T08:10:00Z"},
                "GeoFootprint": {
                    "type": "Polygon",
                    "coordinates": [[
                        (31.048, -29.88),
                        (31.048, -29.82),
                        (31.052, -29.82),
                        (31.052, -29.88),
                        (31.048, -29.88),
                    ]],
                },
            },
            {
                "Name": "S1A_IW_SLC__1SDV_20190425T091000_20190425T091027_000000_000000_0002.SAFE",
                "ContentDate": {"Start": "2019-04-25T09:10:00Z"},
                "GeoFootprint": {
                    "type": "Polygon",
                    "coordinates": [[
                        (30.95, -30.05),
                        (30.95, -29.75),
                        (31.15, -29.75),
                        (31.15, -30.05),
                        (30.95, -30.05),
                    ]],
                },
            },
        ]

        with (
            mock.patch.object(MODULE, "request_json", return_value={"value": products}),
            mock.patch.object(MODULE, "save_cache"),
        ):
            result = MODULE.query_s1_slc(obs, "after", {}, lookup)

        self.assertEqual(result["name"], products[1]["Name"])
        self.assertEqual(result["candidate_count"], 2)
        self.assertGreater(float(result["coverage_ratio"]), 0.75)

    def test_planet_window_is_rendered_as_range_and_deltas_span_that_window(self) -> None:
        obs = next(item for item in MODULE.OBSERVATIONS if item.obs_id == "MERIA_SA_001")
        lookup = MODULE.load_planet_lookup()
        row = MODULE.build_row(
            obs,
            {"name": "before.safe", "start": "2019-04-21T16:37:24Z", "coverage_ratio": "0.812"},
            {"name": "after.safe", "start": "2019-04-25T03:10:55Z", "coverage_ratio": "0.934"},
            lookup,
        )

        self.assertEqual(
            row["planet_acquired"],
            "2019-04-24 07:38:41 UTC to 2019-04-24 08:03:38 UTC",
        )
        self.assertEqual(row["before_delta_h"], "-63.44 to -63.02")
        self.assertEqual(row["after_delta_h"], "+19.12 to +19.54")
        self.assertEqual(row["before_coverage_ratio"], "0.812")
        self.assertEqual(row["after_coverage_ratio"], "0.934")
        self.assertEqual(row["aoi_buffer_km"], "5.0")
        self.assertEqual(row["coverage_threshold"], "0.75")

    def test_single_scene_sa_observation_collapses_to_one_timestamp(self) -> None:
        obs = next(item for item in MODULE.OBSERVATIONS if item.obs_id == "MERIA_SA_005")
        lookup = MODULE.load_planet_lookup()
        row = MODULE.build_row(obs, None, None, lookup)

        self.assertEqual(row["planet_acquired"], "2024-06-13 07:29:05 UTC")
        self.assertEqual(row["before_delta_h"], "-")
        self.assertEqual(row["after_delta_h"], "-")

    def test_docx_includes_coverage_columns(self) -> None:
        rows = [
            {
                "obs_id": "MERIA_SA_001",
                "area": "Durban",
                "date": "2019-04-24",
                "planet_acquired": "2019-04-24 07:38:41 UTC",
                "points": "2",
                "point_coordinates": "A; B",
                "before_name": "before.safe",
                "before_start": "2019-04-21 16:37:24 UTC",
                "before_delta_h": "-63.44",
                "before_coverage_ratio": "0.812",
                "before_candidate_count": "2",
                "before_rejection_reason": "-",
                "before_download_group_key": "before",
                "after_name": "after.safe",
                "after_start": "2019-04-25 03:10:55 UTC",
                "after_delta_h": "+19.12",
                "after_coverage_ratio": "0.934",
                "after_candidate_count": "2",
                "after_rejection_reason": "-",
                "after_download_group_key": "after",
                "aoi_buffer_km": "5.0",
                "coverage_threshold": "0.75",
                "notes": "Example",
            }
        ]
        with TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir) / "inventory.docx"
            with mock.patch.object(MODULE, "DOCX_PATH", out_path):
                MODULE.build_docx(rows)
            with zipfile.ZipFile(out_path) as zf:
                document_xml = zf.read("word/document.xml").decode("utf-8")

        self.assertIn("Before cov", document_xml)
        self.assertIn("After cov", document_xml)
        self.assertIn("0.812", document_xml)
        self.assertIn("0.934", document_xml)


if __name__ == "__main__":
    unittest.main()
