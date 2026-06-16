#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full SLC preprocessing for Ocean Scan target manifests.")
    parser.add_argument(
        "--manifest-root",
        default="/mnt/d/Masters/Domain_SSL/downloads_S1/ocean_scan_2017",
    )
    parser.add_argument("--graphs-dir", default="/mnt/d/Masters/sar_ml_pipeline/graphs")
    parser.add_argument("--out-root", default="/mnt/d/Masters/Domain_SSL/PreProccess/ocean_scan_2017")
    parser.add_argument("--workers", default="1")
    parser.add_argument("--cache-gb", default="4")
    parser.add_argument("--redo-complete", action="store_true")
    args = parser.parse_args()

    manifest_root = Path(args.manifest_root)
    manifests = sorted(manifest_root.glob("*/2017-*/manifest.json"))
    if not manifests:
        raise RuntimeError(f"No manifests found under {manifest_root}")

    for manifest in manifests:
        meta = json.loads(manifest.read_text(encoding="utf-8"))
        subswaths = ",".join(meta["slc"].get("subswaths") or [])
        if not subswaths:
            raise RuntimeError(f"No inferred subswaths in {manifest}")
        final_dir = Path(args.out_root) / f"aoi_{meta['aoi_id']}" / meta["date"] / "final"
        expected = []
        for subswath in subswaths.split(","):
            expected.extend(
                [
                    final_dir / f"slc_{subswath}_tex_tc.tif",
                    final_dir / f"slc_{subswath}_sigma0_tc.tif",
                    final_dir / f"slc_{subswath}_decomp_tc.tif",
                ]
            )
        if not args.redo_complete and expected and all(path.exists() for path in expected):
            print(f"\n=== Skipping complete {manifest} ===", flush=True)
            continue

        cmd = [
            "python3",
            "/mnt/d/Masters/Domain_SSL/Scripts/Preprocessing/preprocess_slc_full.py",
            "--manifest",
            str(manifest),
            "--graphs-dir",
            args.graphs_dir,
            "--out-root",
            args.out_root,
            "--subswaths",
            subswaths,
            "--workers",
            args.workers,
            "--cache-gb",
            args.cache_gb,
            "-v",
        ]
        print(f"\n=== Processing {manifest} | subswaths={subswaths} ===", flush=True)
        subprocess.run(cmd, check=True, cwd="/mnt/d/Masters")


if __name__ == "__main__":
    main()
