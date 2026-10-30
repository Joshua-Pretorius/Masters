import csv,json,shutil,sys
from pathlib import Path
from datetime import datetime,timezone
import requests,yaml
from shapely.geometry import shape,box
from shapely.ops import unary_union
root=Path('D:/Masters'); inv=root/'Data_Creation/global_s1_slc_inventory'; job=root/'sar_server_pipeline/jobs/marida_16pec_20190116'; batch='marida_16pec_20190116_followup'; data=root/'outputs'/batch
backup=job/'backup'; backup.mkdir(exist_ok=True)
def read(p):
 with p.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def append(p,rows,key):
 old=read(p); existing={r[key] for r in old}; new=[r for r in rows if r[key] not in existing]
 if not new:return
 if not (backup/p.name).exists():shutil.copy2(p,backup/p.name)
 with p.open('a',newline='',encoding='utf-8') as f:csv.DictWriter(f,fieldnames=old[0].keys()).writerows(new)
url='https://api.daac.asf.alaska.edu/services/search/param'
params=dict(platform='Sentinel-1',processingLevel='SLC',bbox='-87.28082151836338,15.483434423638773,-85.86093641026656,16.548161550600565',start='2019-01-16T00:00:00Z',end='2019-01-16T23:59:59Z',output='geojson')
r=requests.get(url,params=params,timeout=90);r.raise_for_status(); cat=r.json(); (job/'asf_catalogue.json').write_text(json.dumps(cat,indent=2)); features=sorted(cat['features'],key=lambda f:f['properties']['startTime'])
assert len(features)==2
obs='marida_16PEC_2019-01-12'; aoi=box(-87.28082151836338,15.483434423638773,-85.86093641026656,16.548161550600565)
coverage=unary_union([shape(f['geometry']) for f in features]).intersection(aoi).area/aoi.area
base=next(r for r in read(inv/'global_s1_slc_associations.csv') if r['obs_id']==obs)
ptemplate=read(inv/'global_s1_slc_processing_targets.csv')[0]; points=read(inv/'global_s1_slc_processing_points.csv'); oldid='S1_S1A_IW_SLC__1SDV_20190111T235822_20190111T235849_025437_02D177_4D98'; coords=[r for r in points if r['obs_id']==oldid]
associations=[]; targets=[]; newpoints=[]
for i,f in enumerate(features,1):
 p=f['properties']; g=p['sceneName']; start=p['startTime']; sid='S1_'+g
 delta=(datetime.fromisoformat(start)-datetime.fromisoformat(base['reference_time'])).total_seconds()/3600
 assoc=dict(base,target_id=f'{obs}:followup:{i:02}',role='followup',selection_rank=str(i),granule_name=g+'.SAFE',acquisition_start=start,delta_h=str(round(delta,6)),scene_coverage_ratio=str(round(shape(f['geometry']).intersection(aoi).area/aoi.area,6)),coverage_set_ratio=str(round(coverage,6)),coverage_complete=str(coverage>=.999),download_group_key=g)
 associations.append(assoc)
 target=dict(ptemplate,target_id=sid+':scene',obs_id=sid,source_group_id=g,date=start[:10],reference_time=start,granule_name=g+'.SAFE',acquisition_start=start,download_group_key=g,association_count='1')
 targets.append(target)
 for j,c in enumerate(coords,1):newpoints.append(dict(c,obs_id=sid,point_id=f'{sid}_P{j:04}'))
append(inv/'global_s1_slc_associations.csv',associations,'target_id');append(inv/'global_s1_slc_processing_targets.csv',targets,'target_id');append(inv/'global_s1_slc_processing_points.csv',newpoints,'point_id')
for name,rows in [('targets.csv',targets),('points.csv',newpoints)]:
 with (job/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
p=inv/'global_s1_slc_job.yaml'; doc=yaml.safe_load(p.read_text()); add=[t['target_id'] for t in targets if t['target_id'] not in doc['targets']]
if add:
 shutil.copy2(p,backup/p.name); text=p.read_text(); text=text.replace('inputs:', ''.join('- '+x+'\n' for x in add)+'inputs:',1);p.write_text(text)
manifest=yaml.safe_load((inv/'global_s1_slc_job.yaml').read_text());manifest['run_id']=batch+'-local-v1';manifest['targets']=[t['target_id'] for t in targets];manifest['inputs'].update(match_csv=str(job/'targets.csv'),points_csv=str(job/'points.csv'),raw_slc_root=str(data/'raw/slc'),shapefiles_root=str(data/'shapefiles'))
for key in manifest['outputs']:manifest['outputs'][key]=str(data/key.replace('_root',''))
manifest['stages']['slc_process'].update(gpt='C:/Program Files/esa-snap/bin/gpt.exe',pad_deg=0,keep_zip=True)
manifest['processing'].update(workers=1,cache_gb=8)
(job/'local_job.yaml').write_text(yaml.safe_dump(manifest,sort_keys=False))
prep=json.loads(json.dumps(manifest));prep['run_id']+='-preflight';prep['stages']['slc_process']['prepare_only']=True;(job/'preflight.yaml').write_text(yaml.safe_dump(prep,sort_keys=False))
registry=root/'sar_server_pipeline/digitising/meria_batches.py';text=registry.read_text()
if batch not in text:
 shutil.copy2(registry,backup/registry.name);text=text.replace('MERIA_BATCHES = (','MERIA_BATCHES = (\n    MeriaBatch("'+batch+'", "global", "16PEC", ("20190116T113714", "20190116T113741")),',1);registry.write_text(text)
summary=dict(batch=batch,parent_batch='marida_16pec_20190111_03',status='prepared',local_data_root=str(data),coverage_set_ratio=coverage,reference_time=base['reference_time'],catalogue_url=r.url,scenes=associations,notes='User-requested follow-up outside the default 72-hour optical window. January 12 optical references retained as historical context; January 16 debris labels require review. Both January 11 source slices considered. No contemporary optical acquisition inferred.')
(job/'batch.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
