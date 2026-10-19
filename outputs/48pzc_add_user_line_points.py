"""Add user-supplied 48PZC line vertices to the existing optical reference layer."""

from __future__ import annotations

import shutil
from pathlib import Path

from osgeo import ogr


TARGET = Path(
    r"D:\Joshua\New\marida_48pzc_20191124_01\processed"
    r"\Global_S1_S1_S1A_IW_SLC__1SDV_20191124T105634_20191124T105701_030052_036E82_3F33"
    r"\scene_20191124T105634\digitising"
    r"\marida_48PZC_2019_11_24_after_R01_20191124T105634\task.gpkg"
)
BACKUP = TARGET.with_name("task.before_user_line_20261014.gpkg")
COORDINATES = (
    (108.509130, 15.759380),
    (108.505955, 15.753845),
    (108.499947, 15.751119),
    (108.494711, 15.748558),
    (108.490677, 15.747484),
    (108.485870, 15.748806),
    (108.479261, 15.748889),
)
TASK_ID = "marida_48PZC_2019_11_24_after_R01_20191124T105634"
OBS_ID = "marida_48PZC_2019-11-24"
PREFIX = "marida_48PZC_2019-11-24_USERLINE_"


def main() -> None:
    ogr.UseExceptions()
    if not TARGET.is_file():
        raise RuntimeError(f"Missing GeoPackage: {TARGET}")
    if BACKUP.exists():
        raise RuntimeError(f"Backup already exists; inspect before retrying: {BACKUP}")
    if any(TARGET.with_name(TARGET.name + suffix).exists() for suffix in ("-wal", "-journal")):
        raise RuntimeError("GeoPackage has a journal; close QGIS and inspect before editing")

    dataset = ogr.Open(str(TARGET), 0)
    if dataset is None:
        raise RuntimeError("Could not open GeoPackage for preflight")
    layer = dataset.GetLayerByName("reference_points")
    metadata = dataset.GetLayerByName("task_metadata")
    if layer is None or metadata is None:
        raise RuntimeError("Expected layers are missing")
    meta = metadata.GetNextFeature()
    if meta is None or meta.GetField("task_id") != TASK_ID or meta.GetField("obs_id") != OBS_ID:
        raise RuntimeError("Unexpected task metadata")
    existing_count = layer.GetFeatureCount()
    existing_ids = {f.GetField("point_id") for f in layer}
    if any(point_id.startswith(PREFIX) for point_id in existing_ids if point_id):
        raise RuntimeError("User line points already exist; refusing duplicate insertion")
    delta_h = float(meta.GetField("delta_h"))
    delta_lbl = meta.GetField("delta_lbl")
    dataset = None

    shutil.copy2(TARGET, BACKUP)
    dataset = ogr.Open(str(TARGET), 1)
    if dataset is None:
        raise RuntimeError("Could not open GeoPackage for update")
    layer = dataset.GetLayerByName("reference_points")
    definition = layer.GetLayerDefn()
    if layer.StartTransaction() != ogr.OGRERR_NONE:
        raise RuntimeError("Could not start transaction")
    try:
        for index, (lon, lat) in enumerate(COORDINATES, start=1):
            feature = ogr.Feature(definition)
            feature.SetField("point_id", f"{PREFIX}{index:04d}")
            feature.SetField("task_id", TASK_ID)
            feature.SetField("obs_id", OBS_ID)
            feature.SetField("ref_kind", "user_line_candidate")
            feature.SetField("seed_ok", 0)
            feature.SetField("delta_h", delta_h)
            feature.SetField("delta_lbl", delta_lbl)
            feature.SetField(
                "notes",
                "Vertex of user-supplied LineString; optical candidate reference only. "
                "Acquisition source and debris identity unverified; not an OpenDrift seed.",
            )
            geometry = ogr.Geometry(ogr.wkbPoint)
            geometry.AddPoint_2D(lon, lat)
            feature.SetGeometry(geometry)
            if layer.CreateFeature(feature) != ogr.OGRERR_NONE:
                raise RuntimeError(f"Could not create point {index}")
        if layer.CommitTransaction() != ogr.OGRERR_NONE:
            raise RuntimeError("Could not commit transaction")
    except Exception:
        layer.RollbackTransaction()
        raise
    dataset = None

    dataset = ogr.Open(str(TARGET), 0)
    layer = dataset.GetLayerByName("reference_points")
    if layer.GetFeatureCount() != existing_count + len(COORDINATES):
        raise RuntimeError("Feature count verification failed")
    inserted = {}
    for feature in layer:
        point_id = feature.GetField("point_id")
        if point_id and point_id.startswith(PREFIX):
            inserted[point_id] = (
                feature.GetGeometryRef().GetX(),
                feature.GetGeometryRef().GetY(),
                feature.GetField("ref_kind"),
                feature.GetField("seed_ok"),
            )
    for index, coordinates in enumerate(COORDINATES, start=1):
        point_id = f"{PREFIX}{index:04d}"
        if inserted.get(point_id) != (*coordinates, "user_line_candidate", 0):
            raise RuntimeError(f"Point verification failed: {point_id}")
    print(f"Added {len(inserted)} points: {existing_count} -> {layer.GetFeatureCount()}")
    print(f"GeoPackage: {TARGET}")
    print(f"Backup: {BACKUP}")


if __name__ == "__main__":
    main()
