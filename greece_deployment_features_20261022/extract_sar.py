import os
for key in ['PROJ_LIB','PROJ_DATA','GDAL_DATA']: os.environ.pop(key,None)
from pathlib import Path
import json, hashlib
import numpy as np
import pandas as pd
import fiona, rasterio
from rasterio.windows import from_bounds, Window
from rasterio.features import rasterize
from shapely.geometry import shape, box, mapping
from shapely.ops import transform as geom_transform
from pyproj import Transformer
ROOT=Path(r'D:\Masters\greece_deployment_features_20261022')
for sub in ['data','rasters','plots','models','environment','scripts']: (ROOT/sub).mkdir(exist_ok=True)
BATCHES={2021:Path(r'D:\Joshua\New\floating_greece_plp_20210626_20210702_01'),2024:Path(r'D:\Joshua\New\floating_greece_plp_20240629_20240705_02')}
FEATURES=['vv','vh','vv_refined_lee','vv_refined_lee_db','vv_glcm_mean','vv_glcm_std','vv_glcm_entropy','decomp_entropy','decomp_anisotropy','decomp_alpha']
project=Transformer.from_crs(4326,32635,always_xy=True).transform
waterpath=BATCHES[2021]/'digitising_batches'/BATCHES[2021].name/'Water_Background.shp'
with fiona.open(waterpath) as src: waters=[shape(f['geometry']) for f in src]
rows=[]; geomrows=[]; inventory=[]; allgeo=[]
for year,batch in BATCHES.items():
    folder=batch/'digitising_batches'/batch.name
    shp=folder/('Controlled_2021.shp' if year==2021 else 'Controlled_Deployments_2024.shp')
    with fiona.open(shp) as src: targets=[shape(f['geometry']) for f in src]
    objects=[('deployment',f'{year}_deployment_{i+1}',g) for i,g in enumerate(targets)]+[('water',f'water_{i+1}',g) for i,g in enumerate(waters)]
    for label,obj,g in objects:
        geomrows.append(dict(year=year,label=label,object_id=obj,area_m2=geom_transform(project,g).area,centroid_lon=g.centroid.x,centroid_lat=g.centroid.y,geometry_valid=g.is_valid,source=str(shp if label=='deployment' else waterpath)))
        allgeo.append({'type':'Feature','properties':{'year':year,'label':label,'object_id':obj},'geometry':mapping(g)})
    bounds=np.array([g.bounds for _,_,g in objects]); bbox=[bounds[:,0].min()-.002,bounds[:,1].min()-.002,bounds[:,2].max()+.002,bounds[:,3].max()+.002]
    for vvpath in sorted(batch.glob('processed/*/scene_*/*_slc_native_vv.tif')):
        prefix=vvpath.name[:-len('_slc_native_vv.tif')]; sid=vvpath.parent.name.replace('scene_','')
        paths=[vvpath.parent/(prefix+'_slc_native_'+f+'.tif') for f in FEATURES]
        with rasterio.open(vvpath) as src:
            floating=from_bounds(*bbox,src.transform)
            col,row=int(np.floor(floating.col_off)),int(np.floor(floating.row_off))
            win=Window(col,row,int(np.ceil(floating.col_off+floating.width))-col,int(np.ceil(floating.row_off+floating.height))-row)
            trans=src.window_transform(win); crs=src.crs; profile=src.profile.copy()
        stack=[]
        for path in paths:
            with rasterio.open(path) as src:
                if src.crs!=crs or src.window_transform(win)!=trans: raise ValueError('Grid mismatch '+str(path))
                a=src.read(1,window=win,masked=True).filled(np.nan).astype('float32')
                a[a<=-9990]=np.nan
                stack.append(a)
        stack=np.stack(stack); h,w=stack.shape[1:]
        profile.update(height=h,width=w,transform=trans,count=len(FEATURES),dtype='float32',nodata=np.nan,compress='deflate',predictor=3,tiled=True,blockxsize=256,blockysize=256)
        output=ROOT/'rasters'/f'{sid}_SAR_inputs.tif'
        with rasterio.open(output,'w',**profile) as dst:
            dst.write(stack)
            for i,f in enumerate(FEATURES): dst.set_band_description(i+1,f)
            dst.update_tags(source_acquisition=sid,source_year=year,purpose='Cropped original SAR features; no resampling',footprint_label='known deployment, not guaranteed SAR detectability')
        counts={}
        for label,obj,g in objects:
            mask=rasterize([(mapping(g),1)],out_shape=(h,w),transform=trans,all_touched=True,dtype='uint8')
            nr=0; ncore=0
            for r,c in zip(*np.where(mask)):
                left,top=trans*(int(c),int(r)); right,bottom=trans*(int(c)+1,int(r)+1)
                pixel=box(left,bottom,right,top); fraction=g.intersection(pixel).area/pixel.area
                if fraction<1e-8: continue
                lon,lat=trans*(c+.5,r+.5); x,y=project(lon,lat)
                valid=bool(np.all(np.isfinite(stack[:,r,c])))
                core=fraction>=.5
                data=dict(scene=sid,year=year,label=label,object_id=obj,row=int(r+row),col=int(c+col),crop_row=int(r),crop_col=int(c),longitude=lon,latitude=lat,utm_x=x,utm_y=y,coverage_fraction=fraction,core=core,valid_all=valid,background_reused_from_2021=year==2024 and label=='water')
                data.update({f:float(stack[i,r,c]) for i,f in enumerate(FEATURES)})
                rows.append(data); nr+=1; ncore+=int(core and valid)
            counts[obj]={'intersecting_pixels':nr,'core_valid_pixels':ncore}
        manifest=vvpath.parent/(prefix+'_slc_manifest.json')
        meta=json.loads(manifest.read_text()) if manifest.exists() else {}
        inventory.append(dict(scene=sid,year=year,acquisition=meta.get('acquisition_start',sid),shape=[h,w],transform=list(trans),crs=str(crs),raw_crop=str(output),source_rasters=[str(x) for x in paths],source_manifest=str(manifest),source_polygon=str(shp),water_polygon=str(waterpath),counts=counts,feature_ranges={f:[float(np.nanmin(stack[i])),float(np.nanmax(stack[i]))] for i,f in enumerate(FEATURES)}))
        print(sid,counts,flush=True)
df=pd.DataFrame(rows); df.to_csv(ROOT/'data'/'all_intersecting_pixels.csv',index=False)
core=df[df.core & df.valid_all].copy(); core.to_csv(ROOT/'data'/'core_pixels.csv',index=False)
pd.DataFrame(geomrows).to_csv(ROOT/'data'/'polygon_inventory.csv',index=False)
(ROOT/'data'/'label_polygons.geojson').write_text(json.dumps({'type':'FeatureCollection','features':allgeo}))
(ROOT/'data'/'scene_inventory.json').write_text(json.dumps(inventory,indent=2))
summary=[]
for (sid,obj,label),group in df.groupby(['scene','object_id','label']):
    for f in FEATURES:
        valid=np.isfinite(group[f]); a=group.loc[valid,f].to_numpy(); weights=group.loc[valid,'coverage_fraction'].to_numpy()
        summary.append(dict(scene=sid,object_id=obj,label=label,feature=f,n_intersecting=len(a),n_core=int((group.core & valid).sum()),mean_area_weighted=float(np.average(a,weights=weights)) if len(a) else None,median=float(np.median(a)) if len(a) else None,min=float(np.min(a)) if len(a) else None,max=float(np.max(a)) if len(a) else None))
pd.DataFrame(summary).to_csv(ROOT/'data'/'polygon_feature_summary.csv',index=False)
print('TOTAL',core.groupby(['scene','label']).size().to_dict(),flush=True)
