import os
for k in ['PROJ_LIB','PROJ_DATA','GDAL_DATA']:os.environ.pop(k,None)
from pathlib import Path
import json,numpy as np,pandas as pd,rasterio,fiona
from shapely.geometry import shape,mapping,Point
from rasterio.windows import from_bounds
from sklearn.metrics import roc_auc_score
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(r'D:\Masters\sar_roughness_features_20261023');scenes=json.loads((ROOT/'data/map_scenes.json').read_text());labels=json.loads((ROOT/'data/source_labels.geojson').read_text())['features'];df=pd.read_csv(ROOT/'data/scored_pixels.csv',low_memory=False);rich=pd.read_csv(ROOT/'data/rich_scored_pixels.csv',low_memory=False)
key=['scene','object_id','row','col'];richcolumns=['rich_pooled_corrected_score','rich_pooled_raw_score','rich_scene_fitted_score'];df=df.merge(rich[key+richcolumns],on=key,how='left',validate='one_to_one')
for file,model,name in [('held_out_predictions.csv','roughness_corrected_SAR','held_event_common_score'),('rich_held_out_predictions.csv','rich_roughness_corrected','held_event_rich_score')]:
 held=pd.read_csv(ROOT/'data'/file);held=held[(held.scheme=='leave_event_out')&(held.model==model)];df=df.merge(held[key+['score']].rename(columns={'score':name}),on=key,how='left',validate='one_to_one')
# One short-path GeoPackage for all project layers.
label_schema={'geometry':'Unknown','properties':{'scene':'str','object_id':'str','class_name':'str','label_group':'str','controlled':'int','confidence':'str','training_status':'str','source':'str','sampled_pixels':'int','weight_mass':'float','pooled_common':'float','held_event_common':'float','pooled_rich':'float','held_event_rich':'float'}}
records=[]
for f in labels:
 prop=f['properties'];g=df[(df.scene==prop['scene'])&(df.object_id==prop['object_id'])]
 values={k:prop.get(k) for k in ['scene','object_id','class_name','label_group','confidence','training_status','source']};values.update(controlled=int(prop['controlled']),sampled_pixels=len(g),weight_mass=float(g.trust_weight.sum()) if len(g) else 0)
 for col,target in [('pooled_corrected_score','pooled_common'),('held_event_common_score','held_event_common'),('rich_pooled_corrected_score','pooled_rich'),('held_event_rich_score','held_event_rich')]:values[target]=float(g[col].mean()) if g[col].notna().any() else None
 records.append({'geometry':f['geometry'],'properties':values})
gpkg=ROOT/'data/roughness_samples.gpkg'
with fiona.open(gpkg,'w',driver='GPKG',layer='label_polygons',crs='EPSG:4326',schema=label_schema) as dst:dst.writerecords(records)
properties={c:('str' if df[c].dtype.kind in 'OU' else 'int' if df[c].dtype.kind in 'biu' else 'float') for c in df.columns};schema={'geometry':'Point','properties':properties}
def point_records():
 for _,r in df.iterrows():
  attrs={c:(None if pd.isna(r[c]) else str(r[c]) if properties[c]=='str' else int(r[c]) if properties[c]=='int' else float(r[c])) for c in df.columns}
  yield {'geometry':mapping(Point(r.longitude,r.latitude)),'properties':attrs}
with fiona.open(gpkg,'w',driver='GPKG',layer='sampled_pixels',crs='EPSG:4326',schema=schema) as dst:dst.writerecords(point_records())
df.to_csv(ROOT/'data/combined_scored_pixels.csv',index=False)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'figure.facecolor':'white','axes.spines.top':False,'axes.spines.right':False})
greek=[s for s in scenes if s['location']=='Greece'];fig,axes=plt.subplots(4,4,figsize=(16,14),constrained_layout=True);bbox=(26.5229,39.0379,26.5261,39.0403)
for row,scene in enumerate(greek):
 sid=scene['scene'];local=df[df.scene==sid];water=local[local.label_group=='water']
 with rasterio.open(scene['raw_crop']) as src:
  win=from_bounds(*bbox,src.transform).round_offsets().round_lengths();original=src.read(scene['raw_band_names'].index('vv_refined_lee_db')+1,window=win);b=rasterio.windows.bounds(win,src.transform)
 with rasterio.open(ROOT/'rasters'/f'{sid}_roughness_separation.tif') as src:excess=src.read(7,window=win)
 with rasterio.open(ROOT/'rasters'/f'{sid}_rich_SLC_separation.tif') as src:pooled=src.read(2,window=win);fitted=src.read(5,window=win)
 titles=['Original filtered VV (dB)','VV above expected water\nNormalized by predicted water variability','Weighted pooled rich index\nAll usable SLC observations','Scene-fitted rich index\nExploratory local fit']
 for col,(ax,a,title) in enumerate(zip(axes[row],[original,excess,pooled,fitted],titles)):
  if col==0:ax.imshow(a,extent=[b[0],b[2],b[1],b[3]],cmap='gray',vmin=np.percentile(water.vv_refined_lee_db,2),vmax=np.percentile(water.vv_refined_lee_db,98),interpolation='nearest')
  else:ax.imshow(a,extent=[b[0],b[2],b[1],b[3]],cmap='RdBu_r',vmin=-3,vmax=3,interpolation='nearest')
  for f in labels:
   if f['properties']['scene']==sid and f['properties']['controlled']:
    g=shape(f['geometry']);x,y=g.exterior.xy;ax.plot(x,y,color='#e9bc00',lw=1.4)
  ax.set_aspect(1/np.cos(np.deg2rad(39)));ax.set_xticks([]);ax.set_yticks([])
  if row==0:ax.set_title(title,pad=12,fontsize=12)
  if col==0:ax.set_ylabel(f'{sid[:4]}-{sid[4:6]}-{sid[6:8]}\n{sid[9:11]}:{sid[11:13]} UTC',fontsize=12)
  if col in [2,3]:
   score=local.rich_pooled_corrected_score if col==2 else local.rich_scene_fitted_score;auc=roc_auc_score(local.label_group=='plastic',score);ax.text(.03,.03,f'In-sample pixel AUC {auc:.2f}',transform=ax.transAxes,bbox=dict(facecolor='white',alpha=.85,edgecolor='none'),fontsize=9)
fig.suptitle('Sea-state correction and weighted plastic-reference indices',fontsize=18)
fig.supxlabel('Yellow = controlled footprints. Red = higher excess or score; blue = lower. Fitted scores are exploratory.\nThe environmental baseline is water-trained; it is not an electronic NESZ map. Local views are about 275 m wide.',fontsize=11)
fig.savefig(ROOT/'plots/Greece_roughness_comparison.png',dpi=170);plt.close(fig)
# Show water baseline prediction uncertainty directly.
v=pd.read_csv(ROOT/'data/water_baseline_validation.csv');v=v[v.scheme=='leave_event_out'];fig,axes=plt.subplots(1,2,figsize=(11,5),constrained_layout=True)
for ax,feature in zip(axes,['vv_db','vh_db']):
 g=v[v.feature==feature];ax.scatter(g.observed_water_median_db,g.predicted_environmental_water_db,color='#147b94',s=42,label='Environmental baseline');ax.scatter(g.observed_water_median_db,g.constant_training_water_db,color='#c88a45',s=30,marker='x',label='Constant training-water baseline');lo=min(g.observed_water_median_db.min(),g.predicted_environmental_water_db.min())-1;hi=max(g.observed_water_median_db.max(),g.predicted_environmental_water_db.max())+1;ax.plot([lo,hi],[lo,hi],color='#899ba6',ls='--');ax.set_xlabel('Observed water-polygon median (dB)');ax.set_ylabel('Held-event prediction (dB)');rmse=np.sqrt(np.mean((g.observed_water_median_db-g.predicted_environmental_water_db)**2));ax.set_title(feature.upper()+f' | environmental RMSE {rmse:.2f} dB');ax.legend(fontsize=8)
fig.suptitle('Does environment predict the water backscatter level?',fontsize=16);fig.savefig(ROOT/'plots/water_baseline_validation.png',dpi=170);plt.close(fig)
# Matched before/after comparisons; group metrics cannot be compared to the earlier Greece-only model population.
common=pd.read_csv(ROOT/'data/validation_metrics.csv');richmetrics=pd.read_csv(ROOT/'data/rich_validation_metrics.csv');m=pd.concat([common,richmetrics]);modelnames=['raw_SAR','roughness_corrected_SAR','rich_raw_SAR','rich_roughness_corrected'];pretty=['Common SAR: raw','Common SAR: roughness corrected','Rich SLC: raw','Rich SLC: roughness corrected'];fig,axes=plt.subplots(1,2,figsize=(14,5.2),constrained_layout=True)
positive_scenes=sorted(df[df.label_group=='plastic'].scene.unique());columns=[s for s in positive_scenes if s!='20200915T230129']
for ax,scheme,title in zip(axes,['leave_event_out','leave_location_out'],['Whole event held out','Whole location held out']):
 table=m[(m.scheme==scheme)&(m.subset=='all_negatives')].pivot(index='model',columns='scene',values='object_balanced_auc').reindex(index=modelnames,columns=columns)
 image=ax.imshow(np.ma.masked_invalid(table.to_numpy()),vmin=0,vmax=1,cmap='RdYlGn',aspect='auto')
 for i in range(len(modelnames)):
  for j in range(len(columns)):
   val=table.iloc[i,j];ax.text(j,i,f'{val:.2f}' if np.isfinite(val) else 'N/A',ha='center',va='center',fontsize=10)
 ax.set_xticks(range(len(columns)),[s[:4]+'-'+s[4:6]+'-'+s[6:8] for s in columns],rotation=40,ha='right');ax.set_yticks(range(len(modelnames)),pretty);ax.set_title(title)
fig.colorbar(image,ax=axes,shrink=.7,label='Object-balanced ROC AUC');fig.suptitle('Transfer remains inconsistent after roughness correction',fontsize=17);fig.supxlabel('Haiti has plastic labels only, so no within-scene AUC is reported. Rich SLC features are unavailable for Manila.',fontsize=10);fig.savefig(ROOT/'plots/held_out_comparison.png',dpi=170);plt.close(fig)
# Summarize the increased controlled influence without treating pixel count as independent evidence.
weights=df.groupby(['label_group','controlled']).trust_weight.sum().reset_index();weights.to_csv(ROOT/'data/weight_mass_summary.csv',index=False)
print('Created GeoPackage, figures and joined pixel scores',len(df),flush=True)
