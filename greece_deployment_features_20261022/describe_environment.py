from pathlib import Path
import copernicusmarine as cm, json
p=Path(r'D:\Masters\greece_deployment_features_20261022\environment')
for product in ['MEDSEA_MULTIYEAR_PHY_006_004','MEDSEA_MULTIYEAR_WAV_006_012','MEDSEA_MULTIYEAR_BGC_006_008']:
    result=cm.describe(product_id=product,disable_progress_bar=True)
    data=result.model_dump(mode='json'); (p/(product+'_catalogue.json')).write_text(json.dumps(data,indent=2))
    for prod in data['products']:
        for ds in prod['datasets']:
            print(product,ds['dataset_id'],flush=True)
