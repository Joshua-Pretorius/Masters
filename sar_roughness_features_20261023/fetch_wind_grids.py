from pathlib import Path
import json,requests
from shapely.geometry import shape
ROOT=Path(r'D:\Masters\sar_roughness_features_20261023');scenes=json.loads((ROOT/'data/source_scenes.json').read_text());features=json.loads((ROOT/'data/source_labels.geojson').read_text())['features']
for scene in scenes:
 sid=scene['scene'];out=ROOT/'environment'/f'{sid}_era5_grid.json'
 if out.exists():continue
 coordinates={(round(shape(f['geometry']).centroid.y*4)/4,round(shape(f['geometry']).centroid.x*4)/4) for f in features if f['properties']['scene']==sid};coordinates.add((round(scene['latitude']*4)/4,round(scene['longitude']*4)/4));coordinates=sorted(coordinates)
 date=f'{sid[:4]}-{sid[4:6]}-{sid[6:8]}'
 params={'latitude':','.join(str(c[0]) for c in coordinates),'longitude':','.join(str(c[1]) for c in coordinates),'start_date':date,'end_date':date,'hourly':'wind_speed_10m,wind_direction_10m','models':'era5','wind_speed_unit':'ms','timezone':'GMT','cell_selection':'nearest','elevation':','.join(['nan']*len(coordinates))}
 try:
  r=requests.get('https://archive-api.open-meteo.com/v1/archive',params=params,timeout=60);r.raise_for_status();d=r.json();d=d if isinstance(d,list) else [d];out.write_text(json.dumps({'cells':d,'requested_grid_centres':coordinates,'provenance':{'source':'ERA5 via Open-Meteo','request_url':r.url,'native_grid_degrees':.25}},indent=2));print('wind grid',sid,len(d),flush=True)
 except Exception as e:print('FAILED',sid,str(e),flush=True)

