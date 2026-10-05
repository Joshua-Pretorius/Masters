"""Read local scene inventories and build a three-week planning JSON file."""

import csv
import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(r"D:\Masters")
LOCAL = Path(r"D:\Joshua")
OUT = ROOT / "outputs" / "01a0eef4-348e-7101-a26b-9e5a892080ca"


def rows(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def granule(value):
    return value.removesuffix(".SAFE")


global_rows = rows(
    ROOT / "Data_Creation/global_s1_slc_inventory/global_s1_slc_processing_targets.csv"
)
association_rows = rows(
    ROOT / "Data_Creation/global_s1_slc_inventory/global_s1_slc_associations.csv"
)
sa_rows = rows(
    ROOT / "Data_Creation/meria_sa_plastic_s1_slc/MERIA_SA_plastic_nearest_S1_SLC_before_after.csv"
)

scenes = {}
for row in global_rows:
    key = granule(row["granule_name"])
    scenes[key] = {
        "granule": key,
        "global_target": True,
        "sa_target": False,
        "sources": set(),
        "areas": set(),
        "observations": set(),
        "roles": set(),
        "time_gap_h": None,
        "local_tasks": [],
        "local_batches": set(),
    }

for row in association_rows:
    key = granule(row["granule_name"])
    if key not in scenes:
        continue
    item = scenes[key]
    item["sources"].add(row["source_dataset"])
    item["areas"].add(row["area"])
    item["observations"].add(row["obs_id"])
    item["roles"].add(row["role"])
    if row["delta_h"]:
        gap = abs(float(row["delta_h"]))
        item["time_gap_h"] = gap if item["time_gap_h"] is None else min(item["time_gap_h"], gap)

for row in sa_rows:
    for role in ("before", "after"):
        name = row[f"{role}_name"]
        if not name:
            continue
        key = granule(name)
        if key not in scenes:
            scenes[key] = {
                "granule": key,
                "global_target": False,
                "sa_target": False,
                "sources": set(),
                "areas": set(),
                "observations": set(),
                "roles": set(),
                "time_gap_h": None,
                "local_tasks": [],
                "local_batches": set(),
            }
        item = scenes[key]
        item["sa_target"] = True
        item["sources"].add("MERIA_SA")
        item["areas"].add(row["area"])
        item["observations"].add(row["obs_id"])
        item["roles"].add(role)

batch_names = [
    "sa_durban_2019_apr",
    "ghana_all_001",
    "golden_marida_16pcc_2018",
    "golden_marida_16pdc_2018",
    "golden_marida_18qyf_2021",
    "golden_marida_51pts_2016",
    "golden_kolkata_2020",
    "golden_tungchung_2019",
    "golden_london_2018",
]
local_order = {}
for priority, batch_name in enumerate(batch_names):
    batch_dir = LOCAL / batch_name
    for manifest_path in batch_dir.rglob("task_manifest.json"):
        if any("backup" in part.lower() for part in manifest_path.parts):
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        key = manifest["sentinel1_granule"]
        if key not in scenes:
            raise ValueError(f"Local scene missing from planned targets: {key}")
        scenes[key]["local_tasks"].append(manifest["task_id"])
        scenes[key]["local_batches"].add(batch_name)
        local_order[key] = priority

local_keys = sorted(
    local_order,
    key=lambda key: (local_order[key], key.split("_")[5] if len(key.split("_")) > 5 else key, key),
)
if len(local_keys) != 17 or sum(len(scenes[key]["local_tasks"]) for key in local_keys) != 19:
    raise ValueError("The expected 17 local scenes / 19 local tasks changed")


def source_rank(item):
    sources = item["sources"]
    if item["sa_target"]:
        return 0
    for rank, source in enumerate(
        ["Ghana_Drift", "MARIDA", "Jamila_Floating_Debris", "NASA_PlanetScope", "Greece_S2"],
        start=1,
    ):
        if source in sources:
            return rank
    return 9


remaining_keys = sorted(
    (key for key in scenes if key not in local_order),
    key=lambda key: (
        source_rank(scenes[key]),
        sorted(scenes[key]["areas"])[0] if scenes[key]["areas"] else "",
        scenes[key]["time_gap_h"] if scenes[key]["time_gap_h"] is not None else 999,
        key,
    ),
)
if len(scenes) != 129 or len(remaining_keys) != 112:
    raise ValueError("The expected 129 unique / 112 remaining scene count changed")

for index, key in enumerate(local_keys, 1):
    scenes[key]["alias"] = f"L{index:02d}"
for index, key in enumerate(remaining_keys, 1):
    scenes[key]["alias"] = f"R{index:03d}"

blocks = ["09:00–13:00", "14:00–17:00", "19:00–21:00"]
assignments = defaultdict(list)

first_week = [
    ("2026-09-30", blocks[0], 2),
    ("2026-09-30", blocks[1], 3),
    ("2026-09-30", blocks[2], 1),
    ("2026-10-01", blocks[0], 2),
    ("2026-10-01", blocks[2], 2),
    ("2026-10-02", blocks[0], 3),
    ("2026-10-02", blocks[1], 3),
    ("2026-10-02", blocks[2], 1),
]
offset = 0
for day, block, count in first_week:
    for key in local_keys[offset : offset + count]:
        assignments[(day, block)].append(key)
        scenes[key]["scheduled_date"] = day
        scenes[key]["scheduled_block"] = block
        scenes[key]["prep_date"] = "Already local"
    offset += count
if offset != 17:
    raise ValueError("First-week allocation missed local scenes")

workdays = []
current = date(2026, 10, 5)
while current <= date(2026, 10, 20):
    if current.weekday() < 5:
        workdays.append(current)
    current += timedelta(days=1)
if len(workdays) != 12:
    raise ValueError("Unexpected remaining workday count")

offset = 0
for current in workdays:
    day = current.isoformat()
    meeting = current.weekday() in (1, 3)
    allocation = [(blocks[0], 5), (blocks[1], 0 if meeting else 4), (blocks[2], 2)]
    prior = current - timedelta(days=1)
    while prior.weekday() >= 5:
        prior -= timedelta(days=1)
    for block, count in allocation:
        for key in remaining_keys[offset : offset + count]:
            assignments[(day, block)].append(key)
            scenes[key]["scheduled_date"] = day
            scenes[key]["scheduled_block"] = block
            scenes[key]["prep_date"] = prior.isoformat()
        offset += count
if offset != 112:
    raise ValueError("Remaining allocation missed planned scenes")

calendar_days = []
current = date(2026, 9, 30)
while current <= date(2026, 10, 20):
    day = current.isoformat()
    next_workday = current + timedelta(days=1)
    while next_workday.weekday() >= 5:
        next_workday += timedelta(days=1)
    if next_workday > date(2026, 10, 20):
        next_day = None
    else:
        next_day = next_workday.isoformat()
    prep_keys = [key for key in remaining_keys if scenes[key]["prep_date"] == day]
    calendar_days.append(
        {
            "date": day,
            "weekday": current.strftime("%a"),
            "meeting_day": current.weekday() in (1, 3),
            "masters_day": current.weekday() < 5,
            "next_workday": next_day,
            "prep_aliases": [scenes[key]["alias"] for key in prep_keys],
            "blocks": {
                block: [scenes[key]["alias"] for key in assignments[(day, block)]]
                for block in blocks
            },
        }
    )
    current += timedelta(days=1)

serializable = []
for item in scenes.values():
    record = dict(item)
    for field in ("sources", "areas", "observations", "roles", "local_batches"):
        record[field] = sorted(record[field])
    record["local_tasks"] = sorted(record["local_tasks"])
    serializable.append(record)
serializable.sort(key=lambda item: (0 if item["alias"].startswith("L") else 1, item["alias"]))

payload = {
    "source_files": [
        "Data_Creation/global_s1_slc_inventory/global_s1_slc_processing_targets.csv",
        "Data_Creation/global_s1_slc_inventory/global_s1_slc_associations.csv",
        "Data_Creation/meria_sa_plastic_s1_slc/MERIA_SA_plastic_nearest_S1_SLC_before_after.csv",
        "D:/Joshua/*/processed/**/task_manifest.json (nine current local batches)",
    ],
    "counts": {"unique_physical": 129, "local_tasks": 19, "local_physical": 17, "remaining": 112},
    "scenes": serializable,
    "calendar_days": calendar_days,
}
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "scene_calendar_data.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps(payload["counts"]))
print("Scheduled local:", sum(len(assignments[(day, block)]) for day, block, _ in first_week))
print("Scheduled remaining:", offset)
