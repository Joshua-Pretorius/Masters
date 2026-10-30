from pathlib import Path
import json, sqlite3, zipfile, xml.etree.ElementTree as ET
from osgeo import ogr

lines = [
'''-87.333841,15.8636 -87.332339,15.865003 -87.331824,15.866572 -87.330451,15.866943 -87.329292,15.867728 -87.32779,15.868595 -87.326288,15.869668 -87.321825,15.870989 -87.321053,15.871691 -87.319636,15.871567 -87.317576,15.872062 -87.315474,15.872805 -87.313499,15.873507 -87.312641,15.874332 -87.311482,15.875158 -87.309508,15.876561 -87.305517,15.87846 -87.302341,15.878543 -87.297535,15.878956 -87.293243,15.879699 -87.29084,15.880524 -87.286034,15.880524 -87.284489,15.879781 -87.281828,15.879946 -87.276077,15.880111 -87.273417,15.879699 -87.268267,15.879038 -87.264147,15.879451 -87.261143,15.879616 -87.257967,15.879533 -87.25462,15.878295 -87.249727,15.876809 -87.245693,15.875901 -87.241917,15.874663 -87.237968,15.873507 -87.234192,15.872186 -87.232389,15.871938 -87.229471,15.874085 -87.226896,15.874002 -87.220287,15.872103 -87.215481,15.873177 -87.207842,15.873011 -87.201576,15.872846 -87.196426,15.873342 -87.192392,15.873011 -87.191792,15.875323 -87.187672,15.875818 -87.182178,15.875818 -87.176428,15.875323 -87.166214,15.869461 -87.164841,15.867397 -87.161236,15.873342 -87.152138,15.874332 -87.144413,15.873342 -87.139435,15.867397 -87.134457,15.862113 -87.115402,15.860792 -87.103043,15.867397 -87.09137,15.873507 -87.091541,15.8778 -87.099781,15.881597 -87.101498,15.885395 -87.097206,15.889192 -87.087765,15.894806 -87.080555,15.894806 -87.071285,15.894145 -87.049656,15.885065 -87.035236,15.883413 -87.027512,15.876314 -87.023392,15.866902 -87.029572,15.861783 -87.033005,15.851215 -87.033863,15.847747 -87.031975,15.844609''',
'''-88.138676,16.118224 -88.120651,16.123996 -88.065033,16.139167 -88.006668,16.146422 -87.967529,16.143289 -87.949848,16.140816 -87.941437,16.138177 -87.910538,16.128283 -87.879639,16.11476 -87.858353,16.09365 -87.82402,16.079795 -87.803078,16.072537 -87.769775,16.058351 -87.748833,16.055712 -87.735443,16.058681 -87.71347,16.06132 -87.686348,16.066599 -87.657852,16.065609 -87.63382,16.065609 -87.605667,16.066599 -87.592964,16.066599 -87.577515,16.06363 -87.555885,16.060331 -87.532539,16.059341 -87.506447,16.06264 -87.409286,16.023046 -87.39006,16.015456 -87.364655,16.000936 -87.348175,15.996645 -87.334442,15.992685 -87.322769,16.001596 -87.308693,16.013146 -87.29908,16.016776 -87.287407,16.022716 -87.267494,16.023376 -87.257195,16.017436 -87.237625,16.022386 -87.224922,16.020736 -87.214622,16.016446 -87.197113,16.004896 -87.18338,16.006216 -87.174797,15.998625 -87.161064,15.993015 -87.164497,15.981133 -87.125359,15.967931 -87.110939,15.991365 -87.093086,15.994665 -87.08004,15.990045 -87.061501,15.977173 -87.038841,15.96694 -87.024422,15.96694''',
'''-87.099781,15.790602 -87.088795,15.80299 -87.071629,15.811083 -87.053947,15.811579 -87.034378,15.812735 -87.02837,15.814882 -87.014637,15.815873 -87.005367,15.820002 -86.996956,15.819837 -86.988201,15.824131 -86.98185,15.82793 -86.971722,15.831398 -86.962452,15.832554 -86.946487,15.829251'''
]
coords = [[list(map(float,p.split(','))) for p in line.split()] for line in lines]
p=Path(r'D:\Joshua\New\marida_16pec_20190111_03\digitising_batches\marida_16pec_20190111_03\batch.qgz')
with zipfile.ZipFile(p) as z:
    root=ET.fromstring(z.read(next(n for n in z.namelist() if n.endswith('.qgs'))))
paths=set()
for layer in root.findall('./projectlayers/maplayer'):
    s=layer.findtext('datasource','')
    if '|layername=reference_points' in s: paths.add((p.parent/s.split('|')[0]).resolve())
assert len(paths)==2
prefix='marida_16PEC_USER_20261027_'
expected={f'{prefix}L{i:02d}_V{j:03d}': xy for i,line in enumerate(coords,1) for j,xy in enumerate(line,1)}
print('Vertices per line:',[len(x) for x in coords], 'total:',len(expected))
ogr.UseExceptions()
for path in sorted(paths):
    with sqlite3.connect(path) as c:
        tables=[r[0] for r in c.execute('select table_name from gpkg_contents')]
        before={t:c.execute(f'SELECT * FROM "{t}" ORDER BY 1').fetchall() for t in tables}
        assert not c.execute('select 1 from reference_points where point_id like ?', (prefix+'%',)).fetchone(), 'Already added'
        backup=path.with_name('task.before_user_points_20261027.gpkg')
        assert not backup.exists()
        with sqlite3.connect(backup) as b: c.backup(b)
    ds=ogr.Open(str(path),1)
    layer=ds.GetLayerByName('reference_points')
    assert layer.GetSpatialRef().GetAuthorityCode(None)=='4326'
    first=layer.GetNextFeature()
    task_id=first.GetField('task_id')
    assert ds.StartTransaction()==0
    for pid,xy in expected.items():
        f=ogr.Feature(layer.GetLayerDefn())
        for k,v in {'point_id':pid,'task_id':task_id,'obs_id':'user_supplied_20261027','ref_kind':'user_line_candidate','seed_ok':0,'notes':'User-supplied LineString vertex; unverified optical candidate. Observation date not supplied; not an OpenDrift seed. '+pid}.items(): f.SetField(k,v)
        g=ogr.Geometry(ogr.wkbPoint); g.AddPoint_2D(*xy); f.SetGeometry(g)
        assert layer.CreateFeature(f)==0
        f=None
    assert ds.CommitTransaction()==0
    layer=None; ds=None
    with sqlite3.connect(path) as c:
        assert c.execute('pragma integrity_check').fetchone()[0]=='ok'
        for t,rows in before.items():
            after=c.execute(f'SELECT * FROM "{t}" ORDER BY 1').fetchall()
            if t=='reference_points':
                assert after[:len(rows)]==rows and len(after)==len(rows)+len(expected)
            else: assert after==rows,t
        assert c.execute('select count(*) from rtree_reference_points_geom').fetchone()[0]==len(before['reference_points'])+len(expected)
    ds=ogr.Open(str(path)); layer=ds.GetLayerByName('reference_points')
    actual={}
    for f in layer:
        pid=f.GetField('point_id')
        if pid.startswith(prefix):
            g=f.GetGeometryRef(); actual[pid]=[g.GetX(),g.GetY()]
            assert f.GetField('seed_ok')==0 and f.GetField('delta_h') is None
    assert actual==expected
    layer=None; ds=None
    print(json.dumps({'task':task_id,'before':len(before['reference_points']),'added':len(expected),'after':len(before['reference_points'])+len(expected),'backup':str(backup),'integrity':'ok','other_layers':'unchanged','coordinates':'exact match'}))
