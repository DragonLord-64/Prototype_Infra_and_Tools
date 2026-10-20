import json
from itertools import combinations
from pathlib import Path
p=Path(__file__).parent/'grafana/dashboards/vlan-net-viewer.json'
d=json.loads(p.read_text())
source=json.loads((Path(__file__).parent/'mock-network.json').read_text())
route_colors={'Direct':{'text':'Direct','color':'green','index':0}}
for selected in source['vlans']:
    others=sorted(int(v) for v in source['vlans'] if v!=selected)
    for n in range(1,len(others)+1):
        for combo in combinations(others,n):
            route=str(selected)+' → '+', '.join(map(str,combo))
            route_colors[route]={'text':route,'color':'blue','index':len(route_colors)}
for panel in d['panels']:
    if panel['type']=='stat':panel['options']['textMode']='value'; panel['title']={2:'Inventory',3:'Matching interfaces',4:'Direct',5:'Translated'}[panel['id']]
    if panel['id']==1:
        panel['options']['content']='**Demo · 51 endpoint interfaces.** Select a VLAN. **Green:** directly allowed · **Blue:** explicit translation.'
    if panel['type']=='table':
        panel['transformations'][0]['options']['excludeByName']['Value']=True
        panel['transformations'][0]['options']['renameByName']['allowed_vlans']='VLANs'
        panel['transformations'][1]['options']['sort']=[{'field':'Route','desc':False}]
        panel['options']['sortBy']=[{'displayName':'Route','desc':False}]
        width={'Unit':80,'Switch / interface':130,'VLANs':80,'Route':100}
        panel['fieldConfig']['overrides']=[{'matcher':{'id':'byName','options':k},'properties':[{'id':'custom.width','value':v}]} for k,v in width.items()]
        routes=route_colors
        panel['fieldConfig']['overrides'].append({'matcher':{'id':'byName','options':'Route'},'properties':[{'id':'custom.cellOptions','value':{'type':'color-background','mode':'basic','applyToRow':True}},{'id':'mappings','value':[{'type':'value','options':routes}]}]})
p.write_text(json.dumps(d,indent=2)+'\n')
