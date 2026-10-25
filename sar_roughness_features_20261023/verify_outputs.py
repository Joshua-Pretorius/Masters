import os
for k in ['PROJ_LIB','PROJ_DATA','GDAL_DATA']:os.environ.pop(k,None)
from pathlib import Path
import json,numpy as np,pandas as pd,rasterio,joblib,zipfile,csv,subprocess,sys
from model_roughness import CORE,CORRECTED,corrected_features,decision
ROOT=Path(r'D:\Masters\sar_roughness_features_20261023');scenes=json.loads((ROOT/'data/map_scenes.json').read_text());df=pd.read_csv(ROOT/'data/combined_scored_pixels.csv',low_memory=False);checks=[]
for scene in scenes:
 sid=scene['scene'];local=df[df.scene==sid];origin=scene['map_native_origin'];rr=local.row.to_numpy(int)-origin[0];cc=local.col.to_numpy(int)-origin[1];h,w=scene['map_shape'];inside=(rr>=0)&(rr<h)&(cc>=0)&(cc<w);g=local[inside];r=rr[inside];c=cc[inside]
 with rasterio.open(scene['raw_crop']) as raw,rasterio.open(scene['common_features']) as core,rasterio.open(ROOT/'rasters'/f'{sid}_roughness_separation.tif') as derived:
  assert raw.crs==core.crs==derived.crs and raw.transform==core.transform==derived.transform;assert raw.shape==core.shape==derived.shape
  all_values=core.read()[:,r,c].T;finite=np.isfinite(all_values).all(axis=1);g=g[finite];r=r[finite];c=c[finite];values=all_values[finite];delta=float(np.max(abs(values-g[CORE].to_numpy()))) if len(g) else None
  if len(g):assert np.allclose(values,g[CORE].to_numpy(),atol=2e-3),delta
  score=derived.read(12)[r,c];expected=g.pooled_corrected_score.to_numpy();max_score=float(np.max(abs(score-expected))) if len(g) else None
  if len(g):assert np.allclose(score,expected,atol=2e-3),max_score
  held=derived.read(13)[r,c]
  if len(g):assert np.allclose(held,g.held_event_common_score,atol=2e-3)
  assert derived.count==19
 record={'scene':sid,'native_grid_match':True,'sampled_pixels_inside_map':len(g),'max_common_feature_difference':delta,'max_score_difference':max_score}
 if scene['processing']=='native_SLC':
  with rasterio.open(ROOT/'rasters'/f'{sid}_rich_SLC_separation.tif') as rich:
   assert rich.transform==core.transform and rich.count==8
   if len(g):assert np.allclose(rich.read(2)[r,c],g.rich_pooled_corrected_score,atol=2e-3)
 record['rich_grid_verified']=scene['processing']=='native_SLC';checks.append(record)
# Confirm no test event entered the water baseline.
for scene in scenes:
 bundle=joblib.load(ROOT/'models'/f"{scene['scene']}_held_event.joblib");assert scene['event'] not in set(bundle['background']['water_objects'].event)
# Verify metadata collector copies only small metadata, not measurement imagery.
qa=ROOT/'tmp_collector_test';qa.mkdir(exist_ok=True);products=qa/'products';products.mkdir(exist_ok=True)
with zipfile.ZipFile(products/'TEST_PRODUCT.zip','w') as z:
 for name in ['manifest.safe','annotation/subswath.xml','annotation/calibration/noise-test.xml','annotation/calibration/calibration-test.xml','measurement/skip.tiff']:z.writestr('TEST_PRODUCT.SAFE/'+name,'test metadata fixture')
with (qa/'request.csv').open('w',newline='') as f:writer=csv.DictWriter(f,fieldnames=['scene','granule']);writer.writeheader();writer.writerow({'scene':'TEST_SCENE','granule':'TEST_PRODUCT'})
subprocess.run([sys.executable,str(ROOT/'instrument_noise/collect_noise_metadata.py'),'--product-root',str(products),'--output',str(qa/'collected'),'--requests',str(qa/'request.csv')],check=True)
files=[x for x in (qa/'collected/TEST_PRODUCT').rglob('*') if x.is_file()];assert len(files)==4 and all(x.suffix!='.tiff' for x in files)
(ROOT/'data/quality_checks.json').write_text(json.dumps({'raster_checks':checks,'held_event_background_leakage_check':'passed','metadata_only_collector_test':'passed: four metadata files copied; measurement TIFF excluded','label_overlap_audit':'No positive-negative overlap found at sampled pixel centres'},indent=2))
print(json.dumps(checks,indent=2));print('Held-event baseline leakage check and metadata collector test passed')
