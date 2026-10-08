# Host Filebeat role

Standalone Debian/Ubuntu role named `filebeat`, for the [monitoring Elastic chart](../charts/elasticsearch-kibana/). Copies a controller-local `.deb`, installs through `ansible.builtin.apt`, renders a Jinja configuration, validates it and starts/enables the package's systemd service. Changed configuration/package notifies a Filebeat restart. No package repository is added; dependencies must already be installed or available through the target's configured apt sources. Match package architecture and use a Filebeat version compatible with Elasticsearch; major 9 is required by default.

## Run

From `monitoring/ansible`:

```bash
ansible-playbook -i inventory.example.ini install-filebeat.yml \
  -e @filebeat-vars.example.yml --ask-vault-pass
```

Replace example inventory addresses and controller paths first. Keep real inventory, packages and credentials outside Git. Copy [the credentials example](filebeat-credentials.example.yml) to the configured `filebeat_credentials_file`, set the existing chart publisher password, and encrypt with `ansible-vault encrypt /srv/private/filebeat-credentials.vault.yml`. The role reads this controller-side file with `include_vars`; it is never copied to the server. Plain YAML also works. Credential handling suppresses Ansible output/diffs; the installed configuration contains the publishing password and is root-owned mode 0600.

Use `filebeat_writer` and the password from `elastic-credentials/filebeat-password`. Each server may share those credentials; `add_host_metadata` identifies the actual host. Elasticsearch must be reachable from each server; the default ClusterIP service usually needs a private reachable endpoint. Optional TLS settings take target-side CA paths; certificate verification remains enabled.

## Journal collection and priorities

The only input is the default systemd journal, read through `journalctl`. All available priorities are collected with journal metadata. A processor preserves the translated `log.syslog.priority` field and adds `log.level`: 0 emergency, 1 alert, 2 critical, 3 error, 4 warning, 5 notice, 6 info, 7 debug. Missing or invalid priorities are left untouched rather than assigned a guessed level. Filter or group on these fields in Kibana.

It starts one hour back on first use and resumes its saved cursor thereafter. [Defaults](roles/filebeat/defaults/main.yml) expose the lookback and optional `filebeat_journald_include_matches` journal field matches. By default there are no matches restricting collection. Application, kernel, authentication, sudo and audit messages are included only when present in the journal; separate files are not read. Audit messages present in the journal are not silently dropped.

The target needs `journalctl` and permission to read the journal; the package service runs as root by default. Keep the stable `server-journal` input ID and `/var/lib/filebeat` registry to resume the journal cursor. Do not copy another host's registry. Previously collected file records remain in Elasticsearch; the new configuration stops reading separate log files.

## Elasticsearch setup is required once per Filebeat version

The runtime uses Filebeat's default versioned `filebeat-*` destination. No custom index override is exposed, so it matches the chart's scoped writer permissions. Template installation is disabled and ILM checks/overwrites are disabled; the publisher cannot perform administrator setup. Before starting these hosts, follow [the monitoring guide’s Filebeat setup instructions](../README.md) to preload the matching version's template and ILM using temporary administrator credentials. When running setup with this role’s installed config, additionally pass `-E setup.ilm.check_exists=true` so the administrator can install the policy. Set finite retention centrally. The role does not load modules or depend on module ingest pipelines. In Kibana use a `filebeat-*` data view with `@timestamp`.

## Check whether B is actually sending

The role tests configuration before replacement and tests output before restarting; neither test proves indexed delivery. Set `filebeat_validate_output: false` only if provisioning while Elasticsearch is unavailable. Check mode cannot validate a package that has not yet been installed.

On the target, inspect `systemctl cat filebeat` to ensure the package service uses `/etc/filebeat/filebeat.yml`; custom service overrides need to match any overridden paths. Read `journalctl -u filebeat --since '30 minutes ago'`. Periodic metrics are enabled at info level: inspect collected/published events, output acknowledgements, retries and errors together (acknowledgements alone are not an indexing proof). Look for journal read failures, permission failures, 403 index permissions, missing templates/pipelines and mapping rejections. Generate a distinctive test message in the journal using `logger -p user.err "filebeat-delivery-test-HOSTNAME"` and search for that exact message directly in Elasticsearch; widen Kibana's time range and check `host.name`, `host.hostname`, `host.id`, and `agent.id` if the host seems absent. Do not reset registry state as a first troubleshooting step.

## Verification

```bash
../../.venv/bin/ansible-playbook -i inventory.example.ini install-filebeat.yml --syntax-check
../../.venv/bin/python -m unittest discover -s tests -v
```

Local checks cover syntax and rendered collection/publishing contracts. Actual package install, Filebeat binary validation, apt dependency availability, delivery and two-host visibility require target testing; this role has not been deployed by Codex.

Sources: [Filebeat 9.5.5 journal field translation](https://github.com/elastic/beats/blob/v9.5.5/filebeat/input/journald/pkg/journalfield/default.go), [script processor](https://www.elastic.co/docs/reference/beats/filebeat/processor-script), [journald](https://www.elastic.co/docs/reference/beats/filebeat/filebeat-input-journald), [publisher privileges](https://www.elastic.co/docs/reference/beats/filebeat/privileges-to-publish-events), [ILM](https://www.elastic.co/docs/reference/beats/filebeat/ilm).
