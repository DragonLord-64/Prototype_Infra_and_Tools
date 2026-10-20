"""Synthetic Cisco switch snapshot exporter; all readings reload on each scrape."""
import json
import math
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SOURCE=Path(__file__).with_name('mock-switch.json')
MODES={'access':0,'trunk':1,'private-vlan host isolated':2,
       'private-vlan host community':3,'private-vlan trunk secondary':4,
       'private-vlan promiscuous':5}

def load(path=SOURCE):
    data=json.loads(Path(path).read_text())
    if data.get('synthetic') is not True or len(data['ports'])!=32:
        raise ValueError('Expected a synthetic 32-port switch')
    profiles=data['vlan_profiles'];names=data['vlan_names']
    for profile in profiles.values():
        if not profile or any(str(vlan) not in names for vlan in profile):
            raise ValueError('Every VLAN must have a configured demo name')
    for index,port in enumerate(data['ports'],1):
        if port['number']!=index or len(port['lanes']) not in (1,4):
            raise ValueError('Ports must be ordered 1–32, with one or four actual interfaces')
        for field in ('temperature_celsius','voltage_volts'):
            value=port['transceiver'].get(field)
            if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value)):
                raise ValueError('Invalid transceiver reading')
        for lane in port['lanes']:
            if lane['mode'] not in MODES or str(lane['vlan_profile']) not in profiles:
                raise ValueError('Unknown mode or VLAN profile')
            if lane['state'] not in ('up','down','admin down','unknown'):
                raise ValueError('Unknown link state')
            for key in ('rx_bps','tx_bps','rx_packets_total','tx_packets_total','crc_errors_total','crc_errors_5m','drops_total','drops_5m'):
                v=lane[key]
                if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0:
                    raise ValueError('Invalid interface reading')
            if lane['state'] in ('down','admin down') and (lane['rx_bps'] or lane['tx_bps']):
                raise ValueError('A down demo interface cannot carry traffic')
            if lane['crc_errors_5m']>lane['crc_errors_total']:
                raise ValueError('Recent CRC count exceeds total')
            if lane['drops_5m']>lane['drops_total']:
                raise ValueError('Recent drops exceed total')
    return data

def escape(text):
    return str(text).replace('\\','\\\\').replace('\n','\\n').replace('"','\\"')

def render(data):
    out=['# All values are SYNTHETIC demonstration data.',
         '# HELP cisco_lane_snapshot Synthetic per-interface current snapshot.',
         '# TYPE cisco_lane_snapshot gauge',
         '# HELP cisco_optic_snapshot Synthetic physical-port transceiver snapshot.',
         '# TYPE cisco_optic_snapshot gauge',
         '# HELP cisco_port_snapshot Synthetic aggregate parent-port health and link state.',
         '# TYPE cisco_port_snapshot gauge',
         '# HELP cisco_lane_rx_packets_total Synthetic received packet counter.',
         '# TYPE cisco_lane_rx_packets_total counter',
         '# HELP cisco_lane_tx_packets_total Synthetic transmitted packet counter.',
         '# TYPE cisco_lane_tx_packets_total counter',
         '# HELP cisco_lane_crc_errors_total Synthetic CRC error counter.',
         '# TYPE cisco_lane_crc_errors_total counter']
    def emit(metric,labels,value):
        encoded=','.join(f'{k}="{escape(v)}"' for k,v in labels.items())
        value='NaN' if value is None else value
        out.append(f'{metric}{{{encoded}}} {value}')
    for port in data['ports']:
        base={'switch':data['switch'],'physical_port':port['number']}
        optic=port['transceiver']
        components=[optic]+port.get('components',[])
        overtemp=any(c.get('temperature_celsius') is not None and c['temperature_celsius']>=c.get('temperature_limit_celsius',75) for c in components)
        fault=overtemp or any(c.get('healthy') is False for c in components) or any(l['crc_errors_5m'] or l['drops_5m'] for l in port['lanes'])
        emit('cisco_port_snapshot',{**base,'field':'health'},0 if fault else 1)
        link_states=[l['state'] for l in port['lanes']]
        emit('cisco_port_snapshot',{**base,'field':'link'},1 if 'up' in link_states else 2 if 'unknown' in link_states else 0)
        for field in ('temperature_celsius','voltage_volts'):
            emit('cisco_optic_snapshot',{**base,'field':field},optic.get(field) if optic['present'] else None)
        dom=2 if not optic['present'] else 1 if optic.get('temperature_celsius') is not None else 0
        emit('cisco_optic_snapshot',{**base,'field':'dom_status'},dom)
        emit('cisco_optic_snapshot',{**base,'field':'lane_count'},len(port['lanes']))
        for lane_number in range(1,5):
            labels={**base,'lane':lane_number}
            if lane_number>len(port['lanes']):
                emit('cisco_lane_snapshot',{**labels,'field':'state'},4)
                continue
            lane=port['lanes'][lane_number-1]
            state={'down':0,'up':1,'admin down':2,'unknown':3}[lane['state']]
            quality=1 if lane['crc_errors_5m'] else 2 if lane['drops_5m'] else 0
            health=4 if state==1 and quality==1 else 5 if state==1 and quality==2 else state
            values={k:lane[k] for k in ('rx_bps','tx_bps','rx_packets_total','tx_packets_total','crc_errors_total','crc_errors_5m','drops_total','drops_5m')}
            values.update(state=state,health=health,quality=quality,mode=MODES[lane['mode']],vlan_profile=lane['vlan_profile'])
            for field,value in values.items():
                emit('cisco_lane_snapshot',{**labels,'field':field},value)
            for field in ('rx_packets_total','tx_packets_total','crc_errors_total'):
                emit('cisco_lane_'+field,labels,lane[field])
    return '\n'.join(out)+'\n'

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ('/health','/metrics'):
            self.send_error(404);return
        try:
            data=load();body=('ok: synthetic switch\n' if self.path=='/health' else render(data)).encode()
            code=200
        except (ValueError,KeyError,TypeError,OSError):
            body=b'Invalid synthetic switch source\n';code=503
        self.send_response(code);self.send_header('Content-Type','text/plain; version=0.0.4; charset=utf-8')
        self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def log_message(self,*args): pass

if __name__=='__main__':
    load();ThreadingHTTPServer(('0.0.0.0',9101),Handler).serve_forever()
