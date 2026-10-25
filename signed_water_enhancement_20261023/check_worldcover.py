import os
for k in ['PROJ_LIB','PROJ_DATA','GDAL_DATA']:os.environ.pop(k,None)
os.environ['GDAL_DISABLE_READDIR_ON_OPEN']='EMPTY_DIR';os.environ['CPL_VSIL_CURL_ALLOWED_EXTENSIONS']='.tif'
import rasterio,numpy as np
from rasterio.windows import from_bounds
url='https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N39E024_Map.tif'
with rasterio.open(url) as s:
 a=s.read(1,window=from_bounds(26.5215,39.0374,26.5275,39.0411,s.transform));print(s.crs,s.res,np.unique(a,return_counts=True));print('Target class',list(s.sample([(26.5245,39.0393)])))
