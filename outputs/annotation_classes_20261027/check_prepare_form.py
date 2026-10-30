import os,ast,json
from pathlib import Path
from types import SimpleNamespace
os.environ['QT_QPA_PLATFORM']='offscreen'
from qgis.core import QgsApplication,QgsVectorLayer,QgsField
from qgis.PyQt.QtCore import QVariant
root=Path(r'D:\Masters\sar_server_pipeline\digitising')
namespace={'DigitisingTask':object}
tree=ast.parse((root/'geopackage.py').read_text())
for node in tree.body:
 if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('CLASSES','CONFIDENCE_LEVELS','TRAINING_STATUSES') for t in node.targets):
  exec(compile(ast.Module(body=[node],type_ignores=[]),'constants','exec'),namespace)
tree=ast.parse((root/'project.py').read_text())
for node in tree.body:
 if isinstance(node,ast.FunctionDef) and node.name in ('_qgis','_configure_annotations'):
  exec(compile(ast.Module(body=[node],type_ignores=[]),'project_functions','exec'),namespace)
app=QgsApplication([],False);app.initQgis()
layer=QgsVectorLayer('MultiPolygon?crs=EPSG:4326','prepare smoke','memory')
layer.dataProvider().addAttributes([QgsField(n,QVariant.String) for n in ('Class','feature_confidence','correspondence_confidence','training_status')]);layer.updateFields()
task=SimpleNamespace(task_id='test',observation_id='obs',dataset='global',role='before',scene=SimpleNamespace(scene_id='scene'),area='test',optical_time_representative='2020-01-01',sar_time='2020-01-01',delta_hours=0)
namespace['_configure_annotations'](layer,task,namespace['_qgis']())
values={v for entry in layer.editorWidgetSetup(0).config()['map'] for v in entry.values()}
categories={c.value() for c in layer.renderer().categories()}
assert values==categories==set(namespace['CLASSES'])
assert {'reef','rain'}<=values
print('Future prepare form and renderer: all 10 classes verified')
Path(__file__).with_name('prepare_form_check.json').write_text(json.dumps({'class_choices':sorted(values),'renderer_categories':sorted(categories),'status':'passed'},indent=2))
