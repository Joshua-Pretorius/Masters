#!/usr/bin/env python3
"""
Build a merged marine-debris point layer and compare it to MARIDA SAR acquisitions.

Outputs:
- marine_debris_points.geojson
- marine_debris_points_24h.geojson
- marida_sar_events.geojson
- marida_spatial_overlap_events.csv
- marine_debris_24h_matches.csv
- marine_debris_vs_marida_global.png
- marine_debris_vs_marida_24h_zoom.png
- report.md
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-marine-debris")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from rasterio.warp import transform_geom
import rasterio
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon, mapping, shape
from shapely.prepared import prep


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LABELS_DIR = Path(__file__).resolve().parent / "nasa-marine-debris" / "labels"
DEFAULT_MARIDA_ROOT = REPO_ROOT / "MARIDA" / "downloads"
DEFAULT_OUT_DIR = Path(__file__).resolve().parent / "outputs"


def dt_to_z(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def round_float(value: float | None, ndp: int = 6) -> float | None:
    if value is None:
        return None
    return round(float(value), ndp)


def parse_debris_timestamp(name: str) -> datetime | None:
    parts = Path(name).stem.split("_")
    if len(parts) < 2:
        return None
    try:
        return datetime.strptime(parts[0] + "_" + parts[1], "%Y%m%d_%H%M%S").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


def parse_marida_timestamp(name: str) -> datetime | None:
    parts = Path(name).stem.split("_")
    if len(parts) < 3:
        return None
    try:
        return datetime.strptime(parts[2], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def geometry_bounds(records: Iterable[object], attr: str) -> tuple[float, float, float, float]:
    bounds = [getattr(record, attr).bounds for record in records]
    return (
        min(item[0] for item in bounds),
        min(item[1] for item in bounds),
        max(item[2] for item in bounds),
        max(item[3] for item in bounds),
    )


def pad_bounds(bounds: tuple[float, float, float, float], frac: float = 0.08) -> tuple[float, float, float, float]:
    minx, miny, maxx, maxy = bounds
    dx = max(maxx - minx, 0.1)
    dy = max(maxy - miny, 0.1)
    return (
        minx - dx * frac,
        miny - dy * frac,
        maxx + dx * frac,
        maxy + dy * frac,
    )


def raster_footprint_wgs84(path: Path):
    with rasterio.open(path) as ds:
        bounds = ds.bounds
        footprint = {
            "type": "Polygon",
            "coordinates": [[
                [bounds.left, bounds.bottom],
                [bounds.right, bounds.bottom],
                [bounds.right, bounds.top],
                [bounds.left, bounds.top],
                [bounds.left, bounds.bottom],
            ]],
        }
        if ds.crs:
            footprint = transform_geom(ds.crs, "EPSG:4326", footprint, precision=12)
        return shape(footprint).buffer(0)


def plot_outline(ax, geom, **kwargs) -> None:
    if geom.is_empty:
        return
    if isinstance(geom, Polygon):
        x, y = geom.exterior.xy
        ax.plot(x, y, **kwargs)
        for interior in geom.interiors:
            ix, iy = interior.xy
            ax.plot(ix, iy, **kwargs)
        return
    if isinstance(geom, MultiPolygon):
        for part in geom.geoms:
            plot_outline(ax, part, **kwargs)
        return
    if isinstance(geom, GeometryCollection):
        for part in geom.geoms:
            plot_outline(ax, part, **kwargs)


@dataclass
class DebrisPoint:
    feature_id: str
    source_geojson: str
    feature_index: int
    acquired_dt: datetime | None
    polygon: object
    point: object
    lon: float
    lat: float
    earth_science_event: str | None
    tag_status: str | None
    label: str | None
    name: str | None
    labels: int | None
    spatial_matches: list["EventMatch"] = field(default_factory=list)
    temporal_matches: list["EventMatch"] = field(default_factory=list)
    closest_spatial_match: "EventMatch | None" = None


@dataclass
class MaridaEvent:
    event_id: str
    tile: str
    source_date: str
    sar_dir: str
    acquired_dt: datetime | None
    geometry: object
    centroid: object
    lon: float
    lat: float
    pols: set[str] = field(default_factory=set)
    raster_files: list[str] = field(default_factory=list)
    spatial_feature_ids: set[str] = field(default_factory=set)
    temporal_feature_ids: set[str] = field(default_factory=set)
    spatial_source_files: set[str] = field(default_factory=set)
    temporal_source_files: set[str] = field(default_factory=set)
    delta_hours: list[float] = field(default_factory=list)


@dataclass
class EventMatch:
    event_id: str
    tile: str
    source_date: str
    sar_dir: str
    acquired_dt: datetime | None
    pols: str
    delta_hours: float | None


def load_debris_points(labels_dir: Path) -> list[DebrisPoint]:
    records: list[DebrisPoint] = []
    for geojson_path in sorted(labels_dir.glob("*.geojson")):
        acquired_dt = parse_debris_timestamp(geojson_path.name)
        with geojson_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        for index, feature in enumerate(data.get("features", []), start=1):
            polygon = shape(feature["geometry"]).buffer(0)
            point = polygon.centroid
            props = feature.get("properties", {})
            records.append(
                DebrisPoint(
                    feature_id=f"{geojson_path.stem}::feature_{index}",
                    source_geojson=geojson_path.name,
                    feature_index=index,
                    acquired_dt=acquired_dt,
                    polygon=polygon,
                    point=point,
                    lon=float(point.x),
                    lat=float(point.y),
                    earth_science_event=props.get("earth_science_event"),
                    tag_status=props.get("tag_status"),
                    label=props.get("label"),
                    name=props.get("name"),
                    labels=props.get("labels"),
                )
            )
    return records


def load_marida_events(marida_root: Path) -> list[MaridaEvent]:
    event_map: dict[tuple[str, str, str], MaridaEvent] = {}
    for tif_path in sorted(marida_root.glob("**/SAR_*/*.tif")):
        acquired_dt = parse_marida_timestamp(tif_path.name)
        tile = tif_path.parts[-4]
        source_date = tif_path.parts[-3]
        sar_dir = tif_path.parts[-2]
        key = (tile, sar_dir, dt_to_z(acquired_dt) or "unknown")
        footprint = raster_footprint_wgs84(tif_path)
        pol = tif_path.stem.rsplit("_", 1)[-1].upper()
        event = event_map.get(key)
        if event is None:
            centroid = footprint.centroid
            event = MaridaEvent(
                event_id=f"{tile}_{source_date}_{sar_dir}_{dt_to_z(acquired_dt) or 'unknown'}",
                tile=tile,
                source_date=source_date,
                sar_dir=sar_dir,
                acquired_dt=acquired_dt,
                geometry=footprint,
                centroid=centroid,
                lon=float(centroid.x),
                lat=float(centroid.y),
            )
            event_map[key] = event
        else:
            event.geometry = event.geometry.union(footprint)
            event.centroid = event.geometry.centroid
            event.lon = float(event.centroid.x)
            event.lat = float(event.centroid.y)
        event.pols.add(pol)
        event.raster_files.append(tif_path.name)
    return list(event_map.values())


def analyse_overlaps(
    debris_points: list[DebrisPoint],
    marida_events: list[MaridaEvent],
    time_threshold_hours: float,
) -> None:
    prepared_events = [(event, prep(event.geometry)) for event in marida_events]
    for debris_point in debris_points:
        spatial_matches: list[EventMatch] = []
        temporal_matches: list[EventMatch] = []
        for event, prepared in prepared_events:
            if not prepared.intersects(debris_point.polygon):
                continue
            delta_hours = None
            if debris_point.acquired_dt and event.acquired_dt:
                delta_hours = abs(
                    (debris_point.acquired_dt - event.acquired_dt).total_seconds()
                ) / 3600.0
                event.delta_hours.append(delta_hours)
            match = EventMatch(
                event_id=event.event_id,
                tile=event.tile,
                source_date=event.source_date,
                sar_dir=event.sar_dir,
                acquired_dt=event.acquired_dt,
                pols=",".join(sorted(event.pols)),
                delta_hours=delta_hours,
            )
            spatial_matches.append(match)
            event.spatial_feature_ids.add(debris_point.feature_id)
            event.spatial_source_files.add(debris_point.source_geojson)
            if delta_hours is not None and delta_hours <= time_threshold_hours:
                temporal_matches.append(match)
                event.temporal_feature_ids.add(debris_point.feature_id)
                event.temporal_source_files.add(debris_point.source_geojson)
        spatial_matches.sort(
            key=lambda item: (
                math.inf if item.delta_hours is None else item.delta_hours,
                item.event_id,
            )
        )
        temporal_matches.sort(
            key=lambda item: (
                math.inf if item.delta_hours is None else item.delta_hours,
                item.event_id,
            )
        )
        debris_point.spatial_matches = spatial_matches
        debris_point.temporal_matches = temporal_matches
        if spatial_matches:
            debris_point.closest_spatial_match = spatial_matches[0]


def debris_feature(point: DebrisPoint) -> dict:
    closest = point.closest_spatial_match
    props = {
        "feature_id": point.feature_id,
        "source_geojson": point.source_geojson,
        "feature_index": point.feature_index,
        "source_acquired_utc": dt_to_z(point.acquired_dt),
        "earth_science_event": point.earth_science_event,
        "tag_status": point.tag_status,
        "label": point.label,
        "name": point.name,
        "labels": point.labels,
        "lon": round_float(point.lon),
        "lat": round_float(point.lat),
        "spatial_overlap_any": bool(point.spatial_matches),
        "spatial_overlap_event_count": len(point.spatial_matches),
        "overlap_24h_any": bool(point.temporal_matches),
        "overlap_24h_event_count": len(point.temporal_matches),
        "closest_marida_event_id": closest.event_id if closest else None,
        "closest_marida_tile": closest.tile if closest else None,
        "closest_marida_sar_dir": closest.sar_dir if closest else None,
        "closest_marida_acquired_utc": dt_to_z(closest.acquired_dt) if closest else None,
        "closest_marida_delta_hours": round_float(
            closest.delta_hours, 3
        ) if closest and closest.delta_hours is not None else None,
        "closest_marida_pols": closest.pols if closest else None,
        "matching_marida_event_ids": ";".join(match.event_id for match in point.spatial_matches),
        "matching_marida_24h_event_ids": ";".join(match.event_id for match in point.temporal_matches),
    }
    return {"type": "Feature", "geometry": mapping(point.point), "properties": props}


def marida_event_feature(event: MaridaEvent) -> dict:
    props = {
        "event_id": event.event_id,
        "tile": event.tile,
        "source_date": event.source_date,
        "sar_dir": event.sar_dir,
        "acquired_utc": dt_to_z(event.acquired_dt),
        "pols": ",".join(sorted(event.pols)),
        "raster_file_count": len(event.raster_files),
        "centroid_lon": round_float(event.lon),
        "centroid_lat": round_float(event.lat),
        "spatial_overlap_point_count": len(event.spatial_feature_ids),
        "spatial_overlap_source_file_count": len(event.spatial_source_files),
        "overlap_24h_point_count": len(event.temporal_feature_ids),
        "overlap_24h_source_file_count": len(event.temporal_source_files),
        "min_abs_delta_hours": round_float(min(event.delta_hours), 3) if event.delta_hours else None,
        "max_abs_delta_hours": round_float(max(event.delta_hours), 3) if event.delta_hours else None,
    }
    return {"type": "Feature", "geometry": mapping(event.geometry), "properties": props}


def write_geojson(path: Path, features: list[dict]) -> None:
    payload = {"type": "FeatureCollection", "features": features}
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def save_global_map(
    path: Path,
    debris_points: list[DebrisPoint],
    marida_events: list[MaridaEvent],
    time_threshold_hours: float,
) -> None:
    fig, ax = plt.subplots(figsize=(13, 7), dpi=170)

    non_spatial = [point for point in debris_points if not point.spatial_matches]
    spatial_only = [point for point in debris_points if point.spatial_matches and not point.temporal_matches]
    temporal = [point for point in debris_points if point.temporal_matches]

    for event in marida_events:
        plot_outline(ax, event.geometry, color="#7f8c8d", linewidth=0.8, alpha=0.45)
    for event in marida_events:
        if event.spatial_feature_ids:
            plot_outline(ax, event.geometry, color="#1f77b4", linewidth=1.2, alpha=0.8)
    for event in marida_events:
        if event.temporal_feature_ids:
            plot_outline(ax, event.geometry, color="#d62728", linewidth=1.8, alpha=0.95)

    if non_spatial:
        ax.scatter(
            [point.lon for point in non_spatial],
            [point.lat for point in non_spatial],
            s=8,
            color="#bfc7ce",
            alpha=0.75,
            label="Debris points with no MARIDA spatial overlap",
        )
    if spatial_only:
        ax.scatter(
            [point.lon for point in spatial_only],
            [point.lat for point in spatial_only],
            s=10,
            color="#1f77b4",
            alpha=0.8,
            label="Debris points with spatial overlap only",
        )
    if temporal:
        ax.scatter(
            [point.lon for point in temporal],
            [point.lat for point in temporal],
            s=55,
            marker="*",
            color="#d62728",
            edgecolors="black",
            linewidths=0.4,
            zorder=5,
            label=f"Debris points within {time_threshold_hours:g} h and inside a MARIDA footprint",
        )

    debris_bounds = geometry_bounds(debris_points, "point")
    marida_bounds = geometry_bounds(marida_events, "geometry")
    minx = min(debris_bounds[0], marida_bounds[0])
    miny = min(debris_bounds[1], marida_bounds[1])
    maxx = max(debris_bounds[2], marida_bounds[2])
    maxy = max(debris_bounds[3], marida_bounds[3])
    padded = pad_bounds((minx, miny, maxx, maxy), frac=0.04)
    ax.set_xlim(padded[0], padded[2])
    ax.set_ylim(padded[1], padded[3])
    mean_lat = (padded[1] + padded[3]) / 2.0
    ax.set_aspect(1.0 / max(math.cos(math.radians(mean_lat)), 0.2))
    ax.grid(True, linestyle="--", linewidth=0.4, alpha=0.4)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("Marine debris centroids vs MARIDA SAR acquisition footprints")

    summary = (
        f"Debris points: {len(debris_points)}\n"
        f"MARIDA SAR events: {len(marida_events)}\n"
        f"Spatial-overlap debris points: {sum(1 for point in debris_points if point.spatial_matches)}\n"
        f"Spatial + <= {time_threshold_hours:g} h: {sum(1 for point in debris_points if point.temporal_matches)}"
    )
    ax.text(
        0.015,
        0.02,
        summary,
        transform=ax.transAxes,
        fontsize=8,
        va="bottom",
        ha="left",
        bbox={"facecolor": "white", "alpha": 0.9, "edgecolor": "#cccccc"},
    )

    handles = [
        Line2D([0], [0], color="#7f8c8d", linewidth=1.0, label="All MARIDA SAR footprints"),
        Line2D([0], [0], color="#1f77b4", linewidth=1.2, label="Spatially matched MARIDA footprints"),
        Line2D([0], [0], color="#d62728", linewidth=1.8, label=f"MARIDA footprints matched within {time_threshold_hours:g} h"),
    ]
    if non_spatial:
        handles.append(Line2D([0], [0], marker="o", linestyle="", color="#bfc7ce", markersize=5, label="Debris: no spatial overlap"))
    if spatial_only:
        handles.append(Line2D([0], [0], marker="o", linestyle="", color="#1f77b4", markersize=5, label="Debris: spatial overlap only"))
    if temporal:
        handles.append(Line2D([0], [0], marker="*", linestyle="", color="#d62728", markeredgecolor="black", markersize=9, label=f"Debris: <= {time_threshold_hours:g} h"))
    ax.legend(handles=handles, loc="upper right", fontsize=8)

    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def save_zoom_map(
    path: Path,
    debris_points: list[DebrisPoint],
    marida_events: list[MaridaEvent],
    time_threshold_hours: float,
) -> None:
    temporal_points = [point for point in debris_points if point.temporal_matches]
    matched_events = [event for event in marida_events if event.temporal_feature_ids]
    local_events = [event for event in marida_events if event.spatial_feature_ids]
    if not temporal_points or not matched_events:
        fig, ax = plt.subplots(figsize=(8, 5), dpi=170)
        ax.text(0.5, 0.5, "No spatiotemporal matches found.", ha="center", va="center")
        ax.axis("off")
        fig.tight_layout()
        fig.savefig(path, bbox_inches="tight")
        plt.close(fig)
        return

    local_points = [point for point in debris_points if point.spatial_matches]
    fig, ax = plt.subplots(figsize=(10, 7), dpi=170)
    for event in local_events:
        plot_outline(ax, event.geometry, color="#1f77b4", linewidth=1.2, alpha=0.55)
    for event in matched_events:
        plot_outline(ax, event.geometry, color="#d62728", linewidth=2.0, alpha=0.95)
        ax.text(
            event.lon,
            event.lat,
            f"{event.tile}\n{dt_to_z(event.acquired_dt)}",
            fontsize=8,
            color="#7f0000",
            ha="center",
            va="center",
            bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "#d62728"},
        )
    ax.scatter(
        [point.lon for point in local_points],
        [point.lat for point in local_points],
        s=10,
        color="#8eb8e5",
        alpha=0.7,
        label="Spatial-overlap debris points",
    )
    ax.scatter(
        [point.lon for point in temporal_points],
        [point.lat for point in temporal_points],
        s=85,
        marker="*",
        color="#d62728",
        edgecolors="black",
        linewidths=0.5,
        zorder=5,
        label=f"Debris points within {time_threshold_hours:g} h",
    )
    for point in temporal_points:
        ax.text(
            point.lon,
            point.lat,
            point.source_geojson.replace(".geojson", ""),
            fontsize=7,
            color="#222222",
            ha="left",
            va="bottom",
        )

    point_bounds = geometry_bounds(temporal_points, "point")
    event_bounds = geometry_bounds(matched_events, "geometry")
    padded = pad_bounds(
        (
            min(point_bounds[0], event_bounds[0]),
            min(point_bounds[1], event_bounds[1]),
            max(point_bounds[2], event_bounds[2]),
            max(point_bounds[3], event_bounds[3]),
        ),
        frac=0.2,
    )
    ax.set_xlim(padded[0], padded[2])
    ax.set_ylim(padded[1], padded[3])
    mean_lat = (padded[1] + padded[3]) / 2.0
    ax.set_aspect(1.0 / max(math.cos(math.radians(mean_lat)), 0.2))
    ax.grid(True, linestyle="--", linewidth=0.4, alpha=0.35)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title(f"Zoom: MARIDA overlaps within {time_threshold_hours:g} hours")
    ax.legend(loc="upper right", fontsize=8)

    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def build_event_rows(events: list[MaridaEvent]) -> list[dict]:
    rows = []
    for event in sorted(events, key=lambda item: (len(item.spatial_feature_ids), dt_to_z(item.acquired_dt) or "" ), reverse=True):
        rows.append(
            {
                "event_id": event.event_id,
                "tile": event.tile,
                "source_date": event.source_date,
                "sar_dir": event.sar_dir,
                "acquired_utc": dt_to_z(event.acquired_dt),
                "pols": ",".join(sorted(event.pols)),
                "raster_file_count": len(event.raster_files),
                "spatial_overlap_point_count": len(event.spatial_feature_ids),
                "spatial_overlap_source_file_count": len(event.spatial_source_files),
                "overlap_24h_point_count": len(event.temporal_feature_ids),
                "overlap_24h_source_file_count": len(event.temporal_source_files),
                "min_abs_delta_hours": round_float(min(event.delta_hours), 3) if event.delta_hours else None,
                "max_abs_delta_hours": round_float(max(event.delta_hours), 3) if event.delta_hours else None,
                "centroid_lon": round_float(event.lon),
                "centroid_lat": round_float(event.lat),
            }
        )
    return rows


def build_temporal_rows(points: list[DebrisPoint]) -> list[dict]:
    rows = []
    for point in sorted(
        [item for item in points if item.temporal_matches],
        key=lambda item: (
            item.temporal_matches[0].delta_hours if item.temporal_matches and item.temporal_matches[0].delta_hours is not None else math.inf,
            item.feature_id,
        ),
    ):
        match = point.temporal_matches[0]
        rows.append(
            {
                "feature_id": point.feature_id,
                "source_geojson": point.source_geojson,
                "feature_index": point.feature_index,
                "source_acquired_utc": dt_to_z(point.acquired_dt),
                "lon": round_float(point.lon),
                "lat": round_float(point.lat),
                "marida_event_id": match.event_id,
                "marida_tile": match.tile,
                "marida_source_date": match.source_date,
                "marida_sar_dir": match.sar_dir,
                "marida_acquired_utc": dt_to_z(match.acquired_dt),
                "marida_pols": match.pols,
                "abs_delta_hours": round_float(match.delta_hours, 3) if match.delta_hours is not None else None,
            }
        )
    return rows


def write_report(
    path: Path,
    labels_dir: Path,
    marida_root: Path,
    out_dir: Path,
    debris_points: list[DebrisPoint],
    marida_events: list[MaridaEvent],
    time_threshold_hours: float,
    event_rows: list[dict],
    temporal_rows: list[dict],
) -> None:
    debris_with_spatial = [point for point in debris_points if point.spatial_matches]
    debris_with_temporal = [point for point in debris_points if point.temporal_matches]
    spatial_events = [event for event in marida_events if event.spatial_feature_ids]
    temporal_events = [event for event in marida_events if event.temporal_feature_ids]
    spatial_tiles = Counter(event.tile for event in spatial_events)

    lines: list[str] = []
    lines.append("# Marine Debris vs MARIDA Overlap Report")
    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    lines.append("")
    lines.append("## Inputs")
    lines.append("")
    lines.append(f"- Marine debris labels: `{labels_dir}`")
    lines.append(f"- MARIDA SAR root: `{marida_root}`")
    lines.append("")
    lines.append("## Method")
    lines.append("")
    lines.append("- Each labeled marine-debris polygon was reduced to a centroid point for the merged GeoJSON layer.")
    lines.append("- Spatial overlap was tested with the original debris polygon against MARIDA SAR footprints derived from each raster's bounds and transformed to WGS84.")
    lines.append(f"- Spatiotemporal overlap was defined as spatial overlap plus an absolute acquisition-time difference of at most {time_threshold_hours:g} hours.")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Marine debris label files: **{len(sorted(labels_dir.glob('*.geojson')))}**")
    lines.append(f"- Marine debris objects mapped to points: **{len(debris_points)}**")
    lines.append(f"- MARIDA SAR TIFFs: **{sum(len(event.raster_files) for event in marida_events)}**")
    lines.append(f"- MARIDA SAR acquisition events: **{len(marida_events)}**")
    lines.append(f"- Debris points with any MARIDA spatial overlap: **{len(debris_with_spatial)}**")
    lines.append(f"- MARIDA acquisition events with any debris spatial overlap: **{len(spatial_events)}**")
    lines.append(f"- Debris points with spatial overlap within {time_threshold_hours:g} hours: **{len(debris_with_temporal)}**")
    lines.append(f"- MARIDA acquisition events with at least one <= {time_threshold_hours:g} h match: **{len(temporal_events)}**")
    lines.append("")
    lines.append("## Output Files")
    lines.append("")
    lines.append(f"- `marine_debris_points.geojson`")
    lines.append(f"- `marine_debris_points_24h.geojson`")
    lines.append(f"- `marida_sar_events.geojson`")
    lines.append(f"- `marida_spatial_overlap_events.csv`")
    lines.append(f"- `marine_debris_24h_matches.csv`")
    lines.append(f"- `marine_debris_vs_marida_global.png`")
    lines.append(f"- `marine_debris_vs_marida_24h_zoom.png`")
    lines.append("")
    lines.append("## Maps")
    lines.append("")
    lines.append("![Global overlap map](marine_debris_vs_marida_global.png)")
    lines.append("")
    lines.append(f"![Zoomed <= {time_threshold_hours:g} h overlap map](marine_debris_vs_marida_24h_zoom.png)")
    lines.append("")
    lines.append("## Spatially Overlapping MARIDA Tiles")
    lines.append("")
    for tile, count in spatial_tiles.most_common():
        lines.append(f"- `{tile}`: {count} overlapping acquisition events")
    lines.append("")
    lines.append("## Spatiotemporal Matches")
    lines.append("")
    if temporal_rows:
        lines.append("| feature_id | source_geojson | source_acquired_utc | lon | lat | marida_tile | marida_acquired_utc | marida_sar_dir | pols | abs_delta_hours |")
        lines.append("| --- | --- | --- | ---: | ---: | --- | --- | --- | --- | ---: |")
        for row in temporal_rows:
            lines.append(
                f"| {row['feature_id']} | {row['source_geojson']} | {row['source_acquired_utc']} | "
                f"{row['lon']:.6f} | {row['lat']:.6f} | {row['marida_tile']} | "
                f"{row['marida_acquired_utc']} | {row['marida_sar_dir']} | {row['marida_pols']} | "
                f"{row['abs_delta_hours']:.3f} |"
            )
    else:
        lines.append(f"No overlaps met the <= {time_threshold_hours:g} hour criterion.")
    lines.append("")
    lines.append("## Spatial Overlap Event Summary")
    lines.append("")
    lines.append("| event_id | tile | acquired_utc | sar_dir | pols | spatial_points | overlap_24h_points | min_abs_delta_h | max_abs_delta_h |")
    lines.append("| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: |")
    for row in event_rows:
        if not row["spatial_overlap_point_count"]:
            continue
        min_delta = "" if row["min_abs_delta_hours"] is None else f"{row['min_abs_delta_hours']:.3f}"
        max_delta = "" if row["max_abs_delta_hours"] is None else f"{row['max_abs_delta_hours']:.3f}"
        lines.append(
            f"| {row['event_id']} | {row['tile']} | {row['acquired_utc']} | {row['sar_dir']} | {row['pols']} | "
            f"{row['spatial_overlap_point_count']} | {row['overlap_24h_point_count']} | {min_delta} | {max_delta} |"
        )
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    if temporal_rows:
        first = temporal_rows[0]
        lines.append(
            f"- The only spatiotemporal match within {time_threshold_hours:g} hours is a MARIDA event in tile `{first['marida_tile']}` "
            f"acquired at `{first['marida_acquired_utc']}`."
        )
        lines.append(
            f"- All <= {time_threshold_hours:g} h matches come from Planet debris labels acquired on `{first['source_acquired_utc']}` "
            f"near longitude {first['lon']:.4f}, latitude {first['lat']:.4f}."
        )
    else:
        lines.append(f"- No debris points overlapped a MARIDA SAR acquisition within {time_threshold_hours:g} hours.")
    lines.append(
        "- Spatial overlap alone is much more common because several MARIDA Honduras footprints cover the same area as the debris labels but were acquired on different days or years."
    )

    with path.open("w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels-dir", type=Path, default=DEFAULT_LABELS_DIR)
    parser.add_argument("--marida-root", type=Path, default=DEFAULT_MARIDA_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--time-threshold-hours", type=float, default=24.0)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    debris_points = load_debris_points(args.labels_dir)
    marida_events = load_marida_events(args.marida_root)
    analyse_overlaps(debris_points, marida_events, args.time_threshold_hours)

    event_rows = build_event_rows(marida_events)
    temporal_rows = build_temporal_rows(debris_points)

    write_geojson(
        args.out_dir / "marine_debris_points.geojson",
        [debris_feature(point) for point in debris_points],
    )
    write_geojson(
        args.out_dir / "marine_debris_points_24h.geojson",
        [debris_feature(point) for point in debris_points if point.temporal_matches],
    )
    write_geojson(
        args.out_dir / "marida_sar_events.geojson",
        [marida_event_feature(event) for event in marida_events],
    )
    write_csv(
        args.out_dir / "marida_spatial_overlap_events.csv",
        event_rows,
        [
            "event_id",
            "tile",
            "source_date",
            "sar_dir",
            "acquired_utc",
            "pols",
            "raster_file_count",
            "spatial_overlap_point_count",
            "spatial_overlap_source_file_count",
            "overlap_24h_point_count",
            "overlap_24h_source_file_count",
            "min_abs_delta_hours",
            "max_abs_delta_hours",
            "centroid_lon",
            "centroid_lat",
        ],
    )
    write_csv(
        args.out_dir / "marine_debris_24h_matches.csv",
        temporal_rows,
        [
            "feature_id",
            "source_geojson",
            "feature_index",
            "source_acquired_utc",
            "lon",
            "lat",
            "marida_event_id",
            "marida_tile",
            "marida_source_date",
            "marida_sar_dir",
            "marida_acquired_utc",
            "marida_pols",
            "abs_delta_hours",
        ],
    )
    save_global_map(
        args.out_dir / "marine_debris_vs_marida_global.png",
        debris_points,
        marida_events,
        args.time_threshold_hours,
    )
    save_zoom_map(
        args.out_dir / "marine_debris_vs_marida_24h_zoom.png",
        debris_points,
        marida_events,
        args.time_threshold_hours,
    )
    write_report(
        args.out_dir / "report.md",
        args.labels_dir,
        args.marida_root,
        args.out_dir,
        debris_points,
        marida_events,
        args.time_threshold_hours,
        event_rows,
        temporal_rows,
    )


if __name__ == "__main__":
    main()
