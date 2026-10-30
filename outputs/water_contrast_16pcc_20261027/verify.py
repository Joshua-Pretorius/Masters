import os,json
from pathlib import Path
for k in ('PROJ_LIB','PROJ_DATA','GDAL_DATA'): os.environ.pop(k,None)
import rasterio,numpy as np
from rasterio.windows import Window
ROOT=Path(__file__).resolve().parent
checks=[]
for r in json.loads((ROOT/'results.json').read_text()):
 assert r['status']=='complete',r
 assert not r['missing_worldcover_tiles'],r['missing_worldcover_tiles']
 with rasterio.open(r['source']) as src,rasterio.open(r['path']) as dst:
  assert dst.count==4 and src.crs==dst.crs
  assert dst.transform==src.window_transform(Window(*r['window']))
  assert dst.tags()['fingerprint']==r['fingerprint']
  assert all(n>0 for n in r['valid_counts']) and all(n>0 for n in r['negative_counts']) and all(n>0 for n in r['positive_counts'])
  thumb=dst.read(1,out_shape=(256,256)); rows,cols=np.where(np.isfinite(thumb)); assert len(rows)>0
  row,col=int(rows[len(rows)//2]*dst.height/256),int(cols[len(cols)//2]*dst.width/256)
  a=dst.read(window=Window(max(0,col-64),max(0,row-64),128,128)); assert np.isfinite(a).any()
  x,y=dst.xy(row,col)
  checks.append({'path':r['path'],'grid_and_fingerprint_verified':True,'four_bands_both_signs':True,'render_center':[x,y],'overviews':dst.overviews(1)})
(ROOT/'raster_checks.json').write_text(json.dumps(checks,indent=2)); print(json.dumps(checks,indent=2))
