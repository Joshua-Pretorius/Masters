import json
from pathlib import Path
import geopandas as gpd
from shapely.geometry import shape

# ── CONFIG ────────────────────────────────────────────────────────────
JSON_F = Path(r"C:\Users\Joshua Pretorius\Desktop"
              r"\ocean-scan-mireia-- marine litter signatures "
              r"in sar images-e71e8ee6-e41d-4889-bb08-a821fb5e8bbd.json")

OUT_FILE = Path(r"C:\Users\Joshua Pretorius\Desktop\patches_all.gpkg")

# ── LOAD JSON ─────────────────────────────────────────────────────────
with open(JSON_F, "r", encoding="utf-8", errors="replace") as f:
    observations = json.load(f)["observations"]

# ── BUILD RECORDS ─────────────────────────────────────────────────────
records = []
for obs in observations:
    geom = shape(obs["geometry"])
    records.append({
        "obs_id":    obs.get("id"),
        "timestamp": obs.get("timestamp"),
        "sourceId":  (obs.get("extra") or {}).get("_sourceId"),
        "isAbsence": obs.get("isAbsence", False),
        "geometry":  geom
    })

# ── EXPORT TO GEOPACKAGE ─────────────────────────────────────────────
gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")
gdf.to_file(OUT_FILE, layer="patches", driver="GPKG")
print(f"Wrote {len(gdf)} features to {OUT_FILE}")