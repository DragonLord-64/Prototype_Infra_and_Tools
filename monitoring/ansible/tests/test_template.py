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
        self.assertEqual([i["id"] for i in config["filebeat.inputs"]], ["server-journal"])
        self.assertEqual(config["output.elasticsearch"]["password"], 'quote"\\ colon: newline\n$${PASSWORD}')
        self.assertFalse(config["setup.template.enabled"])
        self.assertFalse(config["setup.ilm.check_exists"])
        self.assertNotIn("index", config["output.elasticsearch"])
        self.assertEqual(config["processors"][0], {"add_host_metadata": {}})

    def test_journal_only_and_matches(self):
        config = self.render(filebeat_journald_include_matches=["SYSLOG_IDENTIFIER=sshd"])
        self.assertEqual(len(config["filebeat.inputs"]), 1)
        self.assertEqual(config["filebeat.inputs"][0]["type"], "journald")
        self.assertEqual(config["filebeat.inputs"][0]["include_matches.match"], ["SYSLOG_IDENTIFIER=sshd"])

    def test_priority_mapping_execution(self):
        import subprocess
        script = self.render()["processors"][1]["script"]["source"]
        harness = r'''
var assert = require("assert");
var levels = ["emergency", "alert", "critical", "error", "warning", "notice", "info", "debug"];
function run(priority) {
  var fields = {"log.syslog.priority": priority};
  process({Get: function(k) { return fields[k]; }, Put: function(k, v) { fields[k] = v; }});
  return fields;
}
for (var n = 0; n < 8; n++) {
  [n, String(n)].forEach(function(value) {
    var fields = run(value);
    assert.strictEqual(fields["log.level"], levels[n]);
    assert.strictEqual(fields["log.syslog.priority"], value);
  });
}
[undefined, null, -1, 8, "", "info", "3junk", "3.0", 2.5, false, []].forEach(function(value) {
  assert.strictEqual(run(value)["log.level"], undefined);
});
'''
        subprocess.run(["node", "-"], input=script + harness, text=True, check=True)

if __name__ == "__main__":
    unittest.main()
