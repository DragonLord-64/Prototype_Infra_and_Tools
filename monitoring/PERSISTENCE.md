# Persistent switch Prometheus configuration

[Monitoring overview](README.md) · [Unmodified upstream source](upstream-switch/README.md)

[switch-prometheus-values.yaml](switch-prometheus-values.yaml) adapts John's newest standalone Prometheus values while preserving switch scraping and recording rules. It enables a **50G** PVC (50,000,000,000 bytes, not 50Gi), requests editable storage class **nfss1**, retains metrics for up to 15 days, and limits stored TSDB blocks to **37GB** (Prometheus's binary unit: about 39.7 decimal GB). The first time/size limit reached wins. WAL/head/index/compaction still need space; retention size is not a strict filesystem quota. Verify the provisioned PV capacity too because a provisioner may round a request upward. The requested claim does not exceed fifty decimal gigabytes.

The forced one-hour block settings were removed; normal Prometheus compaction is retained. The deployment uses Recreate for a single PVC writer. CPU/memory remains John's 500m/2Gi requests and 2CPU/4Gi limits pending measurement.

## REVIEW CANDIDATE — storage decision before deployment

The class name `nfss1` does NOT identify its provisioner. This value is the user's requested candidate, not a claim that its backend is supported. Inspect its provisioner and a provisioned volume. **Prometheus explicitly does not support NFS for local TSDB storage.** If this class is NFS-backed, select a local/block-backed class for this file before applying it; do not treat retries or a smaller volume as a compatibility fix. [Prometheus storage documentation](https://prometheus.io/docs/prometheus/latest/storage/).

Read-only preflight on the intended cluster:

```sh
kubectl get storageclass nfss1 -o yaml
```

Check its `provisioner` and parameters, then confirm the backing filesystem for a provisioned volume. A generic CSI provisioner name can conceal an NFS backend; its name alone is insufficient. Before applying, establish whether this class is actually NFS-backed.

The repository was prepared without access to the user's other cluster. No volume was created, mounted, resized, or migrated. Turning the existing ephemeral release into a PVC-backed release may replace its ephemeral history; preserve anything important separately and review Helm's diff and release ownership first.

## Use with the existing release

This is for the **standalone prometheus-community Prometheus chart**, not kube-prometheus-stack. It was linted/rendered against chart **29.35.0**. The existing deployed chart version is unknown: retain your deployed version unless intentionally upgrading, and verify its schema. Do not install another Prometheus alongside the working one.

Review locally:

```sh
helm template YOUR_EXISTING_RELEASE prometheus \
  --repo https://prometheus-community.github.io/helm-charts --version 29.35.0 \
  -n YOUR_NAMESPACE -f monitoring/switch-prometheus-values.yaml
```

After choosing a supported class and reviewing existing release/image/storage settings, use your normal Helm upgrade on the existing release with this values file and any other existing overrides. The pinned validation version above is not automatic permission to upgrade the deployed Prometheus binary. The chart's standard Prometheus/config-reloader registry dependencies still need to be accessible; changing Elastic registry paths does not change these images.

This configuration currently scrapes the switch Telegraf service only. Central server/node exporter target discovery remains a separate follow-up; it does not silently replace or duplicate existing bare-metal Prometheus deployments. Existing Grafana data sources should continue to use this same service.
