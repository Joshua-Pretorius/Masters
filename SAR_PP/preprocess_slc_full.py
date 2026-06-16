# preprocess_slc_full.py
from __future__ import annotations
import argparse, json, logging
from pathlib import Path
from snap_utils import (
    setup_logging, find_gpt, ensure_dir,
    run_graph, patch_graph_io, patch_graph_params, graph_has_operator, resolve_local_path, uses_windows_paths
)

def _args():
    ap = argparse.ArgumentParser(
        "S1 SLC: IW1–IW3 (all bursts) → "
        "Sigma0 textures (Cal→Deburst→[INT speckle]→GLCM→TC) + "
        "C2 branch (Deburst?→C2→[POL speckle]→Decomp→TC) + "
        "Sigma0→TC (VV/VH) for stacking"
    )
    ap.add_argument("--manifest", required=True, help="Path to date-level manifest.json")
    ap.add_argument("--graphs-dir", required=True, help="Folder with 01..10 SNAP graphs")
    ap.add_argument("--out-root", default=r"D:\Masters\Domain_SSL\PreProccess")
    ap.add_argument("--gpt", default=None)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--cache-gb", type=int, default=12)
    ap.add_argument("--subswaths", default="IW1,IW2,IW3")

    # separate speckle graphs (pass only the ones you want)
    ap.add_argument("--int-speckle-graph", default=None,
                    help="Intensity speckle graph (e.g. 07_speckle_filter.xml) — used on sigma0 branch only.")
    ap.add_argument("--pol-speckle-graph", default=None,
                    help="Polarimetric speckle graph — used on C2 branch only (optional).")

    ap.add_argument("-v", "--verbose", action="count", default=1)
    return ap.parse_args()

def main():
    a = _args()
    setup_logging(a.verbose)
    gpt = find_gpt(a.gpt)
    windows_paths = uses_windows_paths(gpt)

    meta = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    date_str, aoi_id = meta["date"], meta["aoi_id"]
    in_zip = resolve_local_path(meta["slc"]["zip"])
    if not in_zip.exists():
        raise FileNotFoundError(in_zip)

    G = Path(a.graphs_dir)
    g_split  = G / "01_split.xml"
    g_orbit  = G / "02_orbit_apply.xml"
    g_deb    = G / "04_deburst.xml"
    g_cal    = G / "03_calibration.xml"         # Calibrate BEFORE deburst for sigma0 branch
    g_tex    = G / "10_feature_extraction.xml"  # GLCM, etc.
    g_tc     = G / "08_terrain_correction.xml"
    g_c2     = G / "06_polarimetric_matrix.xml"
    g_decomp = G / "09_polarimetric_decomposition.xml"

    for f in [g_split, g_orbit, g_deb, g_cal, g_tex, g_tc, g_c2, g_decomp]:
        if not f.exists(): raise FileNotFoundError(f)

    # Optional speckle graphs (warn & skip if missing)
    g_spk_int = Path(a.int_speckle_graph) if a.int_speckle_graph else None
    if g_spk_int and not g_spk_int.exists():
        logging.warning("Intensity speckle graph not found: %s — skipping.", g_spk_int); g_spk_int = None
    g_spk_pol = Path(a.pol_speckle_graph) if a.pol_speckle_graph else None
    if g_spk_pol and not g_spk_pol.exists():
        logging.warning("Polarimetric speckle graph not found: %s — skipping.", g_spk_pol); g_spk_pol = None

    out_root = ensure_dir(Path(a.out_root) / f"aoi_{aoi_id}" / date_str / "SLC")
    subs = [s.strip() for s in a.subswaths.split(",") if s.strip()]

    for ss in subs:
        logging.info("=== %s | subswath %s ===", date_str, ss)
        out = ensure_dir(out_root / ss)

        # -------- Split (all bursts) --------
        p_split = out / f"slc_{ss}_split.dim"
        gx = patch_graph_io(g_split, in_zip, p_split, windows_paths=windows_paths)
        gx = patch_graph_params(gx, [
            {"op": "TOPSAR-Split", "param": "subswath",        "value": ss},
            {"op": "TOPSAR-Split", "param": "firstBurstIndex", "value": None},
            {"op": "TOPSAR-Split", "param": "lastBurstIndex",  "value": None},
            {"op": "TOPSAR-Split", "param": "selectedBursts",  "value": None},
        ])
        run_graph(gpt, gx, a.cache_gb, a.workers)

        # -------- Orbit --------
        p_orbit = out / f"slc_{ss}_orbit.dim"
        gx = patch_graph_io(g_orbit, p_split, p_orbit, windows_paths=windows_paths); run_graph(gpt, gx, a.cache_gb, a.workers)

        # ================= Branch A: Sigma0 → [INT speckle] → GLCM → TC =================
        p_cal      = out / f"slc_{ss}_cal.dim"
        p_cal_deb  = out / f"slc_{ss}_cal_deburst.dim"
        p_cal_filt = out / f"slc_{ss}_cal_filtered.dim"
        p_tex      = out / f"slc_{ss}_tex.dim"
        p_tex_tc   = out / f"slc_{ss}_tex_tc.dim"

        gx = patch_graph_io(g_cal, p_orbit, p_cal, windows_paths=windows_paths);            run_graph(gpt, gx, a.cache_gb, a.workers)
        gx = patch_graph_io(g_deb, p_cal,   p_cal_deb, windows_paths=windows_paths);        run_graph(gpt, gx, a.cache_gb, a.workers)

        src_for_tex = p_cal_deb
        if g_spk_int:
            logging.info("[Sigma0] INT speckle: %s", g_spk_int)
            gx = patch_graph_io(g_spk_int, p_cal_deb, p_cal_filt, windows_paths=windows_paths); run_graph(gpt, gx, a.cache_gb, a.workers)
            src_for_tex = p_cal_filt

        # FEATURES
        gx = patch_graph_io(g_tex, src_for_tex, p_tex, windows_paths=windows_paths);        run_graph(gpt, gx, a.cache_gb, a.workers)
        gx = patch_graph_io(g_tc,  p_tex,       p_tex_tc, windows_paths=windows_paths);     run_graph(gpt, gx, a.cache_gb, a.workers)

        # ALSO WRITE sigma0→TC (VV/VH in map space) for final stack
        p_sig_tc = out / f"slc_{ss}_sigma0_tc.dim"
        gx = patch_graph_io(g_tc, src_for_tex, p_sig_tc, windows_paths=windows_paths);      run_graph(gpt, gx, a.cache_gb, a.workers)

        # ================= Branch B: Deburst? → C2 → [POL speckle] → Decomp → TC =================
        has_deburst_inside_c2 = graph_has_operator(g_c2, "TOPSAR-Deburst") or graph_has_operator(g_c2, "Deburst")

        p_deb       = out / f"slc_{ss}_deburst.dim"   # only if C2 graph doesn't deburst internally
        p_c2        = out / f"slc_{ss}_c2.dim"
        p_c2f       = out / f"slc_{ss}_c2_filtered.dim"
        p_decmp     = out / f"slc_{ss}_decomp.dim"
        p_c2_tc     = out / f"slc_{ss}_c2_tc.dim"
        p_decmp_tc  = out / f"slc_{ss}_decomp_tc.dim"

        c2_input = p_orbit
        if not has_deburst_inside_c2:
            gx = patch_graph_io(g_deb, p_orbit, p_deb, windows_paths=windows_paths);        run_graph(gpt, gx, a.cache_gb, a.workers)
            c2_input = p_deb

        gx = patch_graph_io(g_c2, c2_input, p_c2, windows_paths=windows_paths);             run_graph(gpt, gx, a.cache_gb, a.workers)

        src_c2 = p_c2
        if g_spk_pol:
            logging.info("[C2] POL speckle: %s", g_spk_pol)
            gx = patch_graph_io(g_spk_pol, p_c2, p_c2f, windows_paths=windows_paths);       run_graph(gpt, gx, a.cache_gb, a.workers)
            src_c2 = p_c2f

        gx = patch_graph_io(g_decomp, src_c2, p_decmp, windows_paths=windows_paths);        run_graph(gpt, gx, a.cache_gb, a.workers)

        # TC for alignment/stacking
        gx = patch_graph_io(g_tc, src_c2,  p_c2_tc, windows_paths=windows_paths);           run_graph(gpt, gx, a.cache_gb, a.workers)
        gx = patch_graph_io(g_tc, p_decmp, p_decmp_tc, windows_paths=windows_paths);        run_graph(gpt, gx, a.cache_gb, a.workers)

        logging.info("Finished SLC %s %s", ss, date_str)

    logging.info("ALL DONE: AOI %s | %s", aoi_id, date_str)

if __name__ == "__main__":
    main()
