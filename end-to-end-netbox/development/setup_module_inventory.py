#!/usr/bin/env python3
"""Switch the existing FHS inventory to module enrichment, retaining vault bytes."""
import argparse
import os
from pathlib import Path
import re

def update(repo,inventory='inventory/dev_env/netbox-inv.yml'):
    repo=Path(repo);path=repo/inventory;original=path.read_text()
    text,count=re.subn(r'(?m)^plugin:[ \t]*netbox\.netbox\.nb_inventory[ \t]*(?:#.*)?$', 'plugin: fhs_nb_inventory',original)
    if not count and not re.search(r'(?m)^plugin:[ \t]*fhs_nb_inventory[ \t]*$',text):raise ValueError('Expected the existing NetBox inventory plugin')
    for key,value in [('interfaces','true'),('fetch_all','false')]:
        text,count=re.subn(r'(?m)^'+key+r':[ \t]*[^\n]*$',key+': '+value,text)
        if not count:text=text.rstrip('\n')+'\n'+key+': '+value+'\n'
    config=repo/'ansible.cfg';before=config.read_text();plugin_path='./playbooks/development/inventory_plugins'
    match=re.search(r'(?m)^inventory_plugins[ \t]*=[ \t]*([^\n]*)$',before)
    if match:
        configured=match.group(1)
        after=before if plugin_path in configured.split(os.pathsep) else before[:match.start(1)]+configured+os.pathsep+plugin_path+before[match.end(1):]
    else:
        after,count=re.subn(r'(?m)^\[defaults\][ \t]*$', '[defaults]\ninventory_plugins = '+plugin_path,before,count=1)
        if not count:raise ValueError('Expected [defaults] in ansible.cfg')
    if text!=original:path.write_text(text)
    if after!=before:config.write_text(after)
    return text!=original or after!=before

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('repo',help='Existing FHS repository root');parser.add_argument('--inventory',default='inventory/dev_env/netbox-inv.yml');args=parser.parse_args()
    print('Inventory module enrichment configured' if update(args.repo,args.inventory) else 'Inventory module enrichment already configured')
