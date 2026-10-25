from pathlib import Path
import json, requests, datetime, math
ROOT=Path(r'D:\Masters\greece_deployment_features_20261022')
scenes=json.loads((ROOT/'data/scene_inventory.json').read_text())
for scene in scenes:
    sid=scene['scene']; date=f'{sid[:4]}-{sid[4:6]}-{sid[6:8]}'
    path=ROOT/'environment'/f'{sid}_era5_wind.json'
    if path.exists() and 'cell_selection=nearest' in __import__('json').loads(path.read_text()).get('_provenance',{}).get('request_url',''): continue
    params={'latitude':39.0393,'longitude':26.52455,'start_date':date,'end_date':date,'hourly':'wind_speed_10m,wind_direction_10m,surface_pressure','models':'era5','wind_speed_unit':'ms','timezone':'GMT','cell_selection':'nearest','elevation':'nan'}
    try:
        r=requests.get('https://archive-api.open-meteo.com/v1/archive',params=params,timeout=60); r.raise_for_status()
        result=r.json(); result['_provenance']={'request_url':r.url,'source':'ERA5 via Open-Meteo','native_resolution_degrees':.25,'time_reference':'UTC','retrieved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
        path.write_text(json.dumps(result,indent=2)); print('wind',sid,r.status_code,flush=True)
    except Exception as e: print('wind failed',sid,str(e),flush=True)
