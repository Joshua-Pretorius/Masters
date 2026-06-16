#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Recursively fix/extract all .zip files under BASE.
- Works even if a same-named top-level folder already exists but is empty or incomplete.
- Extracts only missing/mismatched files (size check) to avoid redundant work.
- Prevents Zip Slip path traversal.
- Prints a concise summary.

Tested with Sentinel-1/2 style archives that unpack to *.SAFE folders.

Run with:  python extract_all.py
Or paste into QGIS Python Console as a single block.
"""

from pathlib import Path, PurePosixPath
import zipfile
import os
import sys
import time
from typing import Iterable, Tuple

# === CONFIG ===
BASE = Path(r"D:\Masters\MERIA\raw_grd")  # change if needed


def ensure_dir(p: Path) -> None:
    if not p.exists():
        p.mkdir(parents=True, exist_ok=True)


def is_within_directory(base: Path, target: Path) -> bool:
    base = base.resolve()
    target = target.resolve()
    try:
        target.relative_to(base)
        return True
    except ValueError:
        return False


def zip_top_levels(zp: zipfile.ZipFile) -> Tuple[str, ...]:
    """Return distinct top-level entries from the zip (first path segment)."""
    tops = set()
    for name in zp.namelist():
        if not name:
            continue
        parts = PurePosixPath(name).parts
        if parts:
            tops.add(parts[0])
    return tuple(sorted(tops))


def file_needs_extract(target: Path, zinfo: zipfile.ZipInfo) -> bool:
    """
    Decide if we should extract this member:
      - If target missing -> True
      - If target exists but size != uncompressed size -> True
      - Else -> False
    """
    if target.is_dir():
        return False  # it's already a directory
    if not target.exists():
        return True
    try:
        stat = target.stat()
        # zinfo.file_size is the uncompressed size in bytes
        if stat.st_size != zinfo.file_size:
            return True
    except OSError:
        return True
    return False


def extract_member(zf: zipfile.ZipFile, member: zipfile.ZipInfo, dest_root: Path) -> bool:
    """
    Safely extract a single member to dest_root.
    Returns True if extraction happened (file written), False otherwise.
    """
    # Normalize to POSIX-like path components from zip
    member_path = PurePosixPath(member.filename)

    # Skip directory entries explicitly (we'll create dirs as needed)
    if str(member.filename).endswith("/"):
        # Ensure directory exists
        target_dir = dest_root / Path(*member_path.parts)
        ensure_dir(target_dir)
        return False

    target = dest_root / Path(*member_path.parts)

    # Zip Slip protection
    if not is_within_directory(dest_root, target):
        raise RuntimeError(f"Blocked path traversal: {member.filename}")

    # Ensure parent directory exists
    ensure_dir(target.parent)

    # Check if extraction required
    if not file_needs_extract(target, member):
        return False

    # Extract
    with zf.open(member, "r") as src, open(target, "wb") as dst:
        # Stream copy to handle large files
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk:
                break
            dst.write(chunk)

    # (Optional) set modified time from ZIP info
    try:
        dt = time.mktime((*member.date_time, 0, 0, -1))
        os.utime(target, (dt, dt))
    except Exception:
        pass

    return True


def process_zip(zip_path: Path) -> Tuple[int, int]:
    """
    Extract (or complete) the contents of zip_path into its parent directory.
    Returns (extracted_files_count, skipped_files_count).
    """
    extracted = 0
    skipped = 0

    parent = zip_path.parent
    ensure_dir(parent)

    with zipfile.ZipFile(zip_path) as zf:
        tops = zip_top_levels(zf)
        # We always extract into the zip's parent directory so that
        # expected top-level folders (e.g., *.SAFE) end up beside the .zip
        dest_root = parent

        for member in zf.infolist():
            try:
                did = extract_member(zf, member, dest_root)
                if did:
                    extracted += 1
                else:
                    skipped += 1
            except Exception as e:
                print(f"  ! Error extracting {zip_path.name}:{member.filename} -> {e}")

    return extracted, skipped


def find_all_zips(base: Path) -> Iterable[Path]:
    return sorted(base.rglob("*.zip"))


def main() -> int:
    if not BASE.is_dir():
        print(f"Base folder not found: {BASE}")
        return 2

    zips = list(find_all_zips(BASE))
    if not zips:
        print(f"No .zip files found under: {BASE}")
        return 0

    print(f"Found {len(zips)} zip(s) under {BASE}\n")

    total_extracted = 0
    total_skipped = 0
    failures = 0

    for idx, zp in enumerate(zips, 1):
        print(f"[{idx}/{len(zips)}] {zp}")
        try:
            ex, sk = process_zip(zp)
            total_extracted += ex
            total_skipped += sk
            print(f"    -> extracted: {ex}, skipped (up-to-date/dirs): {sk}")
        except Exception as e:
            failures += 1
            print(f"  !! Failed processing {zp}: {e}")

    print("\n=== Summary ===")
    print(f"Zips processed : {len(zips)}")
    print(f"Files extracted: {total_extracted}")
    print(f"Skipped (dirs/up-to-date): {total_skipped}")
    print(f"Failures       : {failures}")

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())