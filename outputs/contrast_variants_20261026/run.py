"""Local experimental post-contrast filters; not calibrated speckle correction."""
import os
for k in ('PROJ_LIB','PROJ_DATA','GDAL_DATA'): os.environ.pop(k,None)
os.environ['GDAL_CACHEMAX']='128'
from pathlib import Path
import json, time, sys
import numpy as np
from scipy.ndimage import median_filter, minimum_filter, uniform_filter, gaussian_filter
import rasterio
from rasterio.windows import Window
from rasterio.enums import Resampling
from concurrent.futures import ProcessPoolExecutor

ROOT=Path(__file__).resolve().parent
LABELS=['Median 3x3','Median 5x5','Gaussian sigma 1 px - baseline','Sign support 3x3 - 5 of 9','Sign support 5x5 - 13 of 25','Multiscale persistence - sigma 1 and 2 px']
INPUTS=['Refined Lee VV contrast','VV 30 m patch contrast','VH 30 m patch contrast','VV 60 m patch contrast']
METHOD={
 'domain':'Already-computed signed contrast in dB; post-contrast display experiment, not a SAR noise calibration.',
 'median':'Median of 3x3 or 5x5 window; output only where entire window is valid.',
 'gaussian':'Normalized masked Gaussian sigma=1 pixel, truncate=3; requires >=90% valid kernel weight and valid center.',
 'support':'Retain original contrast only when center exceeds +0.5 dB and >=5/9 (or 13/25) cells exceed +0.5 dB, or symmetric negative rule. Otherwise zero. Entire window must be valid. Counts include center.',
 'persistence':'Normalized Gaussian at sigma1 and sigma2, truncate3. Retain sigma1 value if original, sigma1 and sigma2 have same sign and both smoothed magnitudes >=0.5 dB; otherwise zero. Both kernels >=90% valid weight, original center valid.',
 'mask':'No filling original NoData. Median/support additionally erode boundaries. Zero means suppressed or neutral, not NoData.',
 'interpretation':'Thresholds are exploratory, not estimated false-alarm rates. Spatially correlated input patches are not independent samples. Small debris can be suppressed; noise can survive. Both signs retained. VH electronic noise reliability unassessed.',
 'display':'Fixed blue/white/red -6/0/+6 dB for all views. No new target fitting.',
}

def filters(a):
 valid=np.isfinite(a); x=np.where(valid,a,0).astype('float32')
 all3=minimum_filter(valid,size=3,mode='constant',cval=0)
 all5=minimum_filter(valid,size=5,mode='constant',cval=0)
 m3=np.where(all3,median_filter(x,size=3,mode='constant'),np.nan)
 m5=np.where(all5,median_filter(x,size=5,mode='constant'),np.nan)
 smooth=[]; masks=[]
 for sigma in (1,2):
  w=gaussian_filter(valid.astype('float32'),sigma,truncate=3,mode='constant')
  y=gaussian_filter(x,sigma,truncate=3,mode='constant')/np.maximum(w,1e-8)
  masks.append(valid & (w>=0.9)); smooth.append(y)
 supported=[]
 for size,count,mask in ((3,5,all3),(5,13,all5)):
  p=uniform_filter((x>0.5).astype('float32'),size,mode='constant')*size*size
  n=uniform_filter((x< -0.5).astype('float32'),size,mode='constant')*size*size
  keep=((x>0.5)&(p>=count-0.01))|((x< -0.5)&(n>=count-0.01))
  supported.append(np.where(mask,np.where(keep,x,0),np.nan))
 keep=(x*smooth[0]>0)&(smooth[0]*smooth[1]>0)&(np.abs(smooth[0])>=0.5)&(np.abs(smooth[1])>=0.5)
 persistence=np.where(masks[0]&masks[1],np.where(keep,smooth[0],0),np.nan)
 return [m3,m5,np.where(masks[0],smooth[0],np.nan),*supported,persistence]

def tests():
 rng=np.random.default_rng(90111); a=rng.normal(0,0.4,(80,90)).astype('float32'); a[0:3]=np.nan
 for p,n in zip(filters(a),filters(-a)): np.testing.assert_allclose(p,-n,atol=1e-6,equal_nan=True)
 for p in filters(a): assert np.isnan(p[0:3]).all()
 whole=filters(a); tile=filters(a[14:56,24:66])
 for p,q in zip(whole,tile): np.testing.assert_allclose(p[20:50,30:60],q[6:-6,6:-6],atol=1e-6,equal_nan=True)
 a=np.zeros((61,61),dtype='float32'); a[30,30]=4
 result=filters(a)
 for i in (0,1,3,4,5): assert result[i][30,30]==0
 a[25:36,25:36]=2
 for p in filters(a): assert p[30,30]>1.9
 (ROOT/'tests.json').write_text(json.dumps({'sign_symmetry':'pass','nodata':'pass','tile_halo':'pass','isolated_impulse_suppression':'pass','coherent_patch_retention':'pass'},indent=2))

def generate(entry):
 path=Path(entry['path']); dest=path.parent.parent/'contrast_variants_20261026'; dest.mkdir(exist_ok=True)
 output=dest/'contrast_variants.tif'; done=dest/'methods.json'
 if done.exists() and output.exists(): return json.loads(done.read_text())
 start=time.time(); scene=path.parent.parent.name
 counts=np.zeros(24,dtype='int64'); positive=counts.copy(); negative=counts.copy(); zeros=counts.copy()
 with rasterio.open(path) as src:
  profile=src.profile.copy(); profile.update(count=24,dtype='float32',nodata=np.nan,compress='deflate',predictor=3,zlevel=1,tiled=True,blockxsize=256,blockysize=256,BIGTIFF='YES',interleave='band',NUM_THREADS='2')
  temp=dest/'contrast_variants.partial.tif'
  with rasterio.open(temp,'w',**profile) as dst:
   for band in range(24): dst.set_band_description(band+1,INPUTS[band//6]+' | '+LABELS[band%6])
   total=((src.height+511)//512)*((src.width+511)//512); n=0
   for row in range(0,src.height,512):
    for col in range(0,src.width,512):
     h=min(512,src.height-row); w=min(512,src.width-col)
     arr=src.read(window=Window(col-6,row-6,w+12,h+12),boundless=True,fill_value=np.nan)
     out=np.full((24,h,w),np.nan,dtype='float32')
     if np.isfinite(arr).any():
      for b in range(4):
       if np.isfinite(arr[b]).any():
        for j,value in enumerate(filters(arr[b])): out[b*6+j]=value[6:6+h,6:6+w]
     counts+=np.isfinite(out).sum(axis=(1,2)); positive+=(out>0).sum(axis=(1,2)); negative+=(out<0).sum(axis=(1,2)); zeros+=(out==0).sum(axis=(1,2))
     dst.write(out,window=Window(col,row,w,h)); n+=1
     if n%40==0:
      status={'scene':scene,'tiles':n,'total':total,'percent':round(n/total*100,1),'seconds':round(time.time()-start)}
      (ROOT/(scene+'_progress.json')).write_text(json.dumps(status)); print(status,flush=True)
   dst.update_tags(experiment='contrast_variants_20261026',source=str(path),method=json.dumps(METHOD))
   print(scene+' building overviews',flush=True)
   dst.build_overviews([2,4,8,16],Resampling.average)
  os.replace(temp,output)
  with rasterio.open(output) as check:
   assert check.count==24 and check.transform==src.transform and check.crs==src.crs
   assert (check.width,check.height)==(src.width,src.height)
   for b in range(1,25): assert check.overviews(b)==[2,4,8,16]
 assert (positive>0).all() and (negative>0).all()
 result={'status':'complete','scene':scene,'path':str(output),'source':str(path),'projects':entry['projects'],'methods':METHOD,'inputs':INPUTS,'variants':LABELS,'valid_counts':counts.tolist(),'positive_counts':positive.tolist(),'negative_counts':negative.tolist(),'zero_counts':zeros.tolist(),'seconds':round(time.time()-start),'bytes':output.stat().st_size}
 done.write_text(json.dumps(result,indent=2)); print(scene+' COMPLETE',flush=True); return result

if __name__=='__main__':
 tests()
 entries=[e for e in json.loads(Path(r'D:\Masters\outputs\water_contrast_20261025\results.json').read_text()) if 'marida_16pec_20190111_03' in e.get('path','')]
 if '--test' in sys.argv: print('All tests passed'); sys.exit()
 with ProcessPoolExecutor(max_workers=2) as pool: results=list(pool.map(generate,entries))
 (ROOT/'results.json').write_text(json.dumps(results,indent=2))
