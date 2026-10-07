import unittest
from unittest.mock import patch
from test_fhs import sync,API,filters
class TestManufacturers(unittest.TestCase):
 def ensure(self,api,names,check=False):
  with patch.object(sync.requests,'Session',return_value=api):
   client=sync.Sync(dict(netbox_url='http://test.invalid',netbox_token='synthetic',validate_certs=False),check)
   return sync.ensure_manufacturers(client,names),client.plan
 def test_finisar_absent_created_then_reused_by_id(self):
  api=API();records,plan=self.ensure(api,['Finisar Corp']);self.assertTrue(plan);ident=records['Finisar Corp']['id']
  before=len(api.writes);again,plan=self.ensure(api,['Finisar Corp']);self.assertFalse(plan);self.assertEqual(again['Finisar Corp']['id'],ident);self.assertEqual(len(api.writes),before)
 def test_existing_vendor_custom_slug_preserved(self):
  api=API();api.data['dcim/manufacturers/']=[dict(id=33,name='Finisar Corp',slug='finisar-brand')]
  records,plan=self.ensure(api,['Finisar Corp']);self.assertEqual(records['Finisar Corp']['id'],33);self.assertFalse(plan);self.assertFalse(api.writes)
 def test_slug_collision_does_not_rename_or_invent_alias(self):
  api=API();existing=dict(id=44,name='Another Vendor',slug='finisar-corp');api.data['dcim/manufacturers/']=[existing]
  records,plan=self.ensure(api,['Finisar Corp']);self.assertNotEqual(records['Finisar Corp']['id'],44);self.assertEqual(existing['name'],'Another Vendor');self.assertNotEqual(records['Finisar Corp']['slug'],'finisar-corp')
  self.assertFalse(self.ensure(api,['Finisar Corp'])[1])
 def test_case_only_slug_owner_reused_without_rename(self):
  api=API();api.data['dcim/manufacturers/']=[dict(id=55,name='FINISAR CORP',slug='finisar-corp')]
  records,plan=self.ensure(api,['Finisar Corp']);self.assertEqual(records['Finisar Corp']['id'],55);self.assertFalse(plan)
 def test_preview_does_not_write_and_type_ids_are_vendor_scoped(self):
  api=API();records,plan=self.ensure(api,['Finisar Corp'],True);self.assertTrue(plan);self.assertFalse(api.writes)
  items=[dict(manufacturer='Cisco',model='SAME'),dict(manufacturer='Finisar Corp',model='SAME'),dict(manufacturer='Cisco',model='SAME')]
  self.assertEqual(len(filters.unique_module_types(items)),2)
  ids=filters.module_type_ids([dict(item=items[0],module_type={'id':7}),dict(item=items[1],module_type={'id':8})]);self.assertEqual(len(ids),2)
if __name__=='__main__':unittest.main()
