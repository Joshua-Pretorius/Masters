"""Collect only Sentinel-1 annotation/calibration XMLs from products already available to you.
Example: python collect_noise_metadata.py --product-root /data/raw/slc/_shared_slc_zips --output ./sentinel1_noise_metadata
This script does not download imagery or connect to a server. Run it where the original ZIPs/SAFEs exist.
"""
from pathlib import Path
import argparse,csv,zipfile,json
p=argparse.ArgumentParser();p.add_argument('--product-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--requests',type=Path,default=Path(__file__).with_name('metadata_requests.csv'));args=p.parse_args()
with args.requests.open(encoding='utf-8-sig') as f:records=list(csv.DictReader(f))
root=args.product_root.resolve();args.output.mkdir(parents=True,exist_ok=True);inventory=[]
for rec in records:
 granule=rec['granule'];matches=list(root.rglob(granule+'.zip'))+list(root.rglob(granule+'.SAFE.zip'));safe=list(root.rglob(granule+'.SAFE'));copied=[]
 def wanted(name):
  n=name.replace('\\','/');return n.endswith('/manifest.safe') or ('/annotation/' in n and n.lower().endswith('.xml'))
 if matches:
  with zipfile.ZipFile(matches[0]) as archive:
   for item in archive.infolist():
    if not wanted(item.filename):continue
    rel=Path(*Path(item.filename.replace('\\','/')).parts[1:]);target=(args.output/granule/rel).resolve();base=(args.output/granule).resolve()
    if not target.is_relative_to(base):raise ValueError('Unsafe archive path')
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(archive.read(item));copied.append(str(target))
 elif safe:
  import shutil
  for file in safe[0].rglob('*'):
   if file.is_file() and wanted('/'+str(file.relative_to(safe[0])).replace('\\','/')):
    target=args.output/granule/file.relative_to(safe[0]);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,target);copied.append(str(target))
 inventory.append({'scene':rec['scene'],'granule':granule,'n_files':len(copied),'files':copied,'status':'collected' if copied else 'product_not_found'})
 print(rec['scene'],len(copied),'metadata files')
(args.output/'collection_inventory.json').write_text(json.dumps(inventory,indent=2))
