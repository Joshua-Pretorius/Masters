"""Summarize local QGIS task manifests into optical image search inputs."""

import json
import math
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(r"D:\Joshua")
NAMES = [
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


def bounding_wkt(points, margin_km=3.0):
    if not points:
        return None, None
    lats = [float(point["latitude"]) for point in points]
    lons = [float(point["longitude"]) for point in points]
    mid_lat = (min(lats) + max(lats)) / 2.0
    lat_pad = margin_km / 111.32
    lon_pad = margin_km / (111.32 * max(0.1, math.cos(math.radians(mid_lat))))
    west, east = min(lons) - lon_pad, max(lons) + lon_pad
    south, north = min(lats) - lat_pad, max(lats) + lat_pad
    coords = [(west, south), (east, south), (east, north), (west, north), (west, south)]
    wkt = "POLYGON ((" + ", ".join(f"{lon:.6f} {lat:.6f}" for lon, lat in coords) + "))"
    return [round(west, 6), round(south, 6), round(east, 6), round(north, 6)], wkt


groups = defaultdict(lambda: {"tasks": [], "sar_dates": set(), "optical_dates": set(), "seeds": {}})
for name in NAMES:
    for path in (ROOT / name).rglob("task_manifest.json"):
        if any("backup" in part.lower() for part in path.parts):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        key = (name, data["source_group_id"])
        item = groups[key]
        item["tasks"].append(data["task_id"])
        item["sar_dates"].add(data["sar_time"][:10])
        item["optical_dates"].add(data["optical_time_representative"][:10])
        item["source_dataset"] = data["source_dataset"]
        item["area"] = data["area"]
        for point in data.get("reference_points", []):
            if point.get("seed_eligible") is True:
                pkey = (point.get("point_id"), point["longitude"], point["latitude"])
                item["seeds"][pkey] = point

report = []
for (batch, group), item in groups.items():
    dates = sorted(item["sar_dates"] | item["optical_dates"])
    start, end = date.fromisoformat(dates[0]), date.fromisoformat(dates[-1])
    bbox, wkt = bounding_wkt(list(item["seeds"].values()))
    report.append(
        {
            "batch": batch,
            "group": group,
            "dataset": item["source_dataset"],
            "area": item["area"],
            "task_count": len(item["tasks"]),
            "tasks": sorted(item["tasks"]),
            "optical_dates": sorted(item["optical_dates"]),
            "sar_dates": sorted(item["sar_dates"]),
            "seed_count": len(item["seeds"]),
            "bbox": bbox,
            "wkt": wkt,
            "planet_window": [(start - timedelta(days=1)).isoformat(), (end + timedelta(days=1)).isoformat()],
            "s2_window": [(start - timedelta(days=5)).isoformat(), (end + timedelta(days=5)).isoformat()],
        }
    )
report.sort(key=lambda x: (NAMES.index(x["batch"]), x["group"]))
print(json.dumps(report, indent=2))
