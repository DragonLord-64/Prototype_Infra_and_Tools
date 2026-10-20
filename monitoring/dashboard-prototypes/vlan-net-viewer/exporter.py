"""Reloadable synthetic VLAN interface inventory; explicit scoped, directed translation."""
import json
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
SOURCE = Path(__file__).with_name('mock-network.json')

def load(path=SOURCE):
    data=json.loads(Path(path).read_text())
    if data.get('synthetic') is not True:
        raise ValueError('Expected explicitly synthetic source')
    catalog=data['vlans']; interfaces=data['interfaces']; seen=set()
    for vlan in catalog:
        if not str(vlan).isdigit() or not 1<=int(vlan)<=4094: raise ValueError('Invalid VLAN ID')
    for port in interfaces:
        key=(port['switch'],port['interface'])
        if key in seen: raise ValueError('Duplicate switch/interface identity')
        seen.add(key)
        if port['unit_group'] not in ('VCCU','FSPU'): raise ValueError('Unknown endpoint group')
        if not port['allowed_vlans'] or any(str(v) not in catalog for v in port['allowed_vlans']): raise ValueError('Unknown allowed VLAN')
    for rule in data['translations']:
        if (rule['switch'],rule['interface']) not in seen: raise ValueError('Unknown translation interface')
        if any(str(rule[k]) not in catalog for k in ('selected_vlan','local_vlan')): raise ValueError('Unknown translation VLAN')
    return data

def matching_rows(data, selected):
    """Direct membership first; otherwise only explicit forward rules on this exact interface."""
    selected=int(selected); rows=[]
    for port in data['interfaces']:
        if selected in port['allowed_vlans']:
            rows.append({**port,'selected_vlan':selected,'actual_vlan':selected,'match_kind':'direct','translation':'Direct'})
            continue
        local=sorted({r['local_vlan'] for r in data['translations'] if r['switch']==port['switch'] and r['interface']==port['interface'] and r['selected_vlan']==selected and r['local_vlan'] in port['allowed_vlans']})
        # One interface appears once, even if multiple explicit local translations are present.
        if local:
            rows.append({**port,'selected_vlan':selected,'actual_vlan':','.join(map(str,local)),'match_kind':'translated','translation':f'{selected} → '+', '.join(map(str,local))})
    return rows

def escape(value): return str(value).replace('\\','\\\\').replace('\n','\\n').replace('"','\\"')
def render(data):
    lines=['# All values are SYNTHETIC demonstration configuration.', '# TYPE vlan_catalog_info gauge','# TYPE vlan_interface_inventory gauge','# TYPE vlan_interface_match gauge']
    def emit(name,labels,value):
        lines.append(name+'{'+','.join(f'{k}="{escape(v)}"' for k,v in labels.items())+'} '+str(value))
    for vlan,name in data['vlans'].items(): emit('vlan_catalog_info',{'vlan':vlan,'vlan_name':name},1)
    for port in data['interfaces']:
        emit('vlan_interface_inventory',{k:port[k] for k in ('unit_group','unit','switch','interface')},1)
    for selected in data['vlans']:
        for row in matching_rows(data,selected):
            labels={k:row[k] for k in ('unit_group','unit','switch','interface','selected_vlan','actual_vlan','match_kind','translation')}
            labels['attachment']=row['switch']+' · '+row['interface']
            labels['allowed_vlans']=', '.join(map(str,row['allowed_vlans']))
            labels['allowed_names']=' | '.join(f'{v}: {data["vlans"][str(v)]}' for v in row['allowed_vlans'])
            emit('vlan_interface_match',labels,0 if row['match_kind']=='direct' else 1)
    return '\n'.join(lines)+'\n'
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ('/metrics','/health'): self.send_error(404);return
        try:
            data=load(); body=(render(data) if self.path=='/metrics' else 'ok: synthetic VLAN inventory\n').encode();code=200
        except (ValueError,KeyError,TypeError,OSError): body=b'Invalid synthetic VLAN inventory\n';code=503
        self.send_response(code);self.send_header('Content-Type','text/plain; version=0.0.4; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def log_message(self,*args):pass
if __name__=='__main__':
    load();ThreadingHTTPServer(('0.0.0.0',9103),Handler).serve_forever()
