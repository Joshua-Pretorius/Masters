import os
for k in ['PROJ_LIB','PROJ_DATA','GDAL_DATA']:os.environ.pop(k,None)
from pathlib import Path
import json,math,time,warnings
import numpy as np,rasterio,fiona
from rasterio.windows import Window
from rasterio.features import rasterize
from rasterio.enums import Resampling
from shapely.geometry import shape,box,mapping
from shapely.ops import transform
from pyproj import Transformer,Geod
from scipy.ndimage import uniform_filter
ROOT=Path(r'D:\Masters\signed_water_enhancement_20261023')
CONFIG={'version':'1.0','scales_m':[{'outer_half_width':150,'guard_half_width':50},{'outer_half_width':500,'guard_half_width':150}], 'minimum_water_support':0.70,'minimum_water_cells':30,'spread_floor_db':1.0,'coast_buffer_m':30,'coverage_buffer_m':1000,'display_delta_db':[-6,6],'display_standardized':[-3,3], 'background':'arithmetic mean and population SD of dB values in mapped-water rectangular annulus','input':'unsmoothed positive calibrated linear sigma0 converted with 10log10','land_mask':'GSHHG 2.3.7 full-resolution L1; mapped ocean proxy, inland water excluded','label_use':'coverage only; no fitting, threshold tuning or target-class exclusion','sign':'positive brighter; negative darker; no absolute value or clipping of raster data'}
NAMES=[f'{scale}_{name}' for scale in ['150m','500m'] for name in ['signed_delta_db','signed_standardized','background_mean_db','background_sd_db','water_support_fraction']]+['original_sigma0_db']
def ring_sum(a,outer,inner):
 return uniform_filter(a.astype('float64'),size=outer,mode='constant',cval=0)*np.prod(outer)-uniform_filter(a.astype('float64'),size=inner,mode='constant',cval=0)*np.prod(inner)
def derive(db,water,windows):
 vals=np.where(water,db,0).astype('float64');out=[]
 for outer,inner in windows:
  cells=np.prod(outer)-np.prod(inner);n=np.maximum(ring_sum(water,outer,inner),0);support=np.clip(n/cells,0,1)
  mu=np.divide(ring_sum(vals,outer,inner),n,out=np.full(db.shape,np.nan),where=n>.1)
  second=np.divide(ring_sum(vals*vals,outer,inner),n,out=np.full(db.shape,np.nan),where=n>.1)
  sd=np.sqrt(np.maximum(second-mu*mu,0));delta=db-mu;z=delta/np.maximum(sd,CONFIG['spread_floor_db'])
  enough=water&(support>=CONFIG['minimum_water_support']-1e-10)&(n>=CONFIG['minimum_water_cells'])
  for a in [delta,z,mu,sd]:out.append(np.where(enough,a,np.nan).astype('float32'))
  out.append(np.where(np.isfinite(db),support,np.nan).astype('float32'))
 out.append(db.astype('float32'))
 return np.stack(out)
def metric_windows(src,win):
 lon,lat=Transformer.from_crs(src.crs,4326,always_xy=True).transform(*(src.transform*(win.col_off+win.width/2,win.row_off+win.height/2)))
 if src.crs.is_geographic:
  g=Geod(ellps='WGS84');dx=g.inv(lon,lat,lon+abs(src.res[0]),lat)[2];dy=g.inv(lon,lat,lon,lat+abs(src.res[1]))[2]
 else:dx,dy=map(abs,src.res)
 windows=[]
 for scale in CONFIG['scales_m']:
  size=lambda m:(2*max(1,round(m/dy))+1,2*max(1,round(m/dx))+1)
  windows.append((size(scale['outer_half_width']),size(scale['guard_half_width'])))
 return windows,(dx,dy)
def land_shapes(src,win,halo):
 t=src.window_transform(Window(win.col_off-halo,win.row_off-halo,win.width+2*halo,win.height+2*halo));bb=rasterio.transform.array_bounds(int(win.height+2*halo),int(win.width+2*halo),t)
 togeo=Transformer.from_crs(src.crs,4326,always_xy=True).transform;bounds=transform(togeo,box(*bb)).bounds
 west,south,east,north=bounds;lon=(west+east)/2;lat=(south+north)/2;utm=(32600 if lat>=0 else 32700)+min(60,int((lon+180)//6)+1)
 tom=Transformer.from_crs(4326,utm,always_xy=True).transform;back=Transformer.from_crs(utm,src.crs,always_xy=True).transform
 clip=box(west-.01,south-.01,east+.01,north+.01);shapes=[]
 with fiona.open(ROOT/'coastline/GSHHS_shp/f/GSHHS_f_L1.shp') as coast:
  for f in coast.filter(bbox=clip.bounds):
   g=shape(f['geometry'])
   if not g.is_valid:g=g.buffer(0)
   g=g.intersection(clip)
   if not g.is_empty:shapes.append(mapping(transform(back,transform(tom,g).buffer(CONFIG['coast_buffer_m']))))
 return shapes

def process(job):
 started=time.time();out=Path(job['output']);out.mkdir(parents=True,exist_ok=True);records=[]
 for number,ws in enumerate(job['windows'],1):
  win=Window(*ws)
  for pol in ['vv','vh']:
   if not job.get(pol):continue
   dest=out/f'patch_{number:02d}_{pol}_signed_water.tif';meta=dest.with_suffix('.json')
   if dest.exists() and meta.exists():records.append(json.loads(meta.read_text()));continue
   with rasterio.open(job[pol]) as src:
    windows,pixel_m=metric_windows(src,win);halo=max(max(w[0])//2 for w in windows)+2;land=land_shapes(src,win,halo)
    profile=dict(driver='GTiff',width=int(win.width),height=int(win.height),count=11,dtype='float32',crs=src.crs,transform=src.window_transform(win),nodata=np.nan,tiled=True,blockxsize=256,blockysize=256,compress='deflate',predictor=3,BIGTIFF='IF_SAFER')
    stats=[dict(n=0,negative=0,positive=0,min=None,max=None) for _ in NAMES]
    with rasterio.open(dest,'w',**profile) as dst:
     dst.update_tags(method=json.dumps(CONFIG),source=job[pol],scene=job['scene'],windows_pixels=json.dumps(windows),pixel_size_m=json.dumps(pixel_m))
     for band,name in enumerate(NAMES,1):dst.set_band_description(band,name)
     for row in range(0,int(win.height),512):
      for col in range(0,int(win.width),512):
       h=min(512,int(win.height)-row);w=min(512,int(win.width)-col)
       readwin=Window(win.col_off+col-halo,win.row_off+row-halo,w+2*halo,h+2*halo)
       a=src.read(1,window=readwin,boundless=True,masked=True).astype('float64').filled(np.nan)
       valid=np.isfinite(a)&(a>0);db=np.full(a.shape,np.nan);db[valid]=10*np.log10(a[valid])
       landmask=rasterize([(g,1) for g in land],out_shape=a.shape,transform=src.window_transform(readwin),dtype='uint8',all_touched=True) if land else np.zeros(a.shape,'uint8')
       cube=derive(db,valid&(landmask==0),windows)[:,halo:halo+h,halo:halo+w]
       dst.write(cube,window=Window(col,row,w,h))
       for b,a in enumerate(cube):
        v=a[np.isfinite(a)];s=stats[b]
        if len(v):
         s['n']+=int(len(v));s['negative']+=int((v<0).sum());s['positive']+=int((v>0).sum());s['min']=min(s['min'] if s['min'] is not None else np.inf,float(v.min()));s['max']=max(s['max'] if s['max'] is not None else -np.inf,float(v.max()))
     dst.build_overviews([2,4,8,16],Resampling.average);dst.update_tags(ns='rio_overview',resampling='average')
    record=dict(path=str(dest),source=job[pol],scene=job['scene'],pol=pol,window=ws,pixel_m=pixel_m,windows_pixels=windows,stats=dict(zip(NAMES,stats)))
    meta.write_text(json.dumps(record,indent=2));records.append(record)
  print(job['batch'],job['scene'],'patch',number,'/',len(job['windows']),'seconds',round(time.time()-started),flush=True)
 return records
if __name__=='__main__':
 (ROOT/'method.json').write_text(json.dumps(CONFIG,indent=2));jobs=json.loads((ROOT/'jobs.json').read_text());records=[]
 for j in jobs:records.extend(process(j));(ROOT/'raster_manifest.json').write_text(json.dumps(records,indent=2))
 print('COMPLETE',len(records),'raster patches',flush=True)
