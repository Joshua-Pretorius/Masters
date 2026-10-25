import os
for k in ['PROJ_LIB','PROJ_DATA','GDAL_DATA']:os.environ.pop(k,None)
from pathlib import Path
import json,re,hashlib
import fiona,rasterio
from shapely.geometry import shape,mapping
from shapely.ops import transform as transform_geom
from pyproj import Transformer
ROOT=Path(r'D:\Masters\sar_roughness_features_20261023');BASE=Path(r'D:\Joshua')
for name in ['data','environment','rasters','models','plots','scripts']:(ROOT/name).mkdir(exist_ok=True)
FEATURES=['vv','vh','vv_refined_lee','vv_refined_lee_db','vv_glcm_mean','vv_glcm_std','vv_glcm_entropy','decomp_entropy','decomp_anisotropy','decomp_alpha']
manifest_map={}
for m in BASE.rglob('*_slc_manifest.json'):
 if 'backup' in str(m).lower():continue
 d=json.loads(m.read_text());out=d.get('outputs',{}); paths={f:m.parent/Path(out.get(f,'missing')).name for f in FEATURES}
 if not paths['vv'].exists() or not paths['vh'].exists():continue
 manifest_map.setdefault(d.get('scene_id',m.stem),[]).append((m,d,paths))
entries=json.loads((ROOT/'annotation_inventory.json').read_text());entries.sort(key=lambda x:(not x['path'].startswith(r'D:\Joshua\New'),x['path']))
labels=[];excluded=[];dedup={};scenes={};duplicates=[]
for entry in entries:
 with fiona.open(entry['path'],layer=entry['layer']) as src:
  convert=Transformer.from_crs(src.crs,4326,always_xy=True).transform
  for feature in src:
   prop=dict(feature['properties']); label=str(prop.get('Class') or '').lower(); original_sid=prop.get('scene_id',''); utc=prop.get('sar_utc','');sid=re.sub('[^0-9T]','',str(utc).replace('Z',''))
   if not label or label=='uncertain' or not feature['geometry']:
    excluded.append({'path':entry['path'],'fid':feature.id,'reason':'Unlabelled or uncertain polygon excluded from fitting'});continue
   if label not in ['plastic','open_ocean','calm_water','ship','wake','slick','other']:continue
   g=transform_geom(convert,shape(feature['geometry']))
   if not g.is_valid:g=g.buffer(0)
   if g.is_empty:continue
   key=(sid,label,hashlib.sha256(g.wkb).hexdigest())
   if key in dedup:
    duplicates.append({'path':entry['path'],'fid':feature.id,'kept':dedup[key]});continue
   dedup[key]=entry['path']
   match=manifest_map.get(original_sid,[])
   special=None
   if not match and sid=='20160716T214630':
    folder=Path(r'D:\Masters\MARIDA\downloads\51PTS\2016-07-17\SAR_-4.5h'); vv=folder/'S1_51PTS_20160716T214643_vv.tif';vh=folder/'S1_51PTS_20160716T214643_vh.tif'
    if vv.exists() and vh.exists():special={'vv':str(vv),'vh':str(vh)}
   if not match and not special:
    excluded.append({'path':entry['path'],'fid':feature.id,'scene':sid,'class':label,'reason':'No matching local VV/VH source covering this annotation scene'});continue
   if match:
    manifest,meta,paths=sorted(match,key=lambda x:(not str(x[0]).startswith(r'D:\Joshua\New'),str(x[0])))[0]
    sources={f:str(v) for f,v in paths.items() if v.exists()}; processing='native_SLC';granule=meta.get('slc',{}).get('granule','');source_manifest=str(manifest)
   else:
    sources=special;processing='legacy_calibrated_orthorectified_VV_VH';granule=original_sid.split('_Global_')[0].replace('S1_S1','S1',1);source_manifest=''
   if sid not in scenes:
    if '51PTS' in original_sid or sid=='20160716T214630':location='Manila';event='Manila_2016'
    elif '18QYF' in original_sid or sid in ['20200915T230129','20210123T104729']:location='Haiti';event='Haiti_'+sid[:8]
    elif sid=='20180830T114533':location='Honduras';event='Honduras_2018'
    elif sid=='20180420T175048':location='Scotland';event='Scotland_2018'
    elif sid=='20191124T105634':location='Vietnam';event='Vietnam_2019'
    else:location='site_'+sid;event=location
    scenes[sid]={'scene':sid,'location':location,'event':event,'acquisition_utc':utc,'granule':granule,'processing':processing,'sources':sources,'source_manifest':source_manifest}
   oid=sid+'_'+str(prop.get('feature_uuid') or feature.id)
   # Stable distinction between known controlled footprints and candidate digitised plastic labels.
   labels.append({'type':'Feature','geometry':mapping(g),'properties':{'scene':sid,'object_id':oid,'class_name':label,'label_group':'plastic' if label=='plastic' else 'water' if label in ['calm_water','open_ocean'] else 'distractor','controlled':False,'confidence':prop.get('feature_confidence') or prop.get('confidence') or 'not_assessed','training_status':prop.get('training_status') or 'candidate','source':entry['path'],'source_fid':str(feature.id)}})
# Controlled deployments and the supplied Greek water polygons retain the original native sources.
old=json.loads(Path(r'D:\Masters\greece_deployment_features_20261022\data\scene_inventory.json').read_text())
old_labels=json.loads(Path(r'D:\Masters\greece_deployment_features_20261022\data\label_polygons.geojson').read_text())['features']
for record in old:
 sid=record['scene'];year=record['year'];manifest=json.loads(Path(record['source_manifest']).read_text());scenes[sid]={'scene':sid,'location':'Greece','event':'Greece_'+str(year),'acquisition_utc':record['acquisition'],'granule':manifest['slc']['granule'],'processing':'native_SLC','sources':dict(zip(FEATURES,record['source_rasters'])),'source_manifest':record['source_manifest']}
 for f in old_labels:
  if f['properties']['year']!=year:continue
  sourceprop=f['properties'];controlled=sourceprop['label']=='deployment';props={'scene':sid,'object_id':sid+'_'+sourceprop['object_id'],'class_name':'controlled_plastic' if controlled else 'water','label_group':'plastic' if controlled else 'water','controlled':controlled,'confidence':'known_deployment' if controlled else 'user_water','training_status':'known_deployment' if controlled else 'user_background','source':record['source_polygon'] if controlled else record['water_polygon'],'source_fid':sourceprop['object_id']}
  labels.append({'type':'Feature','geometry':f['geometry'],'properties':props})
# Document scene locations from labels, and test each geometry against the actual raster footprint.
for sid,record in scenes.items():
 gs=[shape(f['geometry']) for f in labels if f['properties']['scene']==sid];positive=[shape(f['geometry']) for f in labels if f['properties']['scene']==sid and f['properties']['label_group']=='plastic'];geoms=positive or gs
 record['longitude']=sum(g.centroid.x for g in geoms)/len(geoms);record['latitude']=sum(g.centroid.y for g in geoms)/len(geoms)
 record['n_polygons']={label:sum(f['properties']['scene']==sid and f['properties']['label_group']==label for f in labels) for label in ['plastic','water','distractor']}
 with rasterio.open(record['sources']['vv']) as src:record['native_crs']=str(src.crs);record['native_shape']=list(src.shape)
(ROOT/'data/source_scenes.json').write_text(json.dumps(sorted(scenes.values(),key=lambda r:r['scene']),indent=2))
(ROOT/'data/source_labels.geojson').write_text(json.dumps({'type':'FeatureCollection','features':labels}))
(ROOT/'data/excluded_sources.json').write_text(json.dumps(excluded,indent=2));(ROOT/'data/duplicate_sources.json').write_text(json.dumps(duplicates,indent=2))
print('Scenes',len(scenes),'label polygons',len(labels),'duplicate copies',len(duplicates))
for sid,r in sorted(scenes.items()):print(sid,r['location'],r['processing'],r['n_polygons'])
print('Excluded plastic polygons',sum(e.get('class')=='plastic' for e in excluded))
