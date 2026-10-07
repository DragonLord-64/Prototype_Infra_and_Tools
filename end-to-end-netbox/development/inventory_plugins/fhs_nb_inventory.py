"""Read-only FHS module enrichment layered on the pinned NetBox inventory plugin."""
import re
from copy import deepcopy
import yaml
from ansible_collections.netbox.netbox.plugins.inventory.nb_inventory import InventoryModule as NetBoxInventory, DOCUMENTATION as PARENT_DOCUMENTATION

doc=yaml.safe_load(PARENT_DOCUMENTATION)
doc['name']='fhs_nb_inventory'
doc['options']['plugin']['choices']=['fhs_nb_inventory']
DOCUMENTATION=yaml.safe_dump(doc,sort_keys=False)


def module_variables(modules,interfaces):
    fpga=[];nic=[];warnings=[]
    allowed=['fpga_bmc_firmware','fpga_board_version','nic_driver','nic_firmware','nic_functions','pci_endpoints']
    for module in modules:
        bay=module.get('module_bay') or {};name=bay.get('name','')
        match=re.fullmatch(r'FPGA CARD (\d+)',name)
        if not match and not name.startswith('NIC '):continue
        kind='FPGA' if match else 'NIC'
        module_type=module.get('module_type') or {};manufacturer=module_type.get('manufacturer') or {}
        entry=dict(id=module['id'],bay=name,model=module_type.get('model',''),serial=module.get('serial') or '',
                   manufacturer=manufacturer.get('name','') if isinstance(manufacturer,dict) else '',
                   custom_fields={key:deepcopy(value) for key,value in (module.get('custom_fields') or {}).items() if key in allowed},
                   interfaces=[deepcopy(interface) for interface in interfaces if (interface.get('module') or {}).get('id')==module['id']])
        if module_type.get('part_number'):entry['part_number']=module_type['part_number']
        if match:entry['card_index']=int(match.group(1));fpga.append(entry)
        else:nic.append(entry)
    fpga.sort(key=lambda entry:entry['card_index']);nic.sort(key=lambda entry:entry['bay'])
    result=dict(fhs_modules=fpga+nic,fhs_fpga_modules=fpga,fhs_nic_modules=nic)
    for index in [0,1]:
        cards=[entry for entry in fpga if entry['card_index']==index]
        if len(cards)==1 and cards[0]['serial']:result['fpga_card'+str(index)+'_sn']=cards[0]['serial']
        elif len(cards)>1:warnings.append('Multiple FPGA modules claim card index '+str(index)+'; serial alias omitted')
    if len(nic)==1 and nic[0]['serial']:result['terabox_nic0_sn']=nic[0]['serial']
    elif len(nic)>1:warnings.append('Multiple NIC modules; legacy nic0 serial alias omitted instead of guessing')
    if warnings:result['fhs_inventory_warnings']=warnings
    return result


class InventoryModule(NetBoxInventory):
    NAME='fhs_nb_inventory'

    def fetch_hosts(self):
        super().fetch_hosts()
        self.fhs_device_modules={}
        for device in self.devices_list:
            self.fhs_device_modules[device['id']]=self.get_resource_list(self.api_endpoint+'/api/dcim/modules/?limit=0&device_id='+str(device['id']))

    def _fill_host_variables(self,host,hostname):
        super()._fill_host_variables(host,hostname)
        if host.get('is_virtual'):return
        interfaces=(self.extract_interfaces(host) or []) if self.interfaces else []
        variables=module_variables(self.fhs_device_modules.get(host['id'],[]),interfaces)
        host.update(variables) # Native compose/groups can also use the enriched variables.
        for name,value in variables.items():self._set_variable(hostname,name,value)
