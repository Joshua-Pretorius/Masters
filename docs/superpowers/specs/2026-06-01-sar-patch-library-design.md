# SAR Patch Library Design

## Goal

Build a new patch-extraction and feature-library stage for `D:\Masters\Data_Creation` that:

- scans the existing processed SLC scene directories for digitised geometry layers
- extracts fixed `256 x 256` SAR image patches centered on each geometry centroid
- creates aligned raster masks for training segmentation models such as U-Net
- computes per-geometry summary features for a tabular SAR library
- writes the outputs under new top-level directories:
  - `D:\Masters\Data_Creation\Patches`
  - `D:\Masters\Data_Creation\Library`

## Scope

This stage will consume already processed scene products from:

- `D:\Masters\Data_Creation\meria_sa_plastic_s1_slc\processed_slc`
- `D:\Masters\Data_Creation\meria_global_s1_slc\processed_slc`

It will not download or process new Sentinel-1 scenes. It will only use the existing processed rasters and digitised vector layers.

## Source Discovery

The extractor will recursively scan both processed SLC roots for shapefiles located under `digitised_patches` or `Digitised_patches`.

Known input variants:

- most scene layers are `*_digitised_patches.shp`
- one Palma scene uses `PalmadeMallorca_before_20181012.shp`
- Ghana has an extra labeled layer: `*_digitised_other_features.shp`

Each discovered layer is tied back to its containing scene directory. The scene directory is expected to contain a processed scene manifest and the feature rasters required for extraction.

## Class Rules

Two labeling modes will be supported.

### Default `digitised_patches`

Features from standard `digitised_patches` layers are treated as class `plastic`.

This applies even when the shapefile attribute table only contains metadata such as:

- `obs_id`
- `dataset`
- `role`
- `scene_id`
- `area`
- `obs_date`
- `patch_id`
- `confidence`
- `notes`

### Explicit labeled layers

Features from explicitly labeled layers, such as Ghana `digitised_other_features`, use the class field from the shapefile.

Initial class normalization rules:

- trim whitespace
- lowercase for canonical storage
- replace spaces with underscores

Examples:

- `Ship` -> `ship`
- `Wake` -> `wake`
- `Slick` -> `slick`
- `calm_water` -> `calm_water`

The raw class value will also be retained in the library CSV for traceability.

## Patch Definition

Each geometry produces one training sample.

### Geometry anchor

The patch is centered on the geometry centroid.

### Patch size

The patch extent is fixed at `256 x 256` pixels.

The extractor will use the georeferenced raster grid of the source scene outputs, so the real-world patch footprint depends on raster resolution. For the existing terrain-corrected products this is expected to be approximately `10 m`, so a patch is roughly `2.56 km x 2.56 km`.

### Alignment

The patch window must be aligned to the raster grid so that:

- image bands remain co-registered
- the target mask aligns exactly to the image patch
- the same geometry footprint is used for raster extraction and feature summarization

### Edge behavior

If a centroid-centered patch crosses the raster boundary:

- extract the overlapping region
- pad the missing image area with nodata
- pad the mask with background `0`
- record an edge-touch flag in the inventory and library outputs

## Raster Bands

Each patch image will be written as a multiband GeoTIFF with these channels, in fixed order:

1. `vv_db`
2. `vh_db`
3. `vv_vh_ratio_db`
4. `vv_minus_vh_db`
5. `vv_glcm_mean`
6. `vv_glcm_std`
7. `vv_glcm_entropy`
8. `decomp_entropy`
9. `decomp_anisotropy`
10. `decomp_alpha`

### Derived bands

The extractor will compute:

- `vv_db` from the processed VV product in dB if available, otherwise from linear VV using `10 * log10`
- `vh_db` from linear VH using `10 * log10`, masking non-positive values
- `vv_vh_ratio_db = vv_db - vh_db`
- `vv_minus_vh_db = vv_db - vh_db`

For V1 `vv_vh_ratio_db` and `vv_minus_vh_db` are numerically identical in dB space. Both will be retained because the downstream feature work may want explicit semantic naming, but implementation will keep the derivation in one place so this can be simplified later.

## Mask Definition

Each sample gets a single-band mask aligned to the image patch.

Mask values:

- `0` = background
- `1` = target geometry

This is intentionally binary per sample. Even if nearby objects of other classes fall inside the patch extent, the mask marks only the current source geometry. This makes each patch a one-target-centered training example for the first dataset version.

## Output Layout

### Patch files

Patches will be written to:

- `D:\Masters\Data_Creation\Patches\<dataset>\<scene_id>\<class_name>\<sample_id>_image.tif`
- `D:\Masters\Data_Creation\Patches\<dataset>\<scene_id>\<class_name>\<sample_id>_mask.tif`

Where:

- `<dataset>` is `meria_sa` or `meria_global`
- `<scene_id>` is the scene folder name
- `<class_name>` is the normalized class label
- `<sample_id>` is a stable identifier derived from scene and feature identity

### Library files

The library stage will write:

- `D:\Masters\Data_Creation\Library\sar_patch_inventory.csv`
- `D:\Masters\Data_Creation\Library\sar_patch_library.csv`

## CSV Contents

### Inventory CSV

One row per patch sample containing:

- dataset
- scene_id
- observation_id if available
- area
- role
- acquisition timestamp
- source shapefile path
- source layer type
- source feature id
- raw class label
- normalized class label
- sample_id
- image path
- mask path
- patch width
- patch height
- centroid coordinates
- geometry area
- edge-touch flag
- extraction status
- notes or warnings

### Library CSV

One row per patch sample containing all inventory identifiers plus summary statistics computed over labeled pixels only, for each band.

Minimum stats per band:

- valid pixel count
- mean
- standard deviation
- minimum
- maximum
- median
- p10
- p25
- p75
- p90

These statistics are calculated only where mask value is `1` and image pixels are valid.

## Processing Flow

1. Discover scene shapefiles.
2. Pair each shapefile with its scene manifest and feature rasters.
3. Read the vector geometries and normalize labels.
4. For each geometry:
   - create a centroid-centered `256 x 256` window
   - extract the multiband image patch
   - rasterize the geometry to a binary patch mask
   - compute per-band summary statistics over mask `1`
   - write image and mask files
   - append rows to inventory and library tables
5. Continue past recoverable scene-level failures and record them in inventory/logging.

## Error Handling

The extractor must be resilient because the scene tree already contains inconsistent manual digitization outputs.

Recoverable conditions:

- missing expected raster bands
- empty or invalid geometry
- centroid patch falls outside raster extent
- unreadable shapefile
- missing manifest

Policy:

- do not stop the full run for one bad scene or feature
- log the issue with scene and file context
- add an inventory row where possible with failure status
- skip the sample when required inputs are unavailable

## Testing Strategy

Tests must cover the new extraction stage directly, without requiring SNAP or network access.

Core tests:

- discover standard and non-standard digitised patch paths
- classify standard `digitised_patches` features as `plastic`
- read explicit classes from Ghana-style labeled layers
- build a centroid-centered `256 x 256` raster window correctly
- pad image and mask outputs at scene edges
- rasterize a geometry into a binary aligned mask
- compute library statistics from labeled pixels only
- skip invalid scenes gracefully while preserving inventory records

Synthetic raster and vector fixtures will be used wherever possible so the tests remain fast and deterministic.

## Implementation Shape

Add a new script under `D:\Masters\Data_Creation` for the extraction stage, with focused helpers for:

- scene discovery
- label normalization
- raster product lookup
- patch window calculation
- patch extraction
- mask rasterization
- feature summarization
- CSV writing

This keeps the patch-library stage separate from the existing SLC download and processing scripts while still reusing their scene output conventions.

## Open Choices Frozen For V1

The following decisions are fixed for the first implementation:

- fixed centroid-centered patches
- patch size `256 x 256`
- binary masks per sample
- standard `digitised_patches` means `plastic`
- explicit class field only where present in dedicated labeled layers
- top-level outputs under `Patches` and `Library`

## Out Of Scope For V1

- scene-wide sliding-window tiling
- multi-class masks containing all classes in one patch
- balancing or stratified train/validation split generation
- augmentation pipelines
- new scene downloading or reprocessing
- full training pipeline integration
