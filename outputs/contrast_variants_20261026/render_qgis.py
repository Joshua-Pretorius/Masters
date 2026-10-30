import os,json
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
from qgis.core import QgsApplication,QgsProject,QgsMapSettings,QgsMapRendererParallelJob,QgsRectangle
from qgis.PyQt.QtCore import QSize
ROOT=Path(__file__).resolve().parent
app=QgsApplication([],False); app.initQgis()
checks=json.loads((ROOT/'project_checks.json').read_text())
previews=json.loads((ROOT/'preview_metrics.json').read_text())
project=QgsProject(); assert project.read(next(c['project'] for c in checks if c['project'].endswith('batch.qgz')))
for scene in sorted({p['scene'] for p in previews}):
 lon,lat=next(p['crop_center'] for p in previews if p['scene']==scene)
 layers=[l for l in project.mapLayers().values() if l.customProperty('contrast_variants/version')=='20261026' and scene in l.source() and l.renderer().inputBand() in (1,24)]
 assert len(layers)==2
 for layer in layers:
  settings=QgsMapSettings(); settings.setLayers([layer]); settings.setDestinationCrs(layer.crs()); settings.setExtent(QgsRectangle(lon-0.016,lat-0.016,lon+0.016,lat+0.016)); settings.setOutputSize(QSize(512,512))
  job=QgsMapRendererParallelJob(settings); job.start(); job.waitForFinished(); im=job.renderedImage(); assert not im.isNull()
  colors={im.pixelColor(x,y).name() for x in range(0,512,8) for y in range(0,512,8)}; assert len(colors)>10
  name=scene+'_qgis_band_'+str(layer.renderer().inputBand())+'.png'; assert im.save(str(ROOT/name)); print(name,flush=True)
