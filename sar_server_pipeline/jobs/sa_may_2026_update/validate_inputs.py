import csv,re
from pathlib import Path
from datetime import datetime
p=Path(__file__).resolve().parent
rows={r['obs_id']:r for r in csv.DictReader((p/'MERIA_SA_plastic_nearest_S1_SLC_before_after.csv').open(encoding='utf-8-sig'))}
targets=re.findall(r'^- (MERIA_SA_\d+):(before|after)$',(p/'job.yaml').read_text(),re.M)
assert len(targets)==6, targets
granules=[]
for oid,role in targets:
    row=rows[oid]
    granule=row[role+'_name']
    acquired=datetime.strptime(granule.split('_')[5],'%Y%m%dT%H%M%S')
    cutoff=datetime(2026,5,7 if oid=='MERIA_SA_013' else 5)
    assert acquired>=cutoff,(oid,granule,cutoff)
    granules.append(granule)
assert len(set(granules))==6
pts=list(csv.DictReader((p/'MERIA_SA_plastic_points.csv').open(encoding='utf-8-sig')))
for oid,count in [('MERIA_SA_010',28),('MERIA_SA_011',105),('MERIA_SA_012',33),('MERIA_SA_013',17)]:
    selected=[(float(r['lon']),float(r['lat'])) for r in pts if r['obs_id']==oid]
    assert len(selected)==len(set(selected))==count,(oid,len(selected))
    assert all(-180<=lon<=180 and -90<=lat<=90 for lon,lat in selected)
print('Validated six unique processing scenes, event cutoffs and 183 new points.')
