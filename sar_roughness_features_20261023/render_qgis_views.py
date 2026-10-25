import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
import json
from qgis.core import QgsApplication,QgsProject,QgsMapSettings,QgsMapRendererParallelJob
from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QColor
root=Path(r'D:\Masters\sar_roughness_features_20261023');app=QgsApplication([],False);app.initQgis();checks=[]
for name in ['All_locations','Greece_2021','Greece_2024']:
 p=QgsProject();assert p.read(str(root/f'{name}_roughness_analysis.qgz'));layers=p.layerTreeRoot().checkedLayers();settings=QgsMapSettings();settings.setDestinationCrs(p.crs());settings.setLayers(layers);settings.setExtent(p.viewSettings().defaultViewExtent());settings.setOutputSize(QSize(1100,850));settings.setBackgroundColor(QColor('white'));job=QgsMapRendererParallelJob(settings);job.start();job.waitForFinished();file=root/'plots'/f'{name}_QGIS_default.png';assert job.renderedImage().save(str(file));checks.append({'project':name,'visible_layers':[l.name() for l in layers],'rendered_preview':str(file)});print(name,[l.name() for l in layers],flush=True)
(root/'data/render_verification.json').write_text(json.dumps(checks,indent=2))
