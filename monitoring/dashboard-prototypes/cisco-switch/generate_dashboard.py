import json
import copy
from pathlib import Path

ROOT=Path(__file__).parent
config=json.loads((ROOT/'mock-switch.json').read_text())
DS={'type':'prometheus','uid':'server-health-demo-prometheus'}
panels=[]
LINKS={'0':{'text':'Down','color':'red'},'1':{'text':'Up','color':'green'},
       '2':{'text':'Admin down','color':'#8e8e8e'},'3':{'text':'Unknown','color':'#8e8e8e'},
       '4':{'text':'Up · CRC','color':'orange'},'5':{'text':'Up · drops','color':'orange'}}
MODE={str(i):{'text':text} for i,text in enumerate(['Access','Trunk','PVLAN host · isolated','PVLAN host · community','PVLAN trunk · secondary','PVLAN promiscuous'])}
VLANS={key:{'text':'VLANs: '+' | '.join(f'{v} · {config["vlan_names"][str(v)]}' for v in values)} for key,values in config['vlan_profiles'].items()}

def element(name,x,y,w,h,text=None,field=None,size=14,color='text',background=None,border=None):
    el={'name':name,'type':'metric-value','placement':{'left':x,'top':y,'width':w,'height':h},
        'constraint':{'horizontal':'left','vertical':'top'},
        'config':{'align':'left','valign':'middle','size':size,'color':{'fixed':color},
                  'text':{'mode':'field' if field else 'fixed','field':field or '', 'fixed':text or ''}}}
    if field and not background: el['config']['color']={'field':field,'fixed':color}
    if background:
        el['background']={'color':background}
        if field: el['config']['color']={'fixed':'#111217'}
    if not field and text=='': el['type']='rectangle'
    if border: el['border']={'width':1,'radius':5,'color':{'fixed':border}}
    return el

def override(name,unit=None,decimals=None,mappings=None,thresholds=None):
    properties=[]
    if unit: properties.append({'id':'unit','value':unit})
    if decimals is not None: properties.append({'id':'decimals','value':decimals})
    if mappings: properties.append({'id':'mappings','value':[{'type':'value','options':mappings}]})
    if thresholds: properties += [{'id':'color','value':{'mode':'thresholds'}},{'id':'thresholds','value':{'mode':'absolute','steps':[{'value':v,'color':c} for v,c in thresholds]}}]
    return {'matcher':{'id':'byName','options':name},'properties':properties}

def canvas(title,elements,targets,overrides,x,y,w,h,repeat=None):
    panel={'id':len(panels)+1,'type':'canvas','title':title,'datasource':DS,'gridPos':{'x':x,'y':y,'w':w,'h':h},
        'targets':targets,'fieldConfig':{'defaults':{'noValue':'N/A','color':{'mode':'fixed','fixedColor':'text'},
            'mappings':[{'type':'special','options':{'match':'nan','result':{'text':'N/A','color':'#8e8e8e'}}}]},'overrides':overrides},
        'options':{'inlineEditing':False,'panZoom':False,'zoomToContent':True,'showAdvancedTypes':True,
            'tooltip':{'mode':'single'},'root':{'name':'Root','type':'frame','elements':elements}}}
    if repeat: panel.update(repeat=repeat,repeatDirection='h',maxPerRow=2)
    panels.append(panel)

def query(ref,metric,legend,filter_text=''):
    selector='switch="demo-9332d-01"'+(','+filter_text if filter_text else '')
    return {'refId':ref,'expr':f'{metric}{{{selector}}} and on(job, instance) (up{{job="cisco-switch-demo"}} == 1)','instant':True,'range':False,'legendFormat':legend}

panels.append({'id':1,'type':'text','title':'','transparent':True,'gridPos':{'x':0,'y':0,'w':24,'h':2},
 'options':{'mode':'markdown','content':'**CISCO 9332D · DEMO DATA** — 32 ports · 128 interfaces. Parent: green = healthy, red = fault. Each interface: link status + Good / Error / Drop. Click a port for details.'}})
elements=[];overrides=[]
for p in range(1,33):
    col=(p-1)%8;row=(p-1)//8;x=col*145;y=row*112
    port_links=[{'title':f'Port {p:02d} details','url':f'/d/cisco-switch-detail?var-port={p}','targetBlank':False,'oneClick':True}]
    first=len(elements)
    health=f'P{p} health';port_link=f'P{p} link'
    elements.append(element(f'P{p} container',x,y,139,106,text='',background={'field':health,'fixed':'#444444'},border='#41444c'))
    elements.append(element(f'P{p} label',x+6,y+2,48,21,text=f'Port {p:02d}',size=11,color='#111217'))
    elements.append(element(f'P{p} link',x+55,y+2,34,21,field=port_link,size=11,color='#111217'))
    elements[-1]['config']['color']={'fixed':'#111217'}
    elements.append(element(f'P{p} health',x+91,y+2,42,21,field=health,size=11,color='#111217'))
    elements[-1]['config']['color']={'fixed':'#111217'}
    overrides.append(override(health,mappings={'0':{'text':'Fault','color':'red'},'1':{'text':'OK','color':'green'}},thresholds=[(None,'red'),(1,'green')]))
    overrides.append(override(port_link,mappings={'0':{'text':'Down'},'1':{'text':'Up'},'2':{'text':'?'}}))
    for lane in range(1,5):
        sx=x+6+((lane-1)%2)*65;sy=y+27+((lane-1)//2)*37
        field=f'P{p} L{lane} state';quality=f'P{p} L{lane} quality'
        elements.append(element(f'P{p} L{lane} box',sx,sy,61,34,text='',background={'fixed':'#202226'},border='#41444c'))
        elements.append(element(f'P{p} L{lane} link',sx+4,sy,54,17,field=field,size=11))
        elements.append(element(f'P{p} L{lane} quality',sx+4,sy+16,54,17,field=quality,size=11))
        overrides.append(override(field,mappings={'0':{'text':f'{lane} Down','color':'red'},'1':{'text':f'{lane} Up','color':'green'},'2':{'text':f'{lane} Down','color':'#8e8e8e'},'3':{'text':f'{lane} ?','color':'#8e8e8e'},'4':{'text':'N/A','color':'#8e8e8e'}}))
        overrides.append(override(quality,mappings={'0':{'text':'Good','color':'green'},'1':{'text':'Error','color':'red'},'2':{'text':'Drop','color':'orange'}}))
    for item in elements[first:]: item['links']=copy.deepcopy(port_links)
canvas('All 32 ports · physical health and interface status',elements,
 [query('A','cisco_lane_snapshot','P{{physical_port}} L{{lane}} {{field}}','field=~"state|quality"'),
  query('B','cisco_port_snapshot','P{{physical_port}} {{field}}')],overrides,0,2,24,14)
overview_panels=copy.deepcopy(panels)

elements=[];overrides=[]
elements.append(element('DOM label',8,4,528,22,text='SHARED TRANSCEIVER · parent physical port',size=14))
elements.append(element('Temperature label',8,32,90,20,text='Temperature',size=12))
elements.append(element('Temperature',100,29,112,26,field='Optics / temperature_celsius',size=18))
elements.append(element('Voltage label',225,32,56,20,text='Voltage',size=12))
elements.append(element('Voltage',285,29,100,26,field='Optics / voltage_volts',size=18))
elements.append(element('DOM status',392,29,155,26,field='Optics / dom_status',size=12))
overrides += [override('Optics / temperature_celsius','celsius',1,thresholds=[(None,'green'),(75,'orange'),(85,'red')]),
              override('Optics / voltage_volts','volt',2),
              override('Optics / dom_status',mappings={'0':{'text':'DOM unavailable'},'1':{'text':'DOM available'},'2':{'text':'Module not fitted'}})]
for lane in range(1,5):
    x=8+((lane-1)%2)*276;y=74+((lane-1)//2)*280
    base=f'Lane {lane} / '
    elements.append(element(f'L{lane} box',x,y,264,272,text='',background={'fixed':'#202226'},border='#41444c'))
    elements.append(element(f'L{lane} title',x+10,y+6,132,22,text=f'Interface /{lane}',size=14))
    elements.append(element(f'L{lane} state',x+142,y+5,112,24,field=base+'health',size=12,background={'field':base+'health','fixed':'#444444'}))
    elements.append(element(f'L{lane} mode',x+10,y+34,244,24,field=base+'mode',size=12))
    elements.append(element(f'L{lane} vlans',x+10,y+61,244,76,field=base+'vlan_profile',size=12))
    for label,field,offset in [('RX','rx_bps',142),('TX','tx_bps',169),('RX packets','rx_packets_total',198)]:
        elements.append(element(f'L{lane} {label} label',x+10,y+offset,86,22,text=label,size=12))
        elements.append(element(f'L{lane} {label}',x+98,y+offset,156,22,field=base+field,size=15 if field.endswith('bps') else 12))
    elements.append(element(f'L{lane} CRC label',x+10,y+245,110,20,text='CRC 5m / total',size=11))
    elements.append(element(f'L{lane} drops label',x+10,y+220,110,20,text='Drops 5m / total',size=11))
    elements.append(element(f'L{lane} drops recent',x+121,y+220,42,20,field=base+'drops_5m',size=12))
    elements.append(element(f'L{lane} drops slash',x+166,y+220,12,20,text='/',size=12))
    elements.append(element(f'L{lane} drops total',x+183,y+220,70,20,field=base+'drops_total',size=12))
    elements.append(element(f'L{lane} CRC recent',x+121,y+245,42,20,field=base+'crc_errors_5m',size=12))
    elements.append(element(f'L{lane} CRC slash',x+166,y+245,12,20,text='/',size=12))
    elements.append(element(f'L{lane} CRC total',x+183,y+245,70,20,field=base+'crc_errors_total',size=12))
    overrides += [override(base+'health',mappings=LINKS,thresholds=[(None,'red'),(1,'green'),(2,'#8e8e8e'),(4,'orange')]),
                  override(base+'mode',mappings=MODE),override(base+'vlan_profile',mappings=VLANS),
                  override(base+'rx_bps','bps',1),override(base+'tx_bps','bps',1),
                  override(base+'rx_packets_total','short',2),override(base+'tx_packets_total','short',2),
                  override(base+'crc_errors_5m','short',0,thresholds=[(None,'green'),(1,'orange')]),
                  override(base+'crc_errors_total','short',0),
                  override(base+'drops_5m','short',0,thresholds=[(None,'green'),(1,'orange')]),override(base+'drops_total','short',0)]
for item in elements:
    item['placement']['top']=round(item['placement']['top']*.85)
    item['placement']['height']=round(item['placement']['height']*.85)
canvas('Ethernet1/$port · physical port and breakout interfaces',elements,
 [query('A','cisco_lane_snapshot','Lane {{lane}} / {{field}}','physical_port=~"${port:regex}"'),
  query('B','cisco_optic_snapshot','Optics / {{field}}','physical_port=~"${port:regex}"')],overrides,0,16,12,16,repeat='port')

dashboard={'uid':'cisco-switch-demo','title':'Cisco 9332D · Ports and Breakouts','schemaVersion':39,'version':1,
 'tags':['demo','synthetic','cisco','switch','breakout'],'editable':True,'refresh':'5s','timezone':'browser',
 'time':{'from':'now-15m','to':'now'},'annotations':{'list':[]},
 'templating':{'list':[{'name':'port','label':'Port(s)','type':'custom','query':','.join(map(str,range(1,33))),
   'multi':True,'includeAll':True,'allValue':'.*','current':{'text':['1','2'],'value':['1','2']},
   'options':[{'text':str(p),'value':str(p),'selected':p in (1,2)} for p in range(1,33)]}]},'panels':panels}
target=ROOT/'grafana/dashboards/cisco-switch.json';target.parent.mkdir(parents=True,exist_ok=True)
detail=copy.deepcopy(dashboard);detail['uid']='cisco-switch-detail';detail['title']='Cisco 9332D · Port Details'
detail['panels']=[copy.deepcopy(panels[0]),copy.deepcopy(panels[-1])]
detail['panels'][0]['options']['content']='**PORT DETAIL · DEMO DATA** — Shared optics appear once above each set of interfaces. [Back to all32 ports](/d/cisco-switch-demo).'
detail['panels'][1]['gridPos']['y']=2
detail['templating']['list'][0]['current']={'text':['1'],'value':['1']}
for option in detail['templating']['list'][0]['options']:option['selected']=option['value']=='1'
(ROOT/'grafana/dashboards/cisco-switch-detail.json').write_text(json.dumps(detail,indent=2)+'\n')
dashboard['panels']=overview_panels;dashboard['templating']={'list':[]}
target.write_text(json.dumps(dashboard,indent=2)+'\n')
print('Generated compact32-port /128-interface overview and separate click-through detail dashboard')
