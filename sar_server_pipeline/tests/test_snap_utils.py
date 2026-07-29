from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
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
                ["gpt", str(graph), "-c", "32G", "-q", "1", "-x", "-Dexample=value"],
            )

    def test_big_tiff_export_uses_bounded_tiles_and_cache_flushing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            with mock.patch.object(snap_utils, "run_graph") as run_graph:
                snap_utils.export_to_geotiff(
                    "gpt",
                    root / "texture.dim",
                    root / "texture.tif",
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
                    "-x",
                    "-Dsnap.dataio.bigtiff.tiling.width=512",
                    "-Dsnap.dataio.bigtiff.tiling.height=512",
                ],
            )


if __name__ == "__main__":
    unittest.main()
