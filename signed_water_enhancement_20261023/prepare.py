import os,json,re,math
from pathlib import Path
for k in ['PROJ_LIB','PROJ_DATA','GDAL_DATA']:os.environ.pop(k,None)
import fiona,rasterio
from shapely.geometry import shape,box,mapping
from shapely.ops import transform,unary_union
from pyproj import Transformer
ROOT=Path(r'D:\Masters\signed_water_enhancement_20261023')
j=json.loads((ROOT/'inventory.json').read_text())
lookup={p.name:str(p) for p in Path(r'D:\Joshua').rglob('*_slc_native_vv.tif')}
old=json.loads(Path(r'D:\Masters\sar_roughness_features_20261023\data\source_scenes.json').read_text())
legacy={s['scene']:s['sources']['vv'] for s in old}
jobs=[];missing=[]
for p in j['projects']:
 batch=Path(p['path']).parent.name
 vv=[l for l in p['layers'] if l['path'].endswith('_slc_native_vv.tif')]
 known={l['path'] for l in vv}
 for src in j['sources']:
  if Path(p['path']).parents[2] in Path(src['path']).parents and src['path'] not in known:
   vv.append(dict(path=src['path'],exists=True));known.add(src['path'])
 for l in vv:
  sid=re.search(r'(\d{8}T\d{6})',Path(l['path']).name).group(1)
  source=l['path'] if l['exists'] else lookup.get(Path(l['path']).name,legacy.get(sid))
  if not source or not Path(source).exists():missing.append(dict(project=p['path'],scene=sid,reason='Matching calibrated SAR source missing locally'));continue
  geometries=[];context=[];seen=set()
  for v in p['layers']:
   if v['type']!='vector' or not v['exists']:continue
   other=re.search(r'scene_(\d{8}T\d{6})',v['path'])
   if other and other.group(1)!=sid:continue
   layer=v['source'].split('layername=')[-1].split('|')[0] if 'layername=' in v['source'] else None
   key=(v['path'],layer)
   if key in seen:continue
   seen.add(key)
   try:
    with fiona.open(v['path'],layer=layer) as f:
     if not f.crs:continue
     tr=Transformer.from_crs(f.crs,4326,always_xy=True).transform
     for feat in f:
      if not feat['geometry']:continue
      prop=dict(feat['properties']);kind=str(prop.get('ref_kind',''))
      if kind=='aoi_proxy' or 'context only' in str(prop.get('notes','')).lower():
       context.append(transform(tr,shape(feat['geometry'])));continue
      geometries.append(transform(tr,shape(feat['geometry'])))
   except Exception as e:print('vector issue',v['name'],str(e)[:100])
  context_fallback=not geometries and bool(context)
  if context_fallback:geometries=[unary_union(context).envelope]
  if not geometries:
   missing.append(dict(project=p['path'],scene=sid,reason='No observation/search geometry; only context AOI markers'));continue
  lat=unary_union(geometries).centroid.y;dx=1000/(111320*math.cos(math.radians(lat)));dy=1000/110574
  areas=unary_union([box(g.bounds[0]-dx,g.bounds[1]-dy,g.bounds[2]+dx,g.bounds[3]+dy) for g in geometries])
  for repeat in range(3):
   parts=list(areas.geoms) if hasattr(areas,'geoms') else [areas]
   areas=unary_union([box(*g.bounds) for g in parts])
  parts=list(areas.geoms) if hasattr(areas,'geoms') else [areas]
  with rasterio.open(source) as r:
   tr=Transformer.from_crs(4326,r.crs,always_xy=True).transform
   windows=[]
   for g in parts:
    b=transform(tr,g).intersection(box(*r.bounds))
    if b.is_empty:continue
    w=rasterio.windows.from_bounds(*b.bounds,transform=r.transform)
    c=max(0,math.floor(w.col_off));row=max(0,math.floor(w.row_off));right=min(r.width,math.ceil(w.col_off+w.width));bottom=min(r.height,math.ceil(w.row_off+w.height))
    if right>c and bottom>row:windows.append([c,row,right-c,bottom-row])
  vh=source.replace('_vv.tif','_vh.tif')
  out=Path(p['path']).parent/'water_relative_enhancement_v1'/sid
  jobs.append(dict(project=p['path'],batch=batch,scene=sid,vv=source,vh=vh if Path(vh).exists() else None,windows=windows,output=str(out),recovered_source=not l['exists'],context_fallback=context_fallback))
(ROOT/'jobs.json').write_text(json.dumps(jobs,indent=2));(ROOT/'missing.json').write_text(json.dumps(missing,indent=2))
for j in jobs:print(j['batch'],j['scene'],'patches',len(j['windows']),'MP',round(sum(w[2]*w[3] for w in j['windows'])/1e6,2),'recovered',j['recovered_source'])
print('TOTAL',len(jobs),'scenes',len({j['project'] for j in jobs}),'projects',round(sum(w[2]*w[3] for j in jobs for w in j['windows'])/1e6,1),'MP; excluded',len(missing))

