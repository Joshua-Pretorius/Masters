from pathlib import Path
import json, datetime, copernicusmarine as cm
ROOT=Path(r'D:\Masters\greece_deployment_features_20261022'); out=ROOT/'environment'
products={
 'currents':('cmems_mod_med_phy-cur_my_4.2km_PT1H-m',['uo','vo'],False,False),
 'waves':('cmems_mod_med_wav_my_4.2km_PT1H-i',['VHM0','VTM02','VMDR','VSDX','VSDY'],False,False),
 'temperature':('cmems_mod_med_phy-temp_my_4.2km_P1D-m',['thetao'],True,True),
 'chlorophyll':('cmems_mod_med_bgc-plankton_my_4.2km_P1D-m',['chl'],True,True)}
log=[]
for scene in sorted(json.loads((ROOT/'data/scene_inventory.json').read_text()),key=lambda x:x['scene']):
 sid=scene['scene']; dt=datetime.datetime.strptime(sid,'%Y%m%dT%H%M%S')
 for name,(dataset,variables,daily,depth) in products.items():
  path=out/f'{sid}_{name}.nc'
  if path.exists(): print('cached',path.name,flush=True); continue
  start=dt.replace(hour=0,minute=0,second=0) if daily else dt.replace(minute=0,second=0)
  end=start+datetime.timedelta(hours=23,minutes=59) if daily else start+datetime.timedelta(hours=1)
  args=dict(dataset_id=dataset,variables=variables,minimum_longitude=26.30,maximum_longitude=26.75,minimum_latitude=38.8,maximum_latitude=39.25,start_datetime=start.isoformat(),end_datetime=end.isoformat(),output_directory=out,output_filename=path.name,credentials_file=Path.home()/'.copernicusmarine'/'.copernicusmarine-credentials',disable_progress_bar=True,netcdf_compression_level=1)
  if depth: args.update(minimum_depth=0,maximum_depth=2,coordinates_selection_method='nearest')
  try:
   result=cm.subset(**args)
   entry={'scene':sid,'kind':name,'dataset':dataset,'variables':variables,'status':'downloaded','path':str(path),'start':start.isoformat(),'end':end.isoformat(),'retrieved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
   print('downloaded',sid,name,flush=True)
  except Exception as e:
   entry={'scene':sid,'kind':name,'dataset':dataset,'status':'failed','error':str(e)}; print('FAILED',sid,name,str(e),flush=True)
  log.append(entry); (out/'download_log.json').write_text(json.dumps(log,indent=2))
