# preprocess_slc_full.py
from __future__ import annotations
import argparse, json, logging, shutil, struct
from pathlib import Path
from snap_utils import (
    setup_logging, find_gpt, ensure_dir,
    run_graph, patch_graph_io, patch_graph_params, graph_has_operator,
    export_to_geotiff,
    resolve_local_path,
    uses_windows_paths,
)

def _args():
    ap = argparse.ArgumentParser(
        "S1 SLC: IW1–IW3 (all bursts) → "
        "Sigma0 textures (Cal→Deburst→[INT speckle]→GLCM→TC) + "
        "C2 branch (Deburst?→C2→Decomp→TC) + Sigma0→TC (VV/VH)"
    )
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--graphs-dir", required=True)
    ap.add_argument("--out-root", default=r"D:\Masters\Domain_SSL\PreProccess")
    ap.add_argument("--gpt", default=None)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--cache-gb", type=int, default=12)
    ap.add_argument("--subswaths", default="IW1,IW2,IW3")
    ap.add_argument("--aoi-shp", default=None, help="Optional WGS84 AOI shapefile used to subset each split SLC.")
    ap.add_argument("--int-speckle-graph", default=None)     # 07_speckle_filter.xml
    ap.add_argument("--pol-speckle-graph", default=None)     # optional
    ap.add_argument("-v", "--verbose", action="count", default=1)
    return ap.parse_args()

def cleanup_snap_product(dim_path: Path) -> None:
    data_dir = dim_path.with_suffix(".data")
    if dim_path.exists():
        dim_path.unlink()
    if data_dir.exists():
        shutil.rmtree(data_dir, ignore_errors=True)

def shapefile_bbox_wkt(shp_path: Path) -> str:
    """Return a WGS84 bbox polygon for an image-specific AOI shapefile."""
    with shp_path.open("rb") as handle:
        header = handle.read(100)
    if len(header) < 68:
        raise ValueError(f"Invalid shapefile header: {shp_path}")
    minx, miny, maxx, maxy = struct.unpack("<4d", header[36:68])
    return (
        f"POLYGON (({minx} {miny}, {maxx} {miny}, {maxx} {maxy}, "
        f"{minx} {maxy}, {minx} {miny}))"
    )

def main():
    a = _args()
    setup_logging(a.verbose)
    gpt = find_gpt(a.gpt)
    windows_paths = uses_windows_paths(gpt)

    meta = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    date_str, aoi_id = meta["date"], meta["aoi_id"]
    in_zip = resolve_local_path(meta["slc"]["zip"])
    if not in_zip.exists(): raise FileNotFoundError(in_zip)
    aoi_arg = a.aoi_shp or meta.get("aoi_shp") or meta.get("aoi", {}).get("shp")
    aoi_wkt = None
    if aoi_arg:
        aoi_path = resolve_local_path(aoi_arg)
        if not aoi_path.exists():
            raise FileNotFoundError(aoi_path)
        aoi_wkt = shapefile_bbox_wkt(aoi_path)
        logging.info("Using AOI subset %s -> %s", aoi_path, aoi_wkt)

    G = Path(a.graphs_dir)
    g_split  = G / "01_split.xml"
    g_subset = G / "05_subset.xml"
    g_orbit  = G / "02_orbit_apply.xml"
    g_cal    = G / "03_calibration.xml"      # Cal BEFORE Deburst on sigma0 branch
    g_deb    = G / "04_deburst.xml"
    g_c2     = G / "06_polarimetric_matrix.xml"
    g_tex    = G / "10_feature_extraction.xml"
    g_tc     = G / "08_terrain_correction.xml"
    g_decomp = G / "09_polarimetric_decomposition.xml"
    required_graphs = [g_split,g_orbit,g_cal,g_deb,g_c2,g_tex,g_tc,g_decomp]
    if aoi_wkt:
        required_graphs.append(g_subset)
    for f in required_graphs:
        if not f.exists(): raise FileNotFoundError(f)

    g_spk_int = Path(a.int_speckle_graph) if a.int_speckle_graph else None
    if g_spk_int and not g_spk_int.exists():
        logging.warning("Intensity speckle graph missing: %s (skipping)", g_spk_int); g_spk_int=None
    g_spk_pol = Path(a.pol_speckle_graph) if a.pol_speckle_graph else None
    if g_spk_pol and not g_spk_pol.exists():
        logging.warning("Polarimetric speckle graph missing: %s (skipping)", g_spk_pol); g_spk_pol=None

    root_date = ensure_dir(Path(a.out_root)/f"aoi_{aoi_id}"/date_str)
    out_root  = ensure_dir(root_date/"SLC")
    final_dir = ensure_dir(root_date/"final")
    subs = [s.strip() for s in a.subswaths.split(",") if s.strip()]

    for ss in subs:
        logging.info("=== %s | %s ===", date_str, ss)
        iw_dir = out_root/ss
        if iw_dir.exists():
            logging.info("Removing stale intermediates: %s", iw_dir)
            shutil.rmtree(iw_dir, ignore_errors=True)
        iw_dir = ensure_dir(iw_dir)

        # Split (all bursts)
        p_split = iw_dir/f"slc_{ss}_split.dim"
        gx = patch_graph_io(g_split, in_zip, p_split, windows_paths=windows_paths)
        gx = patch_graph_params(gx, [
            {"op":"TOPSAR-Split","param":"subswath","value":ss},
            {"op":"TOPSAR-Split","param":"firstBurstIndex","value":None},
            {"op":"TOPSAR-Split","param":"lastBurstIndex","value":None},
            {"op":"TOPSAR-Split","param":"selectedBursts","value":None},
        ])
        run_graph(gpt, gx, a.cache_gb, a.workers)

        # Orbit
        p_orbit = iw_dir/f"slc_{ss}_orbit.dim"
        gx = patch_graph_io(g_orbit, p_split, p_orbit, windows_paths=windows_paths); run_graph(gpt, gx, a.cache_gb, a.workers)
        cleanup_snap_product(p_split)

        # ----- Branch A: Sigma0 → [INT speckle] → GLCM → TC -----
        p_cal      = iw_dir/f"slc_{ss}_cal.dim"
        p_cal_deb  = iw_dir/f"slc_{ss}_cal_deburst.dim"
        p_cal_filt = iw_dir/f"slc_{ss}_cal_filtered.dim"
        p_tex      = iw_dir/f"slc_{ss}_tex.dim"
        p_tex_tc   = iw_dir/f"slc_{ss}_tex_tc.dim"

        gx = patch_graph_io(g_cal, p_orbit, p_cal, windows_paths=windows_paths);         run_graph(gpt, gx, a.cache_gb, a.workers)
        gx = patch_graph_io(g_deb,  p_cal,   p_cal_deb, windows_paths=windows_paths);    run_graph(gpt, gx, a.cache_gb, a.workers)
        cleanup_snap_product(p_cal)

        src_for_tex = p_cal_deb
        if aoi_wkt:
            p_cal_deb_subset = iw_dir/f"slc_{ss}_cal_deburst_subset.dim"
            gx = patch_graph_io(g_subset, p_cal_deb, p_cal_deb_subset, windows_paths=windows_paths)
            gx = patch_graph_params(gx, [{"op":"Subset","param":"geoRegion","value":aoi_wkt}])
            run_graph(gpt, gx, a.cache_gb, a.workers)
            cleanup_snap_product(p_cal_deb)
            src_for_tex = p_cal_deb_subset
        if g_spk_int:
            gx = patch_graph_io(g_spk_int, src_for_tex, p_cal_filt, windows_paths=windows_paths); run_graph(gpt, gx, a.cache_gb, a.workers)
            cleanup_snap_product(src_for_tex)
            src_for_tex = p_cal_filt

        gx = patch_graph_io(g_tex, src_for_tex, p_tex, windows_paths=windows_paths);     run_graph(gpt, gx, a.cache_gb, a.workers)
        gx = patch_graph_io(g_tc,  p_tex,       p_tex_tc, windows_paths=windows_paths);  run_graph(gpt, gx, a.cache_gb, a.workers)
        cleanup_snap_product(p_tex)

        # sigma0 → TC (VV/VH map space)
        p_sig_tc = iw_dir/f"slc_{ss}_sigma0_tc.dim"
        gx = patch_graph_io(g_tc, src_for_tex, p_sig_tc, windows_paths=windows_paths);   run_graph(gpt, gx, a.cache_gb, a.workers)
        cleanup_snap_product(src_for_tex)

        export_to_geotiff(gpt, p_tex_tc,    final_dir/f"slc_{ss}_tex_tc.tif",    cache_gb=a.cache_gb, workers=a.workers, windows_paths=windows_paths)
        export_to_geotiff(gpt, p_sig_tc,    final_dir/f"slc_{ss}_sigma0_tc.tif", cache_gb=a.cache_gb, workers=a.workers, windows_paths=windows_paths)
        cleanup_snap_product(p_tex_tc)
        cleanup_snap_product(p_sig_tc)

        # ----- Branch B: Deburst? → C2 → [POL speckle] → Decomp → TC -----
        need_deburst_before_c2 = not (graph_has_operator(g_c2,"TOPSAR-Deburst") or graph_has_operator(g_c2,"Deburst"))
        p_deb      = iw_dir/f"slc_{ss}_deburst.dim"
        p_c2       = iw_dir/f"slc_{ss}_c2.dim"
        p_c2f      = iw_dir/f"slc_{ss}_c2_filtered.dim"
        p_decmp    = iw_dir/f"slc_{ss}_decomp.dim"
        p_c2_tc    = iw_dir/f"slc_{ss}_c2_tc.dim"
        p_decmp_tc = iw_dir/f"slc_{ss}_decomp_tc.dim"

        c2_input = p_orbit
        if need_deburst_before_c2:
            gx = patch_graph_io(g_deb, p_orbit, p_deb, windows_paths=windows_paths);     run_graph(gpt, gx, a.cache_gb, a.workers)
            c2_input = p_deb
            if aoi_wkt:
                p_deb_subset = iw_dir/f"slc_{ss}_deburst_subset.dim"
                gx = patch_graph_io(g_subset, p_deb, p_deb_subset, windows_paths=windows_paths)
                gx = patch_graph_params(gx, [{"op":"Subset","param":"geoRegion","value":aoi_wkt}])
                run_graph(gpt, gx, a.cache_gb, a.workers)
                cleanup_snap_product(p_deb)
                c2_input = p_deb_subset

        gx = patch_graph_io(g_c2, c2_input, p_c2, windows_paths=windows_paths);          run_graph(gpt, gx, a.cache_gb, a.workers)
        if c2_input != p_orbit:
            cleanup_snap_product(c2_input)
        cleanup_snap_product(p_orbit)

        src_c2 = p_c2
        if g_spk_pol:
            gx = patch_graph_io(g_spk_pol, p_c2, p_c2f, windows_paths=windows_paths);    run_graph(gpt, gx, a.cache_gb, a.workers)
            src_c2 = p_c2f

        gx = patch_graph_io(g_decomp, src_c2,  p_decmp, windows_paths=windows_paths);    run_graph(gpt, gx, a.cache_gb, a.workers)
        gx = patch_graph_io(g_tc,     p_decmp, p_decmp_tc, windows_paths=windows_paths); run_graph(gpt, gx, a.cache_gb, a.workers)
        cleanup_snap_product(src_c2)
        cleanup_snap_product(p_c2)
        cleanup_snap_product(p_c2f)
        cleanup_snap_product(p_decmp)

        # ----- Export finals (GeoTIFF) + delete IW temps -----
        export_to_geotiff(gpt, p_decmp_tc,  final_dir/f"slc_{ss}_decomp_tc.tif", cache_gb=a.cache_gb, workers=a.workers, windows_paths=windows_paths)
        cleanup_snap_product(p_decmp_tc)

        shutil.rmtree(iw_dir, ignore_errors=True)  # drop temps for this IW
        logging.info("IW %s exported → %s (temps removed)", ss, final_dir)

    logging.info("DONE: AOI %s | %s", aoi_id, date_str)

if __name__ == "__main__":
    main()
