"""Inventory, replace and verify existing scene and subswath texture products."""
import argparse
from collections import Counter
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import tempfile

import numpy as np
import rasterio as rio

from .fixed_glcm import KEYS, VERSION, generate, grid

PENDING = ".glcm-backfill.pending"
RECORD = "fixed_glcm"


@contextmanager
def scene_lock(directory, *, shared=False):
    """Lock the stable directory inode on Skua. Readers share the writer's lock."""
    if os.name == "nt":
        import msvcrt
        token = hashlib.sha256(str(directory.resolve()).casefold().encode()).hexdigest()
        with (Path(tempfile.gettempdir()) / ("glcm-" + token + ".lock")).open("a+b") as handle:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fd = os.open(directory, os.O_RDONLY)
        try:
            fcntl.flock(fd, (fcntl.LOCK_SH if shared else fcntl.LOCK_EX) | fcntl.LOCK_NB)
            yield
        finally:
            os.close(fd)


def atomic_json(path, value):
    temp = path.with_name("." + path.name + ".new")
    temp.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def bundles(path, manifest):
    items = [("scene", manifest.get("outputs") or {}, path.parent)]
    for swath, values in (manifest.get("subswath_outputs") or {}).items():
        if swath not in ("IW1", "IW2", "IW3"):
            raise ValueError(f"Unexpected sub-swath name: {swath}")
        items.append((swath, values, path.parent / "subswaths" / swath))
    plans = []
    for name, values, folder in items:
        if not any(values.values()):
            continue
        source_name = Path(str(values.get("vv_refined_lee_db") or "").replace("\\", "/")).name
        if not source_name.endswith("_vv_refined_lee_db.tif"):
            raise ValueError(f"{name}: missing Refined Lee VV dB in manifest")
        source = folder / source_name
        stem = source_name.removesuffix("vv_refined_lee_db.tif")
        targets = [folder / (stem + key + ".tif") for key in KEYS]
        for key, target in zip(KEYS, targets):
            recorded = str(values.get(key) or "").replace("\\", "/")
            if recorded and Path(recorded).name != target.name:
                raise ValueError(f"{key}: unexpected manifest path {recorded}")
            if not recorded:
                values[key] = str(values["vv_refined_lee_db"])[:-len("vv_refined_lee_db.tif")] + target.name[len(stem):]
        paths = [source, *targets]
        if any(not f.resolve().is_relative_to(path.parent.resolve()) for f in paths):
            raise ValueError("Raster outside scene folder")
        if len(set(f.resolve() for f in paths)) != len(paths):
            raise ValueError("Raster paths are not distinct")
        plans.append((name, source, targets))
    if not plans:
        raise ValueError("No populated scene or sub-swath output bundle")
    return plans


def inputs(name, source, processing, allow_unknown):
    owner = source.with_name(source.stem + "_owner.tif")
    with rio.open(source) as src:
        if src.count != 1 or not src.crs:
            raise ValueError(f"Invalid VV grid: {source}")
        if owner.is_file():
            with rio.open(owner) as ds:
                if grid(ds) != grid(src) or ds.count != 1 or ds.dtypes[0] != "uint8":
                    raise ValueError(f"Invalid ownership grid: {owner}")
                generation = src.tags().get("owner_generation")
                if generation and ds.tags().get("owner_generation") != generation:
                    raise ValueError(f"Stale ownership grid: {owner}")
            policy = "same-owner-only"
        elif src.tags().get("owner_generation"):
            raise ValueError(f"Missing recorded ownership grid: {owner}")
        elif name != "scene" or len(processing.get("processed_subswaths") or []) == 1:
            owner, policy = None, "single-subswath"
        elif allow_unknown:
            owner, policy = None, "unknown-joins-unmasked"
        else:
            raise ValueError(f"No sub-swath ownership for {source.name}; see runbook")
    files = [source, owner] if owner else [source]
    stamps = [(f.name, f.stat().st_size, f.stat().st_mtime_ns) for f in files]
    signature = hashlib.sha256(json.dumps([VERSION, policy, stamps]).encode()).hexdigest()
    return owner, policy, signature


def current(source, files, signature, *, verify=False):
    with rio.open(source) as src:
        for key, path in zip(KEYS, files):
            if not path.is_file():
                return False
            with rio.open(path) as ds:
                tags = ds.tags()
                if (grid(ds) != grid(src) or ds.count != 1 or ds.dtypes[0] != "float32"
                    or tags.get("glcm_version") != VERSION or tags.get("glcm_metric") != key
                    or tags.get("input_signature") != signature):
                    return False
                if verify:
                    valid_count = 0
                    high = {"vv_glcm_mean": 31, "vv_glcm_std": 15.5, "vv_glcm_entropy": np.log2(144)}[key]
                    for _, w in ds.block_windows(1):
                        data = ds.read(1, window=w)
                        valid = data[~np.isnan(data)]
                        if valid.size and (valid.min() < -1e-5 or valid.max() > high + 1e-5):
                            raise ValueError(f"Invalid texture values in {path}, {w}")
                        valid_count += valid.size
                    if not valid_count:
                        raise ValueError(f"Empty raster: {path}")
    return True


def process(path, mode, allow_unknown):
    with scene_lock(path.parent, shared=mode != "apply"):
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        processing = payload.setdefault("processing", {})
        if payload.get("status") != "processed":
            raise ValueError(f"Scene status is {payload.get('status')!r}")
        pending = path.parent / PENDING
        plans = bundles(path, payload)
        work = []
        record = {"version": VERSION, "bundles": {}}
        for name, source, targets in plans:
            owner, policy, signature = inputs(name, source, processing, allow_unknown)
            record["bundles"][name] = {"signature": signature, "seam_policy": policy}
            if not current(source, targets, signature, verify=mode == "verify"):
                work.append((name, source, targets, owner, signature, policy))
        policies = ",".join(sorted({v["seam_policy"] for v in record["bundles"].values()}))
        if not work and not pending.exists() and processing.get(RECORD) == record:
            return "current", policies
        if mode == "verify":
            raise ValueError("Pending, stale or missing fixed textures/manifest")
        if mode == "plan":
            return "needs-backfill", policies
        # A persistent marker also protects readers after a writer is interrupted.
        # Retrying regenerates stale/missing members from VV, never from legacy GLCM.
        atomic_json(pending, {"manifest": path.name, "version": VERSION})
        for name, source, targets, owner, signature, policy in work:
            staged = [f.with_name("." + f.stem + ".backfill.tif") for f in targets]
            generate(source, owner, staged, signature, policy)
            if inputs(name, source, processing, allow_unknown)[2] != signature:
                raise ValueError(f"Input changed during backfill: {source}")
            if not current(source, staged, signature):
                raise ValueError(f"Staged output validation failed: {source}")
            for temp, target in zip(staged, targets):
                for ext in (".aux.xml", ".ovr", ".msk"):
                    Path(str(target) + ext).unlink(missing_ok=True)
                os.replace(temp, target)
        processing[RECORD] = record
        atomic_json(path, payload)
        pending.unlink()
        return "updated", policies


def add_arguments(parser):
    parser.add_argument("--root", required=True, type=Path, help="Processed output tree")
    parser.add_argument("--mode", choices=["plan", "apply", "verify"], default="plan")
    parser.add_argument("--allow-unknown-seams", action="store_true",
                        help="Permit fixed-bin results without an ownership mask in legacy mosaics")


def run(args):
    paths = sorted(args.root.rglob("*_slc_manifest.json"))
    if not paths:
        print(f"No scene manifests under {args.root}", flush=True)
        return 1
    counts = Counter()
    for path in paths:
        try:
            status, detail = process(path, args.mode, args.allow_unknown_seams)
        except (ValueError, OSError, RuntimeError, KeyError) as exc:
            status, detail = "blocked", str(exc)
        counts[status] += 1
        print(f"{status:15} {path}  {detail}", flush=True)
    print(f"{VERSION}: {dict(counts)}", flush=True)
    return int(bool(counts["blocked"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    add_arguments(parser)
    raise SystemExit(run(parser.parse_args()))

