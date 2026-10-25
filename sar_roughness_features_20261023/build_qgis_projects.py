import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
import json,csv
from qgis.core import QgsApplication,QgsProject,QgsRasterLayer,QgsVectorLayer,QgsColorRampShader,QgsRasterShader,QgsSingleBandPseudoColorRenderer,QgsSingleBandGrayRenderer,QgsContrastEnhancement,QgsFillSymbol,QgsCategorizedSymbolRenderer,QgsRendererCategory,QgsMultiBandColorRenderer,QgsCoordinateReferenceSystem,QgsRectangle,QgsReferencedRectangle,Qgis
from qgis.PyQt.QtGui import QColor
from osgeo import gdal
gdal.UseExceptions()
ROOT=Path(r'D:\Masters\sar_roughness_features_20261023');app=QgsApplication([],False);app.initQgis()
scenes=json.loads((ROOT/'data/map_scenes.json').read_text())
RASTER_OPTIONS=QgsRasterLayer.LayerOptions();RASTER_OPTIONS.loadDefaultStyle=False
(ROOT/'views').mkdir(exist_ok=True)
def readcsv(name):
 with (ROOT/name).open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))
common=readcsv('data/raster_index.csv');rich=readcsv('data/rich_raster_index.csv');environment=readcsv('environment/native_layer_index.csv');gpkg=ROOT/'data/roughness_samples.gpkg'

def add_raster(project,group,path,name,band,lo,hi,visible=False,gray=False):
 original=Path(path);view=ROOT/'views'/f'{original.stem}_band{band}.vrt'
 if not view.exists():gdal.Translate(str(view),str(original),format='VRT',bandList=[band])
 layer=QgsRasterLayer(str(view),name,'gdal',RASTER_OPTIONS);band=1
 if not layer.isValid():raise ValueError(str(path))
 if hi<=lo:lo-=1;hi+=1
 if gray:
  renderer=QgsSingleBandGrayRenderer(layer.dataProvider(),band);enhance=QgsContrastEnhancement(layer.dataProvider().dataType(band));enhance.setMinimumValue(lo);enhance.setMaximumValue(hi);enhance.setContrastEnhancementAlgorithm(QgsContrastEnhancement.StretchToMinimumMaximum);renderer.setContrastEnhancement(enhance)
 else:
  ramp=QgsColorRampShader();ramp.setColorRampType(QgsColorRampShader.Interpolated);ramp.setColorRampItemList([QgsColorRampShader.ColorRampItem(v,QColor(c),f'{v:.2f}') for v,c in [(lo,'#2166ac'),((lo+hi)/2,'#f7f7f7'),(hi,'#b2182b')]]);shader=QgsRasterShader();shader.setRasterShaderFunction(ramp);renderer=QgsSingleBandPseudoColorRenderer(layer.dataProvider(),band,shader)
 layer.setRenderer(renderer);meta=layer.metadata();meta.setAbstract('Water-only environmental roughness baseline; controlled deployment weight 1.5; candidate observations retain uncertainty. Scores are exploratory. Instrument electronic noise/NESZ not estimated. See REPORT.html.');layer.setMetadata(meta);project.addMapLayer(layer,False);node=group.addLayer(layer);node.setItemVisibilityChecked(visible);node.setExpanded(False);return layer

def add_rgb(project,group,entries,bands,name):
 source=Path(entries[0]['path']);view=ROOT/'views'/(source.stem+'_RGB_'+''.join(str(b) for b in bands)+'.vrt')
 if not view.exists():gdal.Translate(str(view),str(source),format='VRT',bandList=bands)
 layer=QgsRasterLayer(str(view),name,'gdal',RASTER_OPTIONS);r=QgsMultiBandColorRenderer(layer.dataProvider(),1,2,3)
 for channel,(band,setter) in enumerate(zip(bands,[r.setRedContrastEnhancement,r.setGreenContrastEnhancement,r.setBlueContrastEnhancement]),1):
  e=next(x for x in entries if int(x['band'])==band);ce=QgsContrastEnhancement(layer.dataProvider().dataType(channel));ce.setMinimumValue(float(e['p02']));ce.setMaximumValue(max(float(e['p98']),float(e['p02'])+.01));ce.setContrastEnhancementAlgorithm(QgsContrastEnhancement.StretchToMinimumMaximum);setter(ce)
 layer.setRenderer(r);project.addMapLayer(layer,False);group.addLayer(layer).setItemVisibilityChecked(False)
checks=[]
for kind in ['All_locations','Greece_2021','Greece_2024']:
 selected=scenes if kind=='All_locations' else [s for s in scenes if s['location']=='Greece' and s['scene'].startswith(kind[-4:])];default='20240629T041520' if kind in ['All_locations','Greece_2024'] else '20210626T161500';path=ROOT/f'{kind}_roughness_analysis.qgz';project=QgsProject();project.setFileName(str(path));project.setCrs(QgsCoordinateReferenceSystem('EPSG:4326'));project.setTitle('Roughness-controlled plastic reference analysis | '+kind);root=project.layerTreeRoot()
 for scene in sorted(selected,key=lambda s:(s['location']!='Greece',s['scene'])):
  sid=scene['scene'];active=sid==default;group=root.addGroup(f"{scene['location']} | {sid[:4]}-{sid[4:6]}-{sid[6:8]} {sid[9:11]}:{sid[11:13]} UTC");group.setExpanded(active)
  labels=QgsVectorLayer(str(gpkg)+'|layername=label_polygons','Controlled / plastic / water / distractor footprints','ogr');labels.setSubsetString(f'"scene" = \'{sid}\'');categories=[]
  for label,color in [('controlled_plastic','#ffd000'),('plastic','#ff8c00'),('water','#00bed5'),('calm_water','#00bed5'),('open_ocean','#00bed5'),('ship','#8f5bb2'),('wake','#c4519c'),('slick','#78909c'),('other','#657787')]:
   symbol=QgsFillSymbol.createSimple({'color':'0,0,0,0','style':'no','outline_color':color,'outline_width':'0.45' if label=='controlled_plastic' else '0.28'});categories.append(QgsRendererCategory(label,symbol,label))
  labels.setRenderer(QgsCategorizedSymbolRenderer('class_name',categories));project.addMapLayer(labels,False);group.addLayer(labels).setItemVisibilityChecked(True)
  rs=[e for e in rich if e['scene']==sid and e['available']=='True'];cs=[e for e in common if e['scene']==sid]
  if rs:
   rg=group.addGroup('Rich SLC: weighted indices and multivariate views')
   for band,title in [(2,'01 Weighted pooled roughness index | exploratory'),(3,'02 Held-event roughness index'),(4,'03 Held-location roughness index'),(5,'04 Scene-fitted roughness index | exploratory'),(1,'05 Pooled raw SAR index | comparison')]:
    match=[e for e in rs if int(e['band'])==band]
    if match:add_raster(project,rg,match[0]['path'],title,band,-3,3,active and band==2)
   add_rgb(project,rg,rs,[6,7,8],'06 PCA RGB | roughness, polarimetry and texture');rg.setExpanded(active)
  cg=group.addGroup('Shared VV/VH model: all observations including Manila')
  for band,title in [(12,'Weighted pooled roughness index | exploratory'),(13,'Held-event roughness index'),(14,'Held-location roughness index'),(11,'Weighted raw SAR index | comparison')]:
   e=next(x for x in cs if int(x['band'])==band);add_raster(project,cg,e['path'],title,band,-3,3,active and not rs and band==12)
  add_rgb(project,cg,cs,[15,16,17],'PCA RGB | common roughness-corrected features');cg.setExpanded(not rs)
  bg=group.addGroup('Expected water baseline and backscatter-excess indices')
  for band in [7,8,9,10,5,6,1,2,3,4,18,19]:
   e=next(x for x in cs if int(x['band'])==band);lo,hi=float(e['p02']),float(e['p98'])
   if band in [7,8]:lo,hi=-3,3
   elif band in [5,6,9,10]:lo,hi=-6,6
   add_raster(project,bg,e['path'],e['name'].replace('_',' '),band,lo,hi)
  bg.setExpanded(False)
  original=group.addGroup('Original SAR feature inputs | native values')
  for i,name in enumerate(scene['raw_band_names']):
   lo,hi=(0,.05) if name in ['vv','vv_refined_lee'] else (0,.005) if name=='vh' else (-30,-10) if name.endswith('_db') else (0,1) if name in ['decomp_entropy','decomp_anisotropy'] else (0,60) if name=='decomp_alpha' else (0,8) if name=='vv_glcm_entropy' else (0,40)
   add_raster(project,original,scene['raw_crop'],name,i+1,lo,hi,gray=True)
  original.setExpanded(False)
  eg=group.addGroup('Regional environmental grids | native resolution and coastal masks')
  for e in environment:
   if e['scene']==sid:add_raster(project,eg,e['path'],e['name'],int(e['band']),float(e['min']),float(e['max']))
  eg.setExpanded(False);group.setItemVisibilityChecked(active)
 data=root.addGroup('Extracted values | attribute tables');samples=QgsVectorLayer(str(gpkg)+'|layername=sampled_pixels','Sampled SAR values, weights, context and scores','ogr');project.addMapLayer(samples,False);data.addLayer(samples).setItemVisibilityChecked(False);data.setExpanded(False)
 project.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(QgsRectangle(26.5229,39.0379,26.5261,39.0403),project.crs()));project.setFilePathStorage(Qgis.FilePathType.Relative)
 if not project.write(str(path)):raise ValueError('Cannot write '+str(path))
 check=QgsProject();assert check.read(str(path));invalid=[x.name() for x in check.mapLayers().values() if not x.isValid()];record={'project':str(path),'layers':len(check.mapLayers()),'invalid_layers':invalid};checks.append(record);print(record,flush=True)
 if invalid:raise ValueError(invalid)
(ROOT/'data/qgis_verification.json').write_text(json.dumps(checks,indent=2))
