import os,json,shutil,hashlib,datetime
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
from qgis.core import QgsApplication,QgsProject,QgsMapLayerType,QgsRasterLayer,QgsColorRampShader,QgsRasterShader,QgsSingleBandPseudoColorRenderer,QgsSingleBandGrayRenderer,QgsContrastEnhancement
from qgis.PyQt.QtGui import QColor
from osgeo import gdal
gdal.UseExceptions()
ROOT=Path(r'D:\Masters\signed_water_enhancement_20261023');app=QgsApplication([],False);app.initQgis()
NAME='Signed water-relative SAR | fixed v1'
OPTIONS=QgsRasterLayer.LayerOptions();OPTIONS.loadDefaultStyle=False
ABSTRACT='Fixed v1, unsmoothed calibrated sigma0 dB. Signed difference from mapped-water annular mean and division by max(local population SD, 1 dB). Blue=darker, white=background, red=brighter. Square neighbourhood half-widths 150/500 m, guard half-widths 50/150 m. ESA WorldCover 2021 v200 water class 80 with 30 m nonwater margin; >=70% annulus water support and >=30 cells. No plastic label fitting. Mapped water is a proxy; shoreline, ships, wakes and fronts may affect estimates. Standardized values are descriptive, not probabilities or statistical significance. Instrument noise is not removed. Coverage is reference/search areas plus 1 km context; see enhancement README.'
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def renderer(layer,band,lo,hi,diverging=True):
 ramp=QgsColorRampShader();ramp.setColorRampType(QgsColorRampShader.Interpolated);ramp.setMinimumValue(lo);ramp.setMaximumValue(hi)
 colours=[(lo,'#2166ac',f'{lo:g} darker'),(0,'#f7f7f7','0 local background'),(hi,'#b2182b',f'+{hi:g} brighter')] if diverging else [(lo,'#f7fbff',str(lo)),(hi,'#08519c',str(hi))]
 ramp.setColorRampItemList([QgsColorRampShader.ColorRampItem(v,QColor(c),label) for v,c,label in colours]);ramp.setClip(False)
 shader=QgsRasterShader(lo,hi);shader.setRasterShaderFunction(ramp);r=QgsSingleBandPseudoColorRenderer(layer.dataProvider(),band,shader);r.setClassificationMin(lo);r.setClassificationMax(hi);layer.setRenderer(r)
def add(project,group,mosaic,band,name,lo,hi,signed=True,checked=False):
 view=mosaic.with_name(mosaic.stem+f'_band{band:02d}.vrt');gdal.Translate(str(view),str(mosaic),format='VRT',bandList=[band])
 layer=QgsRasterLayer(str(view),name,'gdal',OPTIONS)
 assert layer.isValid(),str(view)
 renderer(layer,1,lo,hi,signed);meta=layer.metadata();meta.setAbstract(ABSTRACT);layer.setMetadata(meta);layer.setCustomProperty('signed_water/version','1.0');project.addMapLayer(layer,False);node=group.addLayer(layer);node.setItemVisibilityChecked(checked);node.setExpanded(False);return layer.id()
jobs=json.loads((ROOT/'jobs.json').read_text());manifest=json.loads((ROOT/'raster_manifest.json').read_text());byproject={}
for j in jobs:
 records=[r for r in manifest if Path(r['path']).parent==Path(j['output']) and r['pol']=='vv']
 if j['windows'] and sum(r['stats']['150m_signed_delta_db']['n'] for r in records)>0:byproject.setdefault(j['project'],[]).append(j)
checks=[]
for path,js in byproject.items():
 p=QgsProject();assert p.read(path),path
 if p.layerTreeRoot().findGroup(NAME):raise RuntimeError('Already enhanced: '+path)
 before=digest(path);sources={k:l.source() for k,l in p.mapLayers().items()};invalid_before={k for k,l in p.mapLayers().items() if not l.isValid()};visibility={n.layerId():n.itemVisibilityChecked() for n in p.layerTreeRoot().findLayers()}
 group=p.layerTreeRoot().insertGroup(0,NAME);group.setExpanded(True);new=[]
 for i,j in enumerate(js):
  sg=group.addGroup(j['scene']+' UTC'+(' | recovered local source' if j['recovered_source'] else ''));sg.setExpanded(i==0)
  for pol in ['vv','vh']:
   records=[r for r in manifest if Path(r['path']).parent==Path(j['output']) and r['pol']==pol]
   if not records:continue
   mosaic=Path(j['output'])/(pol+'_signed_water.vrt');d=gdal.BuildVRT(str(mosaic),[r['path'] for r in records]);assert d;d=None
   pg=sg.addGroup(pol.upper()+' | signed enhancements');pg.setExpanded(pol=='vv')
   for band,title,lo,hi in [(1,'150 m: signed contrast (dB)',-6,6),(2,'150 m: signed standardized contrast',-3,3),(6,'500 m: signed contrast (dB)',-6,6),(7,'500 m: signed standardized contrast',-3,3)]:new.append(add(p,pg,mosaic,band,pol.upper()+' '+title,lo,hi,checked=pol=='vv' and band==1))
   diagnostics=pg.addGroup('Background and support | inspect if uncertain');diagnostics.setExpanded(False)
   for band,title,lo,hi in [(3,'150 m background mean (dB)',-35,-5),(4,'150 m background spread (dB)',0,6),(5,'150 m valid water fraction',0,1),(8,'500 m background mean (dB)',-35,-5),(9,'500 m background spread (dB)',0,6),(10,'500 m valid water fraction',0,1),(11,'Original unsmoothed sigma0 (dB)',-35,-5)]:new.append(add(p,diagnostics,mosaic,band,pol.upper()+' '+title,lo,hi,signed=False))
  maskfiles=sorted(Path(j['output']).glob('patch_*_worldcover_mask.tif'))
  if maskfiles:
   maskmosaic=Path(j['output'])/'water_eligibility.vrt';d=gdal.BuildVRT(str(maskmosaic),[str(x) for x in maskfiles]);assert d;d=None
   new.append(add(p,sg,maskmosaic,2,'Water eligibility | WorldCover 2021 + 30 m margin',0,1,signed=False))
  sg.setItemVisibilityChecked(i==0)
 group.setItemVisibilityChecked(False)
 order=[l for l in p.layerTreeRoot().layerOrder() if l.id() not in new];vectors=[l for l in order if l.type()==QgsMapLayerType.VectorLayer];other=[l for l in order if l.type()!=QgsMapLayerType.VectorLayer]
 p.layerTreeRoot().setHasCustomLayerOrder(True);p.layerTreeRoot().setCustomLayerOrder(vectors+[p.mapLayer(k) for k in new]+other)
 # Stage beside original so all original relative paths keep the same meaning.
 staged=Path(path).with_name('batch.signed_water_staged.qgz');assert p.write(str(staged))
 check=QgsProject();assert check.read(str(staged));newbad=[check.mapLayer(k).name() for k in new if not check.mapLayer(k).isValid()]
 assert not newbad,newbad
 assert all(check.mapLayer(k) and check.mapLayer(k).source()==v for k,v in sources.items()),'Original source changed'
 assert all(check.layerTreeRoot().findLayer(k).itemVisibilityChecked()==v for k,v in visibility.items()),'Original visibility changed'
 invalid_after={k for k,l in check.mapLayers().items() if not l.isValid()};assert invalid_after==invalid_before,'New invalid original layer'
 assert digest(path)==before,'Project changed while staging'
 stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S');backup=Path(path).with_name('batch.before_signed_water_'+stamp+'.qgz');shutil.copy2(path,backup)
 os.replace(staged,path)
 record=dict(project=path,backup=str(backup),original_sha256=before,new_sha256=digest(path),original_layers=len(sources),added_layers=len(new),preexisting_invalid_layers=[check.mapLayer(k).name() for k in invalid_before],new_invalid_layers=newbad,original_sources_preserved=True,original_visibility_preserved=True,scenes=[j['scene'] for j in js])
 checks.append(record);(ROOT/'project_checks.json').write_text(json.dumps(checks,indent=2));print(Path(path).parent.name,'added',len(new),'valid layers; existing invalid',len(invalid_before),flush=True)
print('COMPLETE',len(checks),'projects',flush=True)
