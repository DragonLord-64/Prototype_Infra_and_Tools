from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json,math
P=Path(__file__).with_name('mock-links.json')
def metrics():
 data=json.loads(P.read_text());links=data['links'];seen=set();out=[]
 if len(links)!=648:raise ValueError('Exactly 648 links required')
 for link in links:
  v=link['vccu'];f=link['fspu'];pair=(v,f)
  if v not in [f'{n:02}' for n in range(1,25)] or f not in [f'{n:02}' for n in range(1,28)] or pair in seen:raise ValueError('Invalid/duplicate endpoints')
  seen.add(pair);state={'down':0,'up':1,'degraded':2,'unknown':3}[link['state']];rate=link['rate_gbps'];cap=link['capacity_gbps']
  if type(cap) not in (float,int) or not math.isfinite(cap) or cap<=0:raise ValueError('Invalid capacity')
  if state!=3 and (type(rate) not in (float,int) or not math.isfinite(rate) or not 0<=rate<=cap):raise ValueError('Invalid rate')
  if state==0 and rate!=0:raise ValueError('Down link must have zero rate')
  labels=f'vccu="{v}",fspu="{f}"'
  out.append(f'vccu_fspu_link_state{{{labels}}} {state}')
  out.append(f'vccu_fspu_link_capacity_gbps{{{labels}}} {cap}')
  if state!=3:out.append(f'vccu_fspu_link_rate_gbps{{{labels}}} {rate}')
  # Presentation metric only; actual status and rate remain separate above.
  display=-3 if state==3 else -2 if state==0 else -1000-round(rate) if state==2 else rate
  out.append(f'vccu_fspu_link_display{{{labels}}} {display}')
 return ('# Demo gauges; state: 0 down, 1 up, 2 degraded, 3 unknown.\n'+'\n'.join(out)+'\n').encode()
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  if self.path!='/metrics':self.send_error(404);return
  try:body=metrics()
  except Exception as e:self.send_error(500,str(e));return
  self.send_response(200);self.send_header('Content-Type','text/plain; version=0.0.4');self.end_headers();self.wfile.write(body)
if __name__=='__main__':ThreadingHTTPServer(('0.0.0.0',9102),Handler).serve_forever()
