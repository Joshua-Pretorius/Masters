"""Back up and add experimental layers to this batch's existing projects."""
import os, json, hashlib, shutil, datetime, sys
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
from qgis.core import QgsApplication,QgsProject,QgsRasterLayer,QgsColorRampShader,QgsRasterShader,QgsSingleBandPseudoColorRenderer
from qgis.PyQt.QtGui import QColor
ROOT=Path(__file__).resolve().parent
GROUP='Experimental contrast denoising | 2026-10-26'
app=QgsApplication([],False); app.initQgis()
results=json.loads((ROOT/'results.json').read_text())
projects=sorted({p for r in results for p in r['projects']})
report=[]
for filename in projects:
 path=Path(filename); original_hash=hashlib.sha256(path.read_bytes()).hexdigest()
 project=QgsProject(); assert project.read(str(path)); root=project.layerTreeRoot()
 if any(g.name()==GROUP for g in root.findGroups(True)): raise RuntimeError('Already installed: '+filename)
 original={k:(l.source(),l.isValid(),root.findLayer(k).itemVisibilityChecked()) for k,l in project.mapLayers().items() if root.findLayer(k)}
 old_order=list(root.layerOrder()); insertion={}; added=[]
 for group in list(root.findGroups(True)):
  if group.name()!='SAR rasters': continue
  sources={os.path.normcase(n.layer().source().split('|')[0]) for n in group.findLayers() if n.layer()}
  match=[r for r in results if os.path.normcase(r['source']) in sources]
  if not match: continue
  assert len(match)==1; result=match[0]
  anchor=next(n.layerId() for n in group.findLayers() if n.layer())
  experiment=group.addGroup(GROUP); scene_layers=[]
  for b,input_name in enumerate(result['inputs']):
   subgroup=experiment.addGroup(input_name)
   for j,label in enumerate(result['variants']):
    band=b*6+j+1; options=QgsRasterLayer.LayerOptions(); options.loadDefaultStyle=False
    layer=QgsRasterLayer(result['path'],label+' | '+input_name,'gdal',options); assert layer.isValid()
    ramp=QgsColorRampShader(-6,6); ramp.setColorRampType(QgsColorRampShader.Interpolated); ramp.setClip(False)
    ramp.setColorRampItemList([QgsColorRampShader.ColorRampItem(v,QColor(c),str(v)) for v,c in [(-6,'#2166ac'),(0,'#f7f7f7'),(6,'#b2182b')]])
    shader=QgsRasterShader(-6,6); shader.setRasterShaderFunction(ramp)
    renderer=QgsSingleBandPseudoColorRenderer(layer.dataProvider(),band,shader); renderer.setClassificationMin(-6); renderer.setClassificationMax(6); layer.setRenderer(renderer)
    layer.setCustomProperty('contrast_variants/version','20261026')
    md=layer.metadata(); md.setAbstract(json.dumps(result['methods'],indent=2)); layer.setMetadata(md)
    project.addMapLayer(layer,False); node=subgroup.addLayer(layer); node.setItemVisibilityChecked(False); node.setExpanded(False)
    scene_layers.append(layer); added.append(layer)
   subgroup.setExpanded(False)
  experiment.setExpanded(True); insertion[anchor]=scene_layers
 assert added,filename
 order=[]
 for l in old_order: order.extend(insertion.get(l.id(),[])); order.append(l)
 root.setHasCustomLayerOrder(True); root.setCustomLayerOrder(order)
 staged=path.with_name(path.stem+'.denoise_staged.qgz'); assert project.write(str(staged))
 verify=QgsProject(); assert verify.read(str(staged))
 for key,(source,valid,visible) in original.items():
  l=verify.mapLayer(key); assert l and l.source()==source
  assert not valid or l.isValid()
  assert verify.layerTreeRoot().findLayer(key).itemVisibilityChecked()==visible
 for l in added:
  v=verify.mapLayer(l.id()); assert v.isValid() and v.renderer().inputBand()==l.renderer().inputBand()
 assert hashlib.sha256(path.read_bytes()).hexdigest()==original_hash,'Project changed concurrently'
 backup=path.with_name(path.stem+'.before_contrast_variants_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'.qgz')
 shutil.copy2(path,backup); os.replace(staged,path)
 report.append({'project':filename,'backup':str(backup),'added_layers':len(added),'original_layers_preserved':len(original),'verified':True})
 print(report[-1],flush=True); verify.clear(); project.clear()
(ROOT/'project_checks.json').write_text(json.dumps(report,indent=2))
