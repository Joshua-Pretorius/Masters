from pathlib import Path
import json, numpy as np, pandas as pd, rasterio, joblib
from analyse_features import ROOT,SCENES,ENGINEERED,fit,predict,metric,feature_cube
raw=pd.read_csv(ROOT/'data/model_input_pixels.csv'); calibrated=raw.copy(); parameters={}
for sid,g in raw.groupby('scene'):
 a=g[g.object_id=='water_1'][ENGINEERED].to_numpy(); b=g[g.object_id=='water_3'][ENGINEERED].to_numpy(); n=min(len(a),len(b)); rng=np.random.default_rng(42)
 ref=np.concatenate([a[rng.choice(len(a),n,replace=False)],b[rng.choice(len(b),n,replace=False)]])
 center=np.median(ref,axis=0); scale=np.maximum((np.percentile(ref,75,axis=0)-np.percentile(ref,25,axis=0))/1.349,1e-5)
 parameters[sid]={'center':center.tolist(),'scale':scale.tolist(),'calibration_polygons':['water_1','water_3'],'evaluation_water_polygons':['water_2','water_4']}
 idx=calibrated.scene==sid; calibrated.loc[idx,ENGINEERED]=(raw.loc[idx,ENGINEERED].to_numpy()-center)/scale
use=calibrated[(calibrated.label=='deployment')|calibrated.object_id.isin(['water_2','water_4'])]
metrics=[]; predictions=[]; bundles={}
for scheme,column in [('leave_scene_out','scene'),('leave_year_out','year')]:
 for value in sorted(use[column].unique()):
  train=use[use[column]!=value]; test=use[use[column]==value].copy(); model=fit(train,ENGINEERED); test['score']=predict(model,test)
  if column=='scene':bundles[value]=model
  for sid,g in test.groupby('scene'):
   metrics.append({'scheme':scheme,'scene':sid,**metric((g.label=='deployment').to_numpy(int),g.score.to_numpy())})
  test['scheme']=scheme;predictions.append(test[['scene','label','object_id','row','col','score','scheme']])
pd.DataFrame(metrics).to_csv(ROOT/'data/water_calibrated_validation.csv',index=False)
pd.concat(predictions).to_csv(ROOT/'data/water_calibrated_predictions.csv',index=False)
(ROOT/'models/water_calibration_parameters.json').write_text(json.dumps(parameters,indent=2))
print(pd.DataFrame(metrics).to_string(index=False),flush=True)
for scene in SCENES:
 sid=scene['scene']
 with rasterio.open(scene['raw_crop']) as src: a=feature_cube(src.read()); profile=src.profile
 h,w=a.shape[1:]; data=pd.DataFrame((a.reshape(len(ENGINEERED),-1).T-np.array(parameters[sid]['center']))/np.array(parameters[sid]['scale']),columns=ENGINEERED)
 score=predict(bundles[sid],data).reshape(h,w).astype('float32'); profile.update(count=1,nodata=np.nan)
 with rasterio.open(ROOT/'rasters'/f'{sid}_water_calibrated_held_out.tif','w',**profile) as dst:
  dst.write(score,1);dst.set_band_description(1,'Held-out scene logistic after water1+water3 calibration');dst.update_tags(calibration='Water polygons 1 and 3; excluded from model fit and reported evaluation. Target scene deployment labels not used in this model.',evaluation='Deployment pixels versus water2+water4 only; different evaluation set from main uncalibrated analysis.')
 joblib.dump(bundles[sid],ROOT/'models'/f'{sid}_water_calibrated_held_out.joblib')
 print('calibrated raster',sid,flush=True)
