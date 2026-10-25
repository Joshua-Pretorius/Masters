import os,json,hashlib,shutil,datetime
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
from qgis.core import QgsApplication,QgsProject,QgsRasterLayer,QgsColorRampShader,QgsRasterShader,QgsSingleBandPseudoColorRenderer,QgsPalettedRasterRenderer,QgsMapLayerType,QgsMapSettings,QgsRectangle,QgsMapRendererParallelJob
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtCore import QSize
from osgeo import gdal
gdal.UseExceptions()
ROOT=Path(r'D:\Masters\patch_enhancement_20261023');BASE=Path(r'D:\Joshua\New\Debris_Visible_Not_Done\marida_18qyg_20200305_20200307_01');path=BASE/'digitising_batches'/BASE.name/'batch.qgz';app=QgsApplication([],False);app.initQgis();p=QgsProject();assert p.read(str(path));oldhash=hashlib.sha256(path.read_bytes()).hexdigest();original={k:l.source() for k,l in p.mapLayers().items()};visibility={n.layerId():n.itemVisibilityChecked() for n in p.layerTreeRoot().findLayers()};oldorder=p.layerTreeRoot().layerOrder()
NAME='Area | filtered, patch and VV-VH views v1';assert not p.layerTreeRoot().findGroup(NAME),'Group already added'
group=p.layerTreeRoot().insertGroup(0,NAME);new=[];options=QgsRasterLayer.LayerOptions();options.loadDefaultStyle=False
classes=[(0,'#d9d9d9','Neither exceeds ±1 dB'),(1,'#ef8a62','VV brighter; VH neutral'),(2,'#67a9cf','VV darker; VH neutral'),(3,'#c994c7','VH brighter; VV neutral'),(4,'#8073ac','VH darker; VV neutral'),(5,'#b2182b','Both brighter'),(6,'#2166ac','Both darker'),(7,'#e6ab02','VV brighter / VH darker'),(8,'#66a61e','VV darker / VH brighter')]
status=[(1,'#ffd166','Both supported; instrument noise unassessed'),(2,'#e76f51','VV supported; VH unsupported'),(3,'#8e6bbf','VH supported; VV unsupported'),(4,'#777777','Neither patch supported')]
def add(sg,src,b,name,lo=-6,hi=6,category=None,checked=False,signed=True):
 view=src.with_name(src.stem+f'_band{b:02d}.vrt');d=gdal.Translate(str(view),str(src),format='VRT',bandList=[b]);assert d;d=None
 layer=QgsRasterLayer(str(view),name,'gdal',options);assert layer.isValid()
 if category:layer.setRenderer(QgsPalettedRasterRenderer(layer.dataProvider(),1,[QgsPalettedRasterRenderer.Class(v,QColor(c),label) for v,c,label in category]))
 else:
  ramp=QgsColorRampShader();ramp.setColorRampType(QgsColorRampShader.Interpolated);ramp.setMinimumValue(lo);ramp.setMaximumValue(hi);ramp.setClip(False)
  stops=[(lo,'#2166ac'),(0,'#f7f7f7'),(hi,'#b2182b')] if signed else [(lo,'#ffffff'),(hi,'#222222')]
  ramp.setColorRampItemList([QgsColorRampShader.ColorRampItem(v,QColor(c),str(v)) for v,c in stops]);shader=QgsRasterShader(lo,hi);shader.setRasterShaderFunction(ramp);renderer=QgsSingleBandPseudoColorRenderer(layer.dataProvider(),1,shader);renderer.setClassificationMin(lo);renderer.setClassificationMax(hi);layer.setRenderer(renderer)
 meta=layer.metadata();meta.setAbstract('Full Area.geojson polygon at native SAR spacing. Fixed signed enhancement; no plastic-label fitting. Refined Lee contrast uses mean dB water background, while patches compare means of linear intensity in dB. Independent annual WorldCover water mask plus 30 m margin. Agreement uses a fixed ±1 dB display deadband, not a detection or significance threshold. Instrument noise/NESZ reliability is UNASSESSED for all supported VH values. Unsupported pixels remain NoData; inspect support status. See area_patch_enhancement_v1/README.md.');layer.setMetadata(meta);p.addMapLayer(layer,False);n=sg.addLayer(layer);n.setItemVisibilityChecked(checked);n.setExpanded(False);new.append(layer);return layer
records=json.loads((ROOT/'manifest.json').read_text());preview_layers=[]
for i,r in enumerate(records):
 src=Path(r['path']);sg=group.addGroup(r['scene']+' UTC');sg.setExpanded(i==0)
 fg=sg.addGroup('1 Filtered VV | signed water contrast');fg.setExpanded(True)
 first=add(fg,src,1,'Refined Lee VV | signed contrast (dB)',checked=True);add(fg,src,2,'Refined Lee VV | standardized signed contrast',-3,3)
 pg=sg.addGroup('2 Patch versus surrounding water | signed');pg.setExpanded(True)
 patch=None
 for pol,bands in [('VV',[3,4,5]),('VH',[6,7,8])]:
  for size,b in zip([30,60,120],bands):
   layer=add(pg,src,b,f'{pol} {size} m patch | signed contrast (dB)')
   if b==4:patch=layer
 ag=sg.addGroup('3 VV / VH agreement | noise reliability unassessed');ag.setExpanded(True);agreement=add(ag,src,9,'60 m agreement | ±1 dB deadband; NESZ unassessed',category=classes);add(ag,src,10,'Channel support / instrument-noise status',category=status)
 dg=sg.addGroup('Diagnostics and original values');dg.setExpanded(False)
 for b,name,lo,hi in [(11,'VH 60 m patch mean dB',-35,-5),(12,'VV 60 m patch mean dB',-35,-5),(13,'VV water-ring mean dB',-35,-5),(14,'VH water-ring mean dB',-35,-5),(15,'VV water-ring support',0,1),(16,'VH water-ring support',0,1),(17,'Refined Lee background mean dB',-35,-5),(18,'Refined Lee background support',0,1),(19,'Original VV dB',-35,-5),(20,'Original VH dB',-35,-5)]:add(dg,src,b,name,lo,hi,signed=False)
 add(dg,Path(r['mask']),2,'Water eligibility including calculation halo',0,1,signed=False)
 sg.setItemVisibilityChecked(i==0);preview_layers.append((r,first,patch,agreement))
group.setItemVisibilityChecked(False);vectors=[l for l in oldorder if l.type()==QgsMapLayerType.VectorLayer];others=[l for l in oldorder if l.type()!=QgsMapLayerType.VectorLayer];p.layerTreeRoot().setHasCustomLayerOrder(True);p.layerTreeRoot().setCustomLayerOrder(vectors+new+others)
staged=path.with_name('batch.area_views_staged.qgz');assert p.write(str(staged));check=QgsProject();assert check.read(str(staged));assert all(check.mapLayer(l.id()).isValid() for l in new);assert all(check.mapLayer(k).source()==v for k,v in original.items());assert all(check.layerTreeRoot().findLayer(k).itemVisibilityChecked()==v for k,v in visibility.items());assert hashlib.sha256(path.read_bytes()).hexdigest()==oldhash,'Concurrent project edit'
backup=path.with_name('batch.before_area_patch_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'.qgz');shutil.copy2(path,backup);os.replace(staged,path)
rendered=[]
for r,*layers in preview_layers:
 for label,layer in zip(['filtered','patch60','agreement'],layers):
  settings=QgsMapSettings();settings.setLayers([layer]);settings.setDestinationCrs(layer.crs());settings.setExtent(QgsRectangle(-72.99505,18.85260,-72.61164,19.44792));settings.setOutputSize(QSize(850,1100));settings.setBackgroundColor(QColor('#e5e5e5'));job=QgsMapRendererParallelJob(settings);job.start();job.waitForFinished();assert not job.errors();dest=ROOT/(r['scene']+'_'+label+'.png');assert job.renderedImage().save(str(dest));rendered.append(str(dest))
(ROOT/'project_checks.json').write_text(json.dumps(dict(project=str(path),backup=str(backup),added_layers=len(new),all_new_layers_valid=True,original_sources_preserved=True,original_checked_states_preserved=True,rendered=rendered),indent=2));print('Added',len(new),'layers; rendered',len(rendered),'views; backup',backup,flush=True)
