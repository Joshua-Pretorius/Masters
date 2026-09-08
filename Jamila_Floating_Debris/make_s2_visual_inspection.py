#!/usr/bin/env python3
"""Create RGB, FDI, and 400 m inspection quicklooks from S2 band clips."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.patches import Rectangle
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.enums import ColorInterp, Resampling
from rasterio.plot import plotting_extent
from rasterio.warp import reproject


LAMBDA_RED = 665.0
LAMBDA_NIR = 842.0
LAMBDA_SWIR1 = 1610.0
S2_SCALE = 10_000.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("clips_root", type=Path)
    parser.add_argument("points_csv", type=Path)
    parser.add_argument("--obs-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--box-size-m", type=float, default=400.0)
    return parser.parse_args()


def find_band(scene_dir: Path, band: str) -> Path:
    matches = list(scene_dir.glob(f"*_{band}.tif"))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {band} file in {scene_dir}; found {len(matches)}")
    return matches[0]


def read_to_reference(path: Path, ref: rasterio.io.DatasetReader) -> np.ndarray:
    with rasterio.open(path) as src:
        source = src.read(1).astype("float32") / S2_SCALE
        source[source == 0] = np.nan
        if (
            src.crs == ref.crs
            and src.transform == ref.transform
            and src.width == ref.width
            and src.height == ref.height
        ):
            return source

        destination = np.full((ref.height, ref.width), np.nan, dtype="float32")
        reproject(
            source=source,
            destination=destination,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=np.nan,
            dst_transform=ref.transform,
            dst_crs=ref.crs,
            dst_nodata=np.nan,
            resampling=Resampling.bilinear,
        )
        return destination


def stretch_rgb(red: np.ndarray, green: np.ndarray, blue: np.ndarray) -> np.ndarray:
    rgb = np.dstack([red, green, blue])
    out = np.zeros_like(rgb, dtype="float32")
    valid = np.all(np.isfinite(rgb), axis=2)
    for index in range(3):
        values = rgb[:, :, index][valid]
        low, high = np.nanpercentile(values, (2.0, 98.5))
        out[:, :, index] = np.clip((rgb[:, :, index] - low) / (high - low), 0, 1)
    out[~valid] = 0
    return np.power(out, 0.85)


def load_points(path: Path, obs_id: str) -> list[dict[str, object]]:
    points: list[dict[str, object]] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if row["obs_id"] != obs_id or row["seed_eligible"].lower() != "true":
                continue
            points.append(
                {
                    "point_id": row["point_id"],
                    "label": f"J{len(points) + 1:02d}",
                    "lon": float(row["lon"]),
                    "lat": float(row["lat"]),
                }
            )
    if not points:
        raise RuntimeError(f"No eligible points found for {obs_id}")
    return points


def projected_points(points: list[dict[str, object]], crs) -> list[dict[str, object]]:
    transformer = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    result = []
    for point in points:
        x, y = transformer.transform(point["lon"], point["lat"])
        result.append({**point, "x": x, "y": y})
    return result


def fdi_limits(fdi: np.ndarray) -> tuple[float, float]:
    values = fdi[np.isfinite(fdi)]
    low, high = np.nanpercentile(values, (1.0, 99.5))
    low = min(float(low), -1e-6)
    high = max(float(high), 1e-6)
    return low, high


def write_geotiffs(
    out_dir: Path,
    ref: rasterio.io.DatasetReader,
    rgb_source: tuple[np.ndarray, np.ndarray, np.ndarray],
    fdi: np.ndarray,
) -> tuple[Path, Path]:
    rgb_path = out_dir / "natural_colour_rgb.tif"
    rgb_profile = ref.profile.copy()
    rgb_profile.update(count=3, dtype="uint16", nodata=0, compress="deflate")
    with rasterio.open(rgb_path, "w", **rgb_profile) as dst:
        for index, band in enumerate(rgb_source, start=1):
            data = np.nan_to_num(band * S2_SCALE, nan=0.0).astype("uint16")
            dst.write(data, index)
        dst.colorinterp = (ColorInterp.red, ColorInterp.green, ColorInterp.blue)

    fdi_path = out_dir / "floating_debris_index.tif"
    fdi_profile = ref.profile.copy()
    fdi_profile.update(count=1, dtype="float32", nodata=np.nan, compress="deflate")
    with rasterio.open(fdi_path, "w", **fdi_profile) as dst:
        dst.write(fdi.astype("float32"), 1)
        dst.set_band_description(1, "FDI")
    return rgb_path, fdi_path


def draw_boxes(ax, points: list[dict[str, object]], box_size_m: float) -> None:
    half = box_size_m / 2.0
    for point in points:
        ax.add_patch(
            Rectangle(
                (point["x"] - half, point["y"] - half),
                box_size_m,
                box_size_m,
                fill=False,
                edgecolor="#ffea00",
                linewidth=1.2,
            )
        )
        ax.text(
            point["x"],
            point["y"],
            point["label"],
            color="black",
            fontsize=6,
            ha="center",
            va="center",
            bbox={"facecolor": "#ffea00", "edgecolor": "none", "pad": 0.8},
        )


def make_overview(
    path: Path,
    rgb: np.ndarray,
    fdi: np.ndarray,
    ref: rasterio.io.DatasetReader,
    points: list[dict[str, object]],
    box_size_m: float,
    title: str,
) -> None:
    extent = plotting_extent(ref)
    low, high = fdi_limits(fdi)
    norm = TwoSlopeNorm(vmin=low, vcenter=0.0, vmax=high)
    fig, axes = plt.subplots(2, 1, figsize=(18, 7.5), constrained_layout=True)
    axes[0].imshow(rgb, extent=extent, origin="upper")
    axes[0].set_title(f"{title} — natural colour")
    image = axes[1].imshow(fdi, extent=extent, origin="upper", cmap="RdYlBu_r", norm=norm)
    axes[1].set_title(f"{title} — Floating Debris Index")
    for ax in axes:
        draw_boxes(ax, points, box_size_m)
        ax.set_aspect("equal")
        ax.set_xlabel("Easting (m), EPSG:32645")
        ax.set_ylabel("Northing (m)")
    fig.colorbar(image, ax=axes[1], label="FDI (surface reflectance)", shrink=0.8)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def crop(array: np.ndarray, ref: rasterio.io.DatasetReader, x: float, y: float, size_m: float):
    row, col = ref.index(x, y)
    half_pixels = max(1, round(size_m / (2.0 * abs(ref.transform.a))))
    row0, row1 = max(0, row - half_pixels), min(ref.height, row + half_pixels)
    col0, col1 = max(0, col - half_pixels), min(ref.width, col + half_pixels)
    return array[row0:row1, col0:col1]


def make_contact_sheet(
    path: Path,
    rgb: np.ndarray,
    fdi: np.ndarray,
    ref: rasterio.io.DatasetReader,
    points: list[dict[str, object]],
    box_size_m: float,
    title: str,
) -> None:
    low, high = fdi_limits(fdi)
    norm = TwoSlopeNorm(vmin=low, vcenter=0.0, vmax=high)
    rows = int(np.ceil(len(points) / 3.0))
    fig, axes = plt.subplots(rows, 6, figsize=(18, 3.5 * rows), constrained_layout=True)
    axes = np.atleast_2d(axes)
    for index, point in enumerate(points):
        row, pair = divmod(index, 3)
        ax_rgb, ax_fdi = axes[row, pair * 2], axes[row, pair * 2 + 1]
        rgb_chip = crop(rgb, ref, point["x"], point["y"], box_size_m)
        fdi_chip = crop(fdi, ref, point["x"], point["y"], box_size_m)
        ax_rgb.imshow(rgb_chip, origin="upper")
        ax_fdi.imshow(fdi_chip, origin="upper", cmap="RdYlBu_r", norm=norm)
        ax_rgb.set_title(f"{point['label']} RGB", fontsize=9)
        ax_fdi.set_title(f"{point['label']} FDI", fontsize=9)
        for ax in (ax_rgb, ax_fdi):
            ax.axhline((ax.get_ylim()[0] + ax.get_ylim()[1]) / 2, color="#ffea00", lw=0.6)
            ax.axvline((ax.get_xlim()[0] + ax.get_xlim()[1]) / 2, color="#ffea00", lw=0.6)
            ax.set_xticks([])
            ax.set_yticks([])
    for index in range(len(points), rows * 3):
        row, pair = divmod(index, 3)
        axes[row, pair * 2].axis("off")
        axes[row, pair * 2 + 1].axis("off")
    fig.suptitle(f"{title} — paired {box_size_m:.0f} m debris-point chips", fontsize=14)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def write_box_geojson(
    path: Path,
    points: list[dict[str, object]],
    crs,
    box_size_m: float,
) -> None:
    inverse = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    half = box_size_m / 2.0
    features = []
    for point in points:
        corners_xy = [
            (point["x"] - half, point["y"] - half),
            (point["x"] + half, point["y"] - half),
            (point["x"] + half, point["y"] + half),
            (point["x"] - half, point["y"] + half),
            (point["x"] - half, point["y"] - half),
        ]
        corners = [inverse.transform(x, y) for x, y in corners_xy]
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "label": point["label"],
                    "point_id": point["point_id"],
                    "centre_lon": point["lon"],
                    "centre_lat": point["lat"],
                    "box_size_m": box_size_m,
                },
                "geometry": {"type": "Polygon", "coordinates": [corners]},
            }
        )
    path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    points = load_points(args.points_csv, args.obs_id)
    scene_dirs = sorted({path.parent for path in args.clips_root.rglob("*_B02.tif")})
    if not scene_dirs:
        raise RuntimeError(f"No Sentinel-2 scenes found under {args.clips_root}")

    box_geojson_written = False
    for scene_dir in scene_dirs:
        tile = scene_dir.name.split("_")[1]
        out_dir = args.output_dir / tile
        out_dir.mkdir(parents=True, exist_ok=True)
        with rasterio.open(find_band(scene_dir, "B04")) as ref:
            b02 = read_to_reference(find_band(scene_dir, "B02"), ref)
            b03 = read_to_reference(find_band(scene_dir, "B03"), ref)
            b04 = read_to_reference(find_band(scene_dir, "B04"), ref)
            b06 = read_to_reference(find_band(scene_dir, "B06"), ref)
            b08 = read_to_reference(find_band(scene_dir, "B08"), ref)
            b11 = read_to_reference(find_band(scene_dir, "B11"), ref)
            baseline_factor = ((LAMBDA_NIR - LAMBDA_RED) / (LAMBDA_SWIR1 - LAMBDA_RED)) * 10.0
            fdi = b08 - (b06 + (b11 - b06) * baseline_factor)
            valid = np.all(np.isfinite(np.dstack([b02, b03, b04, b06, b08, b11])), axis=2)
            fdi[~valid] = np.nan
            rgb = stretch_rgb(b04, b03, b02)
            points_xy = projected_points(points, ref.crs)
            write_geotiffs(out_dir, ref, (b04, b03, b02), fdi)
            title = f"Sentinel-2A 2020-11-15 04:40:51 UTC — {tile}"
            make_overview(
                out_dir / "overview_rgb_fdi_400m_boxes.png",
                rgb,
                fdi,
                ref,
                points_xy,
                args.box_size_m,
                title,
            )
            make_contact_sheet(
                out_dir / "debris_points_rgb_fdi_contact_sheet.png",
                rgb,
                fdi,
                ref,
                points_xy,
                args.box_size_m,
                title,
            )
            if not box_geojson_written:
                write_box_geojson(
                    args.output_dir / "kolkata_debris_400m_boxes.geojson",
                    points_xy,
                    ref.crs,
                    args.box_size_m,
                )
                box_geojson_written = True
        print(f"Wrote visual-inspection products for {tile} -> {out_dir}")


if __name__ == "__main__":
    main()
