# run_dates_minimal.py
from __future__ import annotations
import argparse, subprocess, sys, shutil
from pathlib import Path

def sh(cmd:list[str]):
    print(">", " ".join(cmd)); subprocess.check_call(cmd)

def purge_downloads_date(downloads_root:Path, aoi:int, date:str):
    d = downloads_root / f"aoi_{aoi}" / date
    if not d.exists(): return
    for item in d.iterdir():
        nm = item.name.lower()
        if nm in ("bio", "manifest.json"):  # keep bio + manifest
            continue
        print(f"Deleting RAW: {item}")
        if item.is_dir(): shutil.rmtree(item, ignore_errors=True)
        else:
            try: item.unlink()
            except Exception: pass

def main():
    ap = argparse.ArgumentParser("Per-date: preprocess→export finals→delete temps + RAWs")
    ap.add_argument("--downloads-root", required=True)   # D:\Masters\Domain_SSL\downloads_S1
    ap.add_argument("--aoi", required=True, type=int)
    ap.add_argument("--graphs-dir", required=True)
    ap.add_argument("--out-root", default=r"D:\Masters\Domain_SSL\PreProccess")
    ap.add_argument("--gpt", default=r"C:\Program Files\esa-snap\bin\gpt.exe")
    ap.add_argument("--subswaths", default="IW1,IW2,IW3")
    ap.add_argument("--int-speckle-graph", default=None)
    ap.add_argument("--python", default=sys.executable)
    args = ap.parse_args()

    aoi_dir = Path(args.downloads_root)/f"aoi_{args.aoi}"
    dates = sorted([p.name for p in aoi_dir.iterdir() if (aoi_dir/p.name/"manifest.json").exists()])
    if not dates:
        print("No dates found."); return

    for date in dates:
        print(f"\n=== DATE {date} ===")

        # 1) preprocess one date (writes finals, deletes IW temps)
        cmd = [args.python, "preprocess_slc_full.py",
               "--manifest",  str(aoi_dir/date/"manifest.json"),
               "--graphs-dir",str(args.graphs_dir),
               "--out-root",  args.out_root,
               "--gpt",       args.gpt,
               "--subswaths", args.subswaths]
        if args.int_speckle_graph:
            cmd += ["--int-speckle-graph", args.int_speckle_graph]
        sh(cmd)

        # 2) delete any leftover SLC/GRD under PreProccess for that date (usually already gone)
        pre_date = Path(args.out_root)/f"aoi_{args.aoi}"/date
        for p in [pre_date/"SLC", pre_date/"GRD"]:
            if p.exists():
                print(f"Deleting leftover: {p}")
                shutil.rmtree(p, ignore_errors=True)

        # 3) delete RAWs for this date (keep bio + manifest)
        purge_downloads_date(Path(args.downloads_root), args.aoi, date)

    print("\nAll dates done. Only final GeoTIFFs remain under PreProccess\\aoi_X\\<date>\\final.")

if __name__ == "__main__":
    main()
