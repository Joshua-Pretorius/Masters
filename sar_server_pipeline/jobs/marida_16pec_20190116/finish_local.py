import json,time,subprocess,sys,hashlib
from pathlib import Path
import numpy as np,rasterio
job=Path(__file__).resolve().parent;meta=json.loads((job/'batch.json').read_text());data=Path(meta['local_data_root']);marker=data/'manifests'/(meta['batch']+'-local-v1')/'stages/slc_process.json'
def status(state,**more):
 meta.update(status=state,**more);(job/'batch.json').write_text(json.dumps(meta,indent=2))
status('downloading_or_processing')
try:
 while not marker.exists():
  time.sleep(30)
  # A crashed process without a stage marker is a failure, never completion.
  pid=int((job/'process.pid').read_text())
  import ctypes
  from ctypes import wintypes
  kernel=ctypes.WinDLL("kernel32",use_last_error=True)
  kernel.OpenProcess.argtypes=(wintypes.DWORD,wintypes.BOOL,wintypes.DWORD)
  kernel.OpenProcess.restype=wintypes.HANDLE
  kernel.CloseHandle.argtypes=(wintypes.HANDLE,)
  h=kernel.OpenProcess(0x1000,False,pid)
  if not h and not marker.exists():raise RuntimeError('Local processor stopped without a completion marker')
  if h:kernel.CloseHandle(h)
 stage=json.loads(marker.read_text())
 if stage['status']!='success':raise RuntimeError('SLC processing failed; inspect stage marker and local log')
 manifests=list((data/'processed').rglob('*_slc_manifest.json'));assert len(manifests)==2
 checks=[]
 for path in manifests:
  m=json.loads(path.read_text());assert m['status']=='processed'
  grids=[]
  for key,filename in m['outputs'].items():
   if not filename:raise RuntimeError(f'Missing output {key}')
   with rasterio.open(filename) as ds:
    sample=ds.read(1,out_shape=(min(512,ds.height),min(512,ds.width)),masked=True)
    assert sample.count()>0 and np.isfinite(sample.compressed()).any(),f'No valid sampled pixels: {filename}'
    grids.append((str(ds.crs),tuple(ds.transform),ds.width,ds.height))
   checks.append({'product':key,'path':filename,'sampled_valid_pixels':int(sample.count())})
  assert len(set(grids))==1,'Scene product grids do not align'
 (job/'raster_validation.json').write_text(json.dumps(checks,indent=2));status('processed_verified',validated_products=len(checks))
 with (job/'qgis.stdout.log').open('w') as out,(job/'qgis.stderr.log').open('w') as err:
  result=subprocess.run(['C:/Program Files/QGIS 3.40.4/bin/python-qgis-ltr.bat',str(job/'prepare_qgis.py')],stdout=out,stderr=err)
 if result.returncode:raise RuntimeError('SAR outputs verified; QGIS finalization failed, see qgis.stderr.log')
 status('ready_for_digitising',qgis_project=json.loads((job/'qgis_result.json').read_text())['project'])
 with (job/'README.md').open('a') as f:f.write('\n## Completion\nBoth SLC scene manifests report processed. Raster readability, sampled valid data and grid alignment passed. QGIS batch ready; see batch.json and raster_validation.json. Annotation remains pending.\n')
except Exception as exc:
 status('failed_or_needs_attention',error=str(exc));raise
