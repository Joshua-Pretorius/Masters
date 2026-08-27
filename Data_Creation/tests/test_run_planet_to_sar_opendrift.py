from __future__ import annotations

import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import xarray as xr


MODULE_PATH = Path(__file__).resolve().parents[2] / "Domain_SSL" / "Scripts" / "Preprocessing" / "run_planet_to_sar_opendrift.py"
SPEC = importlib.util.spec_from_file_location("run_planet_to_sar_opendrift", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Could not load module spec for {MODULE_PATH}")

stub = types.ModuleType("run_opendrift_batch")
stub.PlastDrift = object
stub.reader_netCDF_CF_generic = types.SimpleNamespace(Reader=object)
sys.modules.setdefault("run_opendrift_batch", stub)

MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class RunPlanetToSarOpenDriftTests(unittest.TestCase):
    def test_installed_opendrift_is_used_when_legacy_helper_is_missing(self) -> None:
        installed_plastdrift = types.SimpleNamespace(PlastDrift=object())
        installed_reader = types.SimpleNamespace(Reader=object())

        def load(name: str):
            if name == "run_opendrift_batch":
                raise ModuleNotFoundError("No module named 'run_opendrift_batch'", name=name)
            if name == "opendrift.models.plastdrift":
                return installed_plastdrift
            if name == "opendrift.readers.reader_netCDF_CF_generic":
                return installed_reader
            raise AssertionError(name)

        with mock.patch.object(MODULE.importlib, "import_module", side_effect=load):
            model, reader = MODULE.load_opendrift_components()

        self.assertIs(model, installed_plastdrift.PlastDrift)
        self.assertIs(reader, installed_reader)

    def test_resolve_drift_tools_dir_falls_back_to_workspace_drift_folder(self) -> None:
        local_drift = MODULE_PATH.resolve().parents[3] / "Drift"

        with mock.patch.object(
            MODULE.Path,
            "exists",
            autospec=True,
            side_effect=lambda path: Path(path) == local_drift,
        ):
            resolved = MODULE.resolve_drift_tools_dir(MODULE_PATH)

        self.assertEqual(resolved, local_drift)

    def test_utm_crs_for_lonlat_picks_ghana_zone(self) -> None:
        self.assertEqual(MODULE.utm_crs_for_lonlat(-0.65, 5.30).to_epsg(), 32630)

    def test_water_snapper_moves_land_points_to_nearest_water_cell(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            forcing_nc = Path(tmp_dir) / "forcing.nc"
            lats = np.array([5.300, 5.301], dtype="float32")
            lons = np.array([-0.650, -0.649], dtype="float32")
            lon2, lat2 = np.meshgrid(lons, lats)
            land_mask = np.array([[[0.0, 0.0], [1.0, 1.0]]], dtype="float32")
            ds = xr.Dataset(
                coords={
                    "time": ("time", np.array(["2018-10-30T18:00:00"], dtype="datetime64[ns]")),
                    "y": ("y", np.arange(len(lats), dtype=np.int32)),
                    "x": ("x", np.arange(len(lons), dtype=np.int32)),
                    "latitude": (("y", "x"), lat2),
                    "longitude": (("y", "x"), lon2),
                },
                data_vars={
                    "land_binary_mask": (("time", "y", "x"), land_mask),
                },
            )
            ds.to_netcdf(forcing_nc)
            ds.close()

            snapper = MODULE.WaterSnapper.from_forcing(forcing_nc)
            lon, lat, snapped, distances, outside = snapper.snap(
                np.array([-0.6492, -0.6498], dtype="float64"),
                np.array([5.3008, 5.3002], dtype="float64"),
            )

        self.assertTrue(snapped[0])
        self.assertFalse(snapped[1])
        self.assertGreater(distances[0], 0.0)
        self.assertEqual(outside, 0)
        self.assertAlmostEqual(lon[0], -0.649, places=6)
        self.assertAlmostEqual(lat[0], 5.300, places=6)


if __name__ == "__main__":
    unittest.main()
