import os
for key in ['PROJ_LIB','PROJ_DATA','GDAL_DATA']: os.environ.pop(key,None)
from pathlib import Path
import json, numpy as np, pandas as pd, rasterio, fiona
from shapely.geometry import shape, mapping, box
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from rasterio.windows import from_bounds
ROOT=Path(r'D:\Masters\greece_deployment_features_20261022')
scenes=sorted(json.loads((ROOT/'data/scene_inventory.json').read_text()),key=lambda s:s['scene'])
df=pd.read_csv(ROOT/'data/scored_pixels.csv'); metrics=pd.read_csv(ROOT/'data/validation_metrics.csv'); labels=json.loads((ROOT/'data/label_polygons.geojson').read_text())['features']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titlesize':12,'figure.facecolor':'white','axes.spines.top':False,'axes.spines.right':False})
# Fixed local map extent; target outlines are reference locations, not injected into the raster scores.
bbox=(26.5229,39.0379,26.5261,39.0403)
fig,axes=plt.subplots(4,4,figsize=(15,14),constrained_layout=True)
for row,scene in enumerate(scenes):
 sid=scene['scene']; local=df[df.scene==sid]; water=local[local.label=='water']
 with rasterio.open(scene['raw_crop']) as src:
  win=from_bounds(*bbox,src.transform).round_offsets().round_lengths(); raw=src.read(4,window=win); bounds=rasterio.windows.bounds(win,src.transform)
 with rasterio.open(ROOT/'rasters'/f'{sid}_derived_features.tif') as src:
  derived=src.read(window=win)
 extent=[bounds[0],bounds[2],bounds[1],bounds[3]]
 pca=derived[:3].transpose(1,2,0); lo=np.nanpercentile(pca,2,axis=(0,1)); hi=np.nanpercentile(pca,98,axis=(0,1)); rgb=np.clip((pca-lo)/np.maximum(hi-lo,.01),0,1)
 images=[raw,derived[3],derived[4],rgb]
 titles=['Original filtered VV (dB)','Scene-fitted hyperplane\nExploratory, trained on this image','Held-out hyperplane\nTrained on other acquisitions','PCA components 1 / 2 / 3\nUnsupervised reference-sample transform']
 for col,(ax,im,title) in enumerate(zip(axes[row],images,titles)):
  if col==0: art=ax.imshow(im,extent=extent,origin='upper',cmap='gray',vmin=np.percentile(water.lee_db,2),vmax=np.percentile(water.lee_db,98),interpolation='nearest')
  elif col in [1,2]: art=ax.imshow(im,extent=extent,origin='upper',cmap='RdBu_r',vmin=-4,vmax=4,interpolation='nearest')
  else: art=ax.imshow(im,extent=extent,origin='upper',interpolation='nearest')
  for feature in labels:
   if feature['properties']['year']==scene['year'] and feature['properties']['label']=='deployment':
    g=shape(feature['geometry']); x,y=g.exterior.xy; ax.plot(x,y,color='#efc700',lw=1.3)
  ax.set_aspect(1/np.cos(np.deg2rad(39.0393))); ax.set_xticks([]); ax.set_yticks([])
  if row==0: ax.set_title(title,pad=10)
  if col==0: ax.set_ylabel(f'{sid[:4]}-{sid[4:6]}-{sid[6:8]}\n{sid[9:11]}:{sid[11:13]} UTC',fontsize=12)
  if col in [1,2]:
   y=(local.label=='deployment').astype(int); score=local.scene_fit_logistic if col==1 else local.held_out_logistic
   from sklearn.metrics import roc_auc_score
   ax.text(.03,.03,f'Labelled-pixel AUC {roc_auc_score(y,score):.2f}',transform=ax.transAxes,color='black',bbox=dict(facecolor='white',alpha=.85,edgecolor='none'),fontsize=9)
fig.suptitle('Known plastic deployments: what the SAR feature combinations reveal',fontsize=18)
fig.supxlabel('Yellow outlines = supplied deployment footprints. Red = higher model score; blue = lower. Scores are not plastic probabilities.\nLocal view is about 275 m wide. PCA RGB is stretched per panel; maps include unlabelled surroundings.',fontsize=11)
fig.savefig(ROOT/'plots/deployment_comparison.png',dpi=180); plt.close(fig)
# Held-out comparisons, no pixel-independence confidence intervals.
models=list(metrics.model.unique()); scene_ids=[s['scene'] for s in scenes]
fig,axes=plt.subplots(1,2,figsize=(13,5.5),constrained_layout=True)
for ax,scheme,title in zip(axes,['leave_scene_out','leave_year_out'],['Leave one SAR acquisition out','Train on the other year']):
 table=metrics[(metrics.scheme==scheme)&(metrics.water_subset=='all')].pivot(index='model',columns='scene',values='roc_auc').reindex(index=models,columns=scene_ids)
 im=ax.imshow(table.values,vmin=0,vmax=1,cmap='RdYlGn',aspect='auto')
 for i in range(len(models)):
  for j in range(4): ax.text(j,i,f'{table.iloc[i,j]:.2f}',ha='center',va='center',fontsize=12)
 ax.set_xticks(range(4),[s[:4]+'-'+s[4:6]+'-'+s[6:8] for s in scene_ids],rotation=35,ha='right'); ax.set_yticks(range(len(models)),[x.replace('SAR_','').replace('_',' ') for x in models]); ax.set_title(title)
fig.colorbar(im,ax=axes,shrink=.7,label='ROC AUC (0.5 = chance ranking)')
fig.suptitle('Does separation survive a new scene?',fontsize=17)
fig.supxlabel('Spatially correlated pixels at one locality; four acquisitions only. These diagnostics are not independent deployment trials.',fontsize=10)
fig.savefig(ROOT/'plots/held_out_validation.png',dpi=180); plt.close(fig)
# PCA plots preserve scenes to reveal confounding by acquisition.
fig,axes=plt.subplots(2,2,figsize=(11,9),constrained_layout=True)
for ax,scene in zip(axes.flat,scenes):
 group=df[df.scene==scene['scene']]; water=group[group.label=='water']; target=group[group.label=='deployment']
 ax.scatter(water.PC1,water.PC2,s=7,alpha=.25,color='#176c9c',label='Water'); ax.scatter(target.PC1,target.PC2,s=35,color='#dc6435',edgecolor='black',linewidth=.4,label='Deployment')
 ax.set_xlabel('PC1'); ax.set_ylabel('PC2'); ax.set_title(scene['scene']); ax.legend(frameon=False)
fig.suptitle('PCA feature space: deployments and supplied water samples',fontsize=16)
fig.savefig(ROOT/'plots/PCA_scatter.png',dpi=180); plt.close(fig)
# Polygon locations against the original data explain the background sampling geography.
fig,axes=plt.subplots(1,2,figsize=(12,6),constrained_layout=True)
for ax,scene in zip(axes,[scenes[1],scenes[3]]):
 with rasterio.open(scene['raw_crop']) as src: a=src.read(4); b=src.bounds
 ax.imshow(a,extent=[b.left,b.right,b.bottom,b.top],cmap='gray',vmin=-30,vmax=-10,interpolation='nearest')
 for feature in labels:
  props=feature['properties']
  if props['year']!=scene['year']: continue
  g=shape(feature['geometry']); x,y=g.exterior.xy; color='#ffc400' if props['label']=='deployment' else '#00d2e6'; ax.plot(x,y,color=color,lw=1)
  if props['label']=='water': ax.annotate(props['object_id'],(g.centroid.x,g.centroid.y),color=color,fontsize=10,xytext=(4,4),textcoords='offset points')
 ax.set_aspect(1/np.cos(np.deg2rad(39))); ax.set_title(f"{scene['year']}: deployment and water sampling"); ax.ticklabel_format(useOffset=False); ax.tick_params(axis='x',rotation=30)
fig.savefig(ROOT/'plots/sampling_geography.png',dpi=180); plt.close(fig)
# Geospatial sample table for QGIS. Cells use the exact SAR grid.
properties={}
keep=[c for c in df.columns if c not in ['acquisition_utc']]
for c in keep: properties[c]='str' if df[c].dtype.kind in 'ObU' else 'float'
schema={'geometry':'Polygon','properties':properties}
gpkg=ROOT/'data/sampled_SAR_pixels.gpkg'
with fiona.open(gpkg,'w',driver='GPKG',layer='sar_pixels',crs='EPSG:4326',schema=schema) as dst:
 for scene in scenes:
  with rasterio.open(scene['raw_crop']) as src: trans=src.transform
  for _,r in df[df.scene==scene['scene']].iterrows():
   x1,y1=trans*(r.crop_col,r.crop_row); x2,y2=trans*(r.crop_col+1,r.crop_row+1)
   attrs={c:(None if pd.isna(r[c]) else str(r[c]) if properties[c]=='str' else float(r[c])) for c in keep}
   dst.write({'geometry':mapping(box(x1,y2,x2,y1)),'properties':attrs})
print('Saved plots and',len(df),'sample polygons',flush=True)
