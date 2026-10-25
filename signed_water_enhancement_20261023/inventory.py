import os,json,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
for k in ['PROJ_LIB','PROJ_DATA','GDAL_DATA']:os.environ.pop(k,None)
import rasterio
root=Path(r'D:\Joshua\New'); out=Path(r'D:\Masters\signed_water_enhancement_20261023')
projects=[]
for p in root.rglob('batch.qgz'):
 if any('backup' in s.lower() for s in p.parts):continue
 with zipfile.ZipFile(p) as z:
  x=ET.fromstring(z.read(next(n for n in z.namelist() if n.endswith('.qgs'))))
 layers=[]
 for l in x.findall('./projectlayers/maplayer'):
  s=l.findtext('datasource',''); raw=s.split('|')[0]; path=Path(raw) if Path(raw).is_absolute() else (p.parent/raw).resolve()
  layers.append(dict(name=l.findtext('layername'),source=s,path=str(path),exists=path.exists(),type=l.get('type')))
 projects.append(dict(path=str(p),layers=layers))
sources=[]
for p in root.rglob('*_slc_native_vv.tif'):
 with rasterio.open(p) as r:sources.append(dict(path=str(p),shape=list(r.shape),crs=str(r.crs),res=list(r.res),bounds=list(r.bounds),nodata=r.nodata))
(out/'inventory.json').write_text(json.dumps(dict(projects=projects,sources=sources),indent=2))
print('PROJECTS',len(projects),'SOURCES',len(sources),'PIXELS',sum(s['shape'][0]*s['shape'][1] for s in sources))
for p in projects:
 vv=[l for l in p['layers'] if l['path'].endswith('_slc_native_vv.tif')]
 print(Path(p['path']).parent.name, 'layers',len(p['layers']),'VV',len(vv),'available',sum(l['exists'] for l in vv))
print('RASTERS',[(Path(s['path']).parent.name,s['shape']) for s in sources])
