import copy,unittest
import exporter
class VLANTests(unittest.TestCase):
    def setUp(self):self.data=exporter.load()
    def test_inventory_and_default(self):
        self.assertEqual(len(self.data['interfaces']),51)
        rows=exporter.matching_rows(self.data,55)
        self.assertEqual(len(rows),40)
        self.assertEqual(sum(r['match_kind']=='translated' for r in rows),5)
    def test_exact_interface_scope(self):
        rows=exporter.matching_rows(self.data,55);keys={(r['switch'],r['interface']) for r in rows}
        self.assertIn(('SW-A','Eth1/17'),keys)
        self.assertNotIn(('SW-A','Eth1/19'),keys)
        self.assertNotIn(('SW-B','Eth1/23'),keys)
    def test_no_switch_leakage(self):
        d=copy.deepcopy(self.data);d['interfaces'].append({'unit_group':'VCCU','unit':'VCCU extra','switch':'SW-C','interface':'Eth1/17','allowed_vlans':[155]})
        self.assertNotIn('VCCU extra',[r['unit'] for r in exporter.matching_rows(d,55)])
    def test_direct_precedence(self):
        d=copy.deepcopy(self.data);d['interfaces'][16]['allowed_vlans'].append(55)
        row=next(r for r in exporter.matching_rows(d,55) if r['unit']=='VCCU 17')
        self.assertEqual(row['match_kind'],'direct');self.assertEqual(row['translation'],'Direct')
    def test_no_reverse_or_transitive_inference(self):
        d=copy.deepcopy(self.data)
        d['translations'].append({'switch':'SW-A','interface':'Eth1/01','selected_vlan':77,'local_vlan':155})
        self.assertNotIn('VCCU 01',[r['unit'] for r in exporter.matching_rows(d,77)])
        # Direct 55 membership doesn't create an inferred 155->55 match.
        self.assertNotIn('VCCU 01',[r['unit'] for r in exporter.matching_rows(d,155)])
    def test_select_other_vlan(self):
        self.assertEqual(len(exporter.matching_rows(self.data,1)),51)
        self.assertEqual(len(exporter.matching_rows(self.data,77)),7)
        self.assertEqual(len(exporter.matching_rows(self.data,155)),4)
    def test_reload_and_metric_encoding(self):
        text=exporter.render(self.data)
        self.assertIn('selected_vlan="55"',text)
        self.assertIn('translation="55 → 155"',text)
        self.assertEqual(text.count('vlan_interface_inventory{'),51)
if __name__=='__main__':unittest.main()
