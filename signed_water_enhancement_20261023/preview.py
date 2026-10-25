import os
for k in ['PROJ_LIB','PROJ_DATA','GDAL_DATA']:os.environ.pop(k,None)
import json,numpy as np,rasterio,fiona
from pathlib import Path
from rasterio.windows import from_bounds,Window
from shapely.geometry import shape
from pyproj import Transformer
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(r'D:\Masters\signed_water_enhancement_20261023')
manifest=json.loads((ROOT/'raster_manifest.json').read_text());jobs=json.loads((ROOT/'jobs.json').read_text())
fig,axes=plt.subplots(2,3,figsize=(13,8),constrained_layout=True)
for row,sid in enumerate(['20210626T161500','20240629T041520']):
 rec=next(r for r in manifest if r['scene']==sid and r['pol']=='vv' and r['window'])
 # Locate the patch covering the fixed deployments, avoiding a different water-reference patch.
 for r in [r for r in manifest if r['scene']==sid and r['pol']=='vv']:
  with rasterio.open(r['path']) as src:
   if src.bounds.left<26.5245<src.bounds.right and src.bounds.bottom<39.0393<src.bounds.top:rec=r;break
 with rasterio.open(rec['path']) as src:
  win=from_bounds(26.5215,39.0374,26.5275,39.0411,src.transform).round_offsets().round_lengths();a=src.read([11,1,2],window=win);extent=rasterio.windows.bounds(win,src.transform);ext=[extent[0],extent[2],extent[1],extent[3]]
 for col,(name,vmin,vmax,cmap) in enumerate([('Original VV (dB)',-30,-5,'gray'),('Signed water contrast (dB)',-6,6,'RdBu_r'),('Signed standardized contrast',-3,3,'RdBu_r')]):
  ax=axes[row,col];im=ax.imshow(a[col],extent=ext,origin='upper',vmin=vmin,vmax=vmax,cmap=cmap,interpolation='nearest');ax.set_title(sid[:8]+'\n'+name,fontsize=11);ax.ticklabel_format(useOffset=False);ax.tick_params(labelsize=7);fig.colorbar(im,ax=ax,shrink=.7)
  job=next(j for j in jobs if j['scene']==sid);sf=Path(job['project']).parent/('Controlled_2021.shp' if sid.startswith('2021') else 'Controlled_Deployments_2024.shp')
  with fiona.open(sf) as fs:
   for f in fs:
    g=shape(f['geometry']);parts=list(g.geoms) if hasattr(g,'geoms') else [g]
    for p in parts:x,y=p.exterior.xy;ax.plot(x,y,color='#d6b600',lw=1)
fig.suptitle('Fixed signed enhancement — small scale, identical display limits across scenes\nOutlines are deployment references; enhancement does not establish target identity',fontsize=13)
fig.savefig(ROOT/'signed_enhancement_preview.png',dpi=160);plt.close(fig)
print('Preview saved')
