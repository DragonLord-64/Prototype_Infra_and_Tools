#!/usr/bin/python
"""Ensure reported vendors without downstream display-name/slug ambiguity."""
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.fhs_netbox import Sync,ensure_manufacturers

def main():
    module=AnsibleModule(argument_spec=dict(netbox_url=dict(required=True),netbox_token=dict(required=True,no_log=True),validate_certs=dict(type='bool',default=True),names=dict(type='list',elements='str',required=True)),supports_check_mode=True)
    try:
        sync=Sync(module.params,module.check_mode)
        records=ensure_manufacturers(sync,module.params['names'])
        module.exit_json(changed=bool(sync.plan),manufacturers={name:record['id'] for name,record in records.items()},plan=sync.plan)
    except Exception as error:
        module.fail_json(msg=str(error) if isinstance(error,ValueError) else 'Manufacturer resolution failed; check NetBox connectivity and API permissions')

if __name__=='__main__':main()
