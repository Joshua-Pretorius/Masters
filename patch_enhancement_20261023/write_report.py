import json,shutil,html,hashlib
from pathlib import Path
ROOT=Path(r'D:\Masters\patch_enhancement_20261023');BASE=Path(r'D:\Joshua\New\Debris_Visible_Not_Done\marida_18qyg_20200305_20200307_01');OUT=BASE/'digitising_batches'/BASE.name/'area_patch_enhancement_v1';rows=json.loads((ROOT/'raster_checks.json').read_text())
shutil.copy2(BASE/'Area.geojson',ROOT/'Area_used.geojson')
text='''# Full-Area filtered, patch and VV/VH enhancement

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
'''
(ROOT/'README.md').write_text(text,encoding='utf-8');(OUT/'README.md').write_text(text,encoding='utf-8')
trs=''.join(f'<tr><td>{r["scene"]}</td><td>{100*r["original_vv_valid"]/r["area_pixels"]:.1f}%</td><td>{100*r["patch60_supported"]/r["area_pixels"]:.1f}%</td></tr>' for r in rows)
page='''<!doctype html><meta charset="utf-8"><title>Full-Area SAR views</title><style>body{max-width:1100px;margin:35px auto;padding:20px;font:16px/1.6 system-ui;color:#213047}h1{line-height:1.2}td,th{padding:10px;border-bottom:1px solid #ccd4dc;text-align:left}img{max-width:100%}.box{background:#edf3f8;padding:20px;border-radius:10px}table{width:100%;border-collapse:collapse}</style><h1>Full-Area filtered, patch and VV/VH views</h1><div class="box">In your usual <b>batch.qgz</b>, enable <b>Area | filtered, patch and VV-VH views v1</b>. Choose an acquisition and start with <b>VV 60 m patch | signed contrast (dB)</b>. Compare it with <b>Refined Lee VV</b> and <b>60 m agreement</b>. View one raster at a time. Blue means darker and red brighter than surrounding water.</div><p>All three enhancement families are generated over the complete Area.geojson polygon for all three scenes. Missing SAR and insufficient water support remain NoData. Source grids and annotations are preserved; no plastic-label fitting is used.</p><table><tr><th>Scene UTC</th><th>Area with valid SAR</th><th>Area with supported VV 60 m contrast</th></tr>'''+trs+'''</table><p>The March 5 images are partial, complementary slices. The March 7 image covers the entire polygon. All bands preserve signed contrast. The agreement legend describes nine VV/VH behaviours; its ±1 dB deadband is a display convention, not a detection threshold. <b>Instrument-noise reliability is unassessed</b>, with a dedicated channel-support/status layer.</p><p><a href="README.md">Full method and usage</a> · <a href="raster_checks.json">Native-grid and numerical checks</a> · <a href="project_checks.json">Project backup and validation</a></p>'''
for r in rows:
 page+='<h2>'+r['scene']+'</h2>'
 for label in ['filtered','patch60','agreement']:page+=f'<details><summary>{label}</summary><img src="{r["scene"]}_{label}.png"></details>'
(ROOT/'REPORT.html').write_text(page,encoding='utf-8');print('Documentation written')
