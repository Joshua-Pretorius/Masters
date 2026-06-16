# Enhanced MERIA SA SLC Data-Creation Pipeline

This document describes the implementation in:

`Data_Creation/process_meria_sa_slc_targets.py`

The pipeline processes selected MERIA South Africa plastic-observation targets through a Sentinel-1 SLC SNAP workflow and writes scene-level single-band GeoTIFF products. The default output geometry is SNAP-native terrain-corrected WGS84 resolution, not the older 10 m UTM grid.

## What The Pipeline Does

For each requested target, the script:

1. Reads the target match from `Data_Creation/meria_sa_plastic_s1_slc/MERIA_SA_plastic_nearest_S1_SLC_before_after.csv`.
2. Reads MERIA point coordinates from `Data_Creation/meria_sa_plastic_s1_slc/MERIA_SA_plastic_points.csv`.
3. Builds a padded WGS84 AOI bounding polygon from those points.
4. Finds or downloads the matching ASF Sentinel-1 SLC zip.
5. Unzips the SAFE product if needed.
6. Runs the SNAP graph workflow for each subswath: `IW1`, `IW2`, `IW3`.
7. Skips a subswath if the AOI does not intersect it after the SNAP subset step.
8. Exports intermediate terrain-corrected SNAP products to GeoTIFF.
9. Mosaics the intersecting subswath products into scene-level single-band outputs.
10. Writes a manifest containing inputs, outputs, processing settings, graph paths, and final grid metadata.

Default targets, when `--target` is not provided:

```text
MERIA_SA_001:after
MERIA_SA_002:after
MERIA_SA_003:before
```

## Products Written

For `--resolution-policy snap-native`, outputs are named:

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

For `--resolution-policy utm-grid`, outputs use `_slc_utm_...` in the filename instead.

All final products are:

- Single-band GeoTIFFs
- `float32`
- Tiled
- DEFLATE compressed
- `NaN` nodata
- Written on the same final scene grid

The older 10 m products named `{scene_id}_slc_vv.tif` and `{scene_id}_slc_vh.tif` are not overwritten by the native pipeline.

When `--output-mode subswath` or `--output-mode both` is used, the same product set is also written per valid IW subswath:

```text
subswaths/IW1/{scene_id}_slc_native_IW1_vv.tif
subswaths/IW2/{scene_id}_slc_native_IW2_vv.tif
subswaths/IW3/{scene_id}_slc_native_IW3_vv.tif
```

Only subswaths that intersect the AOI produce files.

## Main Command Examples

Recommended full run for one target from WSL/Linux:

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

Equivalent PowerShell shape:

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

Prepare only, without download or SNAP processing:

```bash
python3 Data_Creation/process_meria_sa_slc_targets.py \
  --target MERIA_SA_001:after \
  --prepare-only \
  --verbose
```

Download only:

```bash
python3 Data_Creation/process_meria_sa_slc_targets.py \
  --target MERIA_SA_001:after \
  --download-only \
  --keep-zip \
  --verbose
```

Run all default targets:

```bash
python3 Data_Creation/process_meria_sa_slc_targets.py \
  --gpt "/mnt/c/Program Files/esa-snap/bin/gpt.exe" \
  --workers 1 \
  --cache-gb 8 \
  --keep-zip \
  --keep-safe \
  --verbose
```

Run all three IW subswaths as separate products, without scene mosaicking:

```bash
python3 Data_Creation/process_meria_sa_slc_targets.py \
  --target MERIA_SA_005:before \
  --output-mode subswath \
  --subswaths IW1,IW2,IW3 \
  --gpt "/mnt/c/Program Files/esa-snap/bin/gpt.exe" \
  --workers 1 \
  --cache-gb 4 \
  --keep-zip \
  --keep-safe \
  --force \
  --verbose
```

Run separate IW products and the scene mosaic in the same pass:

```bash
python3 Data_Creation/process_meria_sa_slc_targets.py \
  --target MERIA_SA_005:before \
  --output-mode both \
  --subswaths IW1,IW2,IW3 \
  --gpt "/mnt/c/Program Files/esa-snap/bin/gpt.exe" \
  --workers 1 \
  --cache-gb 4 \
  --keep-zip \
  --keep-safe \
  --force \
  --verbose
```

Run with the legacy-style UTM product grid:

```bash
python3 Data_Creation/process_meria_sa_slc_targets.py \
  --target MERIA_SA_001:after \
  --resolution-policy utm-grid \
  --resolution-m 10 \
  --gpt "/mnt/c/Program Files/esa-snap/bin/gpt.exe" \
  --workers 1 \
  --cache-gb 8 \
  --keep-zip \
  --keep-safe \
  --force \
  --verbose
```

## CLI Arguments

| Argument | Default | How to pass it | What it does |
|---|---:|---|---|
| `--target` | Defaults to 3 built-in targets | `--target MERIA_SA_001:after` | Selects a target in `obs_id:before` or `obs_id:after` form. Can be repeated. |
| `--out-root` | `Data_Creation/meria_sa_plastic_s1_slc/processed_slc` | `--out-root /path/to/out` | Root folder for final scene folders and manifests. |
| `--work-root` | `Data_Creation/meria_sa_plastic_s1_slc/_slc_work` | `--work-root /path/to/work` | Temporary SNAP work directory. Removed after success. Preserved after failure. |
| `--graphs-dir` | `sar_ml_pipeline/graphs` | `--graphs-dir /path/to/graphs` | Folder containing SNAP graph XML files. |
| `--gpt` | Auto-detected | `--gpt "/mnt/c/Program Files/esa-snap/bin/gpt.exe"` | SNAP GPT executable. Required for full processing. |
| `--resolution-policy` | `snap-native` | `--resolution-policy snap-native` | Final grid policy. Choices: `snap-native`, `utm-grid`. |
| `--output-mode` | `scene` | `--output-mode subswath` | Output layout. Choices: `scene`, `subswath`, `both`. |
| `--subswaths` | `IW1,IW2,IW3` | `--subswaths IW1,IW2,IW3` | Comma-separated IW subswaths to run. Use `--subswaths IW3` to only run IW3. |
| `--resolution-m` | `10.0` | `--resolution-m 10` | UTM grid spacing in meters. Used only when `--resolution-policy utm-grid`. |
| `--pad-deg` | `0.47` | `--pad-deg 0.47` | WGS84 degree padding around MERIA points before subsetting/mosaicking. This is roughly 52 km north/south and 40-45 km east/west for the current target latitudes. |
| `--workers` | `1` | `--workers 1` | SNAP GPT `-q` worker count. |
| `--cache-gb` | `8` | `--cache-gb 8` | SNAP GPT `-c` cache size in GB. |
| `--download-only` | off | `--download-only` | Downloads or reuses the SLC zip and writes a manifest with status `downloaded`; does not unzip or run SNAP. |
| `--prepare-only` | off | `--prepare-only` | Writes target/AOI manifest metadata with status `prepared`; does not need Earthdata credentials. |
| `--keep-zip` | off | `--keep-zip` | Keeps the ASF SLC zip after successful full processing. |
| `--keep-safe` | off | `--keep-safe` | Keeps the unzipped SAFE folder after successful full processing. |
| `--force` | off | `--force` | Reprocesses even if a complete enhanced manifest and outputs already exist. |
| `--verbose`, `-v` | INFO logging | `--verbose` | Increases logging verbosity. The script defaults to INFO; passing it once moves to DEBUG because the default count is already `1`. |

## Required Credentials

Full runs and `--download-only` need Earthdata credentials unless the matching zip already exists and no download is attempted.

The script reads credentials with `edl_auth()` from:

- `EDL_USER` and `EDL_PASS`
- standard netrc files
- Windows netrc at `/mnt/c/Users/Joshua Pretorius/_netrc`

`--prepare-only` intentionally bypasses credential lookup.

## SNAP Graphs Used

The script expects these graph XMLs under `--graphs-dir`:

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

`ensure_graphs(graphs_dir)` builds this graph map:

```python
{
    "split": graphs_dir / "01_split.xml",
    "orbit": graphs_dir / "02_orbit_apply.xml",
    "calibration": graphs_dir / "03_calibration.xml",
    "deburst": graphs_dir / "04_deburst.xml",
    "subset": graphs_dir / "05_subset.xml",
    "c2": graphs_dir / "06_polarimetric_matrix.xml",
    "speckle": graphs_dir / "07_speckle_filter.xml",
    "terrain": graphs_dir / "08_terrain_correction.xml",
    "decomp": graphs_dir / "09_polarimetric_decomposition.xml",
    "texture": graphs_dir / "10_feature_extraction.xml",
}
```

## Internal Function Call Flow

The script entrypoint is:

```python
main()
```

`main()` does:

1. `parse_args()`
2. `setup_logging(args.verbose)`
3. `parse_targets(args.target)`
4. `load_matches(selected)`
5. `edl_auth()` unless `--prepare-only`
6. `ensure_graphs(Path(args.graphs_dir))` unless `--download-only` or `--prepare-only`
7. `find_gpt(args.gpt)` unless `--download-only` or `--prepare-only`
8. For each target, call `process_target(...)`

The main processing function is:

```python
process_target(
    target: Target,
    out_root: Path,
    work_root: Path,
    graphs: dict[str, Path] | None,
    gpt: str | None,
    auth: tuple[str, str],
    resolution_policy: str,
    resolution_m: float,
    pad_deg: float,
    cache_gb: int,
    workers: int,
    download_only: bool,
    prepare_only: bool,
    keep_zip: bool,
    keep_safe: bool,
    force: bool,
) -> None
```

`process_target()` does:

1. Builds `out_dir`, `raw_dir`, `zip_path`, `safe_dir`, and `manifest_path`.
2. Calls `product_output_paths(target, out_dir, resolution_policy)`.
3. Calls `polarizations_for_granule(target.granule)`.
4. Calls `expected_product_keys(selected_pols)`.
5. Calls `target_bounds_wgs84(target, pad_deg)`.
6. If `resolution_policy == "utm-grid"`, calls `ensure_reference_grid(...)`.
7. Skips processing if `outputs_complete(...)` is true and `force` is false.
8. Writes a prepared manifest with `write_manifest(...)`.
9. Downloads with `stream_download_asf(...)` if the zip is missing.
10. Unzips with `unzip_safe(zip_path, safe_dir)`.
11. For `IW1`, `IW2`, `IW3`, calls `run_enhanced_subswath(...)`.
12. Drops subswaths where `run_enhanced_subswath(...)` returns `None`.
13. Builds the final grid with `native_scene_profile(...)` or the UTM reference grid.
14. Calls `write_scene_products(...)`.
15. Calls `grid_metadata(...)`.
16. Writes a processed manifest.
17. Removes the work directory only after successful processing.
18. Removes SAFE and/or zip unless `--keep-safe` or `--keep-zip` were passed.

## Per-Subswath SNAP Flow

The per-subswath function is:

```python
run_enhanced_subswath(
    gpt: str,
    graphs: dict[str, Path],
    slc_input: Path,
    work_dir: Path,
    subswath: str,
    selected_pols: list[str],
    aoi_wkt: str,
    cache_gb: int,
    workers: int,
) -> SubswathProducts | None
```

It runs the following SNAP flow.

Common setup:

```text
TOPSAR-Split
Apply-Orbit-File
```

For the sigma0 branch:

```text
Calibration
TOPSAR-Deburst
Subset using AOI WKT
Terrain-Correction
Export to GeoTIFF
```

If the subset product is not created because the AOI does not intersect the subswath, the function logs the skip and returns `None`.

For the filtered and texture branch:

```text
Speckle-Filter on calibrated/debursted/subset product
Terrain-Correction of filtered product
Export filtered GeoTIFF
GLCM texture extraction from filtered product
Terrain-Correction of texture product
Export texture GeoTIFF
```

The speckle settings are:

```python
SPECKLE_FILTER = {
    "filter": "Refined Lee",
    "filter_size": [3, 3],
}
```

The GLCM settings are:

```python
GLCM_SETTINGS = {
    "source_bands": "Sigma0_VV,Sigma0_VH",
    "window_size": "5x5",
    "angle": "ALL",
    "quantizer": "Probabilistic Quantizer",
    "quantization_levels": 32,
    "displacement": 1,
    "snap_nodata": -9999.0,
}
```

For the decomposition branch:

```text
TOPSAR-Deburst if the C2 graph does not already contain it
Polarimetric-Matrices C2
Subset using AOI WKT
H-Alpha Dual Pol Decomposition
Terrain-Correction
Export decomposition GeoTIFF
```

The decomposition settings recorded in the manifest are:

```python
DECOMPOSITION = {
    "type": "H-Alpha Dual Pol Decomposition",
    "window_size": 5,
    "outputs": ["Entropy", "Anisotropy", "Alpha"],
}
```

## Final Mosaicking

Final products are generated by:

```python
write_scene_products(
    subswath_products: list[SubswathProducts],
    output_paths: dict[str, Path],
    expected_keys: set[str],
    final_profile: dict,
) -> dict[str, Path | None]
```

For each `ProductSpec`, this function:

1. Finds the matching band index from the source SNAP DIMAP metadata.
2. Passes the matching source GeoTIFFs to `write_mosaic_product(...)`.
3. Writes the final single-band scene-level product.

`write_mosaic_product(...)`:

1. Writes to a hidden temporary GeoTIFF beside the final output.
2. Opens each source as a `WarpedVRT` on the final grid.
3. Reads block windows.
4. Merges valid pixels from available subswaths.
5. Applies product-specific nodata handling.
6. Sets the output band description.
7. Replaces the final path with the completed temp file.

## Nodata And Postprocessing Rules

Sigma0 products:

- Mask non-finite values.
- Mask zero-valued fill pixels.

GLCM products:

- Mask non-finite values.
- Mask SNAP `-9999` nodata values.
- `vv_glcm_std` is produced by taking `sqrt(max(GLCMVariance, 0))`.

Decomposition products:

- Mask non-finite values.
- Preserve valid zero values.

## Product Specifications

The script defines these final products:

| Output key | Source branch | Band tokens | Output suffix | Special handling |
|---|---|---|---|---|
| `vv` | `sigma0` | `vv` | `vv` | Mask zeros |
| `vh` | `sigma0` | `vh` | `vh` | Mask zeros; omitted for VV-only scenes |
| `vv_refined_lee` | `filtered` | `vv` | `vv_refined_lee` | Mask zeros |
| `vv_glcm_mean` | `texture` | `vv`, `glcmmean` | `vv_glcm_mean` | Mask `-9999` |
| `vv_glcm_std` | `texture` | `vv`, `glcmvariance` | `vv_glcm_std` | Mask `-9999`, square root |
| `vv_glcm_entropy` | `texture` | `vv`, `entropy` | `vv_glcm_entropy` | Mask `-9999` |
| `decomp_entropy` | `decomp` | `entropy` | `decomp_entropy` | Preserve zero |
| `decomp_anisotropy` | `decomp` | `anisotropy` | `decomp_anisotropy` | Preserve zero |
| `decomp_alpha` | `decomp` | `alpha` | `decomp_alpha` | Preserve zero |

## Manifest Contents

Each target writes:

```text
{out_root}/{obs_id}_{area}/{role}_{acquisition_key}/{scene_id}_slc_manifest.json
```

The manifest includes:

- MERIA observation metadata
- SLC granule, URL, zip path, and selected polarisations
- Output product paths
- Resolution policy
- AOI WGS84 bounds and WKT
- Pad degrees
- Subswaths attempted
- GLCM settings
- Speckle filter settings
- Decomposition settings
- SNAP graph paths
- Final grid CRS, resolution, shape, bounds, and transform
- Status: `prepared`, `downloaded`, or `processed`

## Output Folder Layout

For `MERIA_SA_001:after`, the default output folder is:

```text
Data_Creation/meria_sa_plastic_s1_slc/processed_slc/
  MERIA_SA_001_Durban/
    after_20190425T031055/
      SLC/
      MERIA_SA_001_Durban_after_20190425T031055_slc_manifest.json
      MERIA_SA_001_Durban_after_20190425T031055_slc_native_vv.tif
      MERIA_SA_001_Durban_after_20190425T031055_slc_native_vh.tif
      ...
```

## Verification Commands

Syntax check:

```bash
python3 -m py_compile Data_Creation/process_meria_sa_slc_targets.py
```

Inspect one output:

```bash
gdalinfo Data_Creation/meria_sa_plastic_s1_slc/processed_slc/MERIA_SA_001_Durban/after_20190425T031055/MERIA_SA_001_Durban_after_20190425T031055_slc_native_vv.tif
```

Check Rasterio metadata:

```bash
MPLCONFIGDIR=/tmp rio info Data_Creation/meria_sa_plastic_s1_slc/processed_slc/MERIA_SA_001_Durban/after_20190425T031055/MERIA_SA_001_Durban_after_20190425T031055_slc_native_vv.tif
```

Confirm skip behavior after a successful run:

```bash
python3 Data_Creation/process_meria_sa_slc_targets.py \
  --target MERIA_SA_001:after \
  --gpt "/mnt/c/Program Files/esa-snap/bin/gpt.exe" \
  --workers 1 \
  --cache-gb 8 \
  --keep-zip \
  --keep-safe \
  --verbose
```

Expected skip message:

```text
Skip MERIA_SA_001_Durban_after_20190425T031055: enhanced snap-native outputs already exist
```

## Current Verified MERIA_SA_001 Result

The verified `MERIA_SA_001:after` run produced 9 native products.

Final grid:

```text
CRS: EPSG:4326
Shape: 2512 rows x 2661 columns
Resolution: 0.00012633546829743302 degrees
```

For this target, `IW1` and `IW2` did not intersect the padded AOI after subsetting, and `IW3` produced the final products.

Quality checks passed:

- All outputs are single-band `float32`.
- All outputs share the same grid.
- GLCM outputs contain no remaining `-9999` values.
- `vv_glcm_std` is nonnegative.
- Decomposition products contain finite valid pixels.
- `vv_refined_lee` differs from unfiltered `vv`.

## Practical Notes

- SNAP may emit DEM retrieval warnings such as SRTM tile HTTP warnings. These are not necessarily fatal; rely on the process exit code and output validation.
- Work directories are removed only after successful full processing. If the script fails, the work directory is preserved for inspection.
- The script may create temporary SNAP XML files under `.snap_tmp` folders. They are generated artifacts and can be cleaned separately when no SNAP run is active.
