import os,json
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
from qgis.core import QgsApplication,QgsProject,QgsMapSettings,QgsMapRendererParallelJob,QgsRectangle
from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QColor
ROOT=Path(r'D:\Masters\signed_water_enhancement_20261023');app=QgsApplication([],False);app.initQgis();checks=[]
for entry in json.loads((ROOT/'project_checks.json').read_text()):
 p=QgsProject();assert p.read(entry['project']);group=p.layerTreeRoot().findGroup('Signed water-relative SAR | fixed v1');assert group
 candidates=[n.layer() for n in group.findLayers() if n.layer().name()=='VV 150 m: signed contrast (dB)'];assert candidates
 layer=candidates[0];extent=layer.extent()
 if Path(entry['project']).parent.name.startswith('floating_greece'):extent=QgsRectangle(26.5215,39.0374,26.5275,39.0411)
 settings=QgsMapSettings();settings.setLayers([layer]);settings.setDestinationCrs(layer.crs());settings.setExtent(extent);settings.setOutputSize(QSize(1000,700));settings.setBackgroundColor(QColor('#dddfe2'))
 job=QgsMapRendererParallelJob(settings);job.start();job.waitForFinished();errors=[e.message for e in job.errors()];assert not errors,errors
 image=job.renderedImage();dest=ROOT/'qgis_previews'/(Path(entry['project']).parent.name+'.png');dest.parent.mkdir(exist_ok=True);assert image.save(str(dest))
 checks.append(dict(project=entry['project'],render=str(dest),errors=errors));print('Rendered',Path(entry['project']).parent.name,flush=True)
(ROOT/'render_checks.json').write_text(json.dumps(checks,indent=2))
