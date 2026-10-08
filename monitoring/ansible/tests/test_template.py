import json
from pathlib import Path
import unittest
import jinja2
import yaml

ROOT = Path(__file__).resolve().parents[1]

class TemplateTests(unittest.TestCase):
    def render(self, **overrides):
        values = yaml.safe_load((ROOT / "roles/filebeat/defaults/main.yml").read_text())
        values.update(filebeat_elasticsearch_hosts=["https://elastic.example:9200"],
                      filebeat_credentials={"filebeat_elasticsearch_username": "filebeat_writer",
                                            "filebeat_elasticsearch_password": 'quote"\\ colon: newline\n${PASSWORD}'})
        values.update(overrides)
        env = jinja2.Environment(undefined=jinja2.StrictUndefined)
        env.filters.update(to_json=json.dumps,
                           to_nice_yaml=lambda value, indent=2: yaml.safe_dump(value, sort_keys=False, indent=indent))
        text = env.from_string((ROOT / "roles/filebeat/templates/filebeat.yml.j2").read_text()).render(**values)
        return yaml.safe_load(text)

    def test_defaults_and_secret_escaping(self):
        config = self.render()
        self.assertEqual([i["id"] for i in config["filebeat.inputs"]], ["server-system", "server-auth"])
        self.assertEqual(config["output.elasticsearch"]["password"], 'quote"\\ colon: newline\n$${PASSWORD}')
        self.assertFalse(config["setup.template.enabled"])
        self.assertFalse(config["setup.ilm.check_exists"])
        self.assertNotIn("index", config["output.elasticsearch"])
        self.assertEqual(config["processors"], [{"add_host_metadata": {}}])

    def test_optional_inputs(self):
        extra = {"type": "filestream", "id": "app", "paths": ["/var/log/app/*.log"]}
        config = self.render(filebeat_audit_enabled=True, filebeat_journald_enabled=True,
                             filebeat_extra_inputs=[extra], filebeat_journald_include_matches=["SYSLOG_IDENTIFIER=sshd"])
        inputs = config["filebeat.inputs"]
        self.assertEqual(len(inputs), 5)
        self.assertEqual(inputs[-1], extra)
        self.assertEqual(inputs[-2]["include_matches.match"], ["SYSLOG_IDENTIFIER=sshd"])

    def test_journal_only(self):
        config = self.render(filebeat_file_inputs_enabled=False, filebeat_journald_enabled=True)
        self.assertEqual([i["type"] for i in config["filebeat.inputs"]], ["journald"])

if __name__ == "__main__":
    unittest.main()
