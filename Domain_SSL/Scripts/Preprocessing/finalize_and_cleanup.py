# finalize_and_cleanup.py
from __future__ import annotations
import argparse, shutil
from pathlib import Path
import subprocess, sys

def run(cmd:list[str]):
    print(">", " ".join(cmd))
    subprocess.check_call(cmd)

def main():
    ap = argparse.ArgumentParser("Build final stacks for a date and purge intermediates")
    ap.add_argument("--preproc-root", required=True, help=r"D:\Masters\Domain_SSL\PreProccess")
    ap.add_argument("--downloads-root", required=True, help=r"D:\Masters\Domain_SSL\downloads_S1")
    ap.add_argument("--aoi", required=True, type=int)
    ap.add_argument("--date", required=True)  # e.g. 2020-08-23
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--keep-downloads", action="store_true", help="Keep original zips; default = keep")
    args = ap.parse_args()

    pre = Path(args.preproc_root) / f"aoi_{args.aoi}" / args.date
    slc = pre / "SLC"
    final_dir = pre / "final"; final_dir.mkdir(parents=True, exist_ok=True)
    bio_dir = Path(args.downloads_root) / f"aoi_{args.aoi}" / args.date / "bio"

    # stack each subswath that exists
    for ss in ("IW1","IW2","IW3"):
        sub = slc / ss
        if not sub.exists(): continue
        out = final_dir / f"slc_{ss}_stack.tif"
        run([args.python, "stack_slc_dir.py",
             "--subswath_dir", str(sub),
             "--bio_dir",      str(bio_dir),
             "--out",          str(out)])

    # ---- PURGE: remove SLC and GRD intermediates (keeps only 'final') ----
    for p in [slc, pre/"GRD"]:
        if p.exists():
            print(f"Deleting {p} ...")
            shutil.rmtree(p, ignore_errors=True)

    # optionally delete downloads for this date (raw inputs) – OFF by default
    if not args.keep_downloads:
        print("Keeping downloads (--keep-downloads not set). Skipping raw purge.")

    print("Done. Final stacks in:", final_dir)

if __name__ == "__main__":
    main()