#!/usr/bin/env python3
"""
Resolve the nearest Planet scene for every Ocean Scan patch without downloading.

Outputs:
- CSV with one row per patch and its resolved Planet item
- JSON summary with unique-item counts and rough storage estimate

Example:
  python resolve_oceanscan_planet_batch.py \
    "D:\\Masters\\ocean-scan-mireia-- marine litter signatures in sar images-e71e8ee6-e41d-4889-bb08-a821fb5e8bbd.json" \
    --api-key-file "D:\\Masters\\planet_api.txt" \
    --out-csv "D:\\Masters\\MERIA\\MERIA_Planet\\planet_resolution_report.csv" \
    --out-json "D:\\Masters\\MERIA\\MERIA_Planet\\planet_resolution_summary.json"
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
from pathlib import Path

import download_oceanscan_planet_scene as dl


LOG = logging.getLogger("planet_batch")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve nearest Planet scenes for all Ocean Scan patch observations."
    )
    parser.add_argument("input_json", type=Path, help="Ocean Scan campaign JSON")
    parser.add_argument(
        "--api-key-file",
        type=Path,
        required=True,
        help="Text file containing the Planet API key",
    )
    parser.add_argument(
        "--item-type",
        default=dl.DEFAULT_ITEM_TYPE,
        help=f"Planet item type to query. Default: {dl.DEFAULT_ITEM_TYPE}",
    )
    parser.add_argument(
        "--search-windows-hours",
        nargs="+",
        type=int,
        default=[12, 24, 72, 168, 720],
        help="Progressive search windows in hours around the patch timestamp.",
    )
    parser.add_argument(
        "--sample-size-bytes",
        type=int,
        default=574047726,
        help="Approximate bytes per scene for rough storage estimate.",
    )
    parser.add_argument(
        "--out-csv",
        type=Path,
        default=Path(r"D:\Masters\MERIA\MERIA_Planet\planet_resolution_report.csv"),
        help="CSV output path.",
    )
    parser.add_argument(
        "--out-json",
        type=Path,
        default=Path(r"D:\Masters\MERIA\MERIA_Planet\planet_resolution_summary.json"),
        help="JSON summary output path.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Console log level.",
    )
    return parser.parse_args()


def human_gib(value: int) -> float:
    return value / (1024 ** 3)


def main() -> int:
    args = parse_args()
    dl.configure_logging(args.log_level)

    args.input_json = dl.adapt_path(args.input_json)
    args.api_key_file = dl.adapt_path(args.api_key_file)
    args.out_csv = dl.adapt_path(args.out_csv)
    args.out_json = dl.adapt_path(args.out_json)

    api_key = dl.read_api_key(args.api_key_file)
    session = dl.planet_session(api_key)
    patches = dl.load_patch_records(args.input_json)

    LOG.info("Loaded %s polygon patch observations", len(patches))

    rows: list[dict[str, object]] = []
    unique_items: dict[str, dict[str, object]] = {}
    failures: list[dict[str, object]] = []

    for patch in patches:
        try:
            window_hours, feature, _payload = dl.search_nearest_item(
                session=session,
                patch=patch,
                item_type=args.item_type,
                search_windows_hours=args.search_windows_hours,
            )
            item_id = feature["id"]
            acquired = feature.get("properties", {}).get("acquired", "")
            delta_hours = abs(
                (dl.parse_utc(acquired) - dl.parse_utc(patch["timestamp"])).total_seconds()
            ) / 3600.0
            row = {
                "patch_index": patch["patch_index"],
                "obs_id": patch["obs_id"],
                "source_id": patch["source_id"],
                "patch_timestamp": patch["timestamp"],
                "planet_item_id": item_id,
                "planet_acquired": acquired,
                "delta_hours": round(delta_hours, 3),
                "search_window_hours": window_hours,
                "centroid_lon": round(patch["centroid_lon"], 6),
                "centroid_lat": round(patch["centroid_lat"], 6),
            }
            rows.append(row)
            unique_items.setdefault(
                item_id,
                {
                    "planet_item_id": item_id,
                    "planet_acquired": acquired,
                    "matched_patch_count": 0,
                },
            )
            unique_items[item_id]["matched_patch_count"] += 1
            LOG.info(
                "Resolved patch %03d -> %s (delta %.3f h)",
                patch["patch_index"],
                item_id,
                delta_hours,
            )
        except Exception as exc:
            failure = {
                "patch_index": patch["patch_index"],
                "obs_id": patch["obs_id"],
                "error": str(exc),
            }
            failures.append(failure)
            LOG.error(
                "Failed patch %03d (%s): %s",
                patch["patch_index"],
                patch["obs_id"],
                exc,
            )

    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.out_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "patch_index",
                "obs_id",
                "source_id",
                "patch_timestamp",
                "planet_item_id",
                "planet_acquired",
                "delta_hours",
                "search_window_hours",
                "centroid_lon",
                "centroid_lat",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    unique_count = len(unique_items)
    estimated_bytes = unique_count * args.sample_size_bytes
    summary = {
        "input_json": str(args.input_json),
        "total_patch_observations": len(patches),
        "resolved_patch_observations": len(rows),
        "failed_patch_observations": len(failures),
        "unique_planet_items": unique_count,
        "estimated_total_bytes": estimated_bytes,
        "estimated_total_gib": round(human_gib(estimated_bytes), 3),
        "estimated_total_gb": round(estimated_bytes / 1_000_000_000, 3),
        "sample_size_bytes": args.sample_size_bytes,
        "unique_items": sorted(unique_items.values(), key=lambda x: str(x["planet_item_id"])),
        "failures": failures,
    }
    args.out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    LOG.info("Wrote CSV: %s", args.out_csv)
    LOG.info("Wrote JSON summary: %s", args.out_json)
    LOG.info("Resolved patches: %s / %s", len(rows), len(patches))
    LOG.info("Unique Planet items: %s", unique_count)
    LOG.info(
        "Estimated storage: %.3f GiB (%.3f GB)",
        summary["estimated_total_gib"],
        summary["estimated_total_gb"],
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
