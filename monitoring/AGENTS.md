# Monitoring knowledge

[Knowledge-base change log](../KNOWLEDGE_LOG.md) · [Top-level index](../AGENTS.md)

Follow the repository ingest/query/lint workflow. Keep source-backed proposed configuration distinct from live verification. Never store credentials. Leave the existing running Grafana outside default deployment/rendering.

- [Simple component overview](README.md)
- [Prometheus values](values/prometheus.yaml)
- [Telegraf values](values/telegraf.yaml)
- [Elasticsearch values](values/elasticsearch.yaml)
- [Kibana overlay](values/kibana.yaml)
- [Optional Grafana reference values](values/grafana.yaml)
- [Render-only helper](render.sh)
- [Storage and retention](PERSISTENCE.md)
- [Slack alert guide](SLACK.md)
- [Original switch source](upstream-switch/README.md)
- [Historical umbrella](reference/umbrella/README.md)
- [Design background](DESIGN.md)
