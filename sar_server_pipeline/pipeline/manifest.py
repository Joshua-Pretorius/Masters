from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_SAR_BAND_ORDER = (
    "vv_db",
    "vh_db",
    "vv_vh_ratio_db",
    "vv_minus_vh_db",
    "vv_glcm_mean",
    "vv_glcm_std",
    "vv_glcm_entropy",
    "decomp_entropy",
    "decomp_anisotropy",
    "decomp_alpha",
)
DEFAULT_BIOPHYSICAL_BANDS = ("uo", "vo", "swh")


@dataclass(frozen=True)
class Inputs:
    match_csv: Path
    points_csv: Path
    raw_slc_root: Path
    shapefiles_root: Path
    biophysical_root: Path | None


@dataclass(frozen=True)
class Outputs:
    processed_root: Path
    patches_root: Path
    stacks_root: Path
    logs_root: Path
    manifests_root: Path


@dataclass(frozen=True)
class StageConfig:
    enabled: bool = True
    overwrite: bool = False
    options: dict[str, Any] | None = None


@dataclass(frozen=True)
class ProcessingConfig:
    resolution_policy: str
    output_mode: str
    subset_mode: str
    subswaths: tuple[str, ...]
    workers: int
    cache_gb: int
    patch_size: int
    sar_band_order: tuple[str, ...]
    biophysical_bands: tuple[str, ...]


@dataclass(frozen=True)
class Manifest:
    schema_version: int
    run_id: str
    dataset_mode: str
    targets: tuple[str, ...]
    inputs: Inputs
    outputs: Outputs
    stages: dict[str, StageConfig]
    processing: ProcessingConfig
    manifest_path: Path

    @property
    def manifest_dir(self) -> Path:
        return self.manifest_path.parent


def _optional_yaml_load(text: str) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ImportError:
        return json.loads(text)
    return yaml.safe_load(text)


def _resolve_path(base_dir: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return path


def _stage_config(data: dict[str, Any] | None) -> StageConfig:
    payload = dict(data or {})
    enabled = bool(payload.pop("enabled", True))
    overwrite = bool(payload.pop("overwrite", False))
    return StageConfig(enabled=enabled, overwrite=overwrite, options=payload)


def _load_payload(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        return _optional_yaml_load(text)
    return json.loads(text)


def load_manifest(path: str | Path) -> Manifest:
    manifest_path = Path(path).resolve()
    payload = _load_payload(manifest_path)
    base_dir = manifest_path.parent

    dataset_mode = str(payload["dataset_mode"]).lower()
    if dataset_mode not in {"sa", "global"}:
        raise ValueError(f"Unsupported dataset_mode: {dataset_mode}")

    targets = tuple(str(item) for item in payload.get("targets", ()))
    if not targets:
        raise ValueError("Manifest must define at least one target.")

    inputs_raw = payload["inputs"]
    outputs_raw = payload["outputs"]
    processing_raw = payload.get("processing", {})

    inputs = Inputs(
        match_csv=_resolve_path(base_dir, inputs_raw["match_csv"]),
        points_csv=_resolve_path(base_dir, inputs_raw["points_csv"]),
        raw_slc_root=_resolve_path(base_dir, inputs_raw["raw_slc_root"]),
        shapefiles_root=_resolve_path(base_dir, inputs_raw["shapefiles_root"]),
        biophysical_root=_resolve_path(base_dir, inputs_raw.get("biophysical_root")),
    )
    outputs = Outputs(
        processed_root=_resolve_path(base_dir, outputs_raw["processed_root"]),
        patches_root=_resolve_path(base_dir, outputs_raw["patches_root"]),
        stacks_root=_resolve_path(base_dir, outputs_raw["stacks_root"]),
        logs_root=_resolve_path(base_dir, outputs_raw["logs_root"]),
        manifests_root=_resolve_path(base_dir, outputs_raw["manifests_root"]),
    )
    stages = {
        name: _stage_config(payload.get("stages", {}).get(name))
        for name in ("slc_process", "patch_extract", "patch_stack")
    }
    resolution_policy = str(processing_raw.get("resolution_policy", "snap-native"))
    if resolution_policy not in {"snap-native", "utm-grid"}:
        raise ValueError(f"Unsupported resolution_policy: {resolution_policy}")

    output_mode = str(processing_raw.get("output_mode", "scene"))
    if output_mode not in {"scene", "subswaths", "both"}:
        raise ValueError(f"Unsupported output_mode: {output_mode}")

    processing = ProcessingConfig(
        resolution_policy=resolution_policy,
        output_mode=output_mode,
        subset_mode=str(processing_raw.get("subset_mode", "aoi")),
        subswaths=tuple(str(item) for item in processing_raw.get("subswaths", ("IW1", "IW2", "IW3"))),
        workers=int(processing_raw.get("workers", 1)),
        cache_gb=int(processing_raw.get("cache_gb", 8)),
        patch_size=int(processing_raw.get("patch_size", 256)),
        sar_band_order=tuple(processing_raw.get("sar_band_order", DEFAULT_SAR_BAND_ORDER)),
        biophysical_bands=tuple(processing_raw.get("biophysical_bands", DEFAULT_BIOPHYSICAL_BANDS)),
    )

    return Manifest(
        schema_version=int(payload["schema_version"]),
        run_id=str(payload["run_id"]),
        dataset_mode=dataset_mode,
        targets=targets,
        inputs=inputs,
        outputs=outputs,
        stages=stages,
        processing=processing,
        manifest_path=manifest_path,
    )
