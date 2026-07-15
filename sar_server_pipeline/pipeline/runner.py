from __future__ import annotations

import json
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from .manifest import Manifest


STAGE_ORDER = ("slc_process", "patch_extract", "patch_stack")


@dataclass(frozen=True)
class StageRunResult:
    stage_name: str
    skipped: bool
    payload: dict[str, Any]


def stage_marker_path(manifest: Manifest, stage_name: str) -> Path:
    return manifest.outputs.manifests_root / manifest.run_id / "stages" / f"{stage_name}.json"


def _normalize_payload(result: Any) -> dict[str, Any]:
    if result is None:
        return {}
    if isinstance(result, dict):
        return result
    if is_dataclass(result):
        return asdict(result)
    return result.__dict__.copy()


def read_stage_marker(manifest: Manifest, stage_name: str) -> dict[str, Any] | None:
    path = stage_marker_path(manifest, stage_name)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_stage_marker(manifest: Manifest, stage_name: str, *, status: str, payload: dict[str, Any]) -> None:
    marker_path = stage_marker_path(manifest, stage_name)
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(
        json.dumps(
            {
                "run_id": manifest.run_id,
                "stage_name": stage_name,
                "status": status,
                "written_at_utc": datetime.now(UTC).isoformat(),
                "payload": payload,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def run_stage(manifest: Manifest, stage_name: str, handler: Callable[[Manifest], Any]) -> StageRunResult:
    config = manifest.stages[stage_name]
    marker = read_stage_marker(manifest, stage_name)
    if marker and marker.get("status") == "success" and not config.overwrite:
        return StageRunResult(stage_name=stage_name, skipped=True, payload=marker.get("payload", {}))

    try:
        payload = _normalize_payload(handler(manifest))
    except Exception as exc:
        write_stage_marker(manifest, stage_name, status="failed", payload={"error": str(exc)})
        raise

    write_stage_marker(manifest, stage_name, status="success", payload=payload)
    return StageRunResult(stage_name=stage_name, skipped=False, payload=payload)


def run_workflow(
    manifest: Manifest,
    *,
    stage_names: tuple[str, ...] = STAGE_ORDER,
    stage_registry: dict[str, Callable[[Manifest], Any]] | None = None,
) -> list[StageRunResult]:
    if stage_registry is None:
        from stages.patch_extract import run_patch_extract
        from stages.patch_stack import run_patch_stack
        from stages.slc_process import run_slc_process

        stage_registry = {
            "slc_process": run_slc_process,
            "patch_extract": run_patch_extract,
            "patch_stack": run_patch_stack,
        }

    results: list[StageRunResult] = []
    for stage_name in stage_names:
        config = manifest.stages[stage_name]
        if not config.enabled:
            continue
        results.append(run_stage(manifest, stage_name, stage_registry[stage_name]))
    return results
