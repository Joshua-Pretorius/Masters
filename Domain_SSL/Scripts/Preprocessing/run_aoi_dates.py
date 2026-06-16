# run_aoi_dates.py
from __future__ import annotations
import argparse, json, subprocess, sys, shutil
from pathlib import Path

def sh(cmd:list[str]):
    print(">", " ".join(cmd))
    subprocess.check_call(cmd)

def main():
    ap = argparse.ArgumentParser("Process all dates for an AOI and purge intermediates per date")
    ap.add_argument("--downloads-root", required=True, help=r"D:\Masters\Domain_SSL\downloads_S1")
    ap.add_argument("--aoi", required=True, type=int)
    ap.add_argument("--graphs-dir", required=True)
    ap.add_argument("--out-root", default=r"D:\Masters\Domain_SSL\PreProccess")
    ap.add_argument("--gpt", default=r"C:\Program Files\esa-snap\bin\gpt.exe")
    ap.add_argument("--int-speckle-graph", default=None)
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--subswaths", default="IW1,IW2,IW3")
    ap.add_argument("--keep-downloads", action="store_true", help="keep raw downloads")
    args = ap.parse_args()

    aoi_root = Path(args.downloads_root) / f"aoi_{args.aoi}"
    dates = sorted([p for p in aoi_root.iterdir() if p.is_dir() and (p/"manifest.json").exists()])
    if not dates:
        print("No dates found."); return

    for d in dates:
        date = d.name
        manifest = d/"manifest.json"
        print(f"\n=== DATE {date} ===")
        # 1) preprocess SLC
        cmd = [args.python, "preprocess_slc_full.py",
               "--manifest", str(manifest),
               "--graphs-dir", str(args.graphs_dir),
               "--out-root", args.out_root,
               "--gpt", args.gpt,
               "--subswaths", args.subswaths]
        if args.int_speckle_graph:
            cmd += ["--int-speckle-graph", args.int_speckle_graph]
        sh(cmd)

        # 2) stack per subswath
        pre_date = Path(args.out_root)/f"aoi_{args.aoi}"/date
        final_dir = pre_date/"final"; final_dir.mkdir(parents=True, exist_ok=True)
        bio_dir = d/"bio"
        for ss in [s.strip() for s in args.subswaths.split(",") if s.strip()]:
            subswath_dir = pre_date/"SLC"/ss
            if subswath_dir.exists():
                out = final_dir/f"slc_{ss}_stack.tif"
                sh([args.python, "stack_slc_dir.py",
                    "--subswath_dir", str(subswath_dir),
                    "--bio_dir",      str(bio_dir),
                    "--out",          str(out)])

        # 3) purge intermediates for this date (keep only final/)
        for p in [pre_date/"SLC", pre_date/"GRD"]:
            if p.exists():
                print(f"Deleting {p} ...")
                shutil.rmtree(p, ignore_errors=True)

        if not args.keep_downloads:
            print("Keeping downloads (default). Use explicit purge if desired.")

    print("\nAll dates done.")

if __name__ == "__main__":
    main()
