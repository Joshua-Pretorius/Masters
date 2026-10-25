import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
import csv,json
from qgis.core import QgsApplication,QgsProject,QgsRasterLayer,QgsVectorLayer,QgsColorRampShader,QgsRasterShader,QgsSingleBandPseudoColorRenderer,QgsSingleBandGrayRenderer,QgsContrastEnhancement,QgsFillSymbol,QgsCoordinateReferenceSystem,QgsRectangle,QgsReferencedRectangle,QgsMultiBandColorRenderer,Qgis
from qgis.PyQt.QtGui import QColor
ROOT=Path(r'D:\Masters\greece_deployment_features_20261022')
app=QgsApplication([],False); app.initQgis()
scenes=sorted(json.loads((ROOT/'data/scene_inventory.json').read_text()),key=lambda s:s['scene'])
with (ROOT/'data/derived_raster_index.csv').open() as f: index=list(csv.DictReader(f))
with (ROOT/'environment/environment_layer_index.csv').open() as f: envindex=list(csv.DictReader(f))

def style(layer,band,lo,hi,gray=False):
 if hi<=lo: hi=lo+1
 if gray:
  renderer=QgsSingleBandGrayRenderer(layer.dataProvider(),band); ce=QgsContrastEnhancement(layer.dataProvider().dataType(band)); ce.setMinimumValue(lo);ce.setMaximumValue(hi);ce.setContrastEnhancementAlgorithm(QgsContrastEnhancement.StretchToMinimumMaximum);renderer.setContrastEnhancement(ce)
 else:
  ramp=QgsColorRampShader();ramp.setColorRampType(QgsColorRampShader.Interpolated)
  colors=['#2166ac','#f7f7f7','#b2182b']; vals=[lo,(lo+hi)/2,hi]
  ramp.setColorRampItemList([QgsColorRampShader.ColorRampItem(v,QColor(c),f'{v:.2f}') for v,c in zip(vals,colors)])
  shader=QgsRasterShader();shader.setRasterShaderFunction(ramp);renderer=QgsSingleBandPseudoColorRenderer(layer.dataProvider(),band,shader)
 layer.setRenderer(renderer)

def raster(project,group,path,name,band,lo,hi,gray=False,visible=False):
 layer=QgsRasterLayer(str(path),name)
 if not layer.isValid(): raise ValueError('Invalid '+str(path))
 style(layer,band,lo,hi,gray);project.addMapLayer(layer,False);node=group.addLayer(layer);node.setItemVisibilityChecked(visible);node.setExpanded(False)
 metadata=layer.metadata();metadata.setAbstract('Known deployment feature analysis. Scores are visualization aids, not calibrated plastic probabilities. See REPORT.html. Native SAR grid retained; environment is regional context.');layer.setMetadata(metadata)
 return layer
checks=[]
for year in [2021,2024]:
 project=QgsProject(); project.setCrs(QgsCoordinateReferenceSystem('EPSG:4326'));project.setTitle(f'Greece {year} - deployment feature analysis')
 root=project.layerTreeRoot(); year_scenes=[s for s in scenes if s['year']==year]
 labelgroup=root.addGroup('Known deployment footprints and sample cells')
 source=str(ROOT/'data/analysis_labels.gpkg')+'|layername=deployments'; layer=QgsVectorLayer(source,f'Controlled deployments {year}','ogr'); layer.setSubsetString(f'"year" = {year}')
 symbol=QgsFillSymbol.createSimple({'color':'0,0,0,0','outline_color':'255,210,0,255','outline_width':'0.45','style':'no'})
 layer.renderer().setSymbol(symbol);project.addMapLayer(layer,False);labelgroup.addLayer(layer)
 water=QgsVectorLayer(str(ROOT/'data/analysis_labels.gpkg')+'|layername=water','Supplied water polygons (2021 locations reused in 2024)','ogr');water.renderer().setSymbol(QgsFillSymbol.createSimple({'color':'0,0,0,0','outline_color':'0,200,230,255','outline_width':'0.35','style':'no'}));project.addMapLayer(water,False);labelgroup.addLayer(water)
 samples=QgsVectorLayer(str(ROOT/'data/sampled_SAR_pixels.gpkg')+'|layername=sar_pixels','Extracted pixel values - attribute table','ogr');samples.setSubsetString(f'"year" = {year}');project.addMapLayer(samples,False);labelgroup.addLayer(samples).setItemVisibilityChecked(False)
 for k,scene in enumerate(year_scenes):
  sid=scene['scene']; group=root.addGroup(f'{sid[:4]}-{sid[4:6]}-{sid[6:8]} {sid[9:11]}:{sid[11:13]} UTC');group.setExpanded(k==0)
  derived=group.addGroup('Derived SAR views - toggle one layer at a time')
  entries=[x for x in index if x['scene']==sid]
  # Place the trained-in-scene view first, explicitly named. Held-out maps are directly below it.
  order=[4,5,6,7,1,2,3,8,9,10,11]
  last=[int(x['band']) for x in entries if 'held_out_scene_environment' in x['name']]; order=order[:2]+last+order[2:]
  for band in order:
   entry=next(x for x in entries if int(x['band'])==band)
   name=entry['name'].replace('_',' ')
   lo,hi=float(entry['p02']),float(entry['p98'])
   if 'logistic' in name or 'LDA' in name or 'robust z' in name:lo,hi=-4,4
   if 'ring contrast' in name:lo,hi=-4,4
   raster(project,derived,entry['path'],name,band,lo,hi,visible=(band==4 and k==0))
  rgb=QgsRasterLayer(str(ROOT/'rasters'/f'{sid}_derived_features.tif'),'PCA RGB | PC1 red, PC2 green, PC3 blue')
  renderer=QgsMultiBandColorRenderer(rgb.dataProvider(),1,2,3)
  for band,setter in [(1,renderer.setRedContrastEnhancement),(2,renderer.setGreenContrastEnhancement),(3,renderer.setBlueContrastEnhancement)]:
   entry=next(x for x in entries if int(x['band'])==band)
   ce=QgsContrastEnhancement(rgb.dataProvider().dataType(band));ce.setMinimumValue(float(entry['p02']));ce.setMaximumValue(float(entry['p98']));ce.setContrastEnhancementAlgorithm(QgsContrastEnhancement.StretchToMinimumMaximum);setter(ce)
  rgb.setRenderer(renderer);project.addMapLayer(rgb,False);derived.addLayer(rgb).setItemVisibilityChecked(False)
  calibrated=ROOT/'rasters'/f'{sid}_water_calibrated_held_out.tif'
  if calibrated.exists(): raster(project,derived,calibrated,'Held-out hyperplane after independent water calibration',1,-4,4)
  interactions=group.addGroup('SAR x environmental interaction indices - exploratory')
  for entry in entries:
   if entry['name'].startswith('interaction_'):
    raster(project,interactions,entry['path'],entry['name'].replace('interaction_','').replace('_x_',' x '),int(entry['band']),float(entry['p02']),float(entry['p98']))
  interactions.setExpanded(False)
  original=group.addGroup('Original SAR features - cropped, no resampling')
  raw_names=['VV linear','VH linear','VV Refined Lee linear','VV Refined Lee dB','GLCM mean (quantized)','GLCM std (quantized)','GLCM entropy (stored units)','Dual-pol entropy H','Dual-pol anisotropy A','Dual-pol alpha degrees']
  ranges=[(.001,.05),(.0001,.005),(.001,.05),(-30,-10),(5,40),(3,25),(1,8),(0,1),(0,1),(0,60)]
  for i,(name,(lo,hi)) in enumerate(zip(raw_names,ranges)): raster(project,original,scene['raw_crop'],name,i+1,lo,hi,True)
  original.setExpanded(False)
  envgroup=group.addGroup('Regional environment - native 4 km grids; coastal gaps preserved')
  for entry in envindex:
   if entry['scene']==sid: raster(project,envgroup,entry['path'],entry['name'],int(entry['band']),float(entry['min']),float(entry['max']))
  envgroup.setExpanded(False)
 project.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(QgsRectangle(26.5229,39.0379,26.5261,39.0403),project.crs()))
 project.setFilePathStorage(Qgis.FilePathType.Relative)
 path=ROOT/f'Greece_{year}_feature_analysis.qgz'
 project.setFileName(str(path))
 if not project.write(str(path)): raise ValueError('Project write failed')
 reread=QgsProject(); assert reread.read(str(path)); invalid=[x.name() for x in reread.mapLayers().values() if not x.isValid()]
 checks.append({'project':str(path),'layers':len(reread.mapLayers()),'invalid_layers':invalid});print(checks[-1],flush=True)
 if invalid:raise ValueError(invalid)
(ROOT/'data/qgis_verification.json').write_text(json.dumps(checks,indent=2))
# Do not call exitQgis while Python still owns project/layer wrappers on Windows.
