"""Reset only the explicitly synthetic sample inventory and health fixtures."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
samples=[('rack-a', [('server-a01',1,2),('server-a02',3,2),('server-a03',7,4),('server-a04',13,2),('server-a05',19,1),('server-a06',23,2),('server-a07',31,4),('server-a08',39,2)]),
 ('rack-b',[('server-b01',1,2),('server-b02',5,4),('server-b03',11,2),('server-b04',17,1),('server-b05',21,2),('server-b06',27,4),('server-b07',35,2),('server-b08',41,2)])]
health={}
for rack, servers in samples:
 for sid,u,h in servers:
  labels={'server_id':sid,'rack':rack,'position_u':str(u),'height_u':str(h),'face':'front'}
  metric='server_rack_info{'+','.join(k+'='+json.dumps(v) for k,v in labels.items())+'} 1\n'
  (ROOT/'inventory'/f'{sid}.prom').write_text('# Provisioned sample: synthetic server-local metadata, not a NetBox connection.\n'+metric)
  health[sid]=0
health['server-a04']=1
health['server-b03']=1
health['server-b06']=None
(ROOT/'mock-health.json').write_text(json.dumps(health,indent=2)+'\n')
