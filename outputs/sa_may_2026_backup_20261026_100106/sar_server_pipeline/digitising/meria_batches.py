"""Focused MERIA digitising batches: one locality, a short window, at most three SAR scenes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .catalog import build_task_catalog


@dataclass(frozen=True)
class MeriaBatch:
    name: str
    dataset: str
    area: str
    acquisitions: tuple[str, ...]
    source_areas: tuple[str, ...] = ()


# Acquisition-start tokens identify physical scenes without depending on their
# processed directory names. Shared optical associations stay in one scene.
MERIA_BATCHES = (
    MeriaBatch("sa_durban_2019_apr21_27", "sa", "Durban", ("20190421T163724", "20190425T031055", "20190427T163647")),
    MeriaBatch("sa_durban_2022_apr05", "sa", "Durban", ("20220405T163741",)),
    MeriaBatch("sa_durban_2022_apr17_20", "sa", "Durban", ("20220417T163741", "20220420T032018")),
    MeriaBatch("sa_durban_2022_apr27", "sa", "Durban", ("20220427T031152",)),
    MeriaBatch("sa_east_london_2024_jun03", "sa", "East London", ("20240603T165337",)),
    MeriaBatch("sa_east_london_2024_jun10_15", "sa", "East London", ("20240610T164532", "20240615T165336")),
    MeriaBatch("sa_gqeberha_2024_jun08", "sa", "Gqeberha", ("20240608T170143",)),
    MeriaBatch("sa_gqeberha_2024_jun20", "sa", "Gqeberha", ("20240620T170142",)),
    MeriaBatch("sa_gqeberha_2026_may05_10", "sa", "Gqeberha", ("20260505T170121", "20260510T170927")),
    MeriaBatch("meria_palma_2018_oct12", "meria_global", "Palma de Mallorca", ("20181012T054431", "20181012T173756")),
    MeriaBatch("meria_honduras_2017_oct05", "meria_global", "Bay Islands of Honduras", ("20171005T113709",)),
    MeriaBatch("meria_honduras_2017_oct17", "meria_global", "Bay Islands of Honduras", ("20171017T113709",)),
    MeriaBatch("meria_honduras_2017_oct29", "meria_global", "Bay Islands of Honduras", ("20171029T113710",)),
    MeriaBatch("meria_ghana_2018_oct18_24", "meria_global", "Ghana", ("20181018T181758", "20181024T181717")),
    MeriaBatch("meria_ghana_2018_oct25_31", "meria_global", "Ghana", ("20181025T180953", "20181031T180908")),
    MeriaBatch("meria_ghana_2018_oct30_nov05", "meria_global", "Ghana", ("20181030T181758", "20181105T181717")),
    MeriaBatch(
        "meria_bay_islands_2018_oct24_25", "meria_global", "Bay Islands (16PDC and 16PCC)",
        ("20181024T113716", "20181024T113744", "20181025T000626"),
        ("16PDC", "16PCC"),
    ),
)

BATCH_BY_NAME = {batch.name: batch for batch in MERIA_BATCHES}


def task_ids_for_batch(batch: MeriaBatch, catalog_root: Path, processed_root: Path) -> tuple[str, ...]:
    """Select one task per acquisition; prepare adds its linked MERIA tasks."""

    if not 1 <= len(batch.acquisitions) <= 3:
        raise ValueError(f"{batch.name}: a batch must contain one to three physical SAR scenes")
    tasks = build_task_catalog(
        catalog_root, processed_root, batch.dataset,
        include_partial=batch.dataset == "meria_global",
    )
    chosen: list[str] = []
    for acquisition in batch.acquisitions:
        matches = [
            task for task in tasks
            if task.scene.granule.split("_")[5] == acquisition
            and task.area in (batch.source_areas or (batch.area,))
        ]
        if not matches:
            raise ValueError(
                f"{batch.name}: {acquisition} has no processed SAR scene and matching {batch.dataset} task"
            )
        granules = {task.scene.granule for task in matches}
        if len(granules) != 1:
            raise ValueError(f"{batch.name}: {acquisition} matched multiple SAR granules")
        scene = matches[0].scene
        manifest = json.loads(scene.manifest_path.read_text(encoding="utf-8-sig"))
        if manifest.get("status") != "processed":
            raise ValueError(f"{batch.name}: {acquisition} manifest is not processed")
        raster_keys = ("vv_refined_lee_db", "vv_refined_lee", "vv", "vh")
        primary = next((scene.outputs[key] for key in raster_keys if key in scene.outputs), scene.reference_grid)
        if primary is None or not primary.is_file():
            raise ValueError(f"{batch.name}: {acquisition} has no local processed raster")
        chosen.append(min(task.task_id for task in matches))
    if len(set(chosen)) != len(chosen):
        raise ValueError(f"{batch.name}: an acquisition was selected twice")
    return tuple(chosen)
