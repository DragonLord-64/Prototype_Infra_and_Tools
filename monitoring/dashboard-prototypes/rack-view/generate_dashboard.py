"""Generate fixed geometry from provisioned textfiles; health remains live."""
import json
from pathlib import Path
from exporter import inventory
ROOT=Path(__file__).resolve().parent
DS={'type':'prometheus','uid':'server-health-demo-prometheus'}
records=inventory(ROOT)
elements=[];overrides=[];targets=[]

def element(name,x,y,w,h,text='',field=None,size=12,color='#DDE1EB',background=None,border=None):
 e={'name':name,'type':'metric-value','placement':{'left':x,'top':y,'width':w,'height':h},'constraint':{'horizontal':'left','vertical':'top'},'config':{'align':'left','valign':'middle','size':size,'color':{'fixed':color},'text':{'mode':'field' if field else 'fixed','field':field or '', 'fixed':text}}}
 if background:e['background']={'color':background}
 if border:e['border']={'width':1,'radius':2,'color':{'fixed':border}}
 if not field and not text:e['type']='rectangle'
 return e

racks=sorted(set((r['rack'],r['face']) for r in records))
for index,(rack,face) in enumerate(racks):
 x=index*410
 elements.append(element(rack+' label',x+28,0,355,28,text=f'{rack.upper()} · {face.upper()} · 42U',size=18))
 elements.append(element(rack+' frame',x+27,34,360,466,background={'fixed':'#171A21'},border='#526076'))
 for u in range(1,43):
  y=36+(42-u)*11
  elements.append(element(f'{rack} U{u}',x+1,y,23,11,text=str(u),size=9,color='#9DA7B7'))
  elements.append(element(f'{rack} slot{u}',x+32,y,350,10,background={'fixed':'#222630'},border='#303744'))
 for r in (r for r in records if (r['rack'],r['face'])==(rack,face)):
  sid=r['server_id'];start=int(r['position_u']);height=int(r['height_u']);y=36+(43-start-height)*11
  field=sid+' health'
  text_size=8 if height == 1 else 11
  begin=len(elements)
  elements.append(element(sid+' body',x+32,y,350,height*11-1,background={'field':field,'fixed':'#586579'},border='#B5C0D0'))
  elements.append(element(sid+' name',x+40,y,180,height*11-1,text=sid,size=text_size,color='#FFFFFF'))
  elements.append(element(sid+' size',x+215,y,72,height*11-1,text=f'{height}U · U{start:02d}',size=min(text_size,10),color='#FFFFFF'))
  elements.append(element(sid+' status',x+295,y,82,height*11-1,field=field,size=text_size,color='#FFFFFF'))
  link=[{'title':'Open shared demo server detail','url':'/d/server-health-demo','targetBlank':False,'oneClick':True}]
  for e in elements[begin:]:
   e['links']=link
   e['oneClickMode']='link'
  targets.append({'refId':'H'+str(len(targets)+1),'expr':f'(rack_server_health{{server_id="{sid}"}} and on(job, instance) (up{{job="rack-view-demo"}} == 1)) or on(server_id) (server_rack_info{{server_id="{sid}"}} * 0 + 2)','instant':True,'range':False,'legendFormat':field})
  overrides.append({'matcher':{'id':'byName','options':field},'properties':[{'id':'mappings','value':[{'type':'value','options':{'0':{'text':'OK','color':'#227647'},'1':{'text':'Fault','color':'#B52E3B'},'2':{'text':'Unknown','color':'#586579'}}}]},{'id':'color','value':{'mode':'thresholds'}},{'id':'thresholds','value':{'mode':'absolute','steps':[{'value':None,'color':'#227647'},{'value':1,'color':'#B52E3B'},{'value':2,'color':'#586579'}]}}]})
panel={'id':2,'type':'canvas','title':'Front elevations · 16 synthetic servers · fixed physical placement, live health','datasource':DS,'gridPos':{'x':0,'y':2,'w':24,'h':17},'targets':targets,'fieldConfig':{'defaults':{'noValue':'Unknown','color':{'mode':'fixed','fixedColor':'#586579'},'mappings':[{'type':'special','options':{'match':'nan','result':{'text':'Unknown','color':'#586579'}}}]},'overrides':overrides},'options':{'inlineEditing':False,'panZoom':False,'zoomToContent':True,'showAdvancedTypes':True,'tooltip':{'mode':'single'},'root':{'name':'Root','type':'frame','elements':elements}}}
dashboard={'uid':'rack-view-demo','title':'Rack View · Server Health','schemaVersion':39,'version':1,'tags':['demo','synthetic','rack','server'],'editable':True,'refresh':'5s','timezone':'browser','time':{'from':'now-15m','to':'now'},'annotations':{'list':[]},'templating':{'list':[]},'panels':[{'id':1,'type':'text','title':'','transparent':True,'gridPos':{'x':0,'y':0,'w':24,'h':2},'options':{'mode':'markdown','content':'**RACK ELEVATION · SYNTHETIC DATA** — Provisioning-generated server-local rack metadata + independent observed health. Green **OK** · Red **Fault** · Grey **Unknown**. [Shared server detail](/d/server-health-demo) (synthetic example).'}},panel]}
(ROOT/'grafana/dashboards/rack-view.json').write_text(json.dumps(dashboard,indent=2)+'\n')
print(f'Generated {len(records)} server placements across {len(racks)} rack faces')
