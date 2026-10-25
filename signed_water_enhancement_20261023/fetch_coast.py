from pathlib import Path
import requests,zipfile,hashlib
p=Path(r'D:\Masters\signed_water_enhancement_20261023\coastline');p.mkdir(exist_ok=True)
zp=p/'gshhg-shp-2.3.7.zip'
if not zp.exists():
 with requests.get('https://github.com/GenericMappingTools/gshhg-gmt/releases/download/2.3.7/gshhg-shp-2.3.7.zip',stream=True,timeout=60) as r:
  r.raise_for_status()
  with zp.open('wb') as f:
   for b in r.iter_content(1024*1024):f.write(b)
assert hashlib.sha256(zp.read_bytes()).hexdigest()=='8dbbe7e071e77e9e75f2d639239099ebca8d5c16d6a07df8169729d49f15cf41'
with zipfile.ZipFile(zp) as z:
 for n in z.namelist():
  if n.startswith('GSHHS_shp/f/GSHHS_f_L1.') or n.endswith('README.TXT') or 'LICENSE' in n.upper():z.extract(n,p)
print('Coastline download verified',zp.stat().st_size)
