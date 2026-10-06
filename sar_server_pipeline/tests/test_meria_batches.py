from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from digitising.catalog import MANUAL_16PCC_GRANULE, build_task_catalog
from digitising.meria_batches import BATCH_BY_NAME, MERIA_BATCHES, task_ids_for_batch


LEGACY_GRANULE = "S1B_IW_SLC__1SDV_20181012T054431_20181012T054458_013115_0183B4_07F8"


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def add_scene(root: Path, granule: str) -> None:
    token = granule.split("_")[5]
    path = root / granule / f"scene_{token}"
    path.mkdir(parents=True)
    raster = path / f"{granule}_vv_refined_lee_db.tif"
    raster.write_bytes(b"test raster placeholder")
    (path / f"{granule}_slc_manifest.json").write_text(
        json.dumps({
            "scene_id": f"{granule}_scene_{token}",
            "slc": {"granule": granule},
            "acquisition_start": f"{token[:4]}-{token[4:6]}-{token[6:8]}T{token[9:11]}:{token[11:13]}:{token[13:15]}Z",
            "status": "processed",
            "outputs": {"vv_refined_lee_db": str(raster)},
        }),
        encoding="utf-8",
    )


class MeriaBatchTests(unittest.TestCase):
    def test_plan_has_only_unique_area_window_groups_of_at_most_three_scenes(self) -> None:
        acquisitions = [token for batch in MERIA_BATCHES for token in batch.acquisitions]
        self.assertEqual(len(MERIA_BATCHES), 17)
        self.assertEqual(len(acquisitions), 26)
        self.assertEqual(len(set(acquisitions)), 26)
        self.assertTrue(all(1 <= len(batch.acquisitions) <= 3 for batch in MERIA_BATCHES))
        self.assertEqual({batch.dataset for batch in MERIA_BATCHES}, {"sa", "meria_global"})
        for batch in MERIA_BATCHES:
            times = [datetime.strptime(token, "%Y%m%dT%H%M%S") for token in batch.acquisitions]
            self.assertLessEqual((max(times) - min(times)).days, 7, batch.name)

    def test_every_planned_scene_resolves_against_the_real_meria_catalogues(self) -> None:
        catalog = PIPELINE_ROOT.parent / "Data_Creation"
        names: set[str] = {MANUAL_16PCC_GRANULE}
        for relative in (
            "meria_sa_plastic_s1_slc/MERIA_SA_plastic_nearest_S1_SLC_before_after.csv",
            "meria_global_s1_slc/MERIA_global_plastic_nearest_S1_SLC_before_after.csv",
        ):
            with (catalog / relative).open(newline="", encoding="utf-8-sig") as handle:
                for row in csv.DictReader(handle):
                    names.update(
                        row[f"{role}_name"].removesuffix(".SAFE")
                        for role in ("before", "after") if row[f"{role}_name"] not in ("", "-")
                    )
        with tempfile.TemporaryDirectory() as temporary:
            processed = Path(temporary) / "processed"
            for name in names:
                add_scene(processed, name)
            selections = {
                batch.name: task_ids_for_batch(batch, catalog, processed)
                for batch in MERIA_BATCHES
            }
            manual = build_task_catalog(catalog, processed, "meria_global", include_partial=True)

        self.assertEqual(len(names), 26)
        self.assertTrue(all(len(selections[b.name]) == len(b.acquisitions) for b in MERIA_BATCHES))
        self.assertEqual(sum(len(ids) for ids in selections.values()), 26)
        candidate = next(task for task in manual if task.source_dataset == "Manual_Sentinel2")
        self.assertEqual(len(candidate.reference_points), 85)
        self.assertNotIn("MARIDA", {task.source_dataset for task in manual})
        self.assertNotIn("Jamila_Floating_Debris", {task.source_dataset for task in manual})

    def test_focused_catalog_preserves_legacy_provenance_and_manual_points(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            catalog = root / "catalog"
            processed = root / "processed"
            add_scene(processed, LEGACY_GRANULE)
            add_scene(processed, MANUAL_16PCC_GRANULE)
            legacy = catalog / "meria_global_s1_slc"
            write_csv(legacy / "MERIA_global_plastic_nearest_S1_SLC_before_after.csv", [{
                "obs_id": "observation-1", "area": "Palma de Mallorca",
                "planet_acquired": "2018-10-12 10:05:28 UTC",
                "before_name": LEGACY_GRANULE + ".SAFE", "before_start": "2018-10-12 05:44:31 UTC",
                "before_delta_h": "-4.35", "before_coverage_ratio": "0.798",
                "after_name": "-", "after_start": "", "after_delta_h": "",
                "after_coverage_ratio": "", "notes": "candidate debris",
            }])
            write_csv(legacy / "MERIA_global_plastic_points.csv", [
                {"obs_id": "observation-1", "pt_id": "observed", "lat": "39.6", "lon": "3.4",
                 "point_source": "explicit", "notes": "observed"},
                {"obs_id": "observation-1", "pt_id": "context", "lat": "39.7", "lon": "3.5",
                 "point_source": "synthetic_center_plus_100km_cardinals", "notes": ""},
            ])
            write_csv(catalog / "global_s1_slc_inventory" / "manual_s2_16pcc_20181024_candidate_points.csv", [
                {"point_id": "P001", "lon": "-88.59", "lat": "16.07"},
                {"point_id": "P002", "lon": "-88.58", "lat": "16.06"},
            ])
            default = build_task_catalog(catalog, processed, "meria_global")
            partial = build_task_catalog(catalog, processed, "meria_global", include_partial=True)
            manual_ids = task_ids_for_batch(BATCH_BY_NAME["meria_16pcc_2018_oct25"], catalog, processed)

        self.assertEqual(len(default), 1)
        self.assertEqual(default[0].source_dataset, "Manual_Sentinel2")
        self.assertEqual(len(default[0].reference_points), 2)
        self.assertTrue(all(point.seed_eligible for point in default[0].reference_points))
        self.assertEqual(len(partial), 2)
        legacy_task = next(task for task in partial if task.source_dataset == "MERIA_Global")
        self.assertEqual([point.seed_eligible for point in legacy_task.reference_points], [True, False])
        self.assertEqual(len(manual_ids), 1)
        self.assertIn("20181025T000626", manual_ids[0])

    def test_batch_refuses_an_unprocessed_acquisition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ValueError, "no processed SAR scene"):
                task_ids_for_batch(
                    BATCH_BY_NAME["sa_durban_2019_apr21_27"], root / "catalog", root / "processed"
                )


if __name__ == "__main__":
    unittest.main()
