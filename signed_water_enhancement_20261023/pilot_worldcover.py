import json
from enhance import ROOT,process
jobs=json.loads((ROOT/'jobs.json').read_text())
for j in jobs:
 if j['batch'].startswith('floating_greece'):process(j)
