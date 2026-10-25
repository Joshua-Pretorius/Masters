import os,sys,json,math,time
for k in ['PROJ_LIB','PROJ_DATA','GDAL_DATA']:os.environ.pop(k,None)
sys.path.insert(0,r'D:\Masters\signed_water_enhancement_20261023')
from worldcover_mask import get_water_mask
from enhance import metric_windows,ring_sum
from pathlib import Path
import numpy as np,rasterio,fiona
from rasterio.windows import Window,from_bounds
from rasterio.features import rasterize
from rasterio.enums import Resampling
from scipy.ndimage import uniform_filter
from shapely.geometry import shape,mapping
from shapely.ops import unary_union
ROOT=Path(r'D:\Masters\patch_enhancement_20261023');BASE=Path(r'D:\Joshua\New\Debris_Visible_Not_Done\marida_18qyg_20200305_20200307_01');PROJECT=BASE/'digitising_batches'/BASE.name/'batch.qgz';OUT=PROJECT.parent/'area_patch_enhancement_v1'
NAMES=['lee_vv_signed_contrast_150m_db','lee_vv_standardized_contrast_150m','vv_patch30_signed_db','vv_patch60_signed_db','vv_patch120_signed_db','vh_patch30_signed_db','vh_patch60_signed_db','vh_patch120_signed_db','vv_vh_agreement_60m','channel_support_noise_status','vh_patch60_mean_db','vv_patch60_mean_db','vv_ring300_mean_db','vh_ring300_mean_db','vv_ring300_water_fraction','vh_ring300_water_fraction','lee_ring150_mean_db','lee_ring150_water_fraction','original_vv_db','original_vh_db']
CONFIG=dict(version='1.0',area=str(BASE/'Area.geojson'),filtered='Existing Refined Lee VV dB, central pixel minus mean dB in 150 m half-width ring excluding 50 m guard',patch='10log10(mean linear sigma0 in central water patch / mean linear sigma0 in surrounding water ring)',patch_widths_m=[30,60,120],patch_ring_outer_half_width_m=300,patch_guard_half_width_m=100,ring_min_water_fraction=.7,patch_min_water_fraction=.9,ring_min_cells=30,patch_min_cells=4,water_mask='WorldCover 2021 v200 class80 with 30 m nonwater margin',agreement_deadband_db=1.0,agreement='Nine categories from VV/VH 60 m contrasts: 0 neutral,1 VV bright only,2 VV dark only,3 VH bright only,4 VH dark only,5 both bright,6 both dark,7 VV bright VH dark,8 VV dark VH bright',quality='1 both supported NESZ unassessed;2 VV supported VH unsupported;3 VH supported VV unsupported;4 neither patch supported',sign='All continuous contrasts signed; no absolute-value or clipping',calibration='NESZ absent; no instrument noise reliability claim; class deadband is display convention not detection/significance threshold',display_limits_db=[-6,6])
def total(a,size):return uniform_filter(np.asarray(a,dtype='float64'),size=size,mode='constant',cval=0)*np.prod(size)
def db(a):
 result=np.full(a.shape,np.nan,dtype='float64');m=np.isfinite(a)&(a>0);result[m]=10*np.log10(a[m]);return result

def calculate(v,h,lee,water,px):
 dx,dy=px
 size=lambda half:(2*max(1,round(half/dy))+1,2*max(1,round(half/dx))+1)
 small,sg=size(150),size(50);outer,guard=size(300),size(100);sizes=[size(w/2) for w in CONFIG['patch_widths_m']]
 lv=np.isfinite(lee)&(lee>-9990);lm=lv&water;ln=np.maximum(ring_sum(lm,small,sg),0);lf=np.clip(ln/(np.prod(small)-np.prod(sg)),0,1);safe=np.maximum(ln,1)
 mu=ring_sum(np.where(lm,lee,0),small,sg)/safe;sd=np.sqrt(np.maximum(ring_sum(np.where(lm,lee*lee,0),small,sg)/safe-mu*mu,0));ok=lm&(lf>=.7-1e-9)&(ln>=30)
 ld=np.where(ok,lee-mu,np.nan);lz=ld/np.maximum(sd,1)
 diffs=[];centres=[];means=[];fractions=[]
 for a in [v,h]:
  valid=np.isfinite(a)&(a>0);m=valid&water;count=np.maximum(ring_sum(m,outer,guard),0);fraction=np.clip(count/(np.prod(outer)-np.prod(guard)),0,1);background=ring_sum(np.where(m,a,0),outer,guard)/np.maximum(count,1);supported=(fraction>=.7-1e-9)&(count>=30)&(background>0)
  cd=[];cm=[]
  for sz in sizes:
   cn=np.maximum(total(m,sz),0);mean=total(np.where(m,a,0),sz)/np.maximum(cn,1);good=m&supported&(cn>=4)&(cn/np.prod(sz)>=.9-1e-9)&(mean>0)
   cd.append(np.where(good,db(mean)-db(background),np.nan));cm.append(np.where(good,db(mean),np.nan))
  diffs.append(cd);centres.append(cm);means.append(np.where(m&supported,db(background),np.nan));fractions.append(np.where(valid,fraction,np.nan))
 vd,hd=diffs[0][1],diffs[1][1];vg=np.isfinite(vd);hg=np.isfinite(hd);both=vg&hg
 sv=np.where(vd>1,1,np.where(vd< -1,-1,0));sh=np.where(hd>1,1,np.where(hd< -1,-1,0));agree=np.full(v.shape,np.nan)
 for c,(a,b) in enumerate([(0,0),(1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,-1),(1,-1),(-1,1)]):agree[both&(sv==a)&(sh==b)]=c
 quality=np.where(both,1,np.where(vg,2,np.where(hg,3,4))).astype(float);quality[~((np.isfinite(v)&(v>0))|(np.isfinite(h)&(h>0)))]=np.nan
 return np.stack([ld,lz,*diffs[0],*diffs[1],agree,quality,centres[1][1],centres[0][1],means[0],means[1],fractions[0],fractions[1],np.where(ok,mu,np.nan),np.where(lv,lf,np.nan),db(v),db(h)]).astype('float32')

def run():
 OUT.mkdir(exist_ok=True);(ROOT/'method.json').write_text(json.dumps(CONFIG,indent=2))
 with fiona.open(BASE/'Area.geojson') as f:area=unary_union([shape(x['geometry']) for x in f])
 assert area.is_valid
 records=[]
 for vv in sorted(BASE.rglob('*_slc_native_vv.tif')):
  sid=vv.parent.name.replace('scene_','');vh=Path(str(vv).replace('_vv.tif','_vh.tif'));lee=Path(str(vv).replace('_vv.tif','_vv_refined_lee_db.tif'));dest=OUT/(sid+'_patch_views.tif');meta=dest.with_suffix('.json')
  if dest.exists() and meta.exists():records.append(json.loads(meta.read_text()));continue
  started=time.time()
  with rasterio.open(vv) as vsrc,rasterio.open(vh) as hsrc,rasterio.open(lee) as lsrc:
   assert vsrc.crs==hsrc.crs==lsrc.crs and vsrc.transform==hsrc.transform==lsrc.transform and vsrc.shape==hsrc.shape==lsrc.shape
   assert vsrc.crs.to_epsg()==4326
   w=from_bounds(*area.bounds,vsrc.transform);left=math.floor(w.col_off);top=math.floor(w.row_off);win=Window(left,top,math.ceil(w.col_off+w.width)-left,math.ceil(w.row_off+w.height)-top)
   _,px=metric_windows(vsrc,win);halo=math.ceil(300/min(px))+3;water,t=get_water_mask(vsrc,win,halo,px,OUT/(sid+'_worldcover.tif'))
   profile=dict(driver='GTiff',width=int(win.width),height=int(win.height),count=len(NAMES),dtype='float32',crs=vsrc.crs,transform=vsrc.window_transform(win),nodata=np.nan,tiled=True,blockxsize=256,blockysize=256,compress='deflate',predictor=3,BIGTIFF='IF_SAFER')
   counts=[dict(valid=0,negative=0,positive=0,min=None,max=None) for _ in NAMES];area_count=0
   with rasterio.open(dest,'w',**profile) as dst:
    dst.update_tags(method=json.dumps(CONFIG),vv_source=str(vv),vh_source=str(vh),lee_source=str(lee),native_window=json.dumps(list(win.flatten())),pixel_size_m=json.dumps(px))
    for b,name in enumerate(NAMES,1):dst.set_band_description(b,name)
    for row in range(0,int(win.height),768):
     for col in range(0,int(win.width),768):
      height=min(768,int(win.height)-row);width=min(768,int(win.width)-col);tw=Window(col,row,width,height)
      am=rasterize([(mapping(area),1)],out_shape=(height,width),transform=dst.window_transform(tw),dtype='uint8')>0;area_count+=int(am.sum())
      if not am.any():dst.write(np.full((len(NAMES),height,width),np.nan,'float32'),window=tw);continue
      rw=Window(left+col-halo,top+row-halo,width+2*halo,height+2*halo)
      arrays=[s.read(1,window=rw,boundless=True,masked=True).astype('float64').filled(np.nan) for s in [vsrc,hsrc,lsrc]]
      eligible=water[row:row+height+2*halo,col:col+width+2*halo]
      cube=calculate(*arrays,eligible,px)[:,halo:halo+height,halo:halo+width];cube[:,~am]=np.nan;dst.write(cube,window=tw)
      for b,a in enumerate(cube):
       finite=a[np.isfinite(a)];s=counts[b]
       if len(finite):s['valid']+=len(finite);s['negative']+=int((finite<0).sum());s['positive']+=int((finite>0).sum());s['min']=min(s['min'] if s['min'] is not None else np.inf,float(finite.min()));s['max']=max(s['max'] if s['max'] is not None else -np.inf,float(finite.max()))
     print(sid,'rows',min(row+768,int(win.height)),'/',int(win.height),flush=True)
    # Nearest overviews preserve categorical agreement/status codes; continuous native data unchanged.
    dst.build_overviews([2,4,8,16],Resampling.nearest)
   record=dict(scene=sid,path=str(dest),vv=str(vv),vh=str(vh),lee=str(lee),mask=str(OUT/(sid+'_worldcover.tif')),window=list(win.flatten()),pixel_m=px,area_pixels=area_count,counts=dict(zip(NAMES,counts)))
   meta.write_text(json.dumps(record,indent=2));records.append(record);(ROOT/'manifest.json').write_text(json.dumps(records,indent=2));print('FINISHED',sid,round(time.time()-started),'seconds',flush=True)
 (ROOT/'manifest.json').write_text(json.dumps(records,indent=2))
if __name__=='__main__':run()
