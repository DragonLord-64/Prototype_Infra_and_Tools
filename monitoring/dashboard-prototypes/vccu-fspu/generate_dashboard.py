from pathlib import Path
import json
R=Path(__file__).parent
D={'type':'prometheus','uid':'server-health-demo-prometheus'}
UP='up{job="vccu-fspu-demo"} == 1'
def q(metric,legend,ref='A',instant=True):
 return {'refId':ref,'expr':f'{metric} and on(job, instance) ({UP})','instant':instant,'range':not instant,'legendFormat':legend}
def el(name,x,y,w,h,text='',field=None,size=12,bg=None):
 e={'name':name,'type':'metric-value','placement':{'left':x,'top':y,'width':w,'height':h},'constraint':{'horizontal':'left','vertical':'top'},'config':{'align':'center','valign':'middle','size':size,'color':{'fixed':'#f4f5f7'},'text':{'mode':'field' if field else 'fixed','field':field or '', 'fixed':text}}}
 if bg:e['background']={'color':bg}
 return e
panels=[{'id':1,'type':'text','transparent':True,'title':'','gridPos':{'x':0,'y':0,'w':24,'h':3},'options':{'mode':'markdown','content':'**DEMO DATA · VCC units → FSP units** · 24 VCCU × 27 FSPU = **648 links** · Each cell shows **Gbit/s** (100 Gbit/s capacity). Blue intensity = rate · **× down** · **! degraded** (number = rate) · **? unknown**. **0 = up, idle.** Use VCCU / FSPU selectors for exact readings and history below. Selectors affect detail panels only; matrix order stays fixed.'}}]
for i,(title,expr,color) in enumerate([('UP','sum(vccu_fspu_link_state == bool 1)','#5794F2'),('DEGRADED','sum(vccu_fspu_link_state == bool 2)','#FFB357'),('DOWN','sum(vccu_fspu_link_state == bool 0)','#F2495C'),('UNKNOWN','sum(vccu_fspu_link_state == bool 3)','#8e8e8e')]):
 # Scrape gating happens before aggregation, so missing exporter produces No data.
 raw=expr.replace('vccu_fspu_link_state',f'(vccu_fspu_link_state and on(job,instance) ({UP}))')
 panels.append({'id':2+i,'type':'stat','title':title,'datasource':D,'gridPos':{'x':i*6,'y':3,'w':6,'h':3},'targets':[{'refId':'A','expr':raw,'instant':True,'range':False}], 'fieldConfig':{'defaults':{'color':{'mode':'fixed','fixedColor':color},'noValue':'NO DATA','decimals':0},'overrides':[]},'options':{'colorMode':'value','graphMode':'none','textMode':'auto','reduceOptions':{'calcs':['lastNotNull'],'values':False}}})
elements=[el('FSPU heading',94,0,1074,23,text='FSP units (FSPU) · columns 01–27',size=14)]
for f in range(1,28):elements.append(el(f'FSPU {f:02}',94+(f-1)*39,27,36,23,text=f'{f:02}',size=12))
ov=[];data=json.loads((R/'mock-links.json').read_text())
for v in range(1,25):
 elements.append(el(f'VCCU {v:02}',0,53+(v-1)*25,88,22,text=f'VCCU {v:02}',size=12))
 for f in range(1,28):
  name=f'VCCU{v:02} FSPU{f:02}'
  elements.append(el(name,94+(f-1)*39,53+(v-1)*25,36,22,field=name,size=10,bg={'field':name,'fixed':'#454851'}))
  maps={'-2':{'text':'×','color':'#C63B50'},'-3':{'text':'?','color':'#555963'}}
  maps.update({str(-1000-n):{'text':f'!{n}','color':'#B0750C'} for n in range(101)})
  ov.append({'matcher':{'id':'byName','options':name},'properties':[{'id':'mappings','value':[{'type':'value','options':maps},{'type':'special','options':{'match':'nan','result':{'text':'?','color':'#555963'}}}]},{'id':'links','value':[{'title':f'Inspect VCCU {v:02} → FSPU {f:02}','url':f'/d/vccu-fspu-demo?var-vccu={v:02}&var-fspu={f:02}&from=now-15m&to=now','targetBlank':False,'oneClick':True}]}]})
for e in elements:
 e['placement']['left']=round(e['placement']['left']*.65)
 e['placement']['width']=round(e['placement']['width']*.65)
 e['placement']['top']=round(e['placement']['top']*.8)
 e['placement']['height']=round(e['placement']['height']*.8)
 e['config']['size']=9 if e['config']['text']['mode']=='field' else 10

panels.append({'id':6,'type':'canvas','title':'VCCU → FSPU · link matrix · Gbit/s','description':'Each cell is one VCCU to FSPU link. Presentation encoding uses negative sentinels for explicit non-up states; independent state and rate gauges drive the detail panels.','datasource':D,'gridPos':{'x':0,'y':6,'w':24,'h':18},'targets':[q('vccu_fspu_link_display','VCCU{{vccu}} FSPU{{fspu}}')],'fieldConfig':{'defaults':{'decimals':0,'noValue':'?','color':{'mode':'thresholds'},'thresholds':{'mode':'absolute','steps':[{'value':None,'color':'#555963'},{'value':0,'color':'#193552'},{'value':20,'color':'#204D7A'},{'value':40,'color':'#245F9B'},{'value':60,'color':'#2D73B6'},{'value':80,'color':'#3987CC'}]},'mappings':[{'type':'special','options':{'match':'nan','result':{'text':'?','color':'#555963'}}}]},'overrides':ov},'options':{'inlineEditing':False,'panZoom':False,'zoomToContent':True,'showAdvancedTypes':True,'tooltip':{'mode':'single'},'root':{'name':'Root','type':'frame','elements':elements}}})
sel='vccu="${vccu}",fspu="${fspu}"'
stateMaps={str(i):{'text':t,'color':c} for i,t,c in [(0,'DOWN','#F2495C'),(1,'UP','#5794F2'),(2,'DEGRADED','#FFB357'),(3,'UNKNOWN','#8e8e8e')]}
for i,(title,metric,unit) in enumerate([('VCCU $vccu → FSPU $fspu · status','state',None),('Selected link · current rate','rate_gbps','suffix: Gbit/s'),('Selected link · capacity','capacity_gbps','suffix: Gbit/s')]):
 defs={'decimals':1,'noValue':'UNKNOWN / NO DATA','color':{'mode':'fixed','fixedColor':'#5794F2'}}
 if unit:defs['unit']=unit
 else:defs['mappings']=[{'type':'value','options':stateMaps}];defs['color']={'mode':'thresholds'}
 panels.append({'id':7+i,'type':'stat','title':title,'datasource':D,'gridPos':{'x':i*8,'y':24,'w':8,'h':4},'targets':[q('vccu_fspu_link_'+metric+'{'+sel+'}','VCCU{{vccu}} → FSPU{{fspu}}')],'fieldConfig':{'defaults':defs,'overrides':[]},'options':{'colorMode':'value','graphMode':'none','textMode':'auto','reduceOptions':{'calcs':['lastNotNull'],'values':False}}})
panels.append({'id':10,'type':'timeseries','title':'VCCU $vccu → FSPU $fspu · rate history','datasource':D,'gridPos':{'x':0,'y':28,'w':24,'h':7},'targets':[q('vccu_fspu_link_rate_gbps{'+sel+'}','VCCU{{vccu}} → FSPU{{fspu}}',instant=False)],'fieldConfig':{'defaults':{'unit':'suffix: Gbit/s','min':0,'max':100,'color':{'mode':'fixed','fixedColor':'#5794F2'},'custom':{'drawStyle':'line','lineInterpolation':'stepAfter','fillOpacity':15,'lineWidth':2,'spanNulls':False}},'overrides':[]},'options':{'legend':{'displayMode':'list','placement':'bottom'},'tooltip':{'mode':'single'}}})
variables=[]
for name,count in [('vccu',24),('fspu',27)]:
 variables.append({'name':name,'label':name.upper(),'type':'custom','query':','.join(f'{i:02}' for i in range(1,count+1)),'current':{'text':'01','value':'01'},'options':[{'text':f'{i:02}','value':f'{i:02}','selected':i==1} for i in range(1,count+1)],'multi':False,'includeAll':False})
dashboard={'uid':'vccu-fspu-demo','title':'VCCU ↔ FSPU · Link Matrix','schemaVersion':39,'version':1,'tags':['demo','synthetic','VCCU','FSPU'],'editable':True,'refresh':'5s','timezone':'browser','time':{'from':'now-15m','to':'now'},'annotations':{'list':[]},'templating':{'list':variables},'panels':panels}
matrix=next(p for p in panels if p['id']==6)
for e in matrix['options']['root']['elements']:
 if e['name'].startswith('VCCU') and ' FSPU' in e['name']:
  v=e['name'][4:6]; f=e['name'][-2:]
  e['links']=[{'title':f'Inspect VCCU {v} → FSPU {f}','url':f'/d/vccu-fspu-demo?var-vccu={v}&var-fspu={f}&from=now-15m&to=now','targetBlank':False,'oneClick':True}]
  e['oneClickMode']='link'
matrix['fieldConfig']['defaults']['mappings']=matrix['fieldConfig']['overrides'][0]['properties'][0]['value']
for override in matrix['fieldConfig']['overrides']:
 override['properties']=[p for p in override['properties'] if p['id']!='mappings']
(R/'grafana/dashboards/vccu-fspu.json').write_text(json.dumps(dashboard,indent=2)+'\n')
print('Generated 648 cells and selected-link detail panels')
