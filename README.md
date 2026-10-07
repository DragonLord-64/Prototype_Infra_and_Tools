# Infrastructure prototypes and tools

[Knowledge-base change log](KNOWLEDGE_LOG.md) · [Knowledge-base index](AGENTS.md)

The active work is the portable Ansible/NetBox inventory pipeline and the monitoring values for the SKA FHS bare-metal repository.

| Area | Purpose |
| --- | --- |
| [NetBox pipeline](end-to-end-netbox/README.md) | Existing discovery, simulators, and local NetBox/test-container setup |
| [Portable development bundle](end-to-end-netbox/development/README.md) | Latest reviewed imports, role layout, and offline tests to copy to FHS Baremetal |
| [Monitoring values](monitoring/) | Exactly five component YAML files; choose what to deploy |
| [Historical archive](archive/README.md) | Previous platform, workloads, host automation, utilities, and default environment |

Only source and wiki documents were relocated. Ignored credentials, environments, generated output, and runtime data remain at their original paths. No running service was restarted or redeployed. Some historical directory names may therefore still exist locally.

For the latest inventory work, start with the portable bundle README. The existing end-to-end entrypoints and fixtures remain available for regression testing. Archive scripts are retained for reference; read the archive usage limitations before running them.

## Monitoring values

[Grafana](monitoring/grafana.yaml), [Prometheus](monitoring/prometheus.yaml), [Telegraf](monitoring/telegraf.yaml), [Elasticsearch](monitoring/elasticsearch.yaml), and [Kibana](monitoring/kibana.yaml) are the only files in `monitoring/`. Use namespace `mid-cbf-monitoring`; no running Grafana or cluster resources were changed.

Grafana, Prometheus, and Telegraf values target their pinned upstream charts (13.2.7,29.35.0,1.8.77). The Elastic values target the retained [local chart](archive/monitoring/elastic-small/README.md), not an upstream chart. Combine both overlays in the same Elastic release when Kibana is desired; applying only Elasticsearch values to a combined release disables Kibana.

For example, render Elastic locally with `helm template logging archive/monitoring/elastic-small -n mid-cbf-monitoring -f monitoring/elasticsearch.yaml -f monitoring/kibana.yaml`. The [previous guides and chart packages](archive/monitoring/README.md) remain archived references. No automatic orchestration is included in the active folder.
