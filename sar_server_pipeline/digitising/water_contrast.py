"""Signed water-relative SAR contrast, on the original raster grid.

No SAR download, resampling, target fitting, or electronic-noise correction.
WorldCover is an ancillary map; absent tiles remain unknown, never assumed water.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
from contextlib import ExitStack
from pathlib import Path

import numpy as np
import rasterio
from pyproj import CRS, Geod, Transformer
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.vrt import WarpedVRT
from rasterio.windows import Window, from_bounds
from rasterio.warp import transform_bounds
from scipy.ndimage import distance_transform_edt, uniform_filter
from shapely.geometry import MultiPoint, box, mapping
from shapely.ops import transform
from .water_contrast_style import LABELS, VERSION, add_qgis_layers

LOG = logging.getLogger(__name__)

CONFIG = dict(
    version=VERSION,
    buffer_m=100000,
    coverage="on-image points convex hull, metric buffer, intersect source bounds",
    lee_outer_half_m=150,
    lee_guard_half_m=50,
    patch_outer_half_m=300,
    patch_guard_half_m=100,
    patch_widths_m=[30, 60],
    ring_fraction=0.7,
    patch_fraction=0.9,
    ring_min_cells=30,
    patch_min_cells=4,
    water="ESA WorldCover 2021 v200 class 80",
    coast_margin_m=30,
    display_db=[-6, 6],
    instrument_noise="unassessed",
)


def pixel_metres(src, window):
    x, y = src.transform * (
        window.col_off + window.width / 2,
        window.row_off + window.height / 2,
    )
    lon, lat = Transformer.from_crs(src.crs, 4326, always_xy=True).transform(x, y)
    if src.transform.b or src.transform.d:
        raise ValueError("Rotated SAR grids are not supported")
    if src.crs.is_geographic:
        geod = Geod(ellps="WGS84")
        return (
            abs(geod.inv(lon, lat, lon + abs(src.res[0]), lat)[2]),
            abs(geod.inv(lon, lat, lon, lat + abs(src.res[1]))[2]),
        )
    units = CRS(src.crs).axis_info
    return (
        abs(src.res[0]) * units[0].unit_conversion_factor,
        abs(src.res[1]) * units[1].unit_conversion_factor,
    )


def window_sizes(pixel_m):
    dx, dy = pixel_m

    def size(half):
        return (2 * max(1, round(half / dy)) + 1, 2 * max(1, round(half / dx)) + 1)

    return dict(
        lee_outer=size(150),
        lee_guard=size(50),
        outer=size(300),
        guard=size(100),
        patch30=size(15),
        patch60=size(30),
    )


def total(a, size):
    return uniform_filter(
        np.asarray(a, dtype="float64"), size=size, mode="constant", cval=0
    ) * np.prod(size)


def ring(a, outer, guard):
    return total(a, outer) - total(a, guard)


def calculate(vv, vh, lee, water, pixel_m):
    """Four Float32 bands; invalid/unsupported centres remain NaN."""
    sizes = window_sizes(pixel_m)
    outer, guard = sizes["lee_outer"], sizes["lee_guard"]
    valid = np.isfinite(lee) & (lee > -9990) & water
    count = np.maximum(ring(valid, outer, guard), 0)
    mean = ring(np.where(valid, lee, 0), outer, guard) / np.maximum(count, 1)
    supported = (
        valid
        & (count >= 30)
        & (count / (np.prod(outer) - np.prod(guard)) >= 0.7 - 1e-9)
    )
    filtered = np.where(supported, lee - mean, np.nan)
    outer, guard = sizes["outer"], sizes["guard"]
    results = []
    for source, widths in [(vv, ("patch30", "patch60")), (vh, ("patch30",))]:
        valid = np.isfinite(source) & (source > 0) & water
        values = np.where(valid, source, 0)
        n = np.maximum(ring(valid, outer, guard), 0)
        background = ring(values, outer, guard) / np.maximum(n, 1)
        enough = (
            (n >= 30)
            & (n / (np.prod(outer) - np.prod(guard)) >= 0.7 - 1e-9)
            & (background > 0)
        )
        for width in widths:
            size = sizes[width]
            cn = np.maximum(total(valid, size), 0)
            centre = total(values, size) / np.maximum(cn, 1)
            good = (
                valid
                & enough
                & (cn >= 4)
                & (cn / np.prod(size) >= 0.9 - 1e-9)
                & (centre > 0)
            )
            out = np.full(source.shape, np.nan)
            out[good] = 10 * np.log10(centre[good]) - 10 * np.log10(background[good])
            results.append(out)
    return np.stack([filtered, results[0], results[2], results[1]]).astype("float32")


def coverage(src, points, buffer_m=100000):
    """Keep points on valid SAR samples, connect in local AEQD, buffer in metres."""
    points = sorted(
        set(
            (float(x), float(y)) for x, y in points if np.isfinite(x) and np.isfinite(y)
        )
    )
    to_source = Transformer.from_crs(4326, src.crs, always_xy=True)
    usable = []
    for lon, lat in points:
        x, y = to_source.transform(lon, lat)
        if not (
            src.bounds.left <= x < src.bounds.right
            and src.bounds.bottom < y <= src.bounds.top
        ):
            continue
        value = next(src.sample([(x, y)], indexes=1, masked=True))[0]
        if not np.ma.is_masked(value) and np.isfinite(value) and value > 0:
            usable.append((lon, lat))
    if not usable:
        return None, None, []
    lon = float(np.mean([p[0] for p in usable]))
    lat = float(np.mean([p[1] for p in usable]))
    metric = CRS.from_proj4(
        f"+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m"
    )
    forward = Transformer.from_crs(4326, metric, always_xy=True).transform
    backward = Transformer.from_crs(metric, src.crs, always_xy=True).transform
    hull = transform(forward, MultiPoint(usable)).convex_hull
    area = transform(backward, hull.buffer(buffer_m, resolution=64)).intersection(
        box(*src.bounds)
    )
    if area.is_empty:
        return None, None, usable
    raw = from_bounds(*area.bounds, src.transform)
    left = max(0, math.floor(raw.col_off))
    top = max(0, math.floor(raw.row_off))
    right = min(src.width, math.ceil(raw.col_off + raw.width))
    bottom = min(src.height, math.ceil(raw.row_off + raw.height))
    return area, Window(left, top, right - left, bottom - top), usable


class WorldCover:
    """Read only relevant COG windows. Constant memory, including for full scenes."""

    def __init__(self, src, window, stack):
        west, south, east, north = transform_bounds(
            src.crs, 4326, *rasterio.windows.bounds(window, src.transform)
        )
        self.sources = []
        self.missing = []
        self.urls = []
        for lat in range(math.floor(south / 3) * 3, math.floor(north / 3) * 3 + 1, 3):
            for lon in range(math.floor(west / 3) * 3, math.floor(east / 3) * 3 + 1, 3):
                tile = f'{"N" if lat>=0 else "S"}{abs(lat):02d}{"E" if lon>=0 else "W"}{abs(lon):03d}'
                url = f"https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
                self.urls.append(url)
                try:
                    self.sources.append(stack.enter_context(rasterio.open(url)))
                except rasterio.errors.RasterioIOError as exc:
                    if "404" not in str(exc):
                        raise
                    self.missing.append(url)
                    LOG.warning("WorldCover tile absent; area stays unknown: %s", tile)

    def read(self, src, window, pixel_m):
        h, w = int(window.height), int(window.width)
        t = src.window_transform(window)
        classes = np.zeros((h, w), "uint8")
        for source in self.sources:
            bounds = transform_bounds(source.crs, src.crs, *source.bounds)
            if not box(*bounds).intersects(
                box(*rasterio.windows.bounds(window, src.transform))
            ):
                continue
            with WarpedVRT(
                source,
                crs=src.crs,
                transform=t,
                width=w,
                height=h,
                resampling=Resampling.nearest,
                nodata=0,
            ) as vrt:
                values = vrt.read(1)
            classes[values != 0] = values[values != 0]
        water = classes == 80
        distance = distance_transform_edt(
            np.pad(water, 1), sampling=(pixel_m[1], pixel_m[0])
        )[1:-1, 1:-1]
        return water & (distance > 30)


def generate(
    outputs, points, directory, *, buffer_m=100000, block=768, water_reader=None
):
    """Generate once per input/point/config fingerprint; never reuse partial outputs.

    water_reader is an explicit injection for offline tests, not a production fallback.
    Missing inputs are reported rather than substituting filtered for raw imagery.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    sources = {
        k: Path(outputs[k])
        for k in ("vv", "vh", "vv_refined_lee_db")
        if k in outputs and Path(outputs[k]).exists()
    }
    missing = sorted(set(("vv", "vh", "vv_refined_lee_db")) - sources.keys())
    if missing:
        return dict(status="missing_inputs", missing=missing)
    points = sorted(set(map(tuple, points)))
    config = dict(CONFIG, buffer_m=buffer_m)
    identity = dict(
        config=config,
        points=points,
        sources={
            k: dict(
                path=str(v.resolve()), size=v.stat().st_size, mtime=v.stat().st_mtime_ns
            )
            for k, v in sources.items()
        },
    )
    fingerprint = hashlib.sha256(
        json.dumps(identity, sort_keys=True).encode()
    ).hexdigest()
    destination = directory / "water_contrast.tif"
    sidecar = directory / "water_contrast.json"
    if sidecar.exists() and destination.exists():
        previous = json.loads(sidecar.read_text())
        if previous.get("fingerprint") == fingerprint:
            with rasterio.open(destination) as check:
                if check.count == 4 and check.tags().get("fingerprint") == fingerprint:
                    return previous
    with ExitStack() as stack:
        srcs = {k: stack.enter_context(rasterio.open(v)) for k, v in sources.items()}
        src = srcs["vv"]
        for value in srcs.values():
            if (value.crs, value.transform, value.shape) != (
                src.crs,
                src.transform,
                src.shape,
            ):
                raise ValueError(
                    "VV, VH and filtered VV must share the exact native grid"
                )
        area, window, on_image = coverage(src, points, buffer_m)
        if area is None:
            return dict(status="no_on_image_points", input_points=len(points))
        pixel_m = pixel_metres(src, window)
        sizes = window_sizes(pixel_m)
        halo = max(sizes["outer"]) // 2 + math.ceil(30 / min(pixel_m)) + 3
        env = stack.enter_context(
            rasterio.Env(
                GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                GDAL_HTTP_MAX_RETRY="3",
                GDAL_HTTP_RETRY_DELAY="2",
            )
        )
        extended = Window(
            window.col_off - halo,
            window.row_off - halo,
            window.width + 2 * halo,
            window.height + 2 * halo,
        )
        world = None if water_reader else WorldCover(src, extended, stack)
        profile = dict(
            driver="GTiff",
            width=int(window.width),
            height=int(window.height),
            count=4,
            dtype="float32",
            crs=src.crs,
            transform=src.window_transform(window),
            nodata=np.nan,
            tiled=True,
            blockxsize=256,
            blockysize=256,
            compress="deflate",
            predictor=3,
            BIGTIFF="IF_SAFER",
        )
        temporary = directory / "water_contrast.partial.tif"
        counts = [0] * 4
        negative = [0] * 4
        positive = [0] * 4
        with rasterio.open(temporary, "w", **profile) as dst:
            dst.update_tags(
                fingerprint=fingerprint,
                method=json.dumps(config),
                pixel_m=json.dumps(pixel_m),
                windows_pixels=json.dumps(sizes),
                source_files=json.dumps({k: str(v) for k, v in sources.items()}),
            )
            for b, label in enumerate(LABELS, 1):
                dst.set_band_description(b, label)
            for row in range(0, int(window.height), block):
                for col in range(0, int(window.width), block):
                    h = min(block, int(window.height) - row)
                    w = min(block, int(window.width) - col)
                    tw = Window(col, row, w, h)
                    inside = (
                        rasterize(
                            [(mapping(area), 1)],
                            out_shape=(h, w),
                            transform=dst.window_transform(tw),
                            dtype="uint8",
                        )
                        > 0
                    )
                    cube = np.full((4, h, w), np.nan, "float32")
                    if inside.any():
                        rw = Window(
                            window.col_off + col - halo,
                            window.row_off + row - halo,
                            w + 2 * halo,
                            h + 2 * halo,
                        )
                        arrays = [
                            srcs[k]
                            .read(1, window=rw, boundless=True, masked=True)
                            .astype("float64")
                            .filled(np.nan)
                            for k in ("vv", "vh", "vv_refined_lee_db")
                        ]
                        if np.any(np.isfinite(arrays[0]) & (arrays[0] > 0)):
                            water = (
                                water_reader(src, rw, pixel_m)
                                if water_reader
                                else world.read(src, rw, pixel_m)
                            )
                            cube = calculate(*arrays, water, pixel_m)[
                                :, halo : halo + h, halo : halo + w
                            ]
                            cube[:, ~inside] = np.nan
                    dst.write(cube, window=tw)
                    for b, a in enumerate(cube):
                        counts[b] += int(np.isfinite(a).sum())
                        negative[b] += int((a < 0).sum())
                        positive[b] += int((a > 0).sum())
                LOG.info(
                    "Water contrast %s: rows %s/%s",
                    directory,
                    min(row + block, int(window.height)),
                    int(window.height),
                )
            levels = [
                n for n in (2, 4, 8, 16) if min(window.width, window.height) // n >= 1
            ]
            if levels:
                dst.build_overviews(levels, Resampling.average)
        os.replace(temporary, destination)
        result = dict(
            status="complete",
            fingerprint=fingerprint,
            path=str(destination),
            method=config,
            sources={k: str(v) for k, v in sources.items()},
            input_points=len(points),
            on_image_points=on_image,
            window=list(window.flatten()),
            pixel_m=pixel_m,
            windows_pixels=sizes,
            valid_counts=counts,
            negative_counts=negative,
            positive_counts=positive,
            worldcover_urls=world.urls if world else [],
            missing_worldcover_tiles=world.missing if world else [],
            worldcover_citation="ESA WorldCover 2021 v200; doi:10.5281/zenodo.7254221; CC BY 4.0",
        )
        geometry = dict(
            type="FeatureCollection",
            features=[
                dict(
                    type="Feature",
                    properties={"buffer_m": buffer_m},
                    geometry=mapping(
                        transform(
                            Transformer.from_crs(
                                src.crs, 4326, always_xy=True
                            ).transform,
                            area,
                        )
                    ),
                )
            ],
        )
        (directory / "coverage.geojson").write_text(
            json.dumps(geometry), encoding="utf-8"
        )
        tmpmeta = sidecar.with_suffix(".json.tmp")
        tmpmeta.write_text(json.dumps(result, indent=2), encoding="utf-8")
        os.replace(tmpmeta, sidecar)
        return result


def prepare_scene(scene, tasks):
    """Gather scene-associated observed/predicted points for both preparation modes."""
    import fiona
    from shapely.geometry import shape

    points = []
    for task in tasks:
        # AOI context is allowed to define coverage, never used as a target label.
        points.extend((p.longitude, p.latitude) for p in task.reference_points)
        gpkg = task.task_dir / "task.gpkg"
        if gpkg.exists() and "predicted_points" in fiona.listlayers(gpkg):
            with fiona.open(gpkg, layer="predicted_points") as source:
                project = Transformer.from_crs(
                    source.crs, 4326, always_xy=True
                ).transform
                for f in source:
                    if not f["geometry"]:
                        continue
                    geom = transform(project, shape(f["geometry"]))
                    if geom.geom_type == "Point":
                        points.append((geom.x, geom.y))
                    elif geom.geom_type == "MultiPoint":
                        points.extend((p.x, p.y) for p in geom.geoms)
    result = generate(scene.outputs, points, scene.scene_dir / VERSION)
    if result.get("status") != "complete":
        LOG.warning("Water contrast unavailable for %s: %s", scene.scene_id, result)
    return result


def transfer_paths(scene):
    directory = scene.scene_dir / VERSION
    return [
        directory / name
        for name in ("water_contrast.tif", "water_contrast.json", "coverage.geojson")
        if (directory / name).exists()
    ]
