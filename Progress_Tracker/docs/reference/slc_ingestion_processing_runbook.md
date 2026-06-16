# MERIA SA SLC Data Ingestion And Processing Runbook

This runbook explains how to run the enhanced Sentinel-1 SLC data ingestion and processing pipeline implemented in:

`Data_Creation/process_meria_sa_slc_targets.py`

Use this document when you want to prepare a target, download the ASF SLC zip, run the SNAP processing chain, or rerun the next MERIA date.

## What The Command Does

The script performs both ingestion and processing:

1. Reads the requested MERIA target from `MERIA_SA_plastic_nearest_S1_SLC_before_after.csv`.
2. Reads the MERIA point geometry from `MERIA_SA_plastic_points.csv`.
3. Builds a padded WGS84 AOI around the MERIA points.
4. Finds or downloads the Sentinel-1 SLC zip from ASF.
5. Unzips the SAFE product.
6. Runs the SNAP graph chain for `IW1`, `IW2`, and `IW3`.
7. Skips any subswath that does not intersect the AOI.
8. Exports SNAP products to GeoTIFF.
9. Mosaics valid subswaths onto one final scene grid.
10. Writes a manifest with inputs, outputs, processing settings, and final grid metadata.

The default final grid is `snap-native`, which keeps SNAP terrain-corrected WGS84 output resolution. It does not force the older 10 m UTM grid unless you explicitly pass `--resolution-policy utm-grid`.

## Output Products

Each complete enhanced target writes these single-band `float32` GeoTIFF products:

```text
vv
vh
vv_refined_lee
vv_glcm_mean
vv_glcm_std
vv_glcm_entropy
decomp_entropy
decomp_anisotropy
decomp_alpha
```

For the default native policy, filenames use this shape:

```text
{scene_id}_slc_native_vv.tif
{scene_id}_slc_native_vh.tif
{scene_id}_slc_native_vv_refined_lee.tif
{scene_id}_slc_native_vv_glcm_mean.tif
{scene_id}_slc_native_vv_glcm_std.tif
{scene_id}_slc_native_vv_glcm_entropy.tif
{scene_id}_slc_native_decomp_entropy.tif
{scene_id}_slc_native_decomp_anisotropy.tif
{scene_id}_slc_native_decomp_alpha.tif
```

All enhanced products for one scene share the same CRS, transform, width, and height. Nodata is written as `NaN`.

## Prerequisites

Run from the repository root:

```bash
cd /mnt/d/Masters
```

You need:

- Python environment with the project dependencies installed.
- ESA SNAP installed.
- SNAP GPT executable available at `C:\Program Files\esa-snap\bin\gpt.exe` on Windows, or reachable from WSL as `/mnt/c/Program Files/esa-snap/bin/gpt.exe`.
- Earthdata credentials in `EDL_USER` and `EDL_PASS`, or in a netrc file.
- SNAP graph XMLs under `sar_ml_pipeline/graphs`.

Required graph files:

```text
01_split.xml
02_orbit_apply.xml
03_calibration.xml
04_deburst.xml
05_subset.xml
06_polarimetric_matrix.xml
07_speckle_filter.xml
08_terrain_correction.xml
09_polarimetric_decomposition.xml
10_feature_extraction.xml
```

## Target Names

Targets are passed as:

```text
--target OBS_ID:before
--target OBS_ID:after
```

The built-in default targets are:

| Target | MERIA observation date | Sentinel-1 acquisition used | Notes |
|---|---|---|---|
| `MERIA_SA_001:after` | `2019-04-24` | `2019-04-25 03:10:55 UTC` | Already verified with enhanced native outputs. |
| `MERIA_SA_002:after` | `2019-04-25` | `2019-04-27 16:36:47 UTC` | This is the next date to run after `MERIA_SA_001:after`. |
| `MERIA_SA_003:before` | `2022-04-14` | `2022-04-12 16:29:35 UTC` | Flood-event before scene. |

If you omit `--target`, the script attempts all three default targets. For controlled long SNAP runs, run one target at a time.

## Recommended Full Run From WSL

This is the standard command for one enhanced native-resolution target:

```bash
python3 Data_Creation/process_meria_sa_slc_targets.py \
  --target MERIA_SA_001:after \
  --work-root Data_Creation/meria_sa_plastic_s1_slc/_slc_work \
  --gpt "/mnt/c/Program Files/esa-snap/bin/gpt.exe" \
  --workers 1 \
  --cache-gb 8 \
  --keep-zip \
  --keep-safe \
  --force \
  --verbose
```

Use `--force` when rebuilding a target, especially if an older VV/VH-only UTM manifest already exists. After a target has complete enhanced `snap-native` products, omit `--force` to let the script skip cleanly.

## Recommended Full Run From PowerShell

Run from `D:\Masters`:

```powershell
.\.venvs\domain_ssl\Scripts\python.exe .\Data_Creation\process_meria_sa_slc_targets.py `
  --target MERIA_SA_001:after `
  --work-root "D:\Masters\Data_Creation\meria_sa_plastic_s1_slc\_slc_work" `
  --gpt "C:\Program Files\esa-snap\bin\gpt.exe" `
  --workers 1 `
  --cache-gb 8 `
  --keep-zip `
  --keep-safe `
  --force `
  --verbose
```

In PowerShell, every continuation backtick must be the last character on that line. Do not paste log text after a backtick, because PowerShell will treat it as part of the command.

## Run The Next Date

The next default target after the verified `MERIA_SA_001:after` scene is:

```text
MERIA_SA_002:after
```

It corresponds to:

```text
MERIA observation date: 2019-04-25
Sentinel-1 SLC acquisition: 2019-04-27 16:36:47 UTC
Granule: S1B_IW_SLC__1SDV_20190427T163647_20190427T163717_015994_01E106_0A21
```

Run it from WSL:

```bash
python3 Data_Creation/process_meria_sa_slc_targets.py \
  --target MERIA_SA_002:after \
  --work-root Data_Creation/meria_sa_plastic_s1_slc/_slc_work \
  --gpt "/mnt/c/Program Files/esa-snap/bin/gpt.exe" \
  --workers 1 \
  --cache-gb 8 \
  --keep-zip \
  --keep-safe \
  --force \
  --verbose
```

Run it from PowerShell:

```powershell
.\.venvs\domain_ssl\Scripts\python.exe .\Data_Creation\process_meria_sa_slc_targets.py `
  --target MERIA_SA_002:after `
  --work-root "D:\Masters\Data_Creation\meria_sa_plastic_s1_slc\_slc_work" `
  --gpt "C:\Program Files\esa-snap\bin\gpt.exe" `
  --workers 1 `
  --cache-gb 8 `
  --keep-zip `
  --keep-safe `
  --force `
  --verbose
```

`--force` is included because this workspace already contains an older VV/VH-only manifest for `MERIA_SA_002:after`. The enhanced skip logic should not treat that old manifest as complete, but `--force` makes the rerun explicit.

## Prepare Only

Use this to confirm target lookup, AOI bounds, and manifest creation without Earthdata credentials, download, unzip, or SNAP processing:

```bash
python3 Data_Creation/process_meria_sa_slc_targets.py \
  --target MERIA_SA_002:after \
  --prepare-only \
  --verbose
```

Expected result:

- A manifest is written.
- Manifest status is `prepared`.
- No SLC zip is downloaded.
- No SNAP graph is run.

## Download Only

Use this to ingest the ASF zip without running SNAP:

```bash
python3 Data_Creation/process_meria_sa_slc_targets.py \
  --target MERIA_SA_002:after \
  --download-only \
  --keep-zip \
  --verbose
```

Expected result:

- Earthdata credentials are checked.
- The matching ASF SLC zip is downloaded or reused.
- Manifest status is `downloaded`.
- No SAFE unzip or SNAP processing is run.

## Run All Default Targets

Use this only when you are ready for a long run:

```bash
python3 Data_Creation/process_meria_sa_slc_targets.py \
  --work-root Data_Creation/meria_sa_plastic_s1_slc/_slc_work \
  --gpt "/mnt/c/Program Files/esa-snap/bin/gpt.exe" \
  --workers 1 \
  --cache-gb 8 \
  --keep-zip \
  --keep-safe \
  --verbose
```

With no `--force`, already complete enhanced native targets are skipped. Older VV/VH-only UTM outputs do not count as complete enhanced products.

## UTM Grid Mode

Use this only if you specifically need the legacy-style 10 m UTM grid:

```bash
python3 Data_Creation/process_meria_sa_slc_targets.py \
  --target MERIA_SA_002:after \
  --resolution-policy utm-grid \
  --resolution-m 10 \
  --work-root Data_Creation/meria_sa_plastic_s1_slc/_slc_work \
  --gpt "/mnt/c/Program Files/esa-snap/bin/gpt.exe" \
  --workers 1 \
  --cache-gb 8 \
  --keep-zip \
  --keep-safe \
  --force \
  --verbose
```

Do not pass `--resolution-m` for normal native runs. It only affects `--resolution-policy utm-grid`.

## Arguments

| Argument | Default | Usage |
|---|---:|---|
| `--target` | built-in default targets | Repeatable target selector in `obs_id:before` or `obs_id:after` form. |
| `--out-root` | `Data_Creation/meria_sa_plastic_s1_slc/processed_slc` | Final output root. |
| `--work-root` | `Data_Creation/meria_sa_plastic_s1_slc/_slc_work` | Temporary SNAP work root. |
| `--graphs-dir` | `sar_ml_pipeline/graphs` | SNAP graph XML directory. |
| `--gpt` | auto-detected | SNAP GPT executable. Pass it explicitly for reliability. |
| `--resolution-policy` | `snap-native` | `snap-native` or `utm-grid`. |
| `--resolution-m` | `10.0` | UTM pixel size in meters, only used in `utm-grid` mode. |
| `--pad-deg` | `0.47` | WGS84 AOI padding around MERIA points. This is roughly 52 km north/south and 40-45 km east/west for the current target latitudes. |
| `--workers` | `1` | SNAP GPT worker count passed as `-q`. |
| `--cache-gb` | `8` | SNAP GPT cache size passed as `-c`. |
| `--download-only` | off | Download the ASF zip and stop. |
| `--prepare-only` | off | Build target/AOI manifest metadata and stop. |
| `--keep-zip` | off | Keep the downloaded ASF zip after success. |
| `--keep-safe` | off | Keep the unzipped SAFE folder after success. |
| `--force` | off | Reprocess even if outputs already exist. |
| `--verbose`, `-v` | INFO logging | Increase logging verbosity. |

## Expected Output Folder Layout

For `MERIA_SA_002:after`, the enhanced native products will be written under:

```text
Data_Creation/meria_sa_plastic_s1_slc/processed_slc/
  MERIA_SA_002_Durban/
    after_20190427T163647/
      MERIA_SA_002_Durban_after_20190427T163647_slc_manifest.json
      MERIA_SA_002_Durban_after_20190427T163647_slc_native_vv.tif
      MERIA_SA_002_Durban_after_20190427T163647_slc_native_vh.tif
      MERIA_SA_002_Durban_after_20190427T163647_slc_native_vv_refined_lee.tif
      MERIA_SA_002_Durban_after_20190427T163647_slc_native_vv_glcm_mean.tif
      MERIA_SA_002_Durban_after_20190427T163647_slc_native_vv_glcm_std.tif
      MERIA_SA_002_Durban_after_20190427T163647_slc_native_vv_glcm_entropy.tif
      MERIA_SA_002_Durban_after_20190427T163647_slc_native_decomp_entropy.tif
      MERIA_SA_002_Durban_after_20190427T163647_slc_native_decomp_anisotropy.tif
      MERIA_SA_002_Durban_after_20190427T163647_slc_native_decomp_alpha.tif
      SLC/
```

## Basic Verification

Compile check:

```bash
python3 -m py_compile Data_Creation/process_meria_sa_slc_targets.py
```

Check the manifest status after a run:

```bash
python3 -m json.tool \
  Data_Creation/meria_sa_plastic_s1_slc/processed_slc/MERIA_SA_002_Durban/after_20190427T163647/MERIA_SA_002_Durban_after_20190427T163647_slc_manifest.json \
  | sed -n '1,140p'
```

Check one output with GDAL:

```bash
gdalinfo Data_Creation/meria_sa_plastic_s1_slc/processed_slc/MERIA_SA_002_Durban/after_20190427T163647/MERIA_SA_002_Durban_after_20190427T163647_slc_native_vv.tif
```

What to confirm:

- Driver is GeoTIFF.
- Product has one band.
- Type is `Float32`.
- CRS is normally `EPSG:4326` for `snap-native`.
- Pixel size is SNAP terrain-corrected native scale, not forced 10 m UTM.
- All nine enhanced outputs have matching CRS, transform, width, and height.
- GLCM outputs do not contain `-9999`.
- `vv_glcm_std` is nonnegative.
- `vv_refined_lee` differs from `vv` but shares the same grid.

## Skip Logic

A target is skipped only when:

- `--force` is not passed.
- The manifest exists.
- Manifest status is `processed`.
- Manifest processing policy is `snap-native` when using the default native run.
- All expected enhanced output products exist.

Old products named like this do not count as complete enhanced products:

```text
{scene_id}_slc_vv.tif
{scene_id}_slc_vh.tif
```

Those were legacy VV/VH-only UTM products.

## Operational Notes

SNAP may print DEM download warnings during terrain correction. If the graph still completes and the final GeoTIFFs validate, those warnings are not necessarily fatal.

If processing fails, the script preserves the target work directory under `_slc_work` for inspection. If processing succeeds, the per-target work directory is removed.

Use `--keep-zip --keep-safe` while developing or debugging so the raw zip and unzipped SAFE are retained. For production cleanup, omit one or both flags once you are confident that re-download is acceptable.
