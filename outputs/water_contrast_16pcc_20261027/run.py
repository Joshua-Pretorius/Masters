import os,sys,json,logging,traceback
from pathlib import Path
for key in ('PROJ_LIB','PROJ_DATA','GDAL_DATA'):os.environ.pop(key,None)
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'sar_server_pipeline'))
import rasterio
from digitising.water_contrast import generate,coverage,VERSION
ROOT=Path(__file__).resolve().parent
logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s')
def worker(item):
 key,job=item
 try:result=generate(job['sources'],job['points'],Path(key).parent/VERSION)
 except Exception as exc:
  traceback.print_exc();result=dict(status='error',error=str(exc))
 result.update(source=key,projects=job['projects'])
 print('SCENE RESULT',Path(key).parent.name,result['status'],result.get('valid_counts'),flush=True)
 return result

if __name__=='__main__':
 records=json.loads((ROOT/'inventory.json').read_text());jobs={}
 for project in records:
  for group in project['groups']:
   if 'vv' not in group['sources']:continue
   key=str(Path(group['sources']['vv']).resolve())
   job=jobs.setdefault(key,dict(sources=group['sources'],points=set(),projects=[]))
   job['points'].update(map(tuple,group['points']));job['projects'].append(project['project'])
 plan=[]
 for key,job in jobs.items():
  job['points']=sorted(job['points']);entry=dict(source=key,point_count=len(job['points']),projects=job['projects'])
  if not all(Path(v).exists() for v in job['sources'].values()):entry['status']='missing_inputs'
  else:
   with rasterio.open(key) as src:
    area,win,points=coverage(src,job['points'])
    entry.update(status='ready' if win else 'no_on_image_points',on_image_points=len(points),window=list(win.flatten()) if win else None,pixels=int(win.width*win.height) if win else 0)
  plan.append(entry)
 (ROOT/'plan.json').write_text(json.dumps(plan,indent=2))
 print('PLAN',[(Path(x['source']).parent.name,x['status'],x.get('pixels')) for x in plan],flush=True)
 if '--plan' in sys.argv:sys.exit()
 from concurrent.futures import ProcessPoolExecutor,as_completed
 results=[]
 with ProcessPoolExecutor(max_workers=4) as pool:
  futures=[pool.submit(worker,item) for item in jobs.items()]
  for future in as_completed(futures):
   results.append(future.result())
   (ROOT/'results.json').write_text(json.dumps(results,indent=2))
