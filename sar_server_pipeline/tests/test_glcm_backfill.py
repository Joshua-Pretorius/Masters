import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import rasterio as rio
from rasterio.transform import from_origin

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.glcm_backfill import KEYS, PENDING, VERSION, process
from pipeline.fixed_glcm import texture_tile
from pipeline.cli import main
from stages.patch_extract import run_patch_extract
from pipeline.manifest import load_manifest
from test_pipeline import build_manifest


def save(path, data, nodata=np.nan):
    with rio.open(path, "w", driver="GTiff", width=data.shape[1], height=data.shape[0],
                  count=1, dtype=data.dtype, transform=from_origin(0, 4, 1, 1),
                  crs="EPSG:4326", nodata=nodata) as ds:
        ds.write(data, 1)


class TextureBackfillTests(unittest.TestCase):
    def test_matches_explicit_matrix_and_masks(self):
        raw = np.random.default_rng(22).uniform(-40, 6, (9, 9))
        valid = np.ones(raw.shape, dtype=bool)
        owner = np.ones(raw.shape, dtype="uint8")
        owner[:, 7:] = 2
        valid[0, 0] = False
        calculated = texture_tile(raw, valid, owner)
        self.assertTrue(np.isnan(calculated[:, 0, 0]).all())
        self.assertTrue(np.isnan(calculated[:, :, 3:]).all())
        q = (raw[2:7, 2:7] + 32).clip(0, 31).astype(int)
        counts = np.zeros((32, 32))
        for y, x in np.ndindex(5, 5):
            for dy, dx in np.ndindex(3, 3):
                row, col = y + dy - 1, x + dx - 1
                if (row, col) != (y, x) and 0 <= row < 5 and 0 <= col < 5:
                    counts[q[y, x], q[row, col]] += 1
        probs = counts / counts.sum()
        marginal = probs.sum(1)
        levels = np.arange(32)
        mean = marginal @ levels
        entropy = -np.sum(probs[probs > 0] * np.log2(probs[probs > 0]))
        np.testing.assert_allclose(calculated[:, 2, 2],
                                   [mean, np.sqrt(marginal @ ((levels-mean)**2)), entropy], rtol=1e-6)

    def test_publish_resume_verify_and_extract(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            job = load_manifest(build_manifest(root))
            path = next(job.outputs.processed_root.rglob("*_slc_manifest.json"))
            payload = json.loads(path.read_text())
            payload["status"] = "processed"
            payload["processing"] = {"processed_subswaths": ["IW1", "IW2"]}
            path.write_text(json.dumps(payload))
            src = Path(payload["outputs"]["vv_refined_lee_db"])
            data = np.random.default_rng(11).uniform(-30, 0, (21, 140)).astype("float32")
            save(src, data)
            self.assertEqual(main(["glcm_backfill", "--root", str(job.outputs.processed_root)]), 1)
            self.assertEqual(process(path, "plan", True), ("needs-backfill", "unknown-joins-unmasked"))
            owners = np.ones(data.shape, dtype="uint8")
            owners[:, 67:] = 2
            save(src.with_name(src.stem + "_owner.tif"), owners, 0)
            mean = Path(payload["outputs"][KEYS[0]])
            std = Path(payload["outputs"][KEYS[1]])
            original = os.replace

            def interrupt(source, destination):
                if destination == std:
                    raise OSError("injected interrupted publish")
                original(source, destination)

            with patch("pipeline.glcm_backfill.os.replace", side_effect=interrupt):
                with self.assertRaisesRegex(OSError, "interrupted"):
                    process(path, "apply", False)
            self.assertTrue((path.parent / PENDING).exists())
            with self.assertRaisesRegex(ValueError, "Interrupted"):
                run_patch_extract(job)
            self.assertEqual(process(path, "apply", False)[0], "updated")
            before = mean.stat().st_mtime_ns
            self.assertEqual(process(path, "verify", False)[0], "current")
            self.assertEqual(process(path, "apply", False)[0], "current")
            self.assertEqual(mean.stat().st_mtime_ns, before)
            with rio.open(mean) as ds:
                image = ds.read(1)
                self.assertTrue(np.isnan(image[:, 65:69]).all())
                self.assertTrue(np.isfinite(image[10, 127:130]).all())
                np.testing.assert_allclose(image[10, 128],
                    texture_tile(data[8:13, 126:131], np.ones((5, 5), bool))[0, 0, 0])
            self.assertEqual(run_patch_extract(job).processed_features, 1)
            with rio.open(next(job.outputs.patches_root.rglob("*_image.tif"))) as ds:
                self.assertEqual(ds.tags()["glcm_version"], VERSION)
            with rio.open(src, "r+") as ds:
                ds.update_tags(revision="changed")
            self.assertEqual(process(path, "plan", False)[0], "needs-backfill")
            with self.assertRaisesRegex(ValueError, "Stale"):
                run_patch_extract(job)

