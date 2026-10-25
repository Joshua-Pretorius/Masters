import os
for k in ['PROJ_LIB','PROJ_DATA','GDAL_DATA']:os.environ.pop(k,None)
from pathlib import Path
import json,numpy as np,pandas as pd,rasterio,joblib
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from model_roughness import ROOT,CORE,CORRECTED,corrected_features,fit_classifier,decision,evaluate,predict_background
from environment_lookup import EnvironmentalLookup
EXTRA=['lee_excess_db','log_glcm_mean','log_glcm_std','glcm_entropy','H','A','alpha']
NEEDED=['vv_refined_lee_db','vv_glcm_mean','vv_glcm_std','vv_glcm_entropy','decomp_entropy','decomp_anisotropy','decomp_alpha']

def rich_matrix(df,bg,corrected=True):
 core,mu,sd=corrected_features(df,bg)
 extra=np.column_stack([df.vv_refined_lee_db.to_numpy()-mu[:,2],np.log1p(np.maximum(df.vv_glcm_mean.to_numpy(),0)),np.log1p(np.maximum(df.vv_glcm_std.to_numpy(),0)),df.vv_glcm_entropy,df.decomp_entropy,df.decomp_anisotropy,df.decomp_alpha])
 if not corrected:core=df[CORE].to_numpy();extra[:,0]=df.vv_refined_lee_db
 return np.column_stack([core,extra])

if __name__=='__main__':
 all_df=pd.read_csv(ROOT/'data/pixels_with_environment.csv',low_memory=False);df=all_df[np.isfinite(all_df[NEEDED]).all(axis=1)].copy();maps=json.loads((ROOT/'data/map_scenes.json').read_text());metrics=[];predictions=[];models={}
 for scheme,column,suffix in [('leave_event_out','event','held_event'),('leave_location_out','location','held_location')]:
  for value in sorted(df[column].unique()):
   train=df[df[column]!=value];test=df[df[column]==value];bundle=joblib.load(ROOT/'models'/f'{test.scene.iloc[0]}_{suffix}.joblib');bg=bundle['background']
   for corrected in [False,True]:
    name='rich_roughness_corrected' if corrected else 'rich_raw_SAR';X=rich_matrix(train,bg,corrected);m=fit_classifier(train,X);score=decision(m,rich_matrix(test,bg,corrected))
    if corrected:
     for sid in test.scene.unique():models[(scheme,sid)]={'background':bg,'classifier':m}
    for sid,g in test.assign(score=score).groupby('scene'):
     for subset in ['all_negatives','water_only','distractors_only']:
      select=g if subset=='all_negatives' else g[(g.label_group=='plastic')|(g.label_group==('water' if subset=='water_only' else 'distractor'))]
      if len(select):metrics.append({'scheme':scheme,'held_out':value,'model':name,'scene':sid,'location':g.location.iloc[0],'subset':subset,**evaluate(select,select.score.to_numpy())})
    records=test[['scene','event','location','object_id','label_group','class_name','controlled','confidence','row','col']].copy();records['scheme']=scheme;records['model']=name;records['score']=score;predictions.append(records)
   print('rich validated',scheme,value,flush=True)
 bg=joblib.load(ROOT/'models/pooled_models.joblib')['background'];X=rich_matrix(df,bg);corrected_model=fit_classifier(df,X);raw_model=fit_classifier(df,rich_matrix(df,bg,False));pca_scale=StandardScaler().fit(X);pca=PCA(n_components=3).fit(pca_scale.transform(X))
 joblib.dump({'background':bg,'corrected_model':corrected_model,'raw_model':raw_model,'PCA':pca,'PCA_scaler':pca_scale,'features':CORRECTED+EXTRA},ROOT/'models/rich_SLC_models.joblib');pd.DataFrame(metrics).to_csv(ROOT/'data/rich_validation_metrics.csv',index=False);pd.concat(predictions).to_csv(ROOT/'data/rich_held_out_predictions.csv',index=False)
 pd.DataFrame(pca.components_.T,index=CORRECTED+EXTRA,columns=['PC1','PC2','PC3']).to_csv(ROOT/'data/rich_PCA_loadings.csv')
 scored=df.copy();scored['rich_pooled_corrected_score']=decision(corrected_model,X);scored['rich_pooled_raw_score']=decision(raw_model,rich_matrix(df,bg,False));scored['rich_scene_fitted_score']=np.nan
 index=[]
 for scene in maps:
  sid=scene['scene']
  if scene['processing']!='native_SLC':continue
  local=df[df.scene==sid];local_model=fit_classifier(local,rich_matrix(local,bg)) if local.label_group.eq('plastic').any() and local.label_group.ne('plastic').any() else None
  if local_model is not None:scored.loc[scored.scene==sid,'rich_scene_fitted_score']=decision(local_model,rich_matrix(local,bg))
  with rasterio.open(scene['common_features']) as src:core=src.read();profile=src.profile;h,w=src.shape;rr,cc=np.indices((h,w));xx=src.transform.c+(cc.ravel()+.5)*src.transform.a;yy=src.transform.f+(rr.ravel()+.5)*src.transform.e
  from pyproj import Transformer
  lon,lat=Transformer.from_crs(profile['crs'],4326,always_xy=True).transform(xx,yy);frame=pd.concat([pd.DataFrame(core.reshape(len(CORE),-1).T,columns=CORE),EnvironmentalLookup(scene).sample(lon,lat)],axis=1)
  with rasterio.open(scene['raw_crop']) as raw:
   for name in NEEDED:frame[name]=raw.read(scene['raw_band_names'].index(name)+1).ravel()
  valid=np.isfinite(frame[CORE+NEEDED].to_numpy()).all(axis=1);frame=frame.astype({n:'float64' for n in CORE+NEEDED});frame.loc[~valid,CORE+NEEDED]=np.nanmedian(df[CORE+NEEDED].to_numpy(),axis=0)
  rich=rich_matrix(frame,bg);pc=pca.transform(pca_scale.transform(rich));event=models[('leave_event_out',sid)];site=models[('leave_location_out',sid)]
  names=['rich_pooled_raw_EXPLORATORY','rich_pooled_roughness_EXPLORATORY','rich_held_event_roughness','rich_held_location_roughness','rich_scene_fit_EXPLORATORY','rich_PC1','rich_PC2','rich_PC3']
  bands=[decision(raw_model,rich_matrix(frame,bg,False)),decision(corrected_model,rich),decision(event['classifier'],rich_matrix(frame,event['background'])),decision(site['classifier'],rich_matrix(frame,site['background'])),decision(local_model,rich) if local_model is not None else np.full(len(frame),np.nan),pc[:,0],pc[:,1],pc[:,2]]
  stack=np.stack(bands).reshape(len(names),h,w).astype('float32');stack[:,~valid.reshape(h,w)]=np.nan;profile.update(count=len(names),nodata=np.nan);path=ROOT/'rasters'/f'{sid}_rich_SLC_separation.tif'
  with rasterio.open(path,'w',**profile) as dst:
   dst.write(stack)
   for i,n in enumerate(names):dst.set_band_description(i+1,n)
   dst.update_tags(scope='Rich SLC subset only; shared background is trained with all available water scenes; Manila contributes through shared VV/VH models and water baseline.',scene_fit='Exploratory fit to the same scene, unavailable for single-class scenes')
  for i,n in enumerate(names):
   finite=stack[i][np.isfinite(stack[i])];lo,hi=np.percentile(finite,[2,98]) if len(finite) else [-1,1];index.append({'scene':sid,'location':scene['location'],'path':str(path),'band':i+1,'name':n,'p02':float(lo),'p98':float(hi),'available':bool(len(finite))})
  print('rich map',sid,flush=True)
 pd.DataFrame(index).to_csv(ROOT/'data/rich_raster_index.csv',index=False);scored.to_csv(ROOT/'data/rich_scored_pixels.csv',index=False)
 pd.DataFrame([{'feature':n,'coefficient':float(c)} for n,c in zip(CORRECTED+EXTRA,corrected_model['classifier'].coef_[0])]).to_csv(ROOT/'data/rich_hyperplane_coefficients.csv',index=False)
 print(pd.DataFrame(metrics).query("subset=='all_negatives'").groupby(['scheme','model']).object_balanced_auc.mean().to_string())

