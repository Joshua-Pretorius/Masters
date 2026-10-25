import os,math,json
from pathlib import Path
import numpy as np,rasterio
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
from rasterio.windows import Window
from rasterio.warp import transform_bounds
from scipy.ndimage import distance_transform_edt
os.environ['GDAL_DISABLE_READDIR_ON_OPEN']='EMPTY_DIR';os.environ['CPL_VSIL_CURL_ALLOWED_EXTENSIONS']='.tif';os.environ['GDAL_HTTP_MAX_RETRY']='3';os.environ['GDAL_HTTP_RETRY_DELAY']='2'
def get_water_mask(src,win,halo,pixel_m,path):
 if path.exists():
  with rasterio.open(path) as f:return f.read(2).astype(bool),f.transform
 extended=Window(win.col_off-halo,win.row_off-halo,win.width+2*halo,win.height+2*halo);t=src.window_transform(extended);h,w=int(extended.height),int(extended.width)
 bounds=rasterio.transform.array_bounds(h,w,t);west,south,east,north=transform_bounds(src.crs,'EPSG:4326',*bounds)
 classes=np.zeros((h,w),'uint8');urls=[]
 for lat in range(math.floor(south/3)*3,math.floor(north/3)*3+1,3):
  for lon in range(math.floor(west/3)*3,math.floor(east/3)*3+1,3):
   tile=f'{"N" if lat>=0 else "S"}{abs(lat):02d}{"E" if lon>=0 else "W"}{abs(lon):03d}'
   url=f'https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif';urls.append(url)
   with rasterio.open(url) as world:
    with WarpedVRT(world,crs=src.crs,transform=t,width=w,height=h,resampling=Resampling.nearest,nodata=0) as warped:a=warped.read(1)
   classes[a!=0]=a[a!=0]
 water=classes==80;distance=distance_transform_edt(np.pad(water,1),sampling=(pixel_m[1],pixel_m[0]))[1:-1,1:-1];safe=water&(distance>30)
 with rasterio.open(path,'w',driver='GTiff',width=w,height=h,count=2,dtype='uint8',crs=src.crs,transform=t,compress='deflate',tiled=True) as f:
  f.write(classes,1);f.write(safe.astype('uint8'),2);f.set_band_description(1,'WorldCover_2021_v200_class_nearest');f.set_band_description(2,'water_class80_with_30m_land_unknown_margin');f.update_tags(source_urls=json.dumps(urls),license='CC BY 4.0',citation='ESA WorldCover 10 m 2021 v200 doi:10.5281/zenodo.7254221',method='Nearest neighbour alignment of categorical ancillary mask only; SAR unchanged')
 return safe,t
