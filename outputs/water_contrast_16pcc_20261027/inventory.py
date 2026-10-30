import os,json,sys
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
from qgis.core import QgsApplication,QgsProject,QgsCoordinateReferenceSystem,QgsCoordinateTransform,QgsWkbTypes
app=QgsApplication([],False);app.initQgis()
root=Path(r'D:\Joshua\New\marida_16pcc_20200924_08');records=[]
for path in sorted(root.rglob('*.qgz')):
 if path.name not in ('batch.qgz','scene.qgz','task.qgz'):continue
 p=QgsProject();assert p.read(str(path))
 groups=[]
 for group in p.layerTreeRoot().findGroups(True):
  if group.name()!='SAR rasters':continue
  parent=group.parent();sources={}
  for node in group.findLayers():
   layer=node.layer()
   if not layer:continue
   src=layer.source().split('|')[0]
   for key,suffix in [('vv','_slc_native_vv.tif'),('vh','_slc_native_vh.tif'),('vv_refined_lee_db','_slc_native_vv_refined_lee_db.tif')]:
    if src.endswith(suffix):sources[key]=src
  pts=[];point_sources=[]
  nodes=list(parent.findLayers())
  nodes+= [n for n in p.layerTreeRoot().findLayers() if n.layer() and 'controlled' in n.layer().name().lower()]
  for node in nodes:
   layer=node.layer()
   if not layer or not layer.isValid() or layer.type()!=0:continue
   if layer.geometryType()!=QgsWkbTypes.PointGeometry and 'controlled' not in layer.name().lower():continue
   trans=QgsCoordinateTransform(layer.crs(),QgsCoordinateReferenceSystem('EPSG:4326'),p)
   n=0
   for f in layer.getFeatures():
    g=f.geometry()
    if g.isEmpty():continue
    g.transform(trans)
    for point in g.vertices():pts.append([point.x(),point.y()]);n+=1
   if n:point_sources.append({'name':layer.name(),'count':n,'source':layer.source()})
  groups.append({'parent':parent.name(),'sources':sources,'points':sorted(set(map(tuple,pts))),'point_sources':point_sources})
 records.append({'project':str(path),'groups':groups,'invalid':[{'name':l.name(),'source':l.source()} for l in p.mapLayers().values() if not l.isValid()]})
 p.clear()
 print(path.name,path.parent.name,[(len(g['points']),{k:Path(v).exists() for k,v in g['sources'].items()}) for g in groups],flush=True)
Path(r'D:\Masters\outputs\water_contrast_16pcc_20261027\inventory.json').write_text(json.dumps(records,indent=2))


