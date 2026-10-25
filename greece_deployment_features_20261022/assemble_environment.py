import os
for key in ['PROJ_LIB','PROJ_DATA','GDAL_DATA']: os.environ.pop(key,None)
from pathlib import Path
import json, numpy as np, pandas as pd, xarray as xr, rasterio
from rasterio.transform import from_origin
from pyproj import Geod
ROOT=Path(r'D:\Masters\greece_deployment_features_20261022'); out=ROOT/'environment'; geo=Geod(ellps='WGS84')
scenes=json.loads((ROOT/'data/scene_inventory.json').read_text()); pixels=pd.read_csv(ROOT/'data/core_pixels.csv')
records=[]; provenance=[]; sampletables=[]; layers=[]
configs={'currents':{'uo':'current_u_m_s','vo':'current_v_m_s'},'waves':{'VHM0':'wave_height_m','VTM02':'wave_period_s','VMDR':'wave_from_direction_deg','VSDX':'stokes_u_m_s','VSDY':'stokes_v_m_s'},'temperature':{'thetao':'sst_C'},'chlorophyll':{'chl':'chlorophyll_mg_m3'}}
for scene in scenes:
 sid=scene['scene']; when=pd.to_datetime(sid,format='%Y%m%dT%H%M%S'); rec={'scene':sid,'acquisition_utc':when.isoformat()+'Z'}; pix=pixels[pixels.scene==sid][['scene','row','col','longitude','latitude']].copy()
 wind=json.loads((out/f'{sid}_era5_wind.json').read_text()); times=pd.to_datetime(wind['hourly']['time']).astype('int64').to_numpy(); t=when.value
 speed=np.array(wind['hourly']['wind_speed_10m']); angle=np.radians(wind['hourly']['wind_direction_10m']); u=np.interp(t,times,-speed*np.sin(angle)); v=np.interp(t,times,-speed*np.cos(angle))
 rec.update(wind_u_m_s=u,wind_v_m_s=v,wind_speed_m_s=np.hypot(u,v),wind_from_direction_deg=np.degrees(np.arctan2(-u,-v))%360,wind_stress_proxy_m2_s2=u*u+v*v)
 provenance.append({'scene':sid,'kind':'wind','source':'ERA5 via Open-Meteo','selected_longitude':wind['longitude'],'selected_latitude':wind['latitude'],'distance_to_deployment_m':geo.inv(26.52455,39.0393,wind['longitude'],wind['latitude'])[2],'native_grid_degrees':.25,'native_resolution_note':'Atmospheric reanalysis approximately 25 km; Open-Meteo nearest grid cell; elevation downscaling disabled','time_method':'Linear interpolation of hourly u/v reconstructed from speed and from-direction','times_used':str(list(wind['hourly']['time'][max(0,when.hour):when.hour+2]))})
 for key in ['wind_u_m_s','wind_v_m_s','wind_speed_m_s']: pix[key]=rec[key]
 for kind,varmap in configs.items():
  path=out/f'{sid}_{kind}.nc'
  if not path.exists():
   for name in varmap.values(): rec[name]=np.nan
   continue
  with xr.open_dataset(path) as opened:
   ds=opened.load()
  if 'depth' in ds.dims: ds=ds.sel(depth=float(ds.depth.min()))
  source_times=[str(x) for x in ds.time.values]
  if ds.sizes.get('time',0)>1:
   # Wave from-direction is circular; interpolate its sine/cosine instead of degrees.
   original=ds
   ds=ds.interp(time=np.datetime64(when))
   if 'VMDR' in original:
    sine=np.sin(np.deg2rad(original.VMDR)).interp(time=np.datetime64(when)); cosine=np.cos(np.deg2rad(original.VMDR)).interp(time=np.datetime64(when)); ds['VMDR']=np.rad2deg(np.arctan2(sine,cosine))%360
   method='Linear between bracketing hourly fields (circular for wave direction)'
  else: ds=ds.isel(time=0); method='Same-day daily mean; not instantaneous'
  lat=ds.latitude.values; lon=ds.longitude.values; xx,yy=np.meshgrid(lon,lat)
  arrays=[ds[v].transpose('latitude','longitude').values.astype(float) for v in varmap]
  valid=np.all(np.isfinite(np.stack(arrays)),axis=0)
  _,_,distance=geo.inv(np.full(xx.shape,26.52455),np.full(yy.shape,39.0393),xx,yy)
  nearest=np.unravel_index(np.argmin(distance),distance.shape); chosen=np.unravel_index(np.argmin(np.where(valid,distance,np.inf)),distance.shape)
  if not np.any(valid):
   for name in varmap.values(): rec[name]=np.nan
   continue
  rec[kind+'_distance_m']=float(distance[chosen]); rec[kind+'_nearest_cell_valid']=bool(valid[nearest]); rec[kind+'_grid_lon']=float(xx[chosen]); rec[kind+'_grid_lat']=float(yy[chosen])
  if distance[chosen]>20000: raise ValueError('No representative regional context within 20 km: '+kind)
  provenance.append({'scene':sid,'kind':kind,'source':str(path),'selected_longitude':float(xx[chosen]),'selected_latitude':float(yy[chosen]),'distance_to_deployment_m':float(distance[chosen]),'nearest_native_cell_valid':bool(valid[nearest]),'native_grid_degrees':float(np.median(np.diff(lon))),'time_method':method,'times_used':str(source_times),'depth_m':float(ds.depth) if 'depth' in ds.coords else None,'selection':'Nearest common-valid marine cell; regional context, no interpolation across land'})
  for a,name in zip(arrays,varmap.values()): rec[name]=float(a[chosen])
  valid_x=xx[valid]; valid_y=yy[valid]; plon=pix.longitude.to_numpy()[:,None]; plat=pix.latitude.to_numpy()[:,None]
  d2=((valid_x[None,:]-plon)*np.cos(np.deg2rad(plat)))**2+(valid_y[None,:]-plat)**2
  which=np.argmin(d2,axis=1)
  _,_,dist=geo.inv(pix.longitude.to_numpy(),pix.latitude.to_numpy(),valid_x[which],valid_y[which])
  pix[kind+'_selected_distance_m']=dist; pix[kind+'_grid_longitude']=valid_x[which]; pix[kind+'_grid_latitude']=valid_y[which]
  nearx=np.argmin(abs(lon[None,:]-plon),axis=1); neary=np.argmin(abs(lat[None,:]-plat),axis=1); pix[kind+'_native_nearest_cell_valid']=valid[neary,nearx]
  for a,name in zip(arrays,varmap.values()):
   pix[name+'_regional_nearest_valid']=a[valid][which]; pix[name+'_native_nearest']=a[neary,nearx]
  # Preserve actual coarse grid and land mask in environmental rasters.
  dx=float(np.median(np.diff(lon))); dy=float(np.median(np.diff(lat)))
  stack=np.stack(arrays)[:,::-1,:].astype('float32'); raster=out/f'{sid}_{kind}_native_grid.tif'
  with rasterio.open(raster,'w',driver='GTiff',width=len(lon),height=len(lat),count=len(arrays),dtype='float32',crs='EPSG:4326',transform=from_origin(lon.min()-dx/2,lat.max()+dy/2,dx,dy),nodata=np.nan,compress='deflate') as dst:
   dst.write(stack)
   for i,name in enumerate(varmap.values()): dst.set_band_description(i+1,name)
   dst.update_tags(source_netcdf=str(path),temporal_sampling=method,resolution='Native 1/24 degree; not SAR pixel resolution')
  for i,name in enumerate(varmap.values()): layers.append({'scene':sid,'kind':kind,'path':str(raster),'band':i+1,'name':name,'min':float(np.nanmin(stack[i])),'max':float(np.nanmax(stack[i]))})
 rec['current_speed_m_s']=float(np.hypot(rec.get('current_u_m_s',np.nan),rec.get('current_v_m_s',np.nan)))
 rec['stokes_speed_m_s']=float(np.hypot(rec.get('stokes_u_m_s',np.nan),rec.get('stokes_v_m_s',np.nan)))
 rec['wave_steepness_proxy']=rec.get('wave_height_m',np.nan)/max(9.81*rec.get('wave_period_s',np.nan)**2/(2*np.pi),.001)
 records.append(rec); sampletables.append(pix)
pd.DataFrame(records).to_csv(out/'scene_environment.csv',index=False)
pd.DataFrame(provenance).to_csv(out/'environment_sampling_audit.csv',index=False)
pd.concat(sampletables).to_csv(out/'pixel_environment_samples.csv',index=False)
pd.DataFrame(layers).to_csv(out/'environment_layer_index.csv',index=False)
print(pd.DataFrame(records)[['scene','wind_speed_m_s','wave_height_m','current_speed_m_s','sst_C','chlorophyll_mg_m3']].to_string(index=False))
print(pd.DataFrame(provenance)[['scene','kind','distance_to_deployment_m']].to_string(index=False))
