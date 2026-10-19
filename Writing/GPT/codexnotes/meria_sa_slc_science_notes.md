# Science Notes: MERIA SA Sentinel-1 SLC Enhanced Product Pipeline

These notes describe the scientific logic behind the MERIA South Africa Sentinel-1 SLC data-creation pipeline. They explain what the pipeline is doing, why each step exists, what each output means, and what results we have verified so far.

Implementation file:

`Data_Creation/process_meria_sa_slc_targets.py`

Operational runbook:

`pipeline documentation/data creation/slc_ingestion_processing_runbook.md`

## Scientific Objective

The pipeline builds analysis-ready radar layers for MERIA South Africa plastic and floating-debris observations. The working problem is to compare known or suspected debris observations with near-time Sentinel-1 SAR acquisitions, then derive radar backscatter, texture, speckle-filtered, and dual-polarimetric descriptors that can support visual analysis and later machine-learning feature construction.

The main target phenomenon is floating material and debris associated with coastal runoff, river plumes, harbour influence, flood events, and nearshore accumulation. Sentinel-1 is useful because C-band SAR can observe surface roughness and scattering structure through cloud cover and independent of daylight. This matters for flood and coastal debris cases where optical images are often cloudy or temporally sparse.

## Why Sentinel-1 SLC

Sentinel-1 SLC products preserve the complex radar measurements before ground-range projection. For interferometric-wide swath mode, the data are organized by TOPS bursts and by subswath: `IW1`, `IW2`, and `IW3`.

The pipeline does not attempt to use raw slant-range complex pixels directly as the final products. Instead, it uses SLC as the high-quality input to SNAP processing, then produces terrain-corrected geocoded layers. In this project, "native resolution" means SNAP terrain-corrected native map resolution, not raw SLC slant-range spacing.

For the verified Durban scene, the native WGS84 terrain-corrected grid was:

```text
CRS: EPSG:4326
Pixel size: 0.00012633546829743302 degrees
Shape: 2512 rows x 2661 columns
```

At Durban latitude, this is roughly SNAP-scale SAR map resolution, around 14 m north-south and about 12 m east-west. The exact meter equivalent varies with latitude because the final grid is in WGS84 degrees.

## High-Level Processing Chain

For each target, the pipeline:

1. Selects a MERIA observation and its matched Sentinel-1 SLC scene.
2. Builds a padded WGS84 AOI from MERIA point locations.
3. Downloads or reuses the ASF SLC zip.
4. Unzips the SAFE package.
5. Processes `IW1`, `IW2`, and `IW3` separately.
6. Runs three scientific branches:
   - calibrated Sigma0 backscatter branch
   - speckle-filtered and GLCM texture branch
   - dual-pol H-alpha decomposition branch
7. Terrain-corrects exported SNAP products.
8. Mosaics valid subswaths onto one scene-level final grid.
9. Writes aligned single-band GeoTIFFs and a manifest.

The result is a stack of nine geospatial products that line up pixel-for-pixel for each scene.

## Target And AOI Selection

The target metadata comes from:

```text
Data_Creation/meria_sa_plastic_s1_slc/MERIA_SA_plastic_nearest_S1_SLC_before_after.csv
```

The MERIA point coordinates come from:

```text
Data_Creation/meria_sa_plastic_s1_slc/MERIA_SA_plastic_points.csv
```

The pipeline converts the selected MERIA points into a WGS84 bounding polygon and expands it by `--pad-deg`, which defaults to `0.47` degrees. This gives the SAR processing enough spatial context around the point observations without processing the full Sentinel-1 swath. At the current Durban, East London, and Mallorca latitudes, that is roughly 52 km north/south and 40-45 km east/west on each side.

Subsetting is done after debursting for the calibrated branch and after C2 creation for the decomposition branch. This keeps the processing smaller while avoiding early burst-boundary problems.

## Subswath Processing

Sentinel-1 IW SLC products are split into `IW1`, `IW2`, and `IW3`. The AOI may intersect only one or two of these. The pipeline tries all three and skips a subswath if SNAP subset output is not created because there is no AOI intersection.

For the verified `MERIA_SA_001:after` Durban scene, `IW1` and `IW2` did not intersect the AOI after subsetting, while `IW3` produced the final products.

## Orbit Correction

After TOPSAR split, SNAP applies orbit information. Orbit correction improves geolocation by replacing or refining the orbit state vectors that describe satellite position and velocity. This matters because all downstream products are geocoded and later mosaicked onto a shared grid.

## Sigma0 Calibration

Calibration converts Sentinel-1 image intensity into normalized radar backscatter. The pipeline writes Sigma0 bands for VV and VH:

```text
vv
vh
```

The calibration graph has:

```text
outputSigmaBand = true
outputImageScaleInDb = false
```

So the final backscatter products are linear Sigma0 values, not decibels. If dB values are needed later, they should be derived explicitly with `10 * log10(sigma0)` after masking nonpositive values.

Scientific meaning:

- `vv` is co-polarized vertical transmit, vertical receive backscatter.
- `vh` is cross-polarized vertical transmit, horizontal receive backscatter.
- VV is often sensitive to surface roughness, waves, slick boundaries, and bright hard targets.
- VH can help describe volume, depolarized, or more complex scattering contributions.

For floating debris work, the absolute backscatter and VV/VH contrast may help separate open water, rough water, harbour structures, vessel contamination, slick-like areas, and textured debris/plume regions.

## Debursting

Sentinel-1 IW SLC data are acquired in TOPS bursts. Debursting merges bursts into a continuous image for each subswath. This step is required before producing clean geocoded products and before AOI subsetting for the calibrated branch.

Without debursting, burst boundaries can produce discontinuities that would contaminate texture and mosaic products.

## Terrain Correction

Terrain correction geocodes the radar products into map coordinates. The default policy is:

```text
--resolution-policy snap-native
```

This means the final products are based on SNAP terrain-corrected native WGS84 output resolution. The pipeline does not force the older 10 m UTM reference grid unless explicitly requested with:

```text
--resolution-policy utm-grid
```

The reason for this choice is to avoid pretending that a finer grid automatically creates finer information. Forcing a 10 m UTM grid resamples the data and may make rasters look finer, but it does not recover information beyond the Sentinel-1 processing resolution. The native policy keeps the SNAP-derived scale and avoids unnecessary resampling.

## Speckle Filtering

SAR images contain speckle, a multiplicative interference effect caused by coherent radar scattering. Speckle is not ordinary sensor noise, but it can obscure stable local patterns and inflate texture metrics.

The pipeline uses SNAP Refined Lee filtering:

```text
Filter: Refined Lee
Window: 3 x 3
```

The product is:

```text
vv_refined_lee
```

Scientific meaning:

- It smooths local speckle while attempting to preserve edges and point-like structure.
- It provides a cleaner VV input for texture computation.
- It is not a replacement for the raw calibrated VV layer; both are retained.

For the verified scene, filtered VV differs from unfiltered VV while sharing the same final grid. That confirms the filter is active and that it did not break spatial alignment.

## GLCM Texture

Texture features are computed with SNAP GLCM on the filtered Sigma0 product. The current settings are:

```text
Source bands: Sigma0_VV,Sigma0_VH
Window size: 5x5
Angle: ALL
Quantizer: Probabilistic Quantizer
Quantization levels: 32
Displacement: 1
SNAP nodata value: -9999.0
```

The pipeline exports the VV texture products:

```text
vv_glcm_mean
vv_glcm_std
vv_glcm_entropy
```

`vv_glcm_std` is derived from SNAP GLCM variance by applying:

```text
sqrt(max(variance, 0))
```

Scientific meaning:

- `vv_glcm_mean` describes the local average VV grey-level structure within the GLCM window.
- `vv_glcm_std` describes local variability in the VV texture window.
- `vv_glcm_entropy` describes disorder or complexity in local VV texture.

These layers are useful because floating debris and plume features are often not defined by a single bright or dark pixel. They can appear as elongated, patchy, or filament-like surface patterns. GLCM features give the model local context around each pixel.

The pipeline masks SNAP GLCM nodata values so `-9999` does not remain in the final GeoTIFFs. Final nodata is `NaN`.

## Dual-Pol C2 Matrix

The decomposition branch builds a dual-polarimetric matrix representation from VV and VH. The graph used is:

```text
06_polarimetric_matrix.xml
```

This step prepares the polarimetric information for decomposition. In simple terms, it turns the dual-pol observations into a form that can describe scattering structure rather than only separate VV and VH intensity values.

The AOI subset is applied after C2 creation. This keeps the decomposition branch consistent and avoids processing unnecessary swath area.

## H-Alpha Dual-Pol Decomposition

The pipeline applies SNAP H-alpha dual-pol decomposition:

```text
Type: H-Alpha Dual Pol Decomposition
Window size: 5
Outputs used: Entropy, Anisotropy, Alpha
```

Final products:

```text
decomp_entropy
decomp_anisotropy
decomp_alpha
```

Scientific meaning:

- `decomp_entropy` describes randomness or disorder in the polarimetric scattering mechanism.
- `decomp_anisotropy` describes the relative importance of secondary scattering mechanisms.
- `decomp_alpha` is related to the dominant scattering type or scattering mechanism angle.

For marine debris and coastal water analysis, these products are exploratory but valuable. They can help distinguish simple open-water backscatter from mixed or structured scattering zones, harbour clutter, vessel-contaminated areas, and possible debris/plume surfaces.

This is separate from `vv_glcm_entropy`. Both entropy products are kept because they describe different things:

- `vv_glcm_entropy` is spatial texture entropy in the VV image.
- `decomp_entropy` is polarimetric scattering entropy from the H-alpha decomposition.

## Mosaic And Final Grid

After SNAP exports per-subswath GeoTIFFs, the Python pipeline mosaics valid subswaths into one scene-level product per layer.

For `snap-native`:

1. The first valid SNAP terrain-corrected Sigma0 source defines CRS and pixel size.
2. The padded AOI bounds are snapped to that source grid.
3. Each requested product is warped only as needed onto the final scene grid.
4. Bilinear resampling is used when a source grid does not align exactly.

All final products share:

- one CRS
- one affine transform
- one width and height
- one nodata policy
- one manifest

For the verified `MERIA_SA_001:after` run, the final grid was:

```text
CRS: EPSG:4326
Resolution: 0.00012633546829743302 x 0.00012633546829743302 degrees
Shape: 2512 x 2661
Bounds: 31.026896505487525, -30.032317421684517, 31.363075186626993, -29.714962725321367
```

## Nodata Handling

The final products use `NaN` nodata and `float32` data type.

Product-specific rules:

- Sigma0 products mask non-finite pixels and zero-valued fill pixels.
- Speckle-filtered VV uses the same Sigma0 masking logic.
- GLCM products convert `-9999` and non-finite values to `NaN`.
- Decomposition products preserve valid zeros and only mask non-finite or source-masked pixels.

This matters because zero can be a valid decomposition value but is usually a fill value in Sigma0 outputs.

## Product Stack

The enhanced output stack is:

| Product | Source branch | Scientific role |
|---|---|---|
| `vv` | calibrated Sigma0 | co-pol backscatter and surface roughness response |
| `vh` | calibrated Sigma0 | cross-pol scattering and additional contrast |
| `vv_refined_lee` | speckle filter | smoother VV for robust texture and comparison |
| `vv_glcm_mean` | GLCM texture | local VV texture mean |
| `vv_glcm_std` | GLCM texture | local VV texture variability |
| `vv_glcm_entropy` | GLCM texture | local VV spatial disorder |
| `decomp_entropy` | H-alpha dual-pol | polarimetric scattering randomness |
| `decomp_anisotropy` | H-alpha dual-pol | secondary scattering mechanism contrast |
| `decomp_alpha` | H-alpha dual-pol | dominant scattering mechanism descriptor |

## Results Verified So Far

The enhanced pipeline has been verified on:

```text
MERIA_SA_001:after
Scene ID: MERIA_SA_001_Durban_after_20190425T031055
Observation date: 2019-04-24
Sentinel-1 acquisition: 2019-04-25 03:10:55 UTC
```

Observed processing behavior:

- `IW1` skipped because it did not intersect the AOI.
- `IW2` skipped because it did not intersect the AOI.
- `IW3` produced the valid scene products.
- All nine enhanced products were written.
- All products are single-band GeoTIFFs.
- All products are `float32`.
- All products share the same CRS, transform, shape, and bounds.
- GLCM outputs no longer contain `-9999`.
- `vv_glcm_std` is nonnegative.
- Decomposition products contain finite values over valid overlap.
- `vv_refined_lee` differs from raw `vv` while staying aligned to the same grid.

The manifest for that run records:

```text
status: processed
resolution_policy: snap-native
reference_grid: null
```

This means the output is not the older 10 m UTM grid.

## How To Interpret The Current Results

The current stack is designed for feature construction rather than as a final detection product by itself.

Useful comparisons include:

- `vv` versus `vv_refined_lee` to inspect how much speckle suppression changes local backscatter.
- `vv` and `vh` together to evaluate polarization contrast.
- `vv_glcm_mean`, `vv_glcm_std`, and `vv_glcm_entropy` to identify locally structured areas rather than isolated bright pixels.
- `decomp_entropy`, `decomp_anisotropy`, and `decomp_alpha` to test whether polarimetric scattering descriptors help separate water, plume, harbour, vessel, and possible debris signatures.

The stack should be treated as aligned feature layers. The most useful analysis will likely combine the products rather than rely on any one layer.

## Practical Scientific Caveats

SAR response over water is strongly affected by wind, wave state, viewing geometry, incidence angle, vessels, harbour infrastructure, slicks, and rainfall effects. Floating debris may be indirect in SAR: it can alter roughness, accumulate along fronts, or appear with plume texture rather than as a simple bright target.

Because of that, the pipeline preserves multiple feature families:

- calibrated backscatter for physical intensity response
- filtered backscatter for reduced speckle
- texture for local spatial structure
- decomposition for polarimetric scattering behavior

The results should be interpreted with the MERIA observation date, Sentinel-1 acquisition time offset, optical/Planet context, and local coastal conditions.

## Next Scientific Step

The next operational date to process is:

```text
MERIA_SA_002:after
```

This target represents the next Durban observation in the current default set:

```text
MERIA observation date: 2019-04-25
Sentinel-1 acquisition: 2019-04-27 16:36:47 UTC
Time offset from observation date: +40.61 hours
```

Run command from WSL:

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

Run command from PowerShell:

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
