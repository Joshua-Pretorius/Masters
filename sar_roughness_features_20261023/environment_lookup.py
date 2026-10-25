import os
for key in ['PROJ_LIB','PROJ_DATA','GDAL_DATA']:os.environ.pop(key,None)
from pathlib import Path
import json,numpy as np,pandas as pd,xarray as xr,rasterio
from scipy.spatial import cKDTree
from rasterio.transform import from_origin
from pyproj import Geod
ROOT=Path(r'D:\Masters\sar_roughness_features_20261023');GEOD=Geod(ellps='WGS84')
CONTEXT=['wind_u_m_s','wind_v_m_s','wind_speed_m_s','current_u_m_s','current_v_m_s','current_speed_m_s','wave_height_m','wave_period_s','wave_direction_deg','surface_temperature_C','chlorophyll_mg_m3','wind_relative_m_s','ascending']
class EnvironmentalLookup:
 def __init__(self,scene):
  self.scene=scene;sid=scene['scene'];when=pd.to_datetime(sid,format='%Y%m%dT%H%M%S');self.sources=[];self.cos=np.cos(np.deg2rad(scene['latitude']));folder=ROOT/'environment'
  windfile=folder/f'{sid}_era5_grid.json';wind=json.loads(windfile.read_text())['cells'] if windfile.exists() else [json.loads((folder/f'{sid}_era5_wind.json').read_text())]
  self.wind=[]
  for cell in wind:
   ts=pd.to_datetime(cell['hourly']['time']).astype('int64').to_numpy();spd=np.array(cell['hourly']['wind_speed_10m']);ang=np.deg2rad(cell['hourly']['wind_direction_10m']);u=np.interp(when.value,ts,-spd*np.sin(ang));v=np.interp(when.value,ts,-spd*np.cos(ang));self.wind.append([cell['longitude'],cell['latitude'],u,v])
  self.wind=np.array(self.wind);self.windtree=cKDTree(np.column_stack([self.wind[:,0]*self.cos,self.wind[:,1]]))
  self.ascending=np.nan
  asffile=folder/f'{sid}_asf_metadata.json'
  if asffile.exists():
   data=json.loads(asffile.read_text());matches=[f['properties'] for f in data.get('features',[]) if f['properties'].get('sceneName')==scene['granule'] and f['properties'].get('flightDirection')]
   if matches:self.ascending=float(matches[0]['flightDirection']=='ASCENDING')
  configs={'physics':{'uo':'current_u_m_s','vo':'current_v_m_s','thetao':'surface_temperature_C'},'waves':{'VHM0':'wave_height_m','VTM02':'wave_period_s','VMDR':'wave_direction_deg'},'chlorophyll':{'chl':'chlorophyll_mg_m3'}}
  if scene['location']=='Greece':configs={'currents':{'uo':'current_u_m_s','vo':'current_v_m_s'},'waves':configs['waves'],'temperature':{'thetao':'surface_temperature_C'},'chlorophyll':configs['chlorophyll']}
  for kind,names in configs.items():
   file=folder/f'{sid}_{kind}_expanded.nc'
   if not file.exists():file=folder/f'{sid}_{kind}.nc'
   if not file.exists():continue
   with xr.open_dataset(file) as opened:ds=opened.load()
   if 'depth' in ds.dims:ds=ds.sel(depth=float(ds.depth.min()))
   times=[str(t) for t in ds.time.values];method='same-day daily mean'
   if ds.sizes.get('time',0)>1:
    original=ds;ds=ds.interp(time=np.datetime64(when));method='linear interpolation of bracketing hours'
    if 'VMDR' in original:
     ds['VMDR']=np.rad2deg(np.arctan2(np.sin(np.deg2rad(original.VMDR)).interp(time=np.datetime64(when)),np.cos(np.deg2rad(original.VMDR)).interp(time=np.datetime64(when))))%360
   else:ds=ds.isel(time=0)
   lat=ds.latitude.values;lon=ds.longitude.values;xx,yy=np.meshgrid(lon,lat);arrays={name:ds[key].transpose('latitude','longitude').values.astype(float) for key,name in names.items()};valid=np.all(np.isfinite(np.stack(list(arrays.values()))),axis=0)
   if not valid.any():continue
   tree=cKDTree(np.column_stack([xx[valid]*self.cos,yy[valid]]));self.sources.append({'kind':kind,'path':str(file),'lon':lon,'lat':lat,'xx':xx,'yy':yy,'arrays':arrays,'valid':valid,'tree':tree,'method':method,'times':times,'depth':float(ds.depth) if 'depth' in ds.coords else None})
 def sample(self,lon,lat):
  lon=np.asarray(lon);lat=np.asarray(lat);out=pd.DataFrame(index=np.arange(len(lon)));_,which=self.windtree.query(np.column_stack([lon*self.cos,lat]));out['wind_u_m_s']=self.wind[which,2];out['wind_v_m_s']=self.wind[which,3];out['wind_speed_m_s']=np.hypot(out.wind_u_m_s,out.wind_v_m_s);_,_,d=GEOD.inv(lon,lat,self.wind[which,0],self.wind[which,1]);out['wind_grid_distance_km']=d/1000;out['ascending']=self.ascending
  for source in self.sources:
   _,ix=source['tree'].query(np.column_stack([lon*self.cos,lat]));vx=source['xx'][source['valid']];vy=source['yy'][source['valid']];_,_,dist=GEOD.inv(lon,lat,vx[ix],vy[ix]);kind=source['kind'];out[kind+'_distance_km']=dist/1000;out[kind+'_selected_lon']=vx[ix];out[kind+'_selected_lat']=vy[ix]
   nearx=np.argmin(abs(source['lon'][None,:]-lon[:,None]),axis=1);neary=np.argmin(abs(source['lat'][None,:]-lat[:,None]),axis=1);out[kind+'_native_nearest_valid']=source['valid'][neary,nearx];out[kind+'_inside_download_extent']=(lon>=source['lon'].min())&(lon<=source['lon'].max())&(lat>=source['lat'].min())&(lat<=source['lat'].max())
   for name,array in source['arrays'].items():
    values=array[source['valid']][ix];values[dist>100000]=np.nan;out[name]=values;out[name+'_native_nearest']=array[neary,nearx]
  for name in CONTEXT:
   if name not in out:out[name]=np.nan
  out['current_speed_m_s']=np.hypot(out.current_u_m_s,out.current_v_m_s);out['wind_relative_m_s']=np.hypot(out.wind_u_m_s-out.current_u_m_s,out.wind_v_m_s-out.current_v_m_s)
  return out
 def native_layers(self):
  result=[]
  for source in self.sources:
   lon=source['lon'];lat=source['lat'];dx=float(np.median(np.diff(lon)));dy=float(np.median(np.diff(lat)));names=list(source['arrays']);stack=np.stack(list(source['arrays'].values()))[:,::-1,:].astype('float32');path=ROOT/'environment'/f"{self.scene['scene']}_{source['kind']}_native_grid.tif"
   with rasterio.open(path,'w',driver='GTiff',width=len(lon),height=len(lat),count=len(names),dtype='float32',crs='EPSG:4326',transform=from_origin(lon.min()-dx/2,lat.max()+dy/2,dx,dy),nodata=np.nan,compress='deflate') as dst:
    dst.write(stack)
    for i,n in enumerate(names):dst.set_band_description(i+1,n)
   for i,n in enumerate(names):result.append({'scene':self.scene['scene'],'path':str(path),'kind':source['kind'],'band':i+1,'name':n,'min':float(np.nanpercentile(stack[i],2)),'max':float(np.nanpercentile(stack[i],98)),'native_grid_degrees':dx,'time_method':source['method'],'source':source['path'],'depth_m':source['depth']})
  return result
if __name__=='__main__':
 scenes=json.loads((ROOT/'data/source_scenes.json').read_text());pixels=pd.read_csv(ROOT/'data/sampled_pixels.csv');parts=[];layers=[];summaries=[]
 for scene in scenes:
  local=pixels[pixels.scene==scene['scene']].reset_index(drop=True);lookup=EnvironmentalLookup(scene);env=lookup.sample(local.longitude.to_numpy(),local.latitude.to_numpy());parts.append(pd.concat([local,env],axis=1));layers+=lookup.native_layers()
  centres=lookup.sample(np.array([scene['longitude']]),np.array([scene['latitude']]));summaries.append({'scene':scene['scene'],'location':scene['location'],**centres.iloc[0].to_dict()});print('environment matched',scene['scene'],flush=True)
 pd.concat(parts,ignore_index=True).to_csv(ROOT/'data/pixels_with_environment.csv',index=False);pd.DataFrame(layers).to_csv(ROOT/'environment/native_layer_index.csv',index=False);pd.DataFrame(summaries).to_csv(ROOT/'environment/scene_context.csv',index=False)
 print(pd.DataFrame(summaries)[['scene','location','wind_speed_m_s','wave_height_m','current_speed_m_s','ascending']].to_string(index=False))
