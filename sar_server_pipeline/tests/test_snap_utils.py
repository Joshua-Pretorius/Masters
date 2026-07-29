from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "vendor"
    / "Domain_SSL"
    / "Scripts"
    / "Preprocessing"
    / "snap_utils.py"
)
SPEC = importlib.util.spec_from_file_location("domain_ssl_snap_utils", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
snap_utils = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(snap_utils)


class SnapUtilsTests(unittest.TestCase):
    def test_run_graph_appends_extra_gpt_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            graph = Path(tmp_dir) / "graph.xml"
            graph.write_text("<graph />", encoding="utf-8")

            with mock.patch.object(
                snap_utils.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 0, stdout=""),
            ) as run:
                snap_utils.run_graph(
                    "gpt",
                    graph,
                    cache_gb=32,
                    workers=1,
                    extra_args=["-x", "-Dexample=value"],
                )

            self.assertEqual(
                run.call_args.args[0],
                [
                    "gpt",
                    str(graph),
                    "-c",
                    "32G",
                    "-q",
                    "1",
                    "-x",
                    "-Dsnap.jai.defaultTileSize=256",
                    "-x",
                    "-Dexample=value",
                ],
            )

    def test_big_tiff_export_uses_bounded_tiles_and_cache_flushing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            out_tif = root / "texture.tif"

            def complete_export(_gpt, graph_path, **_kwargs) -> None:
                graph = ET.parse(graph_path)
                output = graph.findtext(".//node[@id='Write']/parameters/file")
                assert output is not None
                Path(output).write_bytes(b"completed BigTIFF")

            with mock.patch.object(snap_utils, "run_graph", side_effect=complete_export) as run_graph:
                snap_utils.export_to_geotiff(
                    "gpt",
                    root / "texture.dim",
                    out_tif,
                    cache_gb=32,
                    workers=1,
                    windows_paths=False,
                )

            kwargs = run_graph.call_args.kwargs
            self.assertEqual(kwargs["cache_gb"], 32)
            self.assertEqual(kwargs["workers"], 1)
            self.assertEqual(
                kwargs["extra_args"],
                [
                    "-Dsnap.dataio.bigtiff.tiling.width=512",
                    "-Dsnap.dataio.bigtiff.tiling.height=512",
                ],
            )
            self.assertEqual(out_tif.read_bytes(), b"completed BigTIFF")
            self.assertFalse((root / "texture.partial.tif").exists())

    def test_failed_big_tiff_export_removes_partial_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            out_tif = root / "texture.tif"

            def fail_export(_gpt, graph_path, **_kwargs) -> None:
                graph = ET.parse(graph_path)
                output = graph.findtext(".//node[@id='Write']/parameters/file")
                assert output is not None
                Path(output).write_bytes(b"incomplete")
                raise RuntimeError("gpt failed")

            with mock.patch.object(snap_utils, "run_graph", side_effect=fail_export):
                with self.assertRaisesRegex(RuntimeError, "gpt failed"):
                    snap_utils.export_to_geotiff(
                        "gpt",
                        root / "texture.dim",
                        out_tif,
                        windows_paths=False,
                    )

            self.assertFalse(out_tif.exists())
            self.assertFalse((root / "texture.partial.tif").exists())


if __name__ == "__main__":
    unittest.main()
