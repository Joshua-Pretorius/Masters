# preprocess_grd.py
from __future__ import annotations
import argparse, json, logging
from pathlib import Path
from snap_utils import setup_logging, find_gpt, ensure_dir, patch_graph_io, resolve_local_path, run_graph, uses_windows_paths

def args_():
    ap = argparse.ArgumentParser("S1 GRD: Orbit → Calibrate → Speckle → TC")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--graphs-dir", required=True)
    ap.add_argument("--out-root", default=r"D:\Masters\Domain_SSL\PreProccess")
    ap.add_argument("--gpt", default=None)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--cache-gb", type=int, default=12)
    ap.add_argument("-v","--verbose", action="count", default=1)
    return ap.parse_args()

def main():
    a = args_(); setup_logging(a.verbose); gpt = find_gpt(a.gpt)
    windows_paths = uses_windows_paths(gpt)
    meta = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    date_str, aoi_id = meta["date"], meta["aoi_id"]; in_zip = resolve_local_path(meta["grd"]["zip"])
    if not in_zip.exists(): raise FileNotFoundError(in_zip)

    G = Path(a.graphs_dir)
    g_orbit, g_cal, g_spk, g_tc = G/"02_orbit_apply.xml", G/"03_calibration.xml", G/"07_speckle_filter.xml", G/"08_terrain_correction.xml"
    for f in [g_orbit,g_cal,g_spk,g_tc]:
        if not f.exists(): raise FileNotFoundError(f)

    out = ensure_dir(Path(a.out_root)/f"aoi_{aoi_id}"/date_str/"GRD")
    p_orb, p_cal, p_spk, p_tc = out/"grd_orbit.dim", out/"grd_calibrated.dim", out/"grd_spk.dim", out/"grd_tc.dim"

    gx = patch_graph_io(g_orbit, in_zip, p_orb, windows_paths=windows_paths); run_graph(gpt, gx, a.cache_gb, a.workers)
    gx = patch_graph_io(g_cal,   p_orb, p_cal, windows_paths=windows_paths);  run_graph(gpt, gx, a.cache_gb, a.workers)
    gx = patch_graph_io(g_spk,   p_cal, p_spk, windows_paths=windows_paths);  run_graph(gpt, gx, a.cache_gb, a.workers)
    gx = patch_graph_io(g_tc,    p_spk, p_tc, windows_paths=windows_paths);   run_graph(gpt, gx, a.cache_gb, a.workers)
    logging.info("GRD done → %s", p_tc)

if __name__ == "__main__":
    main()
