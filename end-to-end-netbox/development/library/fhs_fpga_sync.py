#!/usr/bin/python
"""Small NetBox reconciler for FPGA modules, templates and interface adoption.

NetBox 4.3's REST serializer doesn't expose UI adoption flags. Create new modules
using a template-free staging type, then attach existing interfaces and switch to
the real type. This preserves existing interface IDs/cables/IPs without duplicate
replication; no resources are deleted. The shared staging type must remain empty.
"""
from ansible.module_utils.basic import AnsibleModule
import re
import requests


def scalar(value):
    if isinstance(value,dict):
        return value.get('id',value.get('value',value))
    return value


class Sync:
    def __init__(self,params,check):
        self.url=params['netbox_url'].rstrip('/')+'/api/'
        self.check=check;self.plan=[];self.virtual=-1;self.cache={}
        self.session=requests.Session();self.session.verify=params['validate_certs']
        token=params['netbox_token'];self.session.headers.update(Authorization=('Bearer ' if token.startswith('nbt_') else 'Token ')+token)
    def request(self,method,path,**kwargs):
        response=self.session.request(method,self.url+path,timeout=30,**kwargs)
        if not response.ok:raise ValueError(f'NetBox {method} {path} failed with HTTP {response.status_code}; no automatic deletion attempted')
        return response.json()
    def find(self,path,**filters):
        key=(path,tuple(sorted(filters.items())))
        if key in self.cache:return self.cache[key]
        if any(isinstance(v,int) and v<0 for v in filters.values()):return None
        data=self.request('GET',path,params=dict(filters,limit=2))
        if data['count']>1:raise ValueError('Ambiguous NetBox object at '+path)
        value=data['results'][0] if data['results'] else None
        self.cache[key]=value
        return value
    def ensure(self,path,key,data,label):
        old=self.find(path,**key)
        changed={k:v for k,v in data.items() if (scalar(old.get(k)) if old else None)!=v}
        # Custom fields merge observations; absent optional values retain existing state.
        if 'custom_fields' in data and old:
            merged=dict(old.get('custom_fields') or {},**data['custom_fields'])
            changed.pop('custom_fields',None)
            if merged!=old.get('custom_fields'):changed['custom_fields']=merged
        if not changed:return old
        self.plan.append(dict(object=label,action='update' if old else 'create',before={k:old.get(k) for k in changed} if old else {},after=changed))
        if self.check:
            if old:result=dict(old,**changed)
            else:
                self.virtual-=1;result=dict(data,id=self.virtual)
        else:result=self.request('PATCH',path+str(old['id'])+'/',json=changed) if old else self.request('POST',path,json=data)
        self.cache[(path,tuple(sorted(key.items())))]=result
        return result


def synchronize(params,check):
    sync=Sync(params,check)
    if not params['cards']:return sync.plan
    device=sync.find('dcim/devices/',name=params['device'])
    if device is None and not check:raise ValueError('Create the parent server before applying FPGA modules')
    device_id=device['id'] if device else -1
    # Validate associations before changing any hardware objects.
    for card in params['cards']:
        existing_bay=sync.find('dcim/module-bays/',device_id=device_id,name=card['bay'])
        existing=sync.find('dcim/modules/',device_id=device_id,module_bay_id=existing_bay['id']) if existing_bay else None
        for interface in card['interfaces']:
            old=sync.find('dcim/interfaces/',device_id=device_id,name=interface['name'])
            if old and old.get('module') and (not existing or scalar(old['module'])!=existing['id']):
                raise ValueError('Interface '+interface['name']+' already belongs to another module')
    maker=sync.ensure('dcim/manufacturers/',{'name':'BittWare'},{'name':'BittWare','slug':'bittware'},'BittWare manufacturer')
    for name,kind in [('fpga_bmc_firmware','text'),('fpga_board_version','text'),('pci_endpoints','json')]:
        old=sync.find('extras/custom-fields/',name=name)
        if old and scalar(old['type'])!=kind:raise ValueError('Incompatible existing custom field '+name)
        types=list((old or {}).get('object_types') or [])
        if 'dcim.module' not in types:types.append('dcim.module')
        sync.ensure('extras/custom-fields/',{'name':name},{'name':name,'type':kind,'object_types':types},name+' field')
    staging=sync.ensure('dcim/module-types/',{'manufacturer_id':maker['id'],'model':'FHS FPGA staging (no components)'},
                        {'manufacturer':maker['id'],'model':'FHS FPGA staging (no components)'},'template-free staging type')
    if staging['id']>0:
        for endpoint in ['interface-templates','power-port-templates','power-outlet-templates','console-port-templates','console-server-port-templates','front-port-templates','rear-port-templates','module-bay-templates']:
            found=sync.request('GET','dcim/'+endpoint+'/',params={'module_type_id':staging['id'],'limit':1})
            if found['count']:raise ValueError('Staging module type must not have component templates')
    for card in params['cards']:
        module_type=sync.ensure('dcim/module-types/',{'manufacturer_id':maker['id'],'model':card['part']},
                                {'manufacturer':maker['id'],'model':card['part'],'part_number':card['part']},card['part']+' module type')
        for port in range(3):
            name=f'C{{module}}-QSFP{port}'
            sync.ensure('dcim/interface-templates/',{'module_type_id':module_type['id'],'name':name},
                        {'module_type':module_type['id'],'name':name,'type':card['interfaces'][port]['type']},card['part']+' '+name+' template')
        bay=sync.ensure('dcim/module-bays/',{'device_id':device_id,'name':card['bay']},
                        {'device':device_id,'name':card['bay'],'position':card['position']},params['device']+' '+card['bay'])
        fields={k:card[v] for k,v in [('fpga_bmc_firmware','bmc_firmware'),('fpga_board_version','version'),('pci_endpoints','pci_endpoints')] if card.get(v)}
        key={'device_id':device_id,'module_bay_id':bay['id']}
        existing=sync.find('dcim/modules/',**key)
        if not existing:
            installed=sync.ensure('dcim/modules/',key,{'device':device_id,'module_bay':bay['id'],'module_type':staging['id'],'serial':card['serial'],'status':'active','custom_fields':fields},card['bay']+' module')
        else:installed=existing
        # Update existing interfaces rather than recreating; keep enabled/type/IP/cable settings.
        for interface in card['interfaces']:
            ikey={'device_id':device_id,'name':interface['name']}
            old=sync.find('dcim/interfaces/',**ikey)
            data={'device':device_id,'name':interface['name'],'module':installed['id']}
            if not old:data.update(type=interface['type'],enabled=True)
            sync.ensure('dcim/interfaces/',ikey,data,interface['name'])
        # PATCH does not replicate module-type templates; interface IDs stay intact.
        sync.ensure('dcim/modules/',key,{'device':device_id,'module_bay':bay['id'],'module_type':module_type['id'],'serial':card['serial'],'status':'active','custom_fields':fields},card['bay']+' identity')
    return sync.plan


def main():
    module=AnsibleModule(argument_spec=dict(netbox_url=dict(required=True),netbox_token=dict(required=True,no_log=True),validate_certs=dict(type='bool',default=True),device=dict(required=True),cards=dict(type='list',elements='dict',required=True),preview=dict(type='bool',default=False)),supports_check_mode=True)
    try:
        plan=synchronize(module.params,module.check_mode or module.params['preview'])
        module.exit_json(changed=bool(plan),plan=plan,diff={'before':'Existing FPGA resources','after':plan} if module._diff else {})
    except Exception as error:
        # Never echo request headers, URLs with user info, response payloads, or tokens.
        module.fail_json(msg=str(error) if isinstance(error,ValueError) else 'FPGA reconciliation failed; check NetBox connectivity and API permissions')


if __name__=='__main__':main()
