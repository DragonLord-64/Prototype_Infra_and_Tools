"""Small shared API client for the portable hardware/manufacturer helpers."""
import re
import hashlib
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


def ensure_manufacturers(sync,names):
    records={}
    for name in dict.fromkeys(value.strip() for value in names):
        if not name:raise ValueError('Manufacturer name cannot be empty')
        existing=sync.find('dcim/manufacturers/',name=name)
        if existing:
            records[name]=existing;continue
        slug=re.sub('[^a-z0-9]+','-',name.lower()).strip('-')[:100] or 'manufacturer'
        owner=sync.find('dcim/manufacturers/',slug=slug)
        if owner and owner['name'].strip().casefold()==name.casefold():
            records[name]=owner;continue
        if owner:
            # No alias guessing or renaming an unrelated vendor. Preserve both names.
            slug=slug[:90]+'-'+hashlib.sha256(name.encode('utf-8')).hexdigest()[:8]
            collision=sync.find('dcim/manufacturers/',slug=slug)
            if collision and collision['name']!=name:
                raise ValueError('Deterministic manufacturer slug collision; review vendor records')
        records[name]=sync.ensure('dcim/manufacturers/',{'name':name},{'name':name,'slug':slug},name+' manufacturer')
    return records
