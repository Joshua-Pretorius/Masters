#!/usr/bin/env python3
from __future__ import annotations

import csv
from pathlib import Path

import process_meria_sa_slc_targets as sa


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "Data_Creation" / "meria_global_s1_slc"
MATCH_CSV = DATA_DIR / "MERIA_global_plastic_nearest_S1_SLC_before_after.csv"
POINTS_CSV = DATA_DIR / "MERIA_global_plastic_points.csv"
OUT_ROOT = DATA_DIR / "processed_slc"
WORK_ROOT = DATA_DIR / "_slc_work"


def default_targets() -> tuple[tuple[str, str], ...]:
    targets: list[tuple[str, str]] = []
    with MATCH_CSV.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            for role in ("before", "after"):
                granule = (row.get(f"{role}_name") or "").strip()
                if granule and granule != "-":
                    targets.append((row["obs_id"], role))
    return tuple(targets)


def main() -> None:
    sa.DATA_DIR = DATA_DIR
    sa.MATCH_CSV = MATCH_CSV
    sa.POINTS_CSV = POINTS_CSV
    sa.OUT_ROOT = OUT_ROOT
    sa.WORK_ROOT = WORK_ROOT
    sa.FOLDER_NAME_STYLE = "area-first"
    sa.DEFAULT_TARGETS = default_targets()
    sa.main()


if __name__ == "__main__":
    main()
