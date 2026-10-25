import os,sys,json,math
for k in ['PROJ_LIB','PROJ_DATA','GDAL_DATA']:os.environ.pop(k,None)
import numpy as np,rasterio,fiona
from rasterio.windows import Window
from rasterio.features import rasterize
from shapely.geometry import shape,mapping
from shapely.ops import unary_union
from generate import ROOT,BASE,calculate
with fiona.open(BASE/'Area.geojson') as f:area=unary_union([shape(x['geometry']) for x in f])
checks=[]
for rec in json.loads((ROOT/'manifest.json').read_text()):
 with rasterio.open(rec['path']) as dst,rasterio.open(rec['vv']) as v,rasterio.open(rec['vh']) as h,rasterio.open(rec['lee']) as l,rasterio.open(rec['mask']) as mask:
  win=Window(*rec['window']);assert dst.crs==v.crs and dst.transform==v.window_transform(win)
  halo=math.ceil(300/min(rec['pixel_m']))+3;errs=[]
  for row,col in [(756,756),(1524,1524),(2292,756),(3060,1524),(3828,2292)]:
   height=min(32,dst.height-row);width=min(32,dst.width-col)
   if min(height,width)<=0:continue
   tw=Window(col,row,width,height);rw=Window(win.col_off+col-halo,win.row_off+row-halo,width+2*halo,height+2*halo)
   a=[s.read(1,window=rw,boundless=True,masked=True).astype('float64').filled(np.nan) for s in [v,h,l]];wm=mask.read(2,window=Window(col,row,width+2*halo,height+2*halo)).astype(bool)
   expected=calculate(*a,wm,rec['pixel_m'])[:,halo:halo+height,halo:halo+width];inside=rasterize([(mapping(area),1)],out_shape=(height,width),transform=dst.window_transform(tw),dtype='uint8')>0;expected[:,~inside]=np.nan;actual=dst.read(window=tw)
   assert np.allclose(actual,expected,atol=3e-4,equal_nan=True),rec['scene'];diff=np.abs(actual-expected);vals=diff[np.isfinite(diff)];errs.append(float(vals.max()) if len(vals) else 0)
  assert rec['counts']['lee_vv_signed_contrast_150m_db']['valid']>0
  assert rec['counts']['vv_patch60_signed_db']['negative']>0 and rec['counts']['vv_patch60_signed_db']['positive']>0
  checks.append(dict(scene=rec['scene'],native_grid_preserved=True,tile_join_recalculation=True,max_error=max(errs),both_signs_present=True,area_pixels=rec['area_pixels'],original_vv_valid=rec['counts']['original_vv_db']['valid'],lee_supported=rec['counts']['lee_vv_signed_contrast_150m_db']['valid'],patch60_supported=rec['counts']['vv_patch60_signed_db']['valid'],agreement_supported=rec['counts']['vv_vh_agreement_60m']['valid']))
(ROOT/'raster_checks.json').write_text(json.dumps(checks,indent=2));print(json.dumps(checks,indent=2))
