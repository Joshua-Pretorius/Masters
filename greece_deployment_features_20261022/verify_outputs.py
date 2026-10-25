import os
for k in ['PROJ_LIB','PROJ_DATA','GDAL_DATA']:os.environ.pop(k,None)
from pathlib import Path
import json,numpy as np,pandas as pd,rasterio,hashlib
from sklearn.metrics import roc_auc_score
p=Path(r'D:\Masters\greece_deployment_features_20261022');scenes=json.loads((p/'data/scene_inventory.json').read_text());df=pd.read_csv(p/'data/scored_pixels.csv');checks=[]
for scene in scenes:
 sid=scene['scene'];g=df[df.scene==sid];r=g.crop_row.to_numpy(int);c=g.crop_col.to_numpy(int)
 with rasterio.open(scene['raw_crop']) as raw,rasterio.open(p/'rasters'/f'{sid}_derived_features.tif') as derived,rasterio.open(p/'rasters'/f'{sid}_water_calibrated_held_out.tif') as cal:
  assert raw.crs.to_epsg()==4326 and raw.transform==derived.transform==cal.transform
  assert raw.width==derived.width==cal.width and raw.height==derived.height==cal.height
  assert np.allclose(derived.read(4)[r,c],g.scene_fit_logistic,atol=1e-5)
  assert np.allclose(derived.read(5)[r,c],g.held_out_logistic,atol=1e-5)
  assert derived.count==19
  with rasterio.open(scene['source_rasters'][0]) as source:
   expected=source.transform*(int(g.col.iloc[0])+.5,int(g.row.iloc[0])+.5)
   actual=raw.transform*(int(g.crop_col.iloc[0])+.5,int(g.crop_row.iloc[0])+.5)
   assert np.allclose(expected,actual,atol=1e-12)
 checks.append({'scene':sid,'native_grid_verified':True,'score_raster_matches_pixel_table':True,'input_bands':10,'derived_bands':19,'core_target':int(sum(g.label=='deployment')),'core_water':int(sum(g.label=='water'))})
# Original labels are only read; hashes document exactly which source polygons were used.
hashes=[]
for path in sorted(set(s['source_polygon'] for s in scenes)|set(s['water_polygon'] for s in scenes)):
 for f in Path(path).parent.glob(Path(path).stem+'.*'):
  hashes.append({'path':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
(p/'data/quality_checks.json').write_text(json.dumps({'checks':checks,'source_polygon_hashes':hashes,'notes':'Model score agreement and exact native grid verified. Source rasters were window-read; no source files were modified.'},indent=2))
fit=[]
for sid,g in df.groupby('scene'):
 near=g[(g.label=='deployment')|g.object_id.isin(['water_2','water_4'])]
 fit.append({'scene':sid,'scene_fit_AUC_all_water':roc_auc_score(g.label=='deployment',g.scene_fit_logistic),'scene_fit_AUC_nearer_water2_4':roc_auc_score(near.label=='deployment',near.scene_fit_logistic)})
pd.DataFrame(fit).to_csv(p/'data/scene_fit_metrics.csv',index=False)
print(json.dumps(checks,indent=2))
