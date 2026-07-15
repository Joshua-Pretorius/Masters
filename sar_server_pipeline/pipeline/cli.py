from __future__ import annotations

import argparse
from typing import Sequence

from .manifest import load_manifest
from .runner import STAGE_ORDER, run_workflow


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser("pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in (*STAGE_ORDER, "run_all"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--manifest", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    manifest = load_manifest(args.manifest)
    if args.command == "run_all":
        run_workflow(manifest, stage_names=STAGE_ORDER)
    else:
        run_workflow(manifest, stage_names=(args.command,))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
