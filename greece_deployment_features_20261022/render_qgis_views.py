import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
from qgis.core import QgsApplication,QgsProject,QgsMapSettings,QgsMapRendererParallelJob
from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QColor
p=Path(r'D:\Masters\greece_deployment_features_20261022');app=QgsApplication([],False);app.initQgis()
for year in [2021,2024]:
 project=QgsProject();assert project.read(str(p/f'Greece_{year}_feature_analysis.qgz'))
 settings=QgsMapSettings();settings.setDestinationCrs(project.crs());layers=project.layerTreeRoot().checkedLayers();settings.setLayers(layers);settings.setExtent(project.viewSettings().defaultViewExtent());settings.setOutputSize(QSize(1100,850));settings.setBackgroundColor(QColor('white'))
 job=QgsMapRendererParallelJob(settings);job.start();job.waitForFinished();assert job.renderedImage().save(str(p/'plots'/f'QGIS_{year}_default_view.png'))
 print(year,'visible layers',[x.name() for x in layers],flush=True)

