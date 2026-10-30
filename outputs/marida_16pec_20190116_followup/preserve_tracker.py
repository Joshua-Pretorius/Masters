from pathlib import Path
import zipfile,xml.etree.ElementTree as E,re,copy
job=Path('D:/Masters/sar_server_pipeline/jobs/marida_16pec_20190116'); out=Path('D:/Masters/outputs/marida_16pec_20190116_followup'); source=job/'backup/MERIA_scene_batch_tracker.xlsx'; generated=out/'tracker_updated.xlsx'; final=out/'tracker_preserved.xlsx'
ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}; uri=ns['s']; E.register_namespace('',uri)
with zipfile.ZipFile(source) as old,zipfile.ZipFile(generated) as new:
 strings=[]
 if 'xl/sharedStrings.xml' in new.namelist(): strings=[''.join(x.itertext()) for x in E.fromstring(new.read('xl/sharedStrings.xml'))]
 changed={}
 for sheet,template,rows,end in [('sheet1.xml',96,[97],'M97'),('sheet2.xml',154,[155,156],'O156')]:
  path='xl/worksheets/'+sheet; raw=old.read(path).decode(); orig=E.fromstring(raw); gen=E.fromstring(new.read(path))
  template_row=orig.find(f'.//s:row[@r="{template}"]',ns); styles={re.sub(r'\d','',c.attrib['r']):c.attrib.get('s') for c in template_row}
  added=[]
  for n in rows:
   row=copy.deepcopy(gen.find(f'.//s:row[@r="{n}"]',ns))
   for c in row:
    col=re.sub(r'\d','',c.attrib['r']);sty=styles.get(col)
    if sty is None:c.attrib.pop('s',None)
    else:c.set('s',sty)
    if c.attrib.get('t')=='s':
     v=c.find('s:v',ns); txt=strings[int(v.text)];c.remove(v);c.set('t','inlineStr'); node=E.SubElement(c,'{'+uri+'}is');E.SubElement(node,'{'+uri+'}t').text=txt
   added.append(E.tostring(row,encoding='unicode'))
  raw=raw.replace('</sheetData>',''.join(added)+'</sheetData>')
  raw=re.sub(r'<dimension ref="[^"]+"',f'<dimension ref="A1:{end}"',raw,count=1)
  changed[path]=raw.encode()
 with zipfile.ZipFile(final,'w',zipfile.ZIP_DEFLATED) as z:
  for entry in old.infolist():z.writestr(entry,changed.get(entry.filename,old.read(entry.filename)))
print(final)
