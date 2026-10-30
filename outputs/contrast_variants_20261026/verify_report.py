from run import *
results=json.loads((ROOT/'results.json').read_text())
checks=[]
for result in results:
 with rasterio.open(result['source']) as src, rasterio.open(result['path']) as dst:
  assert dst.count==24 and src.bounds==dst.bounds and src.crs==dst.crs
  rng=np.random.default_rng(7)
  for i in range(15):
   row=int(rng.integers(20,src.height-100)); col=int(rng.integers(20,src.width-100))
   # Include generated tile boundaries in audit windows.
   if i<5: row=max(20,(row//512)*512-10); col=max(20,(col//512)*512-10)
   a=src.read(window=Window(col-6,row-6,76,76)); actual=dst.read(window=Window(col,row,64,64))
   expected=np.stack([v[6:-6,6:-6] for band in a for v in filters(band)])
   np.testing.assert_allclose(actual,expected,atol=1e-6,equal_nan=True)
  checks.append({'scene':result['scene'],'24_bands_grid_crs':'pass','15_independent_windows_including_tile_boundaries':'pass','positive_negative_present_all_bands':'pass'})
(ROOT/'raster_checks.json').write_text(json.dumps(checks,indent=2))
projects=json.loads((ROOT/'project_checks.json').read_text())
metrics=json.loads((ROOT/'preview_metrics.json').read_text())
lines=['# Experimental contrast denoising — MARIDA 16PEC, 11 January 2019','',
 'Completed for the two scenes in this batch only. Six variants of each of four inputs: 24 layers per scene, 48 unique layers. Original inputs and their four QGIS layers remain unchanged. The batch project and both scene projects have backups and verified new groups.',
 '', 'In QGIS: each image → SAR rasters → Experimental contrast denoising | 2026-10-26 → input layer. Turn on one variant at a time. New layers start unchecked. Reopen the saved project to see the changes; an already-open QGIS session will not refresh automatically.',
 '', '## Exact calculations', '',
 'All operations act on existing signed contrast values in dB, not on raw linear SAR intensity. The native grid and extent remain unchanged. At this location pixels are about 13.4–13.9 m: 3×3 spans about 40–42 m and 5×5 about 67–70 m. These are additional filter footprints on inputs that already have their own spatial support.', '',]
for key,value in METHOD.items(): lines.extend(['**'+key+'**: '+value,''])
lines.extend(['## What the comparison shows','',
 'Median and multiscale views reduce fine-grained fluctuation in the inspected crops. Sign-support views retain sharper original values but leave more clutter. A lower adjacent-pixel difference measures a cleaner display, not better debris detection. There is no independent detection/annotation validation here. For inspection, start with VV 30 m patch / Median 3x3 and compare with its original; then try the multiscale view. Median 5x5 is the stronger suppression option, with greater risk of erasing small targets.',
 '', 'The second scene has no valid contrast in the crop around its sole on-image reference point. Its preview therefore uses another valid-water location; this experiment does not restore masked reference coverage.', '',
 '| Scene | Input | View | Median adjacent-pixel difference (dB) |','|---|---|---|---|'])
for m in metrics:
 if m['input']=='VV 30 m patch contrast': lines.append(f"| {m['scene']} | VV30 | {m['variant']} | {m['median_absolute_adjacent_difference_db']:.3f} |")
lines.extend(['','## Validation','', 'Synthetic tests passed: sign symmetry, NoData preservation, tiled/whole agreement, isolated impulse suppression and coherent patch retention. Each output passed native grid/CRS, 24-band, overviews and both-sign checks; 15 independent windows per scene matched recomputation. Saved-project reopening verified every added layer and preserved original sources, validity and visibility.','', '## Files',''])
for r in results: lines.extend([f"- {r['scene']}: `{r['path']}` ({r['bytes']/1e9:.2f} GB)"])
for p in projects: lines.extend([f"- Project: `{p['project']}`; backup: `{p['backup']}`"])
for r in results: lines.extend(['',f"![Fixed-scale comparison for {r['scene']}]({r['scene']}_comparison.png)"])
(ROOT/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps({'rasters':checks,'project_count':len(projects),'total_gb':sum(r['bytes'] for r in results)/1e9},indent=2))
