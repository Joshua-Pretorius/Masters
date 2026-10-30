import os,json
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
from qgis.core import QgsApplication,QgsProject,QgsMapSettings,QgsMapRendererParallelJob,QgsRectangle
from qgis.PyQt.QtCore import QSize
ROOT=Path(__file__).resolve().parent
app=QgsApplication([],False); app.initQgis()
p=QgsProject(); assert p.read(json.loads((ROOT/'inventory.json').read_text())[0]['project'])
layers=[l for l in p.mapLayers().values() if l.customProperty('water_contrast/version')=='water_contrast_v1']; assert len(layers)==8
checks=json.loads((ROOT/'raster_checks.json').read_text())
for l in layers:
 x,y=next(c['render_center'] for c in checks if os.path.normcase(c['path'])==os.path.normcase(l.source()))
 settings=QgsMapSettings(); settings.setLayers([l]); settings.setDestinationCrs(l.crs()); settings.setExtent(QgsRectangle(x-.01,y-.01,x+.01,y+.01)); settings.setOutputSize(QSize(400,400))
 job=QgsMapRendererParallelJob(settings); job.start(); job.waitForFinished(); assert not job.errors()
 im=job.renderedImage(); colors={im.pixelColor(i,j).name() for i in range(0,400,5) for j in range(0,400,5)}; assert len(colors)>10
 filename=Path(l.source()).parent.parent.name+'_band_'+str(l.renderer().inputBand())+'.png'; assert im.save(str(ROOT/filename))
print('All eight saved-project layers rendered successfully')
