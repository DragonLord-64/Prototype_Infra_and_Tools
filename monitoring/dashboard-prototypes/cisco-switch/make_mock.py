import json
from pathlib import Path

root=Path(__file__).parent
data={'synthetic':True,'switch':'demo-9332d-01','model':'Nexus 9332D family demo',
 'vlan_names':{'1':'my VLAN 1','10':'Management','20':'my special VLAN','30':'Server A',
               '100':'PVLAN primary','101':'Isolated secondary','102':'Community secondary','200':'VCC','300':'FSP'},
 'vlan_profiles':{'1':[30],'2':[1,10,20],'3':[100,101],'4':[100,102],'5':[200,300],'6':[1,10,20,200,300]},'ports':[]}
for p in range(1,33):
    port={'number':p,'breakout':'4x100G','transceiver':{'present':True,'type':'QSFP-DD · demo',
          'temperature_celsius':round(39+p*.37,1),'temperature_limit_celsius':75,'voltage_volts':round(3.27+(p%5)*.01,2)},'lanes':[]}
    for lane in range(1,5):
        mode,profile=[('access',1),('trunk',2),('private-vlan host isolated',3),('private-vlan trunk secondary',3)][lane-1]
        if p%3==0: mode,profile='trunk',5
        state='up'
        if (p,lane)==(2,2): state='down'
        if (p,lane)==(3,4): state='admin down'
        if (p,lane)==(6,1): state='unknown'
        rx=(31+(p*7+lane*11)%62)*1e9 if state=='up' else 0
        tx=(18+(p*3+lane*5)%57)*1e9 if state=='up' else 0
        crc_recent=12 if (p,lane)==(1,3) else 0
        port['lanes'].append({'state':state,'mode':mode,'vlan_profile':profile,
            'rx_bps':rx,'tx_bps':tx,'rx_packets_total':int(1.2e9+p*1e7+lane*1e6),
            'tx_packets_total':int(9e8+p*5e6+lane*7e5),'crc_errors_total':218 if crc_recent else (6 if p==4 and lane==1 else 0),
            'crc_errors_5m':crc_recent,'drops_total':84 if (p,lane)==(2,3) else 0,'drops_5m':17 if (p,lane)==(2,3) else 0})
    if p==4: port['transceiver']={'present':False,'type':'Not fitted','temperature_celsius':None,'voltage_volts':None};port['lanes']=[{**l,'state':'down','rx_bps':0,'tx_bps':0} for l in port['lanes']]
    if p==5: port['transceiver']['temperature_celsius']=None;port['transceiver']['voltage_volts']=None
    if p==7: port['transceiver']['temperature_celsius']=79.2
    data['ports'].append(port)
(root/'mock-switch.json').write_text(json.dumps(data,indent=2)+'\n')
print('Created 32 physical ports, 128 interfaces; all readings synthetic')
