"""Acceptance checks against the captured export schema and generated views."""
import importlib.util
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("switch_dashboard", ROOT/"switch/generate_dashboard.py")
switch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(switch)


class SwitchDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = json.loads((ROOT/"sources/fixtures/switch.json").read_text())["data"]["result"]
        cls.ports = switch.topology(cls.results)
        cls.overview, cls.detail = switch.build(cls.ports)

    def test_actual_mixed_breakouts_and_auxiliary_ports(self):
        self.assertEqual(list(self.ports), list(range(1,35)))
        self.assertEqual(sum(map(len,self.ports.values())),62)
        self.assertEqual(self.ports[1],["eth1/1/1","eth1/1/2","eth1/1/3","eth1/1/4"])
        self.assertEqual(self.ports[3],["eth1/3/1","eth1/3/2"])
        self.assertEqual(self.ports[33],["eth1/33"])
        self.assertEqual(len({v for lanes in self.ports.values() for v in lanes}),62)

    def test_unknown_dn_fails_instead_of_silently_losing_interface(self):
        with self.assertRaises(ValueError):
            switch.topology([{"metric":{"__name__":"nexus_interfaces_ifIndex","dn":"unexpected"}}])

    def test_link_uses_exported_operational_labels(self):
        actual = [row["metric"] for row in self.results if row["metric"]["__name__"]=="nexus_interfaces_ifIndex"]
        self.assertEqual(sum(x["operSt"]=="up" for x in actual),35)
        self.assertEqual(sum(x["operSt"]=="down" for x in actual),27)
        expr=switch.link_expr()
        self.assertIn('operSt="up"',expr)
        self.assertIn('operSt="down"',expr)
        self.assertNotIn("octets",expr)
        self.assertNotIn("operStQualCode",expr)

    def test_port_one_selector_does_not_match_port_eleven(self):
        target=self.detail["panels"][1]["targets"][0]["expr"]
        pattern=re.search(r'dn=~"([^"]+)"',target)[1]
        pattern=pattern.replace("${port:regex}","1").replace("\\\\","\\")
        matched=[row for row in self.results if row["metric"]["__name__"]=="nexus_interfaces_ifIndex" and re.fullmatch(pattern,row["metric"]["dn"])]
        self.assertEqual(len(matched),4)
        self.assertTrue(all("eth1/1/" in row["metric"]["dn"] for row in matched))

    def test_recent_faults_do_not_use_lifetime_nonzero_counts(self):
        self.assertIn("increase(nexus_interfaces_cRCAlignErrors",switch.quality_expr())
        self.assertIn("increase(nexus_interfaces_dropEvents",switch.quality_expr())
        # The supplied old counter is nonzero while an unchanged replay has no new event.
        counts=[float(row["value"][1]) for row in self.results if row["metric"]["__name__"]=="nexus_interfaces_cRCAlignErrors"]
        self.assertGreater(max(counts),0)
        self.assertIn("unless on(source,interface)",switch.quality_expr())
        self.assertIn("or on(port)",switch.parent_health_expr())
        self.assertIn("+ 2",switch.parent_health_expr())

    def test_metadata_and_measurements_do_not_invent_dom_or_vlan_names(self):
        serialized=json.dumps(self.detail)
        self.assertIn("Allowed VLAN IDs",serialized)
        self.assertIn("Access VLAN",serialized)
        self.assertNotIn("cisco_optic_snapshot",serialized)
        self.assertNotIn("cisco_lane_snapshot",serialized)
        self.assertNotIn('"VLAN name"',serialized)
        rates=self.detail["panels"][2]["targets"]
        self.assertEqual(len(rates),2)
        for target in rates:
            self.assertIn("rate(nexus_interfaces_octets",target["expr"])
            self.assertIn(" * 8",target["expr"])

    def test_live_and_replay_use_correct_availability_and_datasource(self):
        for dashboard in (self.overview,self.detail):
            for panel in dashboard["panels"]:
                self.assertEqual(panel["datasource"]["uid"],"export-backed-prometheus")
                for target in panel["targets"]:
                    self.assertIn('up{job="replay-switch"}',target["expr"])
        live=switch.build(self.ports,live=True)
        for dashboard in live:
            self.assertNotIn("export replay",dashboard["title"])
            for panel in dashboard["panels"]:
                for target in panel["targets"]:
                    self.assertNotIn("replay-switch",target["expr"])
                    self.assertIn('up{job=~"$job",instance=~"$instance"}',target["expr"])
                    self.assertEqual(panel["datasource"]["uid"], "${ds}")

    def test_live_filters_and_detail_links_preserve_selection(self):
        for dashboard in switch.build(self.ports, live=True):
            names = [v["name"] for v in dashboard["templating"]["list"]]
            self.assertEqual(names[:4], ["ds", "job", "switch", "instance"])
            serialized = json.dumps(dashboard)
            self.assertNotIn("demo-switch-01", serialized)
            self.assertNotRegex(serialized, r"\$\{(?:switch|job|instance):regex\}")
            self.assertIn("./d/switch-export-", serialized)
            self.assertIn('target="_blank"', dashboard["panels"][0]["options"]["content"])
            for panel in dashboard["panels"]:
                if panel["type"] == "canvas":
                    self.assertTrue(all(link["targetBlank"] for el in panel["options"]["root"]["elements"] for link in el.get("links", [])))
            self.assertNotIn("../switch-export-", serialized)
            self.assertIn("var-ds=${ds:percentencode}", serialized)
            self.assertIn("var-instance=${instance:percentencode}", serialized)
            self.assertNotRegex(serialized, r'(?<!\.)/d/switch-export-')
            self.assertEqual(dashboard, json.loads((ROOT / "live-import" / (dashboard["uid"]+".json")).read_text()))

    def test_canvas_fits_view_and_backgrounds_have_no_placeholder_text(self):
        board=next(p for p in self.overview["panels"] if p["type"]=="canvas")
        self.assertTrue(board["options"]["panZoom"])
        self.assertTrue(board["options"]["zoomToContent"])
        backgrounds=[el for el in board["options"]["root"]["elements"] if el["name"].endswith(("background","box"))]
        self.assertEqual(len(backgrounds),34+62)
        self.assertTrue(all(el["type"]=="rectangle" for el in backgrounds))
        for target,label in zip(board["targets"],["interface","interface","port"]):
            self.assertIn(f"or on({label}) (label_replace(vector(",target["expr"])


def promtool_tests():
    """Counter histories exercise real PromQL, including reset-aware increase()."""
    histories=[]
    for port,crc,drops,state in [
        (1,"0 0 0 0 0 1","0 0 0 0 0 1","up"),
        (2,"0 0 0 0 0 0","0 0 0 0 0 1","down"),
        (3,"5 5 5 5 5 5","0 0 0 0 0 0","unknown"),
    ]:
        for metric,values,suffix,extra in [
            ("nexus_interfaces_cRCAlignErrors",crc,"dbgEtherStats",{}),
            ("nexus_interfaces_dropEvents",drops,"dbgEtherStats",{}),
            ("nexus_interfaces_ifIndex","100 100 100 100 100 100","phys",{"operSt":state}),
        ]:
            labels={"source":"demo-switch-01","instance":"demo:9273","job":"switch-telegraf",
                    "dn":f"sys/intf/phys-[eth1/{port}]/{suffix}",**extra}
            series=metric+"{"+",".join(k+"="+json.dumps(v) for k,v in labels.items())+"}"
            histories.append({"series":series,"values":values})
    checks=[]
    for expr,label,values in [
        (switch.quality_expr(),"interface",[1,2,0]),
        (switch.parent_health_expr(),"port",[0,0,2]),
        (switch.link_expr(),"interface",[1,0,2]),
    ]:
        checks.append({"expr":f"max by({label}) ({expr})".replace("$switch","demo-switch-01"),
                       "eval_time":"5m","exp_samples":[
                           {"labels":"{"+label+"="+json.dumps(f"eth1/{port}" if label=="interface" else str(port))+"}","value":value}
                           for port,value in enumerate(values,1)]})
    fixture=json.loads((ROOT/"sources/fixtures/switch.json").read_text())["data"]["result"]
    dashboard,_=switch.build(switch.topology(fixture))
    board=next(panel for panel in dashboard["panels"] if panel["type"]=="canvas")
    for target,unknown,count in zip(board["targets"],[2,3,2],[62,62,34]):
        checks.append({"expr":f'sum(({target["expr"]}) == bool {unknown})'.replace("$switch","demo-switch-01"),
                       "eval_time":"5m","exp_samples":[{"labels":"{}","value":count}]})
    return {"rule_files":[],"evaluation_interval":"1m","tests":[{
        "interval":"1m","input_series":histories,"promql_expr_test":checks}]}


if __name__=="__main__":
    if "--promtool-json" in sys.argv:
        print(json.dumps(promtool_tests()))
    else:
        unittest.main()
