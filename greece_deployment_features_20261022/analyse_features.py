import os
for key in ['PROJ_LIB','PROJ_DATA','GDAL_DATA']: os.environ.pop(key,None)
from pathlib import Path
import json, numpy as np, pandas as pd, rasterio
from scipy.ndimage import median_filter
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.decomposition import PCA
from sklearn.metrics import roc_auc_score, average_precision_score, balanced_accuracy_score
import joblib
ROOT=Path(r'D:\Masters\greece_deployment_features_20261022')
BASE=['vv_db','vh_db','lee_db','glcm_mean','glcm_std','glcm_entropy','H','A','alpha']
EXTRA=['vh_minus_vv_db','normalized_pol_difference','vv_minus_lee_db','H_times_alpha','one_minus_H_times_A','vv_ring_contrast_db','vh_ring_contrast_db','lee_ring_contrast_db']
ENGINEERED=BASE+EXTRA
SCENES=sorted(json.loads((ROOT/'data/scene_inventory.json').read_text()),key=lambda s:s['scene'])

def feature_cube(a):
    vv,vh,lee,lee_db,mean,std,ent,H,A,alpha=a
    vvdb=10*np.log10(np.maximum(vv,1e-12)); vhdb=10*np.log10(np.maximum(vh,1e-12))
    footprint=np.ones((11,11),bool); footprint[3:8,3:8]=False
    local=[arr-median_filter(arr,footprint=footprint,mode='reflect') for arr in [vvdb,vhdb,lee_db]]
    return np.stack([vvdb,vhdb,lee_db,mean,std,ent,H,A,alpha,vhdb-vvdb,(vv-vh)/np.maximum(vv+vh,1e-12),vvdb-lee_db,H*alpha/90,(1-H)*A,*local]).astype('float32')

def weights(df):
    counts=df.groupby(['scene','label','object_id']).size()
    object_counts=df.groupby(['scene','label']).object_id.nunique()
    w=np.array([1/(counts.loc[(r.scene,r.label,r.object_id)]*object_counts.loc[(r.scene,r.label)]) for r in df.itertuples()])
    return w/w.mean()

def design(df,names,scaler=None,env_scaler=None,interactions=False):
    a=df[names].to_numpy(float)
    if scaler is None: scaler=StandardScaler().fit(a,sample_weight=weights(df))
    a=np.clip(scaler.transform(a),-12,12)
    output_names=list(names)
    if interactions:
        enames=['wind_speed_m_s','wave_height_m','current_speed_m_s','sst_C','chlorophyll_mg_m3']
        # Context is constant across every pixel of a scene: no spatial environment or coordinates as predictors.
        env=df[enames].to_numpy(float)
        if env_scaler is None: env_scaler=StandardScaler().fit(env,sample_weight=weights(df))
        z=np.clip(env_scaler.transform(env),-5,5)
        terms=[('vv_ring_contrast_db',0),('vh_minus_vv_db',0),('lee_ring_contrast_db',1),('H',1),('vh_minus_vv_db',2),('H',3),('vh_ring_contrast_db',4)]
        a=np.column_stack([a]+[a[:,names.index(f)]*z[:,j] for f,j in terms])
        output_names += [f'{f} X {enames[j]}' for f,j in terms]
    return a,scaler,env_scaler,output_names

def fit(df,names,kind='logistic',interactions=False):
    X,scaler,escaler,fnames=design(df,names,interactions=interactions); y=(df.label=='deployment').astype(int)
    if kind=='lda':
        model=LinearDiscriminantAnalysis(solver='lsqr',shrinkage='auto',priors=[.5,.5]).fit(X,y)
    else:
        model=LogisticRegression(C=.1,max_iter=3000,solver='lbfgs').fit(X,y,sample_weight=weights(df))
    return dict(model=model,scaler=scaler,env_scaler=escaler,names=names,feature_names=fnames,interactions=interactions,kind=kind)

def predict(bundle,df):
    X,_,_,_=design(df,bundle['names'],bundle['scaler'],bundle['env_scaler'],bundle['interactions'])
    return bundle['model'].decision_function(X)

def metric(y,s):
    return dict(roc_auc=float(roc_auc_score(y,s)),average_precision=float(average_precision_score(y,s)),balanced_accuracy_at_zero=float(balanced_accuracy_score(y,s>=0)),target_recall_at_zero=float(np.mean(s[y==1]>=0)),water_false_positive_at_zero=float(np.mean(s[y==0]>=0)),n_target=int(sum(y==1)),n_water=int(sum(y==0)))

if __name__=='__main__':
    df=pd.read_csv(ROOT/'data/core_pixels.csv')
    cubes={}; profiles={}
    for scene in SCENES:
        sid=scene['scene']
        with rasterio.open(scene['raw_crop']) as src: cube=feature_cube(src.read()); profile=src.profile
        cubes[sid]=cube; profiles[sid]=profile
        idx=df.scene==sid; r=df.loc[idx,'crop_row'].to_numpy(int); c=df.loc[idx,'crop_col'].to_numpy(int)
        df.loc[idx,ENGINEERED]=cube[:,r,c].T
        print('engineered',sid,flush=True)
    envpath=ROOT/'environment/scene_environment.csv'
    hasenv=False
    if envpath.exists():
        env=pd.read_csv(envpath); df=df.merge(env,on='scene',how='left'); hasenv=df[['wind_speed_m_s','wave_height_m','current_speed_m_s','sst_C','chlorophyll_mg_m3']].notna().all().all()
    df.to_csv(ROOT/'data/model_input_pixels.csv',index=False)
    configs={'SAR_baseline':(BASE,'logistic',False),'SAR_engineered':(ENGINEERED,'logistic',False),'SAR_shrinkage_LDA':(ENGINEERED,'lda',False)}
    if hasenv: configs['SAR_environment_interactions']=(ENGINEERED,'logistic',True)
    metrics=[]; predictions=[]; bundles={}; coefficients=[]; pooled={}
    for name,(names,kind,interactions) in configs.items():
        for scheme,values,column in [('leave_scene_out',sorted(df.scene.unique()),'scene'),('leave_year_out',sorted(df.year.unique()),'year')]:
            for value in values:
                train=df[df[column]!=value]; test=df[df[column]==value].copy()
                bundle=fit(train,names,kind,interactions); scores=predict(bundle,test); test['score']=scores
                if scheme=='leave_scene_out': bundles[(name,str(value))]=bundle
                for sid,group in test.groupby('scene'):
                    y=(group.label=='deployment').to_numpy(int); s=group.score.to_numpy()
                    metrics.append(dict(model=name,scheme=scheme,held_out=str(value),scene=sid,water_subset='all',**metric(y,s)))
                    for water in ['water_1','water_2','water_3','water_4']:
                        small=group[(group.label=='deployment') | (group.object_id==water)]
                        metrics.append(dict(model=name,scheme=scheme,held_out=str(value),scene=sid,water_subset=water,**metric((small.label=='deployment').to_numpy(int),small.score.to_numpy())))
                out=test[['scene','year','label','object_id','row','col','coverage_fraction','score']].copy(); out['model']=name; out['scheme']=scheme; predictions.append(out)
        full=fit(df,names,kind,interactions); pooled[name]=full; joblib.dump(full,ROOT/'models'/f'{name}_pooled.joblib')
        coefficients.extend([dict(model=name,feature=n,standardized_coefficient=float(c)) for n,c in zip(full['feature_names'],full['model'].coef_[0])])
        print('validated',name,flush=True)
    pd.DataFrame(metrics).to_csv(ROOT/'data/validation_metrics.csv',index=False)
    pd.concat(predictions,ignore_index=True).to_csv(ROOT/'data/held_out_predictions.csv',index=False)
    pd.DataFrame(coefficients).to_csv(ROOT/'data/hyperplane_coefficients.csv',index=False)
    if hasenv:
        Z,_,_,znames=design(df,ENGINEERED,pooled['SAR_environment_interactions']['scaler'],pooled['SAR_environment_interactions']['env_scaler'],True)
        interactions_df=df[['scene','label','object_id','row','col']].copy()
        for i,n in enumerate(znames[len(ENGINEERED):]): interactions_df[n]=Z[:,len(ENGINEERED)+i]
        interactions_df.to_csv(ROOT/'data/environment_interaction_indices.csv',index=False)
    # Feature rankings are exploratory, never used to select predictors in held-out models.
    ranks=[]
    for sid,group in df.groupby('scene'):
        for feature in ENGINEERED:
            y=(group.label=='deployment').to_numpy(int); v=group[feature].to_numpy(); auc=roc_auc_score(y,v)
            ranks.append(dict(scene=sid,feature=feature,auc_target_high=auc,descriptive_separation=max(auc,1-auc),target_median=np.median(v[y==1]),water_median=np.median(v[y==0]),direction='high' if auc>=.5 else 'low'))
    pd.DataFrame(ranks).to_csv(ROOT/'data/exploratory_feature_rankings.csv',index=False)
    pscaler=StandardScaler().fit(df[BASE]); pca=PCA(n_components=3,svd_solver='full').fit(pscaler.transform(df[BASE]))
    joblib.dump({'scaler':pscaler,'pca':pca,'features':BASE},ROOT/'models/PCA.joblib')
    pd.DataFrame(pca.components_.T,index=BASE,columns=['PC1','PC2','PC3']).to_csv(ROOT/'data/PCA_loadings.csv')
    pcs=pscaler.transform(df[BASE]); pcs=pca.transform(pcs)
    for i in range(3): df[f'PC{i+1}']=pcs[:,i]
    score_records=[]; raster_index=[]
    selected_model='SAR_engineered'
    for scene in SCENES:
        sid=scene['scene']; cube=cubes[sid]; h,w=cube.shape[1:]; local=df[df.scene==sid].copy()
        fullframe=pd.DataFrame(cube.reshape(len(ENGINEERED),-1).T,columns=ENGINEERED)
        if hasenv:
            for col in env.columns:
                if col!='scene': fullframe[col]=env.loc[env.scene==sid,col].iloc[0]
        pc=pca.transform(pscaler.transform(fullframe[BASE])).T.reshape(3,h,w)
        scene_fit=fit(local,ENGINEERED); joblib.dump(scene_fit,ROOT/'models'/f'{sid}_exploratory_logistic.joblib')
        score=predict(scene_fit,fullframe).reshape(h,w)
        held=predict(bundles[(selected_model,sid)],fullframe).reshape(h,w)
        lda_scene=fit(local,ENGINEERED,'lda'); lda_score=predict(lda_scene,fullframe).reshape(h,w)
        target=local.label=='deployment'; water=local[~target]
        lee_z=(cube[2]-water.lee_db.median())/max(float(np.median(abs(water.lee_db-water.lee_db.median())))*1.4826,.1)
        bands=[*pc,score,held,lda_score,lee_z,cube[9],cube[14],cube[15],cube[16]]
        names=['PC1_reference_PCA','PC2_reference_PCA','PC3_reference_PCA','scene_fit_logistic_EXPLORATORY','held_out_scene_logistic','scene_fit_shrinkage_LDA_EXPLORATORY','lee_water_robust_z_EXPLORATORY','VH_minus_VV_dB','VV_ring_contrast_dB','VH_ring_contrast_dB','Lee_ring_contrast_dB']
        if hasenv:
            envscore=predict(bundles[('SAR_environment_interactions',sid)],fullframe).reshape(h,w)
            interaction_matrix,_,_,interaction_names=design(fullframe,ENGINEERED,pooled['SAR_environment_interactions']['scaler'],pooled['SAR_environment_interactions']['env_scaler'],True)
            for j,n in enumerate(interaction_names[len(ENGINEERED):]):
                bands.append(interaction_matrix[:,len(ENGINEERED)+j].reshape(h,w)); names.append('interaction_'+n.replace(' X ','_x_'))
            # Environment is constant within a scene; scene-only environmental model has no extra information.
            bands.append(envscore); names.append('held_out_scene_environment_interaction_logistic')
        stack=np.stack(bands).astype('float32'); profile=profiles[sid].copy(); profile.update(count=len(bands),compress='deflate',predictor=3,nodata=np.nan)
        raster=ROOT/'rasters'/f'{sid}_derived_features.tif'
        with rasterio.open(raster,'w',**profile) as dst:
            dst.write(stack)
            for i,name in enumerate(names): dst.set_band_description(i+1,name)
            dst.update_tags(description='Exploratory visual scores, not calibrated probabilities or confirmed plastic detection. Land is not masked.',scene=sid)
        # Full numerical coefficients and out-of-sample models retained for reproducibility.
        joblib.dump(bundles[(selected_model,sid)],ROOT/'models'/f'{sid}_held_out_logistic.joblib')
        for i,name in enumerate(names):
            raster_index.append(dict(scene=sid,path=str(raster),band=i+1,name=name,p02=float(np.nanpercentile(stack[i],2)),p98=float(np.nanpercentile(stack[i],98))))
        local['scene_fit_logistic']=predict(scene_fit,local); local['held_out_logistic']=predict(bundles[(selected_model,sid)],local)
        score_records.append(local)
        print('rasters',sid,flush=True)
    pd.concat(score_records).to_csv(ROOT/'data/scored_pixels.csv',index=False)
    pd.DataFrame(raster_index).to_csv(ROOT/'data/derived_raster_index.csv',index=False)
    (ROOT/'models/model_metadata.json').write_text(json.dumps({'base_features':BASE,'engineered_features':EXTRA,'environment_available':bool(hasenv),'PCA_explained_variance_ratio':pca.explained_variance_ratio_.tolist(),'logistic_C':.1,'weighting':'Equal class weight within each scene; equal polygon weight within each class; weights normalized to mean one','validation':'Train-only scaling; fixed features and regularization. Leave one acquisition and leave one year out. Pixels are spatially correlated; these are descriptive diagnostics, not independent trial confidence estimates.','spatial_scope':'Same deployment locality in all scenes; no spatial generalization test. Environmental values in models are constant per scene to avoid coordinate classification. Water footprints from 2021 reused in 2024.','ring':'11x11 pixel median ring excluding central 5x5; no label mask used; native grid retained','GLCM':'Stored SNAP quantized texture values retained; GLCM mean/std are not converted to dB. Stored entropy can be negative and is treated as a numeric texture descriptor.'},indent=2))
    print(pd.DataFrame(metrics).query("water_subset=='all'").groupby(['model','scheme']).roc_auc.mean().to_string(),flush=True)
