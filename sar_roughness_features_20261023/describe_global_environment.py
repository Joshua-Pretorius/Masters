from pathlib import Path
import json,copernicusmarine as cm
root=Path(r'D:\Masters\sar_roughness_features_20261023\environment')
for product in ['GLOBAL_MULTIYEAR_PHY_001_030','GLOBAL_MULTIYEAR_WAV_001_032','GLOBAL_MULTIYEAR_BGC_001_029']:
 p=root/(product+'_catalogue.json')
 if not p.exists():p.write_text(json.dumps(cm.describe(product_id=product,disable_progress_bar=True).model_dump(mode='json'),indent=2))
 for prod in json.loads(p.read_text())['products']:
  for ds in prod['datasets']:
   if any(x in ds['dataset_id'] for x in ['P1D','PT3H','PT1H']):
    print(ds['dataset_id'],[(v['short_name'],v.get('units')) for v in ds['versions'][0]['parts'][0]['services'][0]['variables']],flush=True)
