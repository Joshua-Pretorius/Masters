import run
from run import *
from PIL import Image,ImageDraw
entries=[e for e in json.loads(Path(r'D:\Masters\outputs\water_contrast_20261025\results.json').read_text()) if 'marida_16pec_20190111_03' in e.get('path','')]
metrics=[]
for entry in entries:
 with rasterio.open(entry['path']) as src:
  # Choose the reference-centred crop with most valid water, explicitly not a target-selection metric.
  candidates=[]
  for lon,lat in entry['on_image_points']:
   row,col=src.index(lon,lat); window=Window(col-128,row-128,256,256)
   a=src.read(window=Window(col-134,row-134,268,268),boundless=True,fill_value=np.nan)
   candidates.append((np.isfinite(a).sum(),lon,lat,a,window))
  count,lon,lat,a,window=max(candidates,key=lambda c:c[0])
  location_kind='reference-centred'
  if count < 1000:
   overview=src.read(1,out_shape=(max(1,src.height//64),max(1,src.width//64)))
   rows,cols=np.where(np.isfinite(overview))
   assert len(rows),'No valid water'
   n=len(rows)//2; row=int((rows[n]+0.5)*src.height/overview.shape[0]); col=int((cols[n]+0.5)*src.width/overview.shape[1])
   lon,lat=src.xy(row,col); window=Window(col-128,row-128,256,256)
   a=src.read(window=Window(col-134,row-134,268,268),boundless=True,fill_value=np.nan)
   location_kind='valid-water example (reference crop has no valid contrast)'
  canvas=Image.new('RGB',(7*260,4*295+55),'#e5e5e5'); draw=ImageDraw.Draw(canvas)
  scene=Path(entry['path']).parent.parent.name
  draw.text((10,5),scene+' | '+location_kind+' 256 x 256 pixels | '+str((lon,lat)),fill='black')
  draw.text((10,23),'Same colour scale throughout: blue -6 dB, white 0, red +6 dB. Grey = NoData. Not a plastic validation.',fill='black')
  for b in range(4):
   images=[a[b,6:-6,6:-6]]+[v[6:-6,6:-6] for v in filters(a[b])]
   for j,im in enumerate(images):
    u=np.clip(np.nan_to_num(im)/6,-1,1)[...,None]
    white=np.array([247,247,247]); blue=np.array([33,102,172]); red=np.array([178,24,43])
    rgb=np.where(u>=0,white+u*(red-white),white-u*(blue-white)); rgb[~np.isfinite(im)]=[160,160,160]
    canvas.paste(Image.fromarray(rgb.astype('uint8')),(j*260,b*295+80))
    draw.text((j*260+3,b*295+48),INPUTS[b],fill='black')
    label='Original' if j==0 else LABELS[j-1]
    short=['Original','Median 3x3','Median 5x5','Gaussian sigma 1 px','Support 3x3: 5/9 > +/-0.5 dB','Support 5x5: 13/25 > +/-0.5 dB','Persistence: sigma 1 + 2 px'][j]
    draw.text((j*260+3,b*295+63),short,fill='black')
    finite=np.isfinite(im); dif=np.abs(np.diff(im,axis=1))
    metrics.append({'scene':scene,'input':INPUTS[b],'variant':label,'crop_center':[lon,lat],'location_kind':location_kind,'valid_pixels':int(finite.sum()),'median_absolute_adjacent_difference_db':float(np.nanmedian(dif)) if np.isfinite(dif).any() else None,'nonzero_fraction':float(np.count_nonzero(im[finite])/max(1,finite.sum()))})
  canvas.save(ROOT/(scene+'_comparison.png'))
(ROOT/'preview_metrics.json').write_text(json.dumps(metrics,indent=2))
