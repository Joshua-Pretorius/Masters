import os,json,hashlib
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
from qgis.core import QgsApplication,QgsProject,QgsMapLayerType
ROOT=Path(r'D:\Masters\signed_water_enhancement_20261023');app=QgsApplication([],False);app.initQgis();checks=json.loads((ROOT/'project_checks.json').read_text())
for rec in checks:
 path=Path(rec['project']);before=hashlib.sha256(path.read_bytes()).hexdigest();p=QgsProject();assert p.read(str(path));root=p.layerTreeRoot();old=root.layerOrder();newgroup=root.findGroup('Signed water-relative SAR | fixed v1');new=[n.layer() for n in newgroup.findLayers()];ids={l.id() for l in new};original=[l for l in old if l.id() not in ids];vectors=[l for l in original if l.type()==QgsMapLayerType.VectorLayer];other=[l for l in original if l.type()!=QgsMapLayerType.VectorLayer]
 root.setHasCustomLayerOrder(True);root.setCustomLayerOrder(vectors+new+other)
 stage=path.with_name('batch.signed_order_staged.qgz');assert p.write(str(stage));q=QgsProject();assert q.read(str(stage));assert all(q.mapLayer(l.id()).isValid() for l in new)
 assert hashlib.sha256(path.read_bytes()).hexdigest()==before,'Concurrent project edit';os.replace(stage,path);rec['new_sha256']=hashlib.sha256(path.read_bytes()).hexdigest();rec['annotation_overlays_above_enhancements']=True
 print('Overlay order verified',path.parent.name,flush=True)
(ROOT/'project_checks.json').write_text(json.dumps(checks,indent=2))
