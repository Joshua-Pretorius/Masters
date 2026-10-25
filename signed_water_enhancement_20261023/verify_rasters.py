import os,json,math
for k in ['PROJ_LIB','PROJ_DATA','GDAL_DATA']:os.environ.pop(k,None)
from pathlib import Path
import numpy as np,rasterio
from rasterio.windows import Window
from enhance import ROOT,derive,land_shapes,metric_windows
from rasterio.features import rasterize
manifest=json.loads((ROOT/'raster_manifest.json').read_text());checks=[]
for rec in manifest:
 with rasterio.open(rec['path']) as dst,rasterio.open(rec['source']) as src:
  originalwin=Window(*rec['window']);assert src.crs==dst.crs;assert dst.transform==src.window_transform(originalwin)
  assert (dst.width,dst.height)==(int(originalwin.width),int(originalwin.height))
  # Compare a fresh source calculation across the 512-pixel tile join, where one exists.
  r=min(1012,max(0,dst.height//2-16));c=min(1012,max(0,dst.width//2-16));h=min(32,dst.height-r);w=min(32,dst.width-c)
  windows,pix=metric_windows(src,originalwin);halo=max(max(x[0])//2 for x in windows)+2
  rw=Window(originalwin.col_off+c-halo,originalwin.row_off+r-halo,w+2*halo,h+2*halo)
  a=src.read(1,window=rw,boundless=True,masked=True).astype('float64').filled(np.nan);valid=np.isfinite(a)&(a>0);db=np.full(a.shape,np.nan);db[valid]=10*np.log10(a[valid])
  with rasterio.open(rec['mask_path']) as m:eligible=m.read(2,window=Window(c,r,w+2*halo,h+2*halo)).astype(bool)
  expected=derive(db,valid&eligible,windows)[:,halo:halo+h,halo:halo+w];actual=dst.read(window=Window(c,r,w,h))
  assert np.allclose(expected,actual,atol=2e-4,equal_nan=True),rec['path']
  delta=np.abs(expected-actual);finite=delta[np.isfinite(delta)]
  checks.append(dict(path=rec['path'],native_grid_exact=True,independent_recalculation_matches=True,max_error=float(finite.max()) if len(finite) else None))
(ROOT/'raster_checks.json').write_text(json.dumps(checks,indent=2));print('Verified',len(checks),'native grids and independent calculations')
