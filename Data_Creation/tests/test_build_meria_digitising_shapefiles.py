from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "build_meria_digitising_shapefiles.py"
SPEC = importlib.util.spec_from_file_location("build_meria_digitising_shapefiles", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class BuildMeriaDigitisingShapefilesTests(unittest.TestCase):
    def test_expected_scene_template_count(self) -> None:
        sa_rows = MODULE.load_rows(MODULE.SA_DIR / "MERIA_SA_plastic_nearest_S1_SLC_before_after.csv")
        global_rows = MODULE.load_rows(MODULE.GLOBAL_DIR / "MERIA_global_plastic_nearest_S1_SLC_before_after.csv")
        templates = MODULE.build_scene_templates("SA", MODULE.SA_DIR, sa_rows) + MODULE.build_scene_templates(
            "Global",
            MODULE.GLOBAL_DIR,
            global_rows,
        )
        self.assertEqual(len(templates), 27)

    def test_processed_scene_uses_manifest_scene_id_and_output_folder(self) -> None:
        global_rows = MODULE.load_rows(MODULE.GLOBAL_DIR / "MERIA_global_plastic_nearest_S1_SLC_before_after.csv")
        templates = MODULE.build_scene_templates("Global", MODULE.GLOBAL_DIR, global_rows)
        template = next(item for item in templates if item.obs_id == "91ea9edc-67b4-4211-8532-35deec4a3148" and item.role == "before")
        self.assertEqual(template.scene_id, "91ea9edc-67b4-4211-8532-35deec4a3148_Ghana_before_20181030T181758")
        self.assertEqual(
            template.shapefile_path,
            MODULE.GLOBAL_DIR
            / "processed_slc"
            / "91ea9edc-67b4-4211-8532-35deec4a3148_Ghana"
            / "before_20181030T181758"
            / "digitised_patches"
            / "91ea9edc-67b4-4211-8532-35deec4a3148_Ghana_before_20181030T181758_digitised_patches.shp",
        )

    def test_unprocessed_scene_path_is_derived_from_match_table(self) -> None:
        global_rows = MODULE.load_rows(MODULE.GLOBAL_DIR / "MERIA_global_plastic_nearest_S1_SLC_before_after.csv")
        templates = MODULE.build_scene_templates("Global", MODULE.GLOBAL_DIR, global_rows)
        template = next(item for item in templates if item.obs_id == "91ea9edc-67b4-4211-8532-35deec4a3148" and item.role == "after")
        self.assertEqual(template.scene_id, "91ea9edc-67b4-4211-8532-35deec4a3148_Ghana_after_20181105T181652")
        self.assertEqual(template.shapefile_path.parent.name, "digitised_patches")


if __name__ == "__main__":
    unittest.main()
