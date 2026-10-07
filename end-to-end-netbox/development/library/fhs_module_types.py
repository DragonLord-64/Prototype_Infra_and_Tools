#!/usr/bin/python
"""Upsert vendor-scoped module types using manufacturer_id filters, not slug filters."""
import json
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.fhs_netbox import Sync

def synchronize(params,check):
    sync=Sync(params,check);ids={}
    for item in params['types']:
        vendor=item['manufacturer'];model=item['model']
        if vendor not in params['manufacturers']:raise ValueError('Reported manufacturer was not ensured: '+vendor)
        manufacturer=int(params['manufacturers'][vendor])
        data=dict(manufacturer=manufacturer,model=model)
        if item.get('part'):data['part_number']=item['part']
        record=sync.ensure('dcim/module-types/',dict(manufacturer_id=manufacturer,model=model),data,vendor+' '+model+' module type')
        ids[json.dumps([vendor,model])]=record['id']
    return ids,sync.plan

def main():
    module=AnsibleModule(argument_spec=dict(netbox_url=dict(required=True),netbox_token=dict(required=True,no_log=True),validate_certs=dict(type='bool',default=True),types=dict(type='list',elements='dict',required=True),manufacturers=dict(type='dict',required=True)),supports_check_mode=True)
    try:
        ids,plan=synchronize(module.params,module.check_mode)
        module.exit_json(changed=bool(plan),module_types=ids,plan=plan)
    except Exception as error:
        module.fail_json(msg=str(error) if isinstance(error,ValueError) else 'Module-type resolution failed; check NetBox connectivity and API permissions')

if __name__=='__main__':main()
