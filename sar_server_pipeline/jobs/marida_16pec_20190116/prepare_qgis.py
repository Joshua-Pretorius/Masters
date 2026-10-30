import os,sys,json,logging
from pathlib import Path
job=Path(__file__).resolve().parent
sys.path.insert(0,str(job/'qgis_deps'))
sys.path.insert(0,str(job.parents[1]))
os.environ['QT_QPA_PLATFORM']='offscreen'
os.environ.pop('PROJ_LIB',None)
os.environ.pop('PROJ_DATA',None)
from digitising.workflow import Environment,prepare_batch
from digitising.meria_batches import BATCH_BY_NAME,task_ids_for_batch
from qgis.core import QgsApplication
import rasterio,fiona
if '--check' in sys.argv:
 from qgis.core import QgsCoordinateReferenceSystem
 assert QgsCoordinateReferenceSystem('EPSG:4326').isValid()
 assert rasterio.crs.CRS.from_epsg(4326).to_epsg()==4326
 print('QGIS, rasterio, Fiona, CRS databases and batch workflow imports OK');sys.exit(0)
logging.basicConfig(level=logging.INFO)
meta=json.loads((job/'batch.json').read_text());data=Path(meta['local_data_root']);batch=BATCH_BY_NAME[meta['batch']]
env=Environment(data,Path('D:/Masters/Data_Creation'),Path('D:/Masters/Domain_SSL/Scripts/Preprocessing'),'local',str(data),str(data),job/'unused_cmems',job/'unused_cds')
ids=task_ids_for_batch(batch,env.catalog_root,env.processed_root)
result=prepare_batch(env,dataset='global',limit=2,batch_name=batch.name,task_ids=ids,prediction_mode='skip',grouping='scene')
assert len(result.selected)==2, result
project=data/'digitising_batches'/batch.name/'batch.qgz'
assert project.is_file()
(project.parent/'README.txt').write_text('Local January 16 follow-up to marida_16pec_20190111_03.\nOpen batch.qgz and review both Scene annotations layers.\nJanuary 12 optical points are historical context, not confirmed January 16 labels.\nNo remote transfer or drift prediction was performed.\n')
(job/'qgis_result.json').write_text(json.dumps({'status':'ready','project':str(project),'scenes':list(result.selected)},indent=2))
print('QGIS batch ready:',project)


# Deliver the portable batch only after processing and project preparation pass.
import shutil
from qgis.core import QgsProject
parent=Path('D:/Joshua/New').resolve()
destination=parent/batch.name
staging=parent/(batch.name+'.preparing')
assert destination.parent==parent and staging.parent==parent
if destination.exists():
 raise RuntimeError(f'Destination already exists; refusing to overwrite possible annotations: {destination}')
parent.mkdir(parents=True,exist_ok=True)
transfer=project.parent/'transfer_files.txt'
relatives=set(line.strip() for line in transfer.read_text().splitlines() if line.strip())
# Always include the control files even if the transfer list was written first.
for item in project.parent.iterdir():
 if item.is_file():relatives.add(item.relative_to(data).as_posix())
files=[]
for relative in sorted(relatives):
 source=(data/relative).resolve()
 if not source.is_relative_to(data.resolve()) or not source.is_file():
  raise RuntimeError(f'Invalid or missing batch transfer source: {relative}')
 files.append((source,Path(relative)))
required=sum(source.stat().st_size for source,_ in files)
if shutil.disk_usage(parent).free < required+10*1024**3:
 raise RuntimeError(f'Not enough free space to deliver the portable batch ({required} bytes plus 10 GiB reserve)')
if staging.exists():
 raise RuntimeError(f'Previous delivery staging exists; inspect before retrying: {staging}')
staging.mkdir()
(job/'delivery_status.json').write_text(json.dumps({'status':'copying','destination':str(destination),'files':len(files),'bytes':required},indent=2))
for source,relative in files:
 target=staging/relative
 target.parent.mkdir(parents=True,exist_ok=True)
 shutil.copy2(source,target)
 if target.stat().st_size!=source.stat().st_size:raise RuntimeError(f'Copy size mismatch: {relative}')
portable=staging/project.relative_to(data)
check=QgsProject()
if not check.read(str(portable)):raise RuntimeError('Cannot reopen delivered QGIS project')
invalid=[layer.name() for layer in check.mapLayers().values() if not layer.isValid()]
if invalid:raise RuntimeError(f'Delivered QGIS layers are invalid: {invalid}')
check.clear()
staging.rename(destination)
final_project=destination/project.relative_to(data)
(job/'qgis_result.json').write_text(json.dumps({'status':'ready','project':str(final_project),'source_project':str(project),'scenes':list(result.selected),'delivery_files':len(files)},indent=2))
(job/'delivery_status.json').write_text(json.dumps({'status':'complete','destination':str(destination),'project':str(final_project),'files':len(files),'bytes':required,'qgis_layers_verified':True},indent=2))
print('Delivered and verified QGIS batch:',final_project)
