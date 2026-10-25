# Signed water-relative SAR enhancement — fixed v1

Open your normal batch.qgz. Expand **Signed water-relative SAR | fixed v1**, choose the acquisition and turn on one enhancement layer. The group starts off to preserve your current map. Blue means darker than local mapped water, white means near the background, red means brighter. Switch between acquisitions rather than overlaying them. If QGIS was already open, save any pending annotation edits and reopen the project from disk; saving an old open project can overwrite the newly added layer group.

## What the values mean

For each pixel, convert positive calibrated linear sigma0 to dB using 10 log10. Do not smooth the central value. In a surrounding square ring, use valid mapped-water pixels to compute the arithmetic mean mu and population standard deviation s of dB backscatter.

Signed contrast = pixel dB minus mu.
Signed standardized contrast = (pixel dB minus mu) / max(s, 1 dB).

A pixel of -17 dB against a -22 dB background has +5 dB contrast; the same pixel against -14 dB has -3 dB contrast. The sign is retained in both products. No absolute values, positive-only filtering, or clipping are applied to stored contrast values.

The small scale has nominal outer half-width 150 m and guard half-width 50 m. The broad scale has half-widths 500 m and 150 m. These are square annuli, not circular radii. Dimensions are rounded to an odd number of native pixels using pixel distances at the work-area midpoint. Exact per-patch dimensions and metre spacings are recorded in each GeoTIFF JSON sidecar. Native source grids are preserved; no source interpolation or pixel upsampling. The fixed settings are an initial reproducible design, not empirically optimized or validated optimal scales.

## Background eligibility and limitations

Water eligibility uses ESA WorldCover 2021 v200 class 80 (permanent water), aligned by nearest neighbour to the unchanged SAR grid. Pixels within 30 m of nonwater or unknown classes are excluded. Both ocean and inland permanent water can qualify. This externally produced annual land-cover map uses Sentinel-1 and Sentinel-2; it is not an acquisition-specific water classification or independent sensor measurement. Land-cover errors, reclamation, unmapped structures and changes since 2021 may affect this mask. No target polygons were used to correct it. The historical GSHHG mask was rejected during visual QA because it obscured the known Greece sites; it is not used in the delivered enhancement. At least 70% of the full annulus and at least 30 pixels must be valid mapped water. Unsupported contrast pixels are NoData, never a fabricated zero. Inspect the support-fraction layers, especially near shore or source edges. In the Greece deployment footprints the 150 m view supports 55 of 60 pixel centres across the four images; the 500 m view supports none because of nearby land. This is not a detection result. The larger scale is intentionally blank there.

No SAR brightness threshold defines water, so dark and bright ocean features are treated symmetrically. Ships, wakes, fronts and large debris patches can still affect the mean and spread. The guard limits central-target contamination, but extended features can enter the ring. The two fixed scales expose sensitivity to context; selecting whichever looks most target-like would introduce bias. Use 150 m as the primary predefined view and 500 m as a consistently reviewed secondary view.

These are descriptive enhancement layers, not plastic probabilities, hypothesis-test z scores, or proof of debris. The 1 dB denominator floor prevents amplification of an almost-flat background and has no instrument-calibration meaning. Thermal noise/NESZ correction has not been added. Treat weak VH cautiously. CMEMS and existing plastic labels do not determine these values. Optical/deployment references define where to inspect and coverage only. Improvement in delineation consistency still requires independent evaluation.

## Layers and display

Each scene has VV and, where available, VH. Each polarization has signed dB and standardized contrast at both scales. Blue-white-red display limits are fixed at -6 to +6 dB, or -3 to +3 standardized units, with zero centered. Values outside these ranges retain their numeric values and saturate only in display. There is no scene-specific contrast stretch. Background means, spreads, valid-water fractions and an original unsmoothed dB view are included under diagnostics. Water support is diagnostic and is allowed on mapped land; the contrast itself is water-masked.

## Coverage and preservation

Coverage includes actual optical references, drift/search uncertainty geometries and existing annotations, plus 1 km rectangular context. Disjoint work areas are mosaicked using VRTs with NoData outside them. These are digitising-area products, not complete Sentinel-1 swath products. The batch with only AOI context markers uses that context extent instead; it is recorded in jobs.json. Reference points outside a source image cannot obtain enhancement values from that image. A missing source is not replaced by a texture or decomposition band. Manila uses the separately recovered calibrated VV/VH pair, recorded in the manifest.

GeoTIFFs, per-band VRTs and JSON metadata are stored beside each batch project under water_relative_enhancement_v1. Existing source rasters and annotation datasets are not edited. Each updated batch.qgz has a timestamped batch.before_signed_water_*.qgz backup. Reference and annotation vectors are ordered above the enhancement rasters so their outlines remain visible. The original layer sources and checked states are verified unchanged, and pre-existing broken layers remain documented. New enhancement layers are independently checked. Build scripts, method settings, source inventory, checks and exclusions are in this report directory.

## Reproduction and evidence

Scripts: inventory.py, prepare.py, fetch_coast.py, enhance.py, test_algorithm.py, verify_rasters.py, add_to_projects.py. The add script intentionally refuses to add a second copy of the enhancement group. Generation resumes only from completed TIFF+JSON pairs. For any method changes use a new version directory instead of reusing v1.

Algorithm checks cover additive-dB shift invariance, sign-reversal symmetry, uniform-background zero, direct annulus calculations, masked-land exclusion, and retention of bright/dark signals. Raster checks compare native grids and an independent recalculation across processing-tile joins. Project checks validate new sources and preserve original references and visibility. These are implementation checks, not a demonstration of annotation improvement.

Water mask source: https://esa-worldcover.org/en/data-access
ESA WorldCover 10 m 2021 v200, doi:10.5281/zenodo.7254221, CC BY 4.0. Each cached mask records the exact public source tile URLs. Band 1 preserves aligned land-cover classes and band 2 records water eligibility. The rejected GSHHG archive remains in the audit folder only.
