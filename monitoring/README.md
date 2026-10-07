# Monitoring design and Slack alerts

[Repository index](../AGENTS.md) · [Design](DESIGN.md)

The [design](DESIGN.md) describes reusing current switch monitoring, adding persistent storage, and minimal Elasticsearch/Kibana/Filebeat logging. This folder includes switch-monitoring values, a small Elasticsearch/Kibana Helm chart, the alert template, and design notes. It is not yet one umbrella monitoring release.

## What the alert does

[node-exporter-slack.yaml](node-exporter-slack.yaml) creates a Grafana-managed rule and Slack contact point. A target whose Prometheus `up` remains zero for two minutes alerts; successful recovery generates a resolved notification. Prometheus `up` means scrape success, not proof the server is powered off.

The inspected FHS Baremetal `roles/manage_prometheus/templates/prometheus.yml.j2` uses job `node` for `localhost:9100`. The template therefore uses `up{job="node"} == bool 0`: failed targets return 1, healthy targets 0. It preserves per-instance labels without treating a healthy fleet as no data. Replace the job selector with your actual job if different. Only targets already scraped by this Prometheus are covered.

A target removed from discovery disappears rather than returning zero. Missing inventory targets and a disappearing whole job need a separate expected-target comparison; this template deliberately does not invent a fleet list. No data is OK for this rule, so verify the selector before installing it. Query errors produce Grafana's Error state; review error notification routing separately.

## Fill the template

1. In Grafana, open Connections → Data sources → your Prometheus source. Get its UID from its settings URL or its provisioning definition (`uid:`). In Explore, run `up{job="node"}` and confirm the expected instances. Replace BOTH `REPLACE_PROMETHEUS_UID` values with that UID. Do not use a dashboard variable here; rule query models do not interpolate environment variables.
2. Create a Slack incoming webhook for your chosen channel. Store it in a Kubernetes Secret named `grafana-slack`, key `webhook-url`, in the SAME namespace as Grafana. Use your secret manager or Kubernetes tooling; never write the real URL into this YAML, Helm values, Git, or a ConfigMap.
3. Create a ConfigMap named `grafana-node-exporter-alerting` from the filled non-secret file. The following command acts on the selected cluster; review the namespace/context before running it:

   ```sh
   kubectl -n YOUR_GRAFANA_NAMESPACE create configmap grafana-node-exporter-alerting \
     --from-file=node-exporter-slack.yaml=node-exporter-slack.yaml \
     --dry-run=client -o yaml | kubectl apply -f -
   ```

4. Merge [grafana-helm-values.example.yaml](grafana-helm-values.example.yaml) into your existing Grafana chart values, preserving other environment entries and extra mounts. For kube-prometheus-stack, nest the example keys under `grafana:`. Upgrade the EXISTING release using its reviewed chart/version and full existing values; do not install a second Grafana. If Grafana is deployed by plain Kubernetes manifests instead, add the same Secret-backed environment variable and ConfigMap file mount to its existing Deployment.
5. Restart Grafana through your normal release update, or reload alert provisioning via the Grafana Admin API. Provisioning runs on startup/reload; editing a ConfigMap alone does not automatically reload rules. This example uses a subPath file mount, so recreate the pod after ConfigMap changes to refresh the mounted file. Then inspect Alerting → Alert rules and Contact points, and explicitly test the Slack contact point when ready.

The ConfigMap mounts one file at `/etc/grafana/provisioning/alerting/node-exporter-slack.yaml`; it does not mask other provisioning files. `SLACK_WEBHOOK_URL` is read from the Secret at Grafana startup and expanded in contact point `settings.url`. Current Grafana file provisioning uses `settings`, not a separate `secureSettings` contact-point field; Grafana handles notifier secrets internally. Secret rotation requires restarting the pod and reprovisioning.

## Version and policy compatibility

Direct rule-level `notification_settings.receiver` is confirmed in Grafana's 11.6 provisioning schema and current source; the local historical Grafana manifest pins 12.1.1. The user's other cluster version remains unknown. Verify support there before installation. This file contains NO policy tree, so it does not overwrite existing notification policies.

On an older version without direct rule routing, remove `notification_settings` and add a narrowly scoped child policy matching `component=node-exporter` to your existing policy tree, receiver `cluster-slack`. Edit/merge the current tree rather than importing an unrelated replacement. Keep stable unique rule/contact-point UIDs; if those resources already exist with different ownership, export/reconcile them first.

Validation performed: YAML parsing and isolated structural/condition checks, plus comparison with official provisioning/Helm schemas. No Grafana deployment, Slack message, or live target failure test was executed.

## Sources

- [Grafana file provisioning and interpolation](https://grafana.com/docs/grafana/latest/alerting/set-up/provision-alerting-resources/file-provisioning/)
- [Grafana rule provisioning schema](https://github.com/grafana/grafana/blob/v11.6.0/pkg/services/provisioning/alerting/rules_types.go)
- [Grafana contact point schema](https://github.com/grafana/grafana/blob/main/pkg/services/provisioning/alerting/contact_point_types.go)
- [Grafana Helm chart values](https://github.com/grafana-community/helm-charts/blob/main/charts/grafana/values.yaml)
- [Prometheus jobs, instances, and up](https://prometheus.io/docs/concepts/jobs_instances/)

## Current switch source

[Latest upstream switch monitoring setup](upstream-switch/README.md) contains John So's current Telegraf/Prometheus values, recording rules, and Grafana dashboard as unchanged reference inputs.

## Deployable configuration additions

- [Persistent switch Prometheus values and storage decision](PERSISTENCE.md): fifty-decimal-gigabyte requested PVC, nfss1 candidate class, retention and single-writer settings. Backend support must be checked before deployment.
- [Small Elasticsearch/Kibana Helm chart](elastic-small/README.md): fresh single-node installation, matching Docker Hub images, existing Secret references; no live upgrade performed.
