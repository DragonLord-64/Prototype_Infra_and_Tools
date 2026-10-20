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
        ("complete cool card is healthy", "Component 1", base, 1, 0),
        ("complete warm card is degraded", "Component 1", {**base, "fpga_temperature_celcius": 75}, 1, 1),
        ("partial warm card is unknown", "Component 1", {**base, "fpga_temperature_celcius": 75, "num_metrics_unavailable": 3}, 1, 3),
        ("missing required power is unknown", "Component 1", {k: v for k, v in base.items() if k != "total_input_power_watts"}, 1, 3),
        ("failure wins over partial coverage", "Component 1", {**base, "fpga_temperature_celcius": 95, "num_metrics_unavailable": 3}, 1, 2),
        ("exporter down hides old good values", "Component 1", base, 0, 3),
        ("missing source up is unknown", "Component 1", base, None, 3),
        ("zero fan with partial source is failed", "Fan 1", {"fan1_rpm": 0, "fsc_temperature_celcius": 45, "num_metrics_total": 8, "num_metrics_unavailable": 5}, 1, 2),
        ("unverified PSU flag zeros are not healthy", "PSU 1", {"sts_psu1": 0, "sts_psu1_fan": 0, "sts_psu1_ac_lost": 0, "num_metrics_total": 8, "num_metrics_unavailable": 0}, 1, 3),
        ("CPU temperature failure wins over unverified flags", "CPU", {"cpu_temperature_celcius": 95, "prochot_cpu": 0, "cpu1_thermtrip": 0, "sts_cpu_mce": 0, "num_metrics_total": 4, "num_metrics_unavailable": 0}, 1, 2),
        ("NIC temperature alone cannot prove complete health", "NIC", {"nic_temperature_celcius": 60}, 1, 3),
        ("one missing DIMM cannot hide behind max", "Memory", {**{f"ddr5_{s}1_temperature_celcius": 45 for s in "abceghi"}, "num_metrics_total": 8, "num_metrics_unavailable": 0}, 1, 3),
    ]
    tests = []
    for title, component_title, metrics, up, expected in cases:
        c = by_title[component_title]
        inputs = [{"series": f'{name}{{node_name="demo-server-01",source="{c["source"]}",job="fhs-exporter"}}', "values": f"{value}+0x12"} for name, value in metrics.items()]
        if up is not None:
            inputs.append({"series": 'up{job="replay-fhs",instance="replay:9100"}', "values": f"{up}+0x12"})
        tests.append({"name": title, "interval": "5s", "input_series": inputs,
                      "promql_expr_test": [{"expr": fhs.component_query(c).replace("$node", "demo-server-01"), "eval_time": "1m", "exp_samples": [{"labels": "{}", "value": expected}]}]})
    return {"rule_files": [], "evaluation_interval": "5s", "tests": tests}


class FHSContract(unittest.TestCase):
    def test_no_invented_physical_components(self):
        titles = [c["title"] for c in fhs.COMPONENTS]
        self.assertEqual(len(titles), 12)
        self.assertEqual([t for t in titles if t.startswith("Fan ")], ["Fan 1", "Fan 2"])
        self.assertEqual(titles[:2], ["Component 1", "Component 2"])

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
        self.assertEqual(len(cases), 12)
        self.assertEqual({c["promql_expr_test"][0]["exp_samples"][0]["value"] for c in cases}, {0, 1, 2, 3})

    def test_live_mode_uses_actual_jobs_and_keeps_replay_default(self):
        live = json.dumps(fhs.build_dashboard(live=True))
        self.assertNotIn("replay-fhs", live)
        self.assertNotIn("replay-node", live)
        self.assertNotIn("FHS · EXPORT REPLAY", live)
        self.assertIn('job=\\"fhs-exporter\\",node_name=~\\"$node\\"', live)
        self.assertIn("replay-fhs", json.dumps(fhs.build_dashboard()))


if __name__ == "__main__" and len(sys.argv) == 3 and sys.argv[1] == "--write-promql-tests":
    Path(sys.argv[2]).write_text(json.dumps(acceptance_cases(), indent=2)+"\n")
else:
    if __name__ == "__main__":
        unittest.main()
