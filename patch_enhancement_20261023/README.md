# Full-Area filtered, patch and VV/VH enhancement

Open the usual batch.qgz and expand **Area | filtered, patch and VV-VH views v1**. This group starts switched off so the saved view is preserved. Choose one acquisition at a time. Start with **VV 60 m patch | signed contrast (dB)**, then compare with **Refined Lee VV | signed contrast (dB)** and **60 m agreement**. Existing annotation and reference vectors remain above the new raster layers.

The entire Area.geojson polygon is included at each source's native SAR pixel spacing. Pixels outside the polygon or without valid SAR/support are NoData. The source raster grids are not resampled. Surrounding-water calculations use a halo outside the polygon to avoid artificial clipping-edge effects. The March 5 images are complementary slices with partial data coverage; March 7 has data throughout the polygon. No coverage has been invented for either slice.

## 1. Filtered VV

Use the existing Refined Lee VV dB raster, without further speckle filtering. Signed contrast = central filtered dB value minus the mean filtered dB in a surrounding square annulus. Outer half-width is 150 m and excluded guard half-width is 50 m. The standardized companion divides by max(background population SD, 1 dB). This is descriptive normalization, not statistical significance or thermal-noise removal. Boundaries may change with the pre-existing filter; original unsmoothed VV and VH dB views are retained for comparison.

## 2. Patch versus surrounding water

For nominal central square widths of 30, 60 and 120 m, average positive calibrated linear sigma0 over eligible water pixels. Compare that mean with the mean linear sigma0 in a surrounding square annulus of outer half-width 300 m and guard half-width 100 m:

    signed patch contrast = 10 log10(central mean intensity / surrounding mean intensity)

Compute separately for VV and VH. Positive means brighter, negative means darker. Do not divide dB values. No absolute-value transformation or clipping is applied to stored contrasts. Averaging reduces local variability but can dilute small targets and blur apparent boundaries. The three sizes are fixed comparison views, not target-dependent parameter choices. Central patches must be at least 90% eligible water with four cells; rings must be at least 70% eligible water with 30 cells. A central unsupported pixel remains unsupported even if neighbours qualify.

Metre dimensions are rounded to odd pixel windows using source spacing at the Area midpoint, and can differ slightly from the nominal widths. Exact spacing and native windows are in each raster's metadata and JSON sidecar. Source values are not interpolated.

## 3. VV/VH agreement at 60 m

Categorize each signed channel contrast as brighter (>+1 dB), darker (<-1 dB), or within the deadband (including ±1 dB). The nine combinations are preserved: both brighter, both darker, either opposite-direction combination, four one-channel changes, and neither outside the deadband. The ±1 dB boundary is a fixed display convention, not a debris threshold or significance test. Continuous signed channels remain available alongside the categories.

Instrument thermal-noise/NESZ calibration is unavailable. Every supported agreement pixel is explicitly marked **instrument noise unassessed**; it must not be interpreted as verified reliable VH. A separate status layer identifies both channels supported, VV-only support, VH-only support, or neither patch supported. Unsupported agreement pixels are transparent. Mean VH intensity, water-background intensity and support fractions are included as diagnostics; none establishes a calibrated electronic noise floor.

## Shared settings and limitations

Blue-white-red continuous displays use fixed -6 to +6 dB bounds and zero centre; standardized filtered contrast uses -3 to +3. Values outside the display range remain numerically intact. Annual ESA WorldCover 2021 v200 class 80 (permanent water), nearest-neighbour aligned to the SAR grid, defines eligible water with a 30 m margin from nonwater/unknown classes. This ancillary map is not an acquisition-specific water mask; it uses Sentinel-1 and Sentinel-2 and may contain errors or changes since 2021. No debris labels or fitted plastic classifier determine enhancement values. Strong contrasts can also arise from ships, wakes, fronts and other water processes. These are annotation aids; improved delineation has not been validated.

Categorical agreement/status and continuous bands are stored together; nearest-neighbour overviews preserve category codes. Native-resolution values are unchanged by overview generation. All calculations use actual source pixels with halo processing and explicit validity masks.

Inputs and annotation datasets were not edited. A timestamped backup of batch.qgz was created. New layers are in a separate initially-off group. Save pending annotation layer edits before reloading an already-open QGIS project; avoid overwriting the new group by saving an old project layout. Original layer references and checked states were verified unchanged.

Source and processing records: method.json, manifest.json, algorithm_checks.json, raster_checks.json, project_checks.json in D:/Masters/patch_enhancement_20261023. Scripts: generate.py, test_method.py, verify.py, update_project.py. Generation uses the existing isolated Python environment and QGIS 3.40.4; masks use the prior worldcover_mask.py helper. Do not reuse completed outputs after changing method settings: use a new version directory.

Water-map attribution: ESA WorldCover 10 m 2021 v200, doi:10.5281/zenodo.7254221, CC BY 4.0. Public tile URLs are recorded in each cached mask.
