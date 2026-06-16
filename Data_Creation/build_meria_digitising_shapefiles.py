#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SA_DIR = ROOT / "meria_sa_plastic_s1_slc"
GLOBAL_DIR = ROOT / "meria_global_s1_slc"
OGR2OGR_PATH = Path(r"C:\Program Files\PostgreSQL\17\bin\ogr2ogr.exe")


@dataclass(frozen=True)
class SceneTemplate:
    dataset: str
    obs_id: str
    area: str
    role: str
    obs_date: str
    scene_id: str
    shapefile_path: Path


def slug(text: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in text.strip()).strip("_")


def load_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_manifest_lookup(root_dir: Path) -> dict[tuple[str, str], dict[str, str | Path]]:
    processed_root = root_dir / "processed_slc"
    lookup: dict[tuple[str, str], dict[str, str | Path]] = {}
    for manifest_path in sorted(processed_root.rglob("*_slc_manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        lookup[(manifest["observation_id"], manifest["role"])] = {
            "scene_id": manifest["scene_id"],
            "scene_dir": manifest_path.parent,
        }
    return lookup


def build_scene_templates(dataset: str, root_dir: Path, rows: list[dict[str, str]]) -> list[SceneTemplate]:
    manifest_lookup = load_manifest_lookup(root_dir)
    templates: list[SceneTemplate] = []
    for row in rows:
        obs_id = row["obs_id"]
        area = row["area"]
        obs_date = row["date"]
        for role in ("before", "after"):
            granule_safe = (row.get(f"{role}_name") or "").strip()
            if not granule_safe or granule_safe == "-":
                continue
            granule = granule_safe.removesuffix(".SAFE")
            acq_key = granule.split("_")[5]
            manifest_info = manifest_lookup.get((obs_id, role))
            if manifest_info:
                scene_id = str(manifest_info["scene_id"])
                scene_dir = Path(str(manifest_info["scene_dir"]))
            else:
                scene_id = f"{obs_id}_{slug(area)}_{role}_{acq_key}"
                scene_dir = root_dir / "processed_slc" / f"{obs_id}_{slug(area)}" / f"{role}_{acq_key}"
            digitising_dir = scene_dir / "digitised_patches"
            shapefile_path = digitising_dir / f"{scene_id}_digitised_patches.shp"
            templates.append(
                SceneTemplate(
                    dataset=dataset,
                    obs_id=obs_id,
                    area=area,
                    role=role,
                    obs_date=obs_date,
                    scene_id=scene_id,
                    shapefile_path=shapefile_path,
                )
            )
    return templates


def feature_collection(template: SceneTemplate) -> dict[str, object]:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": None,
                "properties": {
                    "obs_id": template.obs_id,
                    "dataset": template.dataset,
                    "role": template.role,
                    "scene_id": template.scene_id,
                    "area": template.area,
                    "obs_date": template.obs_date,
                    "patch_id": "",
                    "confidence": "",
                    "notes": "",
                },
            }
        ],
    }


def write_template_shapefile(template: SceneTemplate) -> None:
    if not OGR2OGR_PATH.exists():
        raise FileNotFoundError(f"ogr2ogr not found at {OGR2OGR_PATH}")

    template.shapefile_path.parent.mkdir(parents=True, exist_ok=True)
    layer_name = template.shapefile_path.stem
    with tempfile.TemporaryDirectory(prefix="meria_digitising_") as tmp_dir:
        tmp_geojson = Path(tmp_dir) / "template.geojson"
        tmp_geojson.write_text(json.dumps(feature_collection(template), ensure_ascii=False), encoding="utf-8")
        cmd = [
            str(OGR2OGR_PATH),
            "-overwrite",
            "-f",
            "ESRI Shapefile",
            str(template.shapefile_path),
            str(tmp_geojson),
            "-nlt",
            "POLYGON",
            "-lco",
            "ENCODING=UTF-8",
            "-sql",
            (
                "SELECT "
                "CAST(obs_id AS character(64)) AS obs_id, "
                "CAST(dataset AS character(16)) AS dataset, "
                "CAST(role AS character(16)) AS role, "
                "CAST(scene_id AS character(96)) AS scene_id, "
                "CAST(area AS character(80)) AS area, "
                "obs_date, "
                "CAST(patch_id AS character(32)) AS patch_id, "
                "CAST(confidence AS character(16)) AS confidence, "
                "CAST(notes AS character(254)) AS notes "
                "FROM template"
            ),
            "-nln",
            layer_name,
        ]
        subprocess.run(cmd, check=True)


def main() -> None:
    sa_templates = build_scene_templates("SA", SA_DIR, load_rows(SA_DIR / "MERIA_SA_plastic_nearest_S1_SLC_before_after.csv"))
    global_templates = build_scene_templates(
        "Global",
        GLOBAL_DIR,
        load_rows(GLOBAL_DIR / "MERIA_global_plastic_nearest_S1_SLC_before_after.csv"),
    )
    templates = sorted(sa_templates + global_templates, key=lambda item: (item.dataset, item.obs_id, item.role, item.obs_date))
    for template in templates:
        write_template_shapefile(template)
    print(f"Wrote {len(templates)} digitising shapefiles")


if __name__ == "__main__":
    main()
