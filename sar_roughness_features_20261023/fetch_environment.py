from pathlib import Path
import json,datetime,requests,shutil
import copernicusmarine as cm
ROOT=Path(r'D:\Masters\sar_roughness_features_20261023');out=ROOT/'environment';scenes=json.loads((ROOT/'data/source_scenes.json').read_text());old=Path(r'D:\Masters\greece_deployment_features_20261022\environment');log=[]
products={'physics':('cmems_mod_glo_phy_my_0.083deg_P1D-m',['uo','vo','thetao'],True,True),'waves':('cmems_mod_glo_wav_my_0.2deg_PT3H-i',['VHM0','VTM02','VMDR','VSDX','VSDY'],False,False),'chlorophyll':('cmems_mod_glo_bgc_my_0.25deg_P1D-m',['chl'],True,True)}
for scene in scenes:
 sid=scene['scene'];dt=datetime.datetime.strptime(sid,'%Y%m%dT%H%M%S');lat,lon=scene['latitude'],scene['longitude']
 wind=out/f'{sid}_era5_wind.json'
 if not wind.exists():
  if scene['location']=='Greece':shutil.copy2(old/wind.name,wind)
  else:
   date=dt.date().isoformat();args={'latitude':lat,'longitude':lon,'start_date':date,'end_date':date,'hourly':'wind_speed_10m,wind_direction_10m,surface_pressure','models':'era5','wind_speed_unit':'ms','timezone':'GMT','cell_selection':'nearest','elevation':'nan'}
   try:
    response=requests.get('https://archive-api.open-meteo.com/v1/archive',params=args,timeout=60);response.raise_for_status();data=response.json();data['_provenance']={'source':'ERA5 via Open-Meteo','request_url':response.url,'native_resolution_degrees':.25};wind.write_text(json.dumps(data,indent=2));print('wind',sid,flush=True)
   except Exception as e:print('Wind failed',sid,str(e),flush=True)
 # ASF metadata are public; only flight direction/orbit metadata are requested, no imagery or remote server connection.
 asf=out/f'{sid}_asf_metadata.json'
 if not asf.exists() and scene.get('granule'):
  try:
   response=requests.get('https://api.daac.asf.alaska.edu/services/search/param',params={'granule_list':scene['granule'],'output':'geojson'},timeout=40);response.raise_for_status();asf.write_text(response.text);data=response.json();print('asf',sid,len(data.get('features',[])),flush=True)
  except Exception as e:print('ASF metadata unavailable',sid,str(e),flush=True)
 if scene['location']=='Greece':
  for file in old.glob(sid+'*.nc'):shutil.copy2(file,out/file.name)
  continue
 for kind,(dataset,variables,daily,depth) in products.items():
  target=out/f'{sid}_{kind}.nc'
  if target.exists():continue
  start=dt.replace(hour=0,minute=0,second=0) if daily else dt.replace(hour=(dt.hour//3)*3,minute=0,second=0)
  end=start+datetime.timedelta(hours=23,minutes=59) if daily else start+datetime.timedelta(hours=3)
  args=dict(dataset_id=dataset,variables=variables,minimum_longitude=lon-.8,maximum_longitude=lon+.8,minimum_latitude=lat-.8,maximum_latitude=lat+.8,start_datetime=start.isoformat(),end_datetime=end.isoformat(),output_directory=out,output_filename=target.name,credentials_file=Path.home()/'.copernicusmarine'/'.copernicusmarine-credentials',disable_progress_bar=True,netcdf_compression_level=1)
  if depth:args.update(minimum_depth=1,maximum_depth=1,coordinates_selection_method='nearest')
  try:
   cm.subset(**args);entry={'scene':sid,'kind':kind,'dataset':dataset,'variables':variables,'status':'downloaded','start':start.isoformat(),'end':end.isoformat()};print('marine',sid,kind,flush=True)
  except Exception as e:entry={'scene':sid,'kind':kind,'dataset':dataset,'status':'failed','error':str(e)};print('FAILED',sid,kind,str(e),flush=True)
  log.append(entry);(out/'download_log.json').write_text(json.dumps(log,indent=2))
