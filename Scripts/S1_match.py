from pathlib import Path
from datetime import datetime, timedelta, timezone
import pandas as pd
from pystac_client import Client

# ---------- CONFIG ----------------------------------------------------
patch_dir  = Path(r"D:\Masters\MARIDA\MARIDA\patches")
output_csv = patch_dir / "S1_match.csv"
stac_url   = "https://planetarycomputer.microsoft.com/api/stac/v1"
window_hr  = 48
s1_colls   = ["sentinel-1-grd", "sentinel-1-rtc"]

catalog = Client.open(stac_url)

# ---------- UTILS -----------------------------------------------------
def parse_folder_name(name: str):
    # "S2_1-12-19_48MYU"  ➜  tile="48MYU", date=2019-12-01
    try:
        _, dmy, tile = name.split("_")
        d, m, y = map(int, dmy.split("-"))
        return tile, datetime(2000 + y, m, d)
    except Exception:
        return None, None

def fetch_s2_item(tile: str, approx_date: datetime):
    day = approx_date.strftime("%Y-%m-%d")
    search = catalog.search(
        collections=["sentinel-2-l2a"],
        query={"s2:mgrs_tile": {"eq": tile}},
        datetime=f"{day}T00:00:00Z/{day}T23:59:59Z",
        limit=5,
    )
    items = list(search.items())
    return items[0] if items else None
def _as_z(dt):
    """Return RFC-3339 string in UTC with trailing Z, no microseconds."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc).replace(microsecond=0)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def nearest_s1(s2_item):
    t_s2  = s2_item.datetime
    geom  = s2_item.geometry
    t0, t1 = _as_z(t_s2 - timedelta(hours=window_hr)), _as_z(t_s2 + timedelta(hours=window_hr))

    search = catalog.search(
        collections=s1_colls,
        intersects=geom,
        datetime=f"{t0}/{t1}",
        limit=100,
    )
    items = list(search.items())
    if not items:
        return None, None, None

    closest = min(items, key=lambda it: abs((it.datetime - t_s2).total_seconds()))
    delta_h = (closest.datetime - t_s2).total_seconds() / 3600
    return closest.id, closest.datetime, delta_h

# -------------------- MAIN -------------------------------------------
records = []
for p in patch_dir.iterdir():
    if not p.is_dir():
        continue
    tile, approx_date = parse_folder_name(p.name)
    if tile is None:
        continue

    s2_item = fetch_s2_item(tile, approx_date)
    if not s2_item:
        print(f"[!] No S2 scene for {tile} on {approx_date.date()}")
        continue

    s1_id, s1_dt, delta = nearest_s1(s2_item)
    records.append(
        dict(
            s2_tile      = tile,
            s2_datetime  = s2_item.datetime,
            s1_id        = s1_id,
            s1_datetime  = s1_dt,
            delta_hours  = delta,
        )
    )

df = pd.DataFrame(records)
df.to_csv(output_csv, index=False)
print(f"[✓] {len(df)} matches ➜ {output_csv}")
