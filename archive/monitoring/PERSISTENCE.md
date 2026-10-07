# Persistent switch Prometheus configuration

[Monitoring overview](README.md) · [Unmodified upstream source](upstream-switch/README.md)

[values/prometheus.yaml](../../monitoring/prometheus.yaml) adapts John's newest standalone Prometheus values while preserving switch scraping and recording rules. It enables a **50G** PVC (50,000,000,000 bytes, not 50Gi), requests the confirmed Ceph RBD storage class **bds1**, retains metrics for up to 15 days, and limits stored TSDB blocks to **37GB** (Prometheus's binary unit: about 39.7 decimal GB). The first time/size limit reached wins. WAL/head/index/compaction still need space; retention size is not a strict filesystem quota. Verify the provisioned PV capacity too because a provisioner may round a request upward. The requested claim does not exceed fifty decimal gigabytes.

The forced one-hour block settings were removed; normal Prometheus compaction is retained. The deployment uses Recreate for a single PVC writer. CPU/memory remains John's 500m/2Gi requests and 2CPU/4Gi limits pending measurement.

## Confirmed storage and deployment boundary

The user confirmed **bds1** uses Ceph RBD in the rook-ceph cluster and volumes pool, with cluster health reported OK. Block-backed RBD resolves the earlier NFS compatibility concern. This does not establish available pool capacity, provisioned volume size, or backup durability. Prometheus local TSDB is not supported on NFS; keep this block-backed class rather than the earlier unverified nfss1 candidate.

No claim or volume was created, resized, or migrated here. Review the existing release/PVC ownership before switching ephemeral data to persistent storage.

## Use with the existing release

This is for the **standalone prometheus-community Prometheus chart**, not kube-prometheus-stack. It was linted/rendered against chart **29.35.0**. The existing deployed chart version is unknown: retain your deployed version unless intentionally upgrading, and verify its schema. Do not install another Prometheus alongside the working one.

Review locally:

```sh
helm template YOUR_EXISTING_RELEASE prometheus \
  --repo https://prometheus-community.github.io/helm-charts --version 29.35.0 \
  -n YOUR_NAMESPACE -f monitoring/values/prometheus.yaml
```

After choosing a supported class and reviewing existing release/image/storage settings, use your normal Helm upgrade on the existing release with this values file and any other existing overrides. The pinned validation version above is not automatic permission to upgrade the deployed Prometheus binary. The chart's standard Prometheus/config-reloader registry dependencies still need to be accessible; changing Elastic registry paths does not change these images.

The primary values file explicitly scrapes the switch collector and all eight supplied node/custom exporter pairs. It installs no server-side exporters or per-server Prometheus. Existing Grafana can add the central Prometheus service manually; its running release is unchanged.
