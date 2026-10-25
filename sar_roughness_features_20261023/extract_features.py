import os
for key in ['PROJ_LIB','PROJ_DATA','GDAL_DATA']:os.environ.pop(key,None)
from pathlib import Path
import json,numpy as np,pandas as pd,rasterio
from scipy.ndimage import median_filter,uniform_filter
from rasterio.features import rasterize
from rasterio.windows import Window,from_bounds
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from shapely.geometry import shape,mapping,box
from shapely.ops import transform as geom_transform
from pyproj import Transformer
ROOT=Path(r'D:\Masters\sar_roughness_features_20261023')
RAW=['vv','vh','vv_refined_lee','vv_refined_lee_db','vv_glcm_mean','vv_glcm_std','vv_glcm_entropy','decomp_entropy','decomp_anisotropy','decomp_alpha']
CORE=['vv_db','vh_db','vv_median3_db','vh_median3_db','pol_ratio_db','vv_ring_db','vh_ring_db','vv_std5_db','vh_std5_db']

def features(vv,vh):
 valid=np.isfinite(vv)&np.isfinite(vh)&(vv>0)&(vh>0)
 v=10*np.log10(np.maximum(vv,1e-12));h=10*np.log10(np.maximum(vh,1e-12))
 for a in [v,h]:a[~valid]=np.nanmedian(a[valid]) if np.any(valid) else 0
 ring=np.ones((11,11),bool);ring[3:8,3:8]=False
 medv=median_filter(v,size=3,mode='reflect');medh=median_filter(h,size=3,mode='reflect')
 rv=v-median_filter(v,footprint=ring,mode='reflect');rh=h-median_filter(h,footprint=ring,mode='reflect')
 sv=np.sqrt(np.maximum(uniform_filter(v*v,size=5)-uniform_filter(v,size=5)**2,0));sh=np.sqrt(np.maximum(uniform_filter(h*h,size=5)-uniform_filter(h,size=5)**2,0))
 cube=np.stack([v,h,medv,medh,h-v,rv,rh,sv,sh]).astype('float32')
 context=uniform_filter(valid.astype(float),size=11,mode='constant')>.99999
 cube[:,~valid]=np.nan
 return cube,valid&context

def read_sources(scene,window,reference):
 arrays={}
 for name,path in scene['sources'].items():
  with rasterio.open(path) as src:
   if src.crs==reference.crs and src.transform==reference.transform and src.shape==reference.shape:
    a=src.read(1,window=window,masked=True).filled(np.nan).astype('float32')
   else:
    with WarpedVRT(src,crs=reference.crs,transform=reference.transform,width=reference.width,height=reference.height,resampling=Resampling.bilinear,nodata=np.nan) as aligned:a=aligned.read(1,window=window,masked=True).filled(np.nan).astype('float32')
   a[a<=-9990]=np.nan;arrays[name]=a
 return arrays

def integer_window(bounds,src,pad=8):
 win=from_bounds(*bounds,src.transform);c=max(0,int(np.floor(win.col_off))-pad);r=max(0,int(np.floor(win.row_off))-pad);right=min(src.width,int(np.ceil(win.col_off+win.width))+pad);bottom=min(src.height,int(np.ceil(win.row_off+win.height))+pad)
 return Window(c,r,max(0,right-c),max(0,bottom-r))

if __name__=='__main__':
 scenes=json.loads((ROOT/'data/source_scenes.json').read_text());labels=json.loads((ROOT/'data/source_labels.geojson').read_text())['features'];allrows=[];summaries=[];maprecords=[]
 for scene in scenes:
  sid=scene['scene'];local=[f for f in labels if f['properties']['scene']==sid]
  with rasterio.open(scene['sources']['vv']) as ref:
   native=Transformer.from_crs(4326,ref.crs,always_xy=True).transform;to_geo=Transformer.from_crs(ref.crs,4326,always_xy=True).transform
   objects=[(f,geom_transform(native,shape(f['geometry']))) for f in local]
   for number,(f,g) in enumerate(objects):
    prop=f['properties'];win=integer_window(g.bounds,ref)
    if win.width<=0 or win.height<=0:summaries.append({**prop,'excluded':'outside source extent'});continue
    trans=ref.window_transform(win);arrays=read_sources(scene,win,ref);cube,valid=features(arrays['vv'],arrays['vh'])
    mask=rasterize([(mapping(g),1)],out_shape=valid.shape,transform=trans,dtype='uint8').astype(bool)&valid
    rr,cc=np.where(mask);original_n=len(rr);limit=1200 if prop['label_group']=='water' else 800 if prop['label_group']=='plastic' else 500
    if len(rr)>limit:
     index=np.random.default_rng(42).choice(len(rr),limit,replace=False);rr=rr[index];cc=cc[index]
    selected=0
    for r,c in zip(rr,cc):
     x1,y1=trans*(int(c),int(r));x2,y2=trans*(int(c)+1,int(r)+1);cell=box(x1,y2,x2,y1);fraction=g.intersection(cell).area/cell.area
     if fraction<.5:continue
     lon,lat=to_geo((x1+x2)/2,(y1+y2)/2)
     row={**prop,'event':scene['event'],'location':scene['location'],'processing':scene['processing'],'row':int(r+win.row_off),'col':int(c+win.col_off),'longitude':lon,'latitude':lat,'coverage_fraction':fraction,'total_core_candidates':original_n}
     row.update({name:float(cube[i,r,c]) for i,name in enumerate(CORE)});row.update({name:float(arrays[name][r,c]) if name in arrays else np.nan for name in RAW});allrows.append(row);selected+=1
    summaries.append({**prop,'location':scene['location'],'event':scene['event'],'total_core_candidates':original_n,'sampled_pixels':selected,'window_pixels':int(win.width*win.height)})
   # Target-focused products: bound all positive footprints. Negative-only scenes show the first water control.
   focus=[g for f,g in objects if f['properties']['label_group']=='plastic'] or [objects[0][1]]
   b=np.array([g.bounds for g in focus]);bounds=[b[:,0].min(),b[:,1].min(),b[:,2].max(),b[:,3].max()]
   pad=35 if scene['location']=='Greece' else 25
   win=integer_window(bounds,ref,pad=pad)
   arrays=read_sources(scene,win,ref);cube,map_valid=features(arrays['vv'],arrays['vh']);cube[:,~map_valid]=np.nan;trans=ref.window_transform(win)
   profile={'driver':'GTiff','height':int(win.height),'width':int(win.width),'crs':ref.crs,'transform':trans,'dtype':'float32','nodata':np.nan,'compress':'deflate','predictor':3,'tiled':True,'blockxsize':256,'blockysize':256}
   raw_names=[n for n in RAW if n in arrays];raw_path=ROOT/'rasters'/f'{sid}_original_inputs.tif'
   with rasterio.open(raw_path,'w',count=len(raw_names),**profile) as dst:
    for i,n in enumerate(raw_names):dst.write(arrays[n],i+1);dst.set_band_description(i+1,n)
   feature_path=ROOT/'rasters'/f'{sid}_common_features.tif'
   with rasterio.open(feature_path,'w',count=len(CORE),**profile) as dst:
    dst.write(cube)
    for i,n in enumerate(CORE):dst.set_band_description(i+1,n)
   # Preserve every available ancillary layer in its native units for tables and optional PCA.
   record={**scene,'raw_crop':str(raw_path),'common_features':str(feature_path),'raw_band_names':raw_names,'map_shape':[int(win.height),int(win.width)],'map_native_origin':[int(win.row_off),int(win.col_off)]};maprecords.append(record)
  print(sid,scene['location'],'sampled',sum(r['scene']==sid for r in allrows),'map',record['map_shape'],flush=True)
 pd.DataFrame(allrows).to_csv(ROOT/'data/sampled_pixels.csv',index=False)
 pd.DataFrame(summaries).to_csv(ROOT/'data/polygon_sampling_audit.csv',index=False)
 (ROOT/'data/map_scenes.json').write_text(json.dumps(maprecords,indent=2))
 df=pd.DataFrame(allrows);print(df.groupby(['location','label_group']).size().to_string(),flush=True)
