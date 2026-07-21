from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from unittest import mock

from pipeline.manifest import Manifest


SERVER_REPO_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = SERVER_REPO_ROOT / "vendor"
DEFAULT_GRAPH_DIR = SERVER_REPO_ROOT / "docker" / "snap_graphs"


@dataclass(frozen=True)
class SlcProcessResult:
    processor_script: str
    target_count: int


def _default_processor_script(dataset_mode: str) -> Path:
    script_name = "process_sa_slc_targets.py" if dataset_mode == "sa" else "process_global_slc_targets.py"
    return VENDOR_ROOT / "Data_Creation" / script_name


def _load_module(script_path: Path):
    spec = importlib.util.spec_from_file_location(f"server_s1_{script_path.stem}", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load SLC processor: {script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_slc_process(manifest: Manifest) -> SlcProcessResult:
    config = manifest.stages["slc_process"]
    script_path = Path(config.options.get("processor_script")) if config.options and config.options.get("processor_script") else _default_processor_script(manifest.dataset_mode)
    module = _load_module(script_path)

    module.MATCH_CSV = manifest.inputs.match_csv
    module.POINTS_CSV = manifest.inputs.points_csv
    # Keep shared SLC downloads on the mounted server data volume so multiple
    # targets and later container runs can reuse the same granule.
    module.DATA_DIR = manifest.inputs.raw_slc_root
    module.OUT_ROOT = manifest.outputs.processed_root
    module.WORK_ROOT = manifest.outputs.processed_root / "_slc_work"
    if manifest.dataset_mode == "global":
        module.FOLDER_NAME_STYLE = "area-first"

    argv = [script_path.name]
    for target in manifest.targets:
        argv.extend(["--target", target])
    argv.extend(["--out-root", str(manifest.outputs.processed_root)])
    argv.extend(["--work-root", str(module.WORK_ROOT)])
    argv.extend(["--graphs-dir", str(config.options.get("graphs_dir", DEFAULT_GRAPH_DIR) if config.options else DEFAULT_GRAPH_DIR)])
    argv.extend(["--subset-mode", manifest.processing.subset_mode])
    argv.extend(["--subswaths", ",".join(manifest.processing.subswaths)])
    argv.extend(["--workers", str(manifest.processing.workers)])
    argv.extend(["--cache-gb", str(manifest.processing.cache_gb)])
    if config.options and config.options.get("gpt"):
        argv.extend(["--gpt", str(config.options["gpt"])])
    if config.options and config.options.get("download_only"):
        argv.append("--download-only")
    if config.options and config.options.get("prepare_only"):
        argv.append("--prepare-only")
    if config.options and config.options.get("keep_zip"):
        argv.append("--keep-zip")
    if config.options and config.options.get("keep_safe"):
        argv.append("--keep-safe")
    if config.options and config.options.get("force"):
        argv.append("--force")
    argv.append("--verbose")

    with mock.patch.object(sys, "argv", argv):
        module.main()

    return SlcProcessResult(processor_script=str(script_path), target_count=len(manifest.targets))
