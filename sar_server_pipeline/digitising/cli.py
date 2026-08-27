from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Sequence

from .catalog import build_task_catalog
from .workflow import Environment, import_batch, prepare_batch, reconcile_task


def _environment(args: argparse.Namespace) -> Environment:
    return Environment(
        data_root=Path(args.data_root),
        catalog_root=Path(args.catalog_root),
        drift_tools_root=Path(args.drift_tools_root),
        remote=args.remote,
        remote_data_root=args.remote_data_root,
        desktop_root=args.desktop_root,
        cmems_credentials=Path(args.cmems_credentials),
        cdsapirc=Path(args.cdsapirc),
    )


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--data-root", default=os.environ.get("DATA_ROOT", "/data"))
    parser.add_argument("--catalog-root", default=os.environ.get("CATALOG_ROOT", "/repo/Data_Creation"))
    parser.add_argument(
        "--drift-tools-root",
        default=os.environ.get("DRIFT_TOOLS_ROOT", "/repo/Domain_SSL/Scripts/Preprocessing"),
    )
    parser.add_argument("--remote", default=os.environ.get("DIGITISING_REMOTE", "bolelang@146.64.214.137"))
    parser.add_argument(
        "--remote-data-root",
        default=os.environ.get("REMOTE_DATA_ROOT", "/mnt/storage/bolelang_mount/Joshua/sar-data"),
    )
    parser.add_argument(
        "--desktop-root",
        default=os.environ.get("DESKTOP_ROOT", "/home/bsibolla/Desktop/Joshua"),
    )
    parser.add_argument(
        "--cmems-credentials",
        default=os.environ.get("CMEMS_CREDENTIALS", "/run/secrets/cmems_credentials"),
    )
    parser.add_argument("--cdsapirc", default=os.environ.get("CDSAPIRC", "/run/secrets/cdsapirc"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="digitising", description="Prepare and import portable MERIA QGIS tasks.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="Prepare the next pending QGIS digitisation batch.")
    _common(prepare)
    prepare.add_argument("--dataset", choices=("all", "sa", "global"), default="all")
    prepare.add_argument("--limit", type=int, required=True)
    prepare.add_argument("--batch-name", required=True)
    prepare.add_argument("--task", action="append", default=[], dest="task_ids")
    prepare.add_argument("--prediction-mode", choices=("auto", "cached-only", "skip"), default="auto")
    prepare.add_argument("--dry-run", action="store_true")

    import_parser = subparsers.add_parser("import", help="Validate and import a returned desktop-QGIS batch.")
    _common(import_parser)
    import_parser.add_argument("--batch", required=True)

    validate = subparsers.add_parser("validate-export", help="Validate populated tasks and refresh canonical exports.")
    _common(validate)
    validate.add_argument("--dataset", choices=("all", "sa", "global"), default="all")
    selection = validate.add_mutually_exclusive_group(required=True)
    selection.add_argument("--all", action="store_true")
    selection.add_argument("--task", action="append", default=[], dest="task_ids")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)
    environment = _environment(args)
    if args.command == "prepare":
        result = prepare_batch(
            environment,
            dataset=args.dataset,
            limit=args.limit,
            batch_name=args.batch_name,
            task_ids=args.task_ids,
            prediction_mode=args.prediction_mode,
            dry_run=args.dry_run,
        )
        print(json.dumps({
            "batch_name": result.batch_name,
            "selected": result.selected,
            "skipped_complete": result.skipped_complete,
            "unavailable": result.unavailable,
            "pull_command": result.pull_command,
            "return_command": result.return_command,
        }, indent=2))
        return 0
    if args.command == "import":
        report = import_batch(environment, args.batch)
        print(json.dumps(report, indent=2))
        return 1 if report["invalid"] or report["conflicts"] else 0

    tasks = build_task_catalog(environment.catalog_root, environment.processed_root, args.dataset)
    selected = set(args.task_ids)
    results: dict[str, object] = {}
    for task in tasks:
        if selected and task.task_id not in selected:
            continue
        validation = reconcile_task(environment, task)
        results[task.task_id] = {
            "valid": validation.valid,
            "feature_count": validation.feature_count,
            "errors": validation.errors,
        }
    missing = selected - set(results)
    if missing:
        raise ValueError("Unknown or unprocessed task id(s): " + ", ".join(sorted(missing)))
    print(json.dumps(results, indent=2))
    return 0 if all(item["valid"] for item in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
