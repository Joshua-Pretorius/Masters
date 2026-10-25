from pathlib import Path
import json,datetime,copernicusmarine as cm
from shapely.geometry import shape
p=Path(r'D:\Masters\sar_roughness_features_20261023');features=json.loads((p/'data/source_labels.geojson').read_text())['features'];sid='20180420T175048';gs=[shape(f['geometry']) for f in features if f['properties']['scene']==sid];left=min(g.bounds[0] for g in gs)-.25;bottom=min(g.bounds[1] for g in gs)-.25;right=max(g.bounds[2] for g in gs)+.25;top=max(g.bounds[3] for g in gs)+.25
for kind,dataset,variables,depth in [('physics','cmems_mod_glo_phy_my_0.083deg_P1D-m',['uo','vo','thetao'],True),('waves','cmems_mod_glo_wav_my_0.2deg_PT3H-i',['VHM0','VTM02','VMDR','VSDX','VSDY'],False),('chlorophyll','cmems_mod_glo_bgc_my_0.25deg_P1D-m',['chl'],True)]:
 filename=f'{sid}_{kind}_expanded.nc'
 if (p/'environment'/filename).exists():continue
 args=dict(dataset_id=dataset,variables=variables,minimum_longitude=left,maximum_longitude=right,minimum_latitude=bottom,maximum_latitude=top,start_datetime='2018-04-20T00:00:00' if depth else '2018-04-20T15:00:00',end_datetime='2018-04-20T23:59:00' if depth else '2018-04-20T18:00:00',output_directory=p/'environment',output_filename=filename,credentials_file=Path.home()/'.copernicusmarine'/'.copernicusmarine-credentials',disable_progress_bar=True,netcdf_compression_level=1)
 if depth:args.update(minimum_depth=1,maximum_depth=1,coordinates_selection_method='nearest')
 cm.subset(**args);print('expanded',kind,flush=True)
