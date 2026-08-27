from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class ReferencePoint:
    point_id: str
    latitude: float
    longitude: float
    reference_kind: str
    seed_eligible: bool
    notes: str = ""


@dataclass(frozen=True)
class ProcessedScene:
    scene_id: str
    scene_dir: Path
    manifest_path: Path
    granule: str
    acquisition_start: str
    outputs: dict[str, Path]
    reference_grid: Path | None


@dataclass(frozen=True)
class DigitisingTask:
    task_id: str
    dataset: str
    observation_id: str
    source_dataset: str
    source_group_id: str
    area: str
    role: str
    optical_time_start: str
    optical_time_end: str
    sar_time: str
    delta_hours: float
    delta_label: str
    scene: ProcessedScene
    reference_points: tuple[ReferencePoint, ...]
    notes: str = ""
    planet_item_ids: tuple[str, ...] = field(default_factory=tuple)

    @property
    def task_dir(self) -> Path:
        return self.scene.scene_dir / "digitising" / self.task_id

    @property
    def optical_time_representative(self) -> str:
        start = datetime.fromisoformat(self.optical_time_start.replace("Z", "+00:00"))
        end = datetime.fromisoformat((self.optical_time_end or self.optical_time_start).replace("Z", "+00:00"))
        midpoint = start + (end - start) / 2
        return midpoint.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
