import os
for key in ['PROJ_LIB','PROJ_DATA','GDAL_DATA']:os.environ.pop(key,None)
from pathlib import Path
import json,numpy as np,pandas as pd,rasterio,joblib
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge,LogisticRegression
from sklearn.decomposition import PCA
from sklearn.metrics import roc_auc_score,average_precision_score,balanced_accuracy_score
from environment_lookup import ROOT,EnvironmentalLookup
from extract_features import CORE
ENV_FEATURES=['log_relative_wind','log_wave_height','log_current_speed','ascending']
CORRECTED=['VV_excess_z','VH_excess_z','VV_median3_excess_z','VH_median3_excess_z','polarization_excess_db','VV_ring_relative','VH_ring_relative','VV_texture_relative','VH_texture_relative']

def environmental_design(df):
 return np.column_stack([np.log1p(df.wind_relative_m_s.to_numpy(float)),np.log1p(df.wave_height_m.to_numpy(float)),np.log1p(df.current_speed_m_s.to_numpy(float)),df.ascending.to_numpy(float)])

def weighted_quantile(a,w,q):
 order=np.argsort(a);a=np.asarray(a)[order];w=np.asarray(w)[order];return float(np.interp(q,(np.cumsum(w)-.5*w)/w.sum(),a))

def training_weights(df,controlled_multiplier=1.5):
 data=df.copy();data['binary']=(data.label_group=='plastic').astype(int)
 n=data.groupby('object_id').object_id.transform('size').to_numpy();objects=data.groupby(['event','scene','label_group']).object_id.transform('nunique').to_numpy()
 scene_counts=data[['event','scene','label_group']].drop_duplicates().groupby(['event','label_group']).size()
 scene_n=np.array([scene_counts.loc[(r.event,r.label_group)] for r in data.itertuples()])
 negativegroups=data[data.binary==0][['event','label_group']].drop_duplicates().groupby('event').size()
 group_n=np.array([negativegroups.loc[r.event] if r.binary==0 else 1 for r in data.itertuples()])
 quality=data.confidence.astype(str).str.lower().map({'high':1.0,'medium':.8,'low':.6,'not_assessed':.75,'known_deployment':1.0,'user_water':1.0}).fillna(.75).to_numpy()
 quality*=np.where(data.controlled.to_numpy(bool),controlled_multiplier,1.0)
 w=quality*np.minimum(data.coverage_fraction.to_numpy(float),1)/(n*objects*scene_n*group_n)
 for klass in [0,1]:
  ix=data.binary.to_numpy()==klass
  if np.any(ix):w[ix]*=50/w[ix].sum()
 return w

def water_summary(df):
 records=[]
 for oid,g in df[df.label_group=='water'].groupby('object_id'):
  rec={'object_id':oid,'scene':g.scene.iloc[0],'event':g.event.iloc[0],'location':g.location.iloc[0]}
  for name in ['wind_relative_m_s','wave_height_m','current_speed_m_s','ascending']:rec[name]=g[name].median()
  for name in CORE[:4]:rec[name]=g[name].median()
  for name in ['vv_db','vh_db']:rec[name+'_sd']=max(float(np.median(abs(g[name]-g[name].median()))*1.4826),.5)
  records.append(rec)
 return pd.DataFrame(records)

def fit_background(df):
 refs=water_summary(df);objects=refs.groupby('scene').object_id.transform('size').to_numpy();events=refs[['event','scene']].drop_duplicates().groupby('event').size();w=np.array([1/(objects[i]*events.loc[r.event]) for i,r in enumerate(refs.itertuples())]);w*=len(w)/w.sum()
 X=environmental_design(refs);imputer=SimpleImputer(strategy='median');X=imputer.fit_transform(X);scaler=StandardScaler().fit(X,sample_weight=w);X=scaler.transform(X)
 y=np.column_stack([refs[CORE[:4]],np.log(refs[['vv_db_sd','vh_db_sd']])]);reg=Ridge(alpha=10).fit(X,y,sample_weight=w)
 bundle={'imputer':imputer,'scaler':scaler,'regression':reg,'water_objects':refs,'feature_names':ENV_FEATURES,'fallback_water_median':np.average(y[:,:4],axis=0,weights=w)}
 # Empirical upper-water envelope, estimated from training water only.
 water=df[df.label_group=='water'];mu,sd=predict_background(bundle,water);z=(water[['vv_db','vh_db']].to_numpy()-mu[:,:2])/sd;counts=water.groupby('object_id').object_id.transform('size').to_numpy();ww=1/counts
 bundle['water_q95_z']=[weighted_quantile(z[:,i],ww,.95) for i in range(2)]
 return bundle

def predict_background(bundle,df):
 X=bundle['scaler'].transform(bundle['imputer'].transform(environmental_design(df)));p=bundle['regression'].predict(X);return p[:,:4],np.clip(np.exp(p[:,4:6]),.5,12)

def corrected_features(df,bg):
 mu,sd=predict_background(bg,df);a=df[CORE].to_numpy(float);z=(a[:,:4]-mu)/np.column_stack([sd,sd]);ratio=a[:,4]-(mu[:,1]-mu[:,0]);other=a[:,5:9]/np.column_stack([sd,sd]);return np.column_stack([z,ratio,other]),mu,sd

def fit_classifier(df,X,multiplier=1.5):
 w=training_weights(df,multiplier);scaler=StandardScaler().fit(X,sample_weight=w);z=np.clip(scaler.transform(X),-12,12);model=LogisticRegression(C=1.0,solver='lbfgs',max_iter=2000).fit(z,(df.label_group=='plastic').astype(int),sample_weight=w)
 return {'scaler':scaler,'classifier':model,'controlled_multiplier':multiplier}

def decision(bundle,X):return bundle['classifier'].decision_function(np.clip(bundle['scaler'].transform(X),-12,12))

def evaluate(df,scores):
 y=(df.label_group=='plastic').to_numpy(int);weights=training_weights(df);result={'n_positive':int(sum(y==1)),'n_negative':int(sum(y==0)),'positive_objects':int(df.loc[y==1,'object_id'].nunique()),'negative_objects':int(df.loc[y==0,'object_id'].nunique()),'roc_auc':None,'object_balanced_auc':None,'average_precision':None,'recall_at_zero':float(np.mean(scores[y==1]>=0)) if np.any(y==1) else None,'negative_false_positive_at_zero':float(np.mean(scores[y==0]>=0)) if np.any(y==0) else None}
 if len(np.unique(y))==2:result.update(roc_auc=float(roc_auc_score(y,scores)),object_balanced_auc=float(roc_auc_score(y,scores,sample_weight=weights)),average_precision=float(average_precision_score(y,scores)))
 return result

if __name__=='__main__':
 df=pd.read_csv(ROOT/'data/pixels_with_environment.csv',low_memory=False);metrics=[];prediction_rows=[];baseline_errors=[];held_event={};held_site={}
 for scheme,col in [('leave_event_out','event'),('leave_location_out','location')]:
  for value in sorted(df[col].unique()):
   train=df[df[col]!=value];test=df[df[col]==value];bg=fit_background(train);Xtrain,_,_=corrected_features(train,bg);Xtest,_,_=corrected_features(test,bg)
   for modelname,trainX,testX in [('raw_SAR',train[CORE].to_numpy(),test[CORE].to_numpy()),('roughness_corrected_SAR',Xtrain,Xtest)]:
    model=fit_classifier(train,trainX);score=decision(model,testX)
    for sid,g in test.assign(score=score).groupby('scene'):
     for subset in ['all_negatives','water_only','distractors_only']:
      select=g if subset=='all_negatives' else g[(g.label_group=='plastic') | (g.label_group==('water' if subset=='water_only' else 'distractor'))]
      if len(select):metrics.append({'scheme':scheme,'held_out':str(value),'model':modelname,'scene':sid,'location':g.location.iloc[0],'subset':subset,**evaluate(select,select.score.to_numpy())})
    records=test[['scene','event','location','object_id','label_group','class_name','controlled','confidence','row','col']].copy();records['scheme']=scheme;records['model']=modelname;records['score']=score;prediction_rows.append(records)
    if modelname=='roughness_corrected_SAR':
     for sid in test.scene.unique():
      (held_event if scheme=='leave_event_out' else held_site)[sid]={'background':bg,'model':model}
   water=water_summary(test)
   if len(water):
    mu,_=predict_background(bg,water)
    for i,r in enumerate(water.itertuples()):
     for j,name in enumerate(CORE[:2]):baseline_errors.append({'scheme':scheme,'held_out':value,'object_id':r.object_id,'scene':r.scene,'feature':name,'observed_water_median_db':getattr(r,name),'predicted_environmental_water_db':mu[i,j],'constant_training_water_db':bg['fallback_water_median'][j]})
   print('validated',scheme,value,flush=True)
 pd.DataFrame(metrics).to_csv(ROOT/'data/validation_metrics.csv',index=False);pd.concat(prediction_rows,ignore_index=True).to_csv(ROOT/'data/held_out_predictions.csv',index=False);pd.DataFrame(baseline_errors).to_csv(ROOT/'data/water_baseline_validation.csv',index=False)
 bg=fit_background(df);X,mu,sd=corrected_features(df,bg);model=fit_classifier(df,X);rawmodel=fit_classifier(df,df[CORE].to_numpy());joblib.dump({'background':bg,'corrected_model':model,'raw_model':rawmodel},ROOT/'models/pooled_models.joblib');bg['water_objects'].to_csv(ROOT/'data/water_calibration_objects.csv',index=False)
 fitdf=df.copy();fitdf['pooled_raw_score']=decision(rawmodel,df[CORE].to_numpy());fitdf['pooled_corrected_score']=decision(model,X);fitdf['trust_weight']=training_weights(df)
 for i,name in enumerate(CORRECTED):fitdf[name]=X[:,i]
 fitdf['expected_water_VV_db']=mu[:,0];fitdf['expected_water_VH_db']=mu[:,1];fitdf['water_VV_spread_db']=sd[:,0];fitdf['water_VH_spread_db']=sd[:,1]
 fitdf.to_csv(ROOT/'data/scored_pixels.csv',index=False)
 # PCA is an exploratory transform of all corrected reference samples, without target weighting.
 pscale=StandardScaler().fit(X);pca=PCA(n_components=3).fit(pscale.transform(X));joblib.dump({'scaler':pscale,'pca':pca},ROOT/'models/corrected_PCA.joblib');pd.DataFrame(pca.components_.T,index=CORRECTED,columns=['PC1','PC2','PC3']).to_csv(ROOT/'data/corrected_PCA_loadings.csv')
 coef=[]
 for name,m,fnames in [('raw_SAR',rawmodel,CORE),('roughness_corrected_SAR',model,CORRECTED)]:coef.extend({'model':name,'feature':f,'coefficient':float(c)} for f,c in zip(fnames,m['classifier'].coef_[0]))
 pd.DataFrame(coef).to_csv(ROOT/'data/hyperplane_coefficients.csv',index=False)
 # Check the requested modest weighting against two nearby settings; the default remains 1.5.
 sensitivity=[]
 for multiplier in [1.,1.5,2.]:
  for event in sorted(df.event.unique()):
   train=df[df.event!=event];test=df[df.event==event];b=held_event[test.scene.iloc[0]]['background'];tr,_,_=corrected_features(train,b);te,_,_=corrected_features(test,b);m=fit_classifier(train,tr,multiplier);s=decision(m,te)
   sensitivity.append({'controlled_multiplier':multiplier,'held_event':event,**evaluate(test,s)})
 pd.DataFrame(sensitivity).to_csv(ROOT/'data/weight_sensitivity.csv',index=False)
 maps=json.loads((ROOT/'data/map_scenes.json').read_text());raster_index=[]
 for scene in maps:
  sid=scene['scene']
  with rasterio.open(scene['common_features']) as src:core=src.read();profile=src.profile;h,w=src.shape;rr,cc=np.indices((h,w));xx=src.transform.c+(cc.ravel()+.5)*src.transform.a;yy=src.transform.f+(rr.ravel()+.5)*src.transform.e
  from pyproj import Transformer
  lon,lat=Transformer.from_crs(profile['crs'],4326,always_xy=True).transform(xx,yy);env=EnvironmentalLookup(scene).sample(lon,lat);frame=pd.concat([pd.DataFrame(core.reshape(len(CORE),-1).T,columns=CORE),env],axis=1)
  good=np.isfinite(frame[CORE].to_numpy()).all(axis=1);safe=frame.astype({n:'float64' for n in CORE});safe.loc[~good,CORE]=np.nanmedian(df[CORE].to_numpy(),axis=0)
  corrected,mean,spread=corrected_features(safe,bg);eventbundle=held_event[sid];heldX,_,_=corrected_features(safe,eventbundle['background']);sitebundle=held_site[sid];siteX,_,_=corrected_features(safe,sitebundle['background']);pcs=pca.transform(pscale.transform(corrected))
  q=np.array(bg['water_q95_z']);z=(safe[['vv_db','vh_db']].to_numpy()-mean[:,:2])/spread
  names=['expected_water_VV_db','expected_water_VH_db','water_VV_spread_db','water_VH_spread_db','VV_excess_above_water_db','VH_excess_above_water_db','VV_normalized_excess','VH_normalized_excess','VV_above_water95_db','VH_above_water95_db','pooled_raw_hyperplane_EXPLORATORY','pooled_roughness_hyperplane_EXPLORATORY','held_event_roughness_hyperplane','held_location_roughness_hyperplane','corrected_PC1','corrected_PC2','corrected_PC3','positive_joint_excess','expected_water_polarization_db']
  bands=[mean[:,0],mean[:,1],spread[:,0],spread[:,1],safe.vv_db.to_numpy()-mean[:,0],safe.vh_db.to_numpy()-mean[:,1],z[:,0],z[:,1],safe.vv_db.to_numpy()-(mean[:,0]+q[0]*spread[:,0]),safe.vh_db.to_numpy()-(mean[:,1]+q[1]*spread[:,1]),decision(rawmodel,safe[CORE].to_numpy()),decision(model,corrected),decision(eventbundle['model'],heldX),decision(sitebundle['model'],siteX),pcs[:,0],pcs[:,1],pcs[:,2],np.sqrt(np.maximum(z[:,0],0)**2+np.maximum(z[:,1],0)**2),mean[:,1]-mean[:,0]]
  stack=np.stack(bands).reshape(len(names),h,w).astype('float32');stack[:,~good.reshape(h,w)]=np.nan;path=ROOT/'rasters'/f'{sid}_roughness_separation.tif';profile.update(count=len(names),nodata=np.nan)
  with rasterio.open(path,'w',**profile) as dst:
   dst.write(stack)
   for i,n in enumerate(names):dst.set_band_description(i+1,n)
   dst.update_tags(baseline='Empirical water-only environmental sea-clutter estimate; electronic NESZ not estimated',controlled_weight='1.5 relative multiplier; confidence and event/object balancing',warning='Exploratory scores, not calibrated plastic probabilities; no land mask')
  for i,n in enumerate(names):raster_index.append({'scene':sid,'location':scene['location'],'path':str(path),'band':i+1,'name':n,'p02':float(np.nanpercentile(stack[i],2)),'p98':float(np.nanpercentile(stack[i],98))})
  joblib.dump(eventbundle,ROOT/'models'/f'{sid}_held_event.joblib');joblib.dump(sitebundle,ROOT/'models'/f'{sid}_held_location.joblib');print('map',sid,flush=True)
 pd.DataFrame(raster_index).to_csv(ROOT/'data/raster_index.csv',index=False)
 metadata={'controlled_multiplier':1.5,'confidence_multipliers':{'high':1,'medium':.8,'low':.6,'not_assessed':.75},'classifier_effective_total_weight':100,'logistic_C':1,'background_regression':'Water polygon medians and robust spread; Ridge alpha=10; no plastic or distractors used','background_predictors':ENV_FEATURES,'water_q95_z':bg['water_q95_z'],'common_features':CORE,'corrected_features':CORRECTED,'PCA_explained_variance_ratio':pca.explained_variance_ratio_.tolist(),'validation':'Entire events and entire locations held out; all background models, scaling and classifier fits use training data only','instrument_NESZ':'Not available for these map pixels; no synthetic electronic noise floor invented','limitations':'Nine acquisitions; seven events; six locations. Coarse environmental context and missing local incidence angle limit physical interpretation. Candidate proxy labels retain their original status. Legacy Manila VV/VH processing differs from native SLC.'};(ROOT/'models/model_metadata.json').write_text(json.dumps(metadata,indent=2))
 print(pd.DataFrame(metrics).query("subset=='all_negatives'").groupby(['scheme','model']).object_balanced_auc.mean().to_string(),flush=True)
