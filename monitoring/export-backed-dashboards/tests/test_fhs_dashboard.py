"""FHS metric contract and executable PromQL health acceptance cases.

Run this file directly to write the promtool test suite; run unittest normally for
the static checks. Promtool evaluates the dashboard's real expressions.
"""
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("fhs_dashboard", ROOT / "fhs/generate_dashboard.py")
fhs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fhs)


def acceptance_cases():
    """Expected behavior is specified independently of the PromQL implementation."""
    by_title = {c["title"]: c for c in fhs.COMPONENTS}
    base = {"fpga_temperature_celcius": 45, "front_temperature_celcius": 35, "fpga_fabric_temperature_celcius": 50,
            "fpga_ftile_temperature_celcius": 52, "fpga_bmc_temperature_celcius": 60,
            "total_input_power_watts": 87, "num_metrics_total": 21,
            "num_metrics_unavailable": 0}
    cases = [
        ("complete cool card is healthy", "FPGA 0", base, 1, 0),
        ("complete warm card is degraded", "FPGA 0", {**base, "fpga_temperature_celcius": 75}, 1, 1),
        ("partial warm card is unknown", "FPGA 0", {**base, "fpga_temperature_celcius": 75, "num_metrics_unavailable": 3}, 1, 3),
        ("missing required power is unknown", "FPGA 0", {k: v for k, v in base.items() if k != "total_input_power_watts"}, 1, 3),
        ("failure wins over partial coverage", "FPGA 0", {**base, "fpga_temperature_celcius": 95, "num_metrics_unavailable": 3}, 1, 2),
        ("exporter down hides old good values", "FPGA 0", base, 0, 3),
        ("missing source up is unknown", "FPGA 0", base, None, 3),
        ("zero fan with partial source is failed", "Fan 1", {"fan1_rpm": 0, "fsc_temperature_celcius": 45, "num_metrics_total": 8, "num_metrics_unavailable": 5}, 1, 2),
        ("unverified PSU flag zeros are not healthy", "PSU 1", {"sts_psu1": 0, "sts_psu1_fan": 0, "sts_psu1_ac_lost": 0, "num_metrics_total": 8, "num_metrics_unavailable": 0}, 1, 3),
        ("CPU temperature failure wins over unverified flags", "CPU", {"cpu_temperature_celcius": 95, "prochot_cpu": 0, "cpu1_thermtrip": 0, "sts_cpu_mce": 0, "num_metrics_total": 4, "num_metrics_unavailable": 0}, 1, 2),
        ("NIC temperature alone cannot prove complete health", "NIC", {"nic_temperature_celcius": 60}, 1, 3),
        ("missing DIMM is unknown", "DIMM K1", {"num_metrics_total": 8, "num_metrics_unavailable": 0}, 1, 3),
    ]
    tests = []
    for title, component_title, metrics, up, expected in cases:
        c = by_title[component_title]
        inputs = [{"series": f'{name}{{node_name="demo-server-01",source="{c["source"]}",job="fhs-exporter"}}', "values": f"{value}+0x12"} for name, value in metrics.items()]
        if up is not None:
            inputs.append({"series": 'up{job="replay-fhs",instance="replay:9100"}', "values": f"{up}+0x12"})
        tests.append({"name": title, "interval": "5s", "input_series": inputs,
                      "promql_expr_test": [{"expr": fhs.component_query(c).replace("$node", "demo-server-01"), "eval_time": "1m", "exp_samples": [{"labels": "{}", "value": expected}]}]})
    return {"rule_files": [], "evaluation_interval": "5s", "tests": tests + live_acceptance_cases()}


def live_acceptance_cases():
    dashboard = fhs.build_dashboard(live=True)
    panels = dashboard["panels"]
    expressions = {p["title"]: panels[i-1]["targets"][0]["expr"] for i,p in enumerate(panels) if p["title"] in {c["title"] for c in fhs.COMPONENTS}}
    variables = {"node": "selected", "job": "hardware-custom", "instance": "selected:9110", "node_job": "node-custom", "node_instance": "selected:9100"}
    def series(name, value, node=False, **extra):
        labels = {"node_name": "selected", "job": "node-custom" if node else "hardware-custom", "instance": "selected:9100" if node else "selected:9110", **extra}
        return {"series": name+"{"+",".join(k+"="+json.dumps(v) for k,v in labels.items())+"}", "values": f"{value}+0x12"}
    def case(name, component, inputs, expected):
        expression = expressions[component]
        for key, value in sorted(variables.items(), key=lambda item: -len(item[0])):
            expression = expression.replace("$"+key, value)
        return {"name": name, "interval": "5s", "input_series": inputs,
                "promql_expr_test": [{"expr": expression, "eval_time": "1m", "exp_samples": [{"labels": "{}", "value": expected}]}]}
    cool_card = {"fpga_temperature_celcius": 45, "front_temperature_celcius": 35, "fpga_fabric_temperature_celcius": 50,
                 "fpga_ftile_temperature_celcius": 52, "fpga_bmc_temperature_celcius": 60,
                 "total_input_power_watts": 87, "num_metrics_total": 21, "num_metrics_unavailable": 0}
    card = [series(k,v,source="FPGA0") for k,v in cool_card.items()]
    memory = [series("num_metrics_unavailable",0,source="DIMM"), series("num_metrics_total",8,source="DIMM"),
              series("ddr5_a1_temperature_celcius",40,source="DIMM"), series("ddr5_k1_temperature_celcius",95,source="DIMM")]
    drive = [series("node_hwmon_temp_celsius",40,node=True,chip="nvme_nvme0",sensor="temp1"),
             series("node_hwmon_temp_celsius",44,node=True,chip="nvme_nvme0",sensor="temp2")]
    return [
        case("live custom jobs isolate selected server and instance", "FPGA 0", card + [series("up",1),
             series("fpga_temperature_celcius",99,source="FPGA0",instance="other:9110"),
             series("fpga_temperature_celcius",99,source="FPGA0",node_name="other")], 0),
        case("another endpoint UP cannot hide selected endpoint DOWN", "FPGA 0", card + [series("up",0), series("up",1,instance="other:9110")], 3),
        case("DIMM K1 heat does not contaminate DIMM A1", "DIMM A1", memory+[series("up",1)], 0),
        case("DIMM K1 heat is shown on K1", "DIMM K1", memory+[series("up",1)], 2),
        case("absent DIMM K1 remains unknown", "DIMM K1", [x for x in memory if not x["series"].startswith("ddr5_k1")]+[series("up",1)], 3),
        case("NVMe non-live controller fails with observed temperatures", "NVMe 0", drive+[series("up",1,node=True),series("node_nvme_info",1,node=True,device="nvme0",state="dead")], 2),
        case("NVMe missing controller remains unknown", "NVMe 0", drive+[series("up",1,node=True)], 3),
        case("other NVMe heat does not contaminate selected drive", "NVMe 0", drive+[series("up",1,node=True),series("node_nvme_info",1,node=True,device="nvme0",state="live"),series("node_hwmon_temp_celsius",99,node=True,chip="nvme_nvme1",sensor="temp1")], 0),
    ]


class FHSContract(unittest.TestCase):
    def test_no_invented_physical_components(self):
        titles = [c["title"] for c in fhs.COMPONENTS]
        self.assertEqual(len(titles), 21)
        self.assertEqual([t for t in titles if t.startswith("DIMM ")], [f"DIMM {s}1" for s in "ABCEGHIK"])
        self.assertEqual([t for t in titles if t.startswith("NVMe ")], ["NVMe 0", "NVMe 1"])
        self.assertEqual([t for t in titles if t.startswith("Fan ")], ["Fan 1", "Fan 2"])
        self.assertEqual(titles[:2], ["FPGA 0", "FPGA 1"])

    def test_committed_dashboard_is_generated(self):
        saved = json.loads((ROOT / "fhs/grafana/dashboards/fhs-export-backed.json").read_text())
        self.assertEqual(saved, fhs.build_dashboard())

    def test_real_temperature_spelling_and_identity_join(self):
        dashboard = json.dumps(fhs.build_dashboard())
        self.assertIn("fpga_temperature_celcius", dashboard)
        self.assertNotIn("fpga_temperature_celsius", dashboard)
        self.assertIn("node_name", dashboard)
        self.assertNotIn("192.168.", dashboard)

    def test_unknown_precedence_acceptance_coverage(self):
        cases = acceptance_cases()["tests"]
        self.assertEqual(len(cases), 20)
        self.assertEqual({c["promql_expr_test"][0]["exp_samples"][0]["value"] for c in cases}, {0, 1, 2, 3})

    def test_live_mode_uses_actual_jobs_and_keeps_replay_default(self):
        live = json.dumps(fhs.build_dashboard(live=True))
        self.assertNotIn("replay-fhs", live)
        self.assertNotIn("replay-node", live)
        self.assertNotRegex(live, r"\$\{(?:node|job|instance|node_job|node_instance):regex\}")
        self.assertIn("./d/switch-export-backed/switch-ports", live)
        self.assertNotIn("FHS · EXPORT REPLAY", live)
        dashboard = fhs.build_dashboard(live=True)
        self.assertIn('target="_blank"', dashboard["panels"][0]["options"]["content"])
        variables = dashboard["templating"]["list"]
        self.assertEqual([v["name"] for v in variables[:6]], ["ds", "job", "node", "instance", "node_job", "node_instance"])
        for panel in dashboard["panels"]:
            if panel.get("targets"):
                self.assertEqual(panel["datasource"]["uid"], "${ds}")
        self.assertIn("replay-fhs", json.dumps(fhs.build_dashboard()))
        self.assertEqual(dashboard, json.loads((ROOT / "live-import/fhs-export-backed.json").read_text()))

    def test_component_panels_do_not_overlap_interfaces(self):
        panels = fhs.build_dashboard(live=True)["panels"]
        for i, left in enumerate(panels):
            a = left["gridPos"]
            for right in panels[i+1:]:
                b = right["gridPos"]
                overlap = a["x"] < b["x"]+b["w"] and b["x"] < a["x"]+a["w"] and a["y"] < b["y"]+b["h"] and b["y"] < a["y"]+a["h"]
                self.assertFalse(overlap, (left["title"], right["title"]))



if __name__ == "__main__" and len(sys.argv) == 3 and sys.argv[1] == "--write-promql-tests":
    Path(sys.argv[2]).write_text(json.dumps(acceptance_cases(), indent=2)+"\n")
else:
    if __name__ == "__main__":
        unittest.main()
