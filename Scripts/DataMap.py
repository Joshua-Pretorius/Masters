# -*- coding: utf-8 -*-
"""
Make PNG maps with a light basemap behind MERIA + MARIDA SAR centroids.

Outputs to: D:\Masters\Maps_SAR\
 - map_meria_points.png
 - map_marida_points.png
 - map_all_points.png
"""

import os, re, glob, math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import rasterio
from rasterio.warp import transform_bounds
from pyproj import CRS, Transformer

import geopandas as gpd
from shapely.geometry import Point
import contextily as ctx

# ---------- CONFIG (edit if needed) ----------
MERIA_ROOT  = r"D:\Masters\MERIA\raw_grd"
MARIDA_ROOT = r"D:\Masters\MARIDA\downloads"
MAP_OUT     = r"D:\Masters\Maps_SAR"
os.makedirs(MAP_OUT, exist_ok=True)

# ---------- FILE LISTING ----------
def list_meria_files():
    # measurement TIFFs under *.SAFE
    pat = os.path.join(MERIA_ROOT, "**", "*.SAFE", "measurement", "*.tif*")
    return glob.glob(pat, recursive=True)

def list_marida_files():
    # TIFFs inside folders named SAR_* (e.g. SAR_-4.6h)
    pat = os.path.join(MARIDA_ROOT, "**", "SAR_*", "*.tif*")
    return glob.glob(pat, recursive=True)

# ---------- GEO UTILS ----------
def raster_centroid_wgs84(path: str):
    """Centroid (lon, lat) from raster bounds; transform to EPSG:4326."""
    with rasterio.open(path) as ds:
        b = ds.bounds
        if ds.crs:
            try:
                tb = transform_bounds(ds.crs, "EPSG:4326", b.left, b.bottom, b.right, b.top, densify_pts=21)
                lon = (tb[0] + tb[2]) / 2.0
                lat = (tb[1] + tb[3]) / 2.0
                return float(lon), float(lat)
            except Exception:
                pass
        # Fallback if CRS missing/weird: assume lon/lat bounds
        lon = (b.left + b.right) / 2.0
        lat = (b.top  + b.bottom) / 2.0
        return float(lon), float(lat)

def parse_meria_record(path: str):
    p = Path(path)
    # find SAFE folder name
    safe_dir = next((pr.name for pr in p.parents if pr.name.endswith(".SAFE")), p.stem)
    # pol from file name
    pol_m = re.search(r'-(vv|vh)-', p.name, re.I)
    pol = pol_m.group(1).upper() if pol_m else ""
    lon, lat = raster_centroid_wgs84(path)
    return dict(source="MERIA", product=safe_dir, file=p.name, pol=pol, lon=lon, lat=lat)

def parse_marida_record(path: str):
    p = Path(path)
    pol_m = re.search(r'_(vv|vh)\.tif[f]?$', p.name, re.I)
    pol = pol_m.group(1).upper() if pol_m else ""
    # label from parent folders e.g. ...\downloads\16PDC\2018-10-24\SAR_-4.6h\file.tif
    try:
        product = f"{p.parent.parent.name}_{p.parent.name}"
    except Exception:
        product = p.stem
    lon, lat = raster_centroid_wgs84(path)
    return dict(source="MARIDA", product=product, file=p.name, pol=pol, lon=lon, lat=lat)

# ---------- PLOTTING ----------
def _pad_extent(bounds, frac=0.12, min_pad_m=2000):
    xmin, ymin, xmax, ymax = bounds
    dx, dy = (xmax - xmin), (ymax - ymin)
    px = max(min_pad_m, dx * frac) if dx > 0 else min_pad_m
    py = max(min_pad_m, dy * frac) if dy > 0 else min_pad_m
    return (xmin - px, xmax + px, ymin - py, ymax + py)

def save_points_map(points, png_path, title="SAR Scene Centroids", label=False):
    """Plot EPSG:3857 points over a light basemap. Points are given as lon/lat."""
    if not points:
        fig = plt.figure(figsize=(9.5, 5.5), dpi=150)
        ax = plt.gca()
        ax.set_title(f"{title} (no points found)")
        ax.set_axis_off()
        fig.tight_layout(); fig.savefig(png_path, bbox_inches="tight"); plt.close(fig)
        return

    gdf_wgs = gpd.GeoDataFrame(points, geometry=[Point(d["lon"], d["lat"]) for d in points], crs="EPSG:4326")
    gdf_3857 = gdf_wgs.to_crs(3857)

    fig = plt.figure(figsize=(9.5, 5.5), dpi=150)
    ax = plt.gca()

    # Draw points first (so labels sit on top later)
    gdf_3857.plot(ax=ax, markersize=14, linewidth=0, alpha=0.95)

    xmin, ymin, xmax, ymax = gdf_3857.total_bounds
    x0, x1, y0, y1 = _pad_extent((xmin, ymin, xmax, ymax))
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)

    # Basemap (CartoDB Positron); if tiles fail (no net), continue without
    try:
        ctx.add_basemap(ax, source=ctx.providers.CartoDB.Positron, crs="EPSG:3857", attribution_size=6)
        # After basemap, re-apply padded extent (contextily can tweak limits)
        ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
    except Exception as e:
        print(f"[warn] basemap not added: {e}")

    ax.set_title(title)
    ax.set_axis_off()

    if label:
        for i, row in gdf_3857.reset_index().iterrows():
            ax.text(row.geometry.x, row.geometry.y, str(i+1), fontsize=8)

    fig.tight_layout()
    fig.savefig(png_path, bbox_inches="tight")
    plt.close(fig)

# ---------- MAIN ----------
def main():
    meria_files  = list_meria_files()
    marida_files = list_marida_files()
    print(f"MERIA files:  {len(meria_files)}")
    print(f"MARIDA files: {len(marida_files)}")

    meria_pts  = [parse_meria_record(f)  for f in meria_files]
    marida_pts = [parse_marida_record(f) for f in marida_files]

    out_meria  = str(Path(MAP_OUT) / "map_meria_points.png")
    out_marida = str(Path(MAP_OUT) / "map_marida_points.png")
    out_combo  = str(Path(MAP_OUT) / "map_all_points.png")

    save_points_map(meria_pts,  out_meria,  title="MERIA SAR Scene Centroids")
    save_points_map(marida_pts, out_marida, title="MARIDA SAR Scene Centroids")
    save_points_map(meria_pts + marida_pts, out_combo, title="All SAR Scene Centroids")

    print("Saved:")
    print(" ", out_meria)
    print(" ", out_marida)
    print(" ", out_combo)

if __name__ == "__main__":
    main()