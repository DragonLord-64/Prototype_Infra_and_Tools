# Minimal Elasticsearch and Kibana Helm chart

Fresh-install chart for a private small cluster: one persistent Elasticsearch node, one Kibana instance, and a bounded setup Job for Kibana's service account password. It does not deploy Prometheus, Grafana, Telegraf, Filebeat, Logstash, or an operator.

## Image versions

Both products are pinned to matching **9.5.5** Docker Official Images maintained by Elastic on Docker Hub, with immutable multiarchitecture digests. Their matching latest tags were verified through Docker Hub metadata on October 6, 2026. Every application/setup image uses `docker.io`; no `docker.elastic.co` image or runtime plugin download is required. Publication does not prove the user's cluster can pull the image.

This is a new installation, not an upgrade of the user's older Elastic cluster. Never point it at an existing older data PVC. An existing installation needs a version-specific upgrade path and snapshot/restore plan; changing image tags is not a migration plan. When overriding a tag, also change/clear its digest and keep Kibana/Elasticsearch versions compatible.

## Prerequisites

- Review the selected Kubernetes context and choose the namespace.
- Prepare node `vm.max_map_count` for the chosen Elasticsearch version (current documentation recommends 1048576) via existing node provisioning. No privileged sysctl init container is included.
- Choose a storage class whose filesystem locking/durability behaves like local disk; block-backed storage is a straightforward choice. `elasticsearch.persistence.storageClass` is intentionally empty so the cluster's default applies. An NFS class is not automatically safe: validate the backend and workload. The default 20Gi claim is a small test starting point; choose capacity/retention from measured log growth.
- Provide an existing Secret named `elastic-credentials` in that namespace, with `elastic-password`, `kibana-password`, and `kibana-encryption-key`. Generate independent strong hexadecimal values (at least 32 characters; encryption key at least 32 characters) and keep them in your secret manager. The chart never stores real values in Helm files. The setup Job requires `kibana-password` to be hexadecimal so it can safely construct its JSON request.

Authentication is enabled. Services are ClusterIP only, and HTTP inside the private cluster is intentionally unencrypted. Use port-forwarding for initial UI access; configure TLS/network controls before exposing it beyond that trusted network. The `elastic` administrator is for setup/UI bootstrap, not a shared long-term Filebeat credential.

## Render and install

From the repository root, first render for review:

```sh
helm lint monitoring/elastic-small
helm template logging monitoring/elastic-small -n YOUR_NAMESPACE \
  --set elasticsearch.persistence.storageClass=YOUR_TESTED_CLASS
```

When the Secret and node/storage prerequisites are ready, installation is an explicit cluster action:

```sh
helm upgrade --install logging monitoring/elastic-small -n YOUR_NAMESPACE \
  --set elasticsearch.persistence.storageClass=YOUR_TESTED_CLASS \
  --wait --wait-for-jobs --timeout 10m
kubectl -n YOUR_NAMESPACE port-forward service/logging-elastic-kibana 5601:5601
```

Sign in at localhost port 5601 with `elastic` and the stored administrator password. Prefer a normal user for daily access. The setup Job authenticates with the administrator and configures `kibana_system` from the Secret, without printing credentials. It is a regular Job so it can run before `--wait` finishes. A new revision runs setup again; avoid rotating the administrator Secret without updating the persisted Elasticsearch user first. Rotating Secret-backed pod credentials requires a pod restart through the normal rollout process.

Elasticsearch data and Kibana saved objects live on the Elasticsearch PVC. Kibana encryption keys are stable in the Secret. A PVC is not a backup: configure Elasticsearch snapshots separately. Uninstall preserves the StatefulSet's data claim by default; verify your storage-class reclaim policy and never delete it as routine cleanup.

## Existing Filebeat

Reuse the existing host Filebeat installation. Configure its Elasticsearch output with the reachable service endpoint and a dedicated publishing user/API key kept in the host's secret mechanism; disable any old Logstash output. The cluster-local service is `http://logging-elastic.YOUR_NAMESPACE.svc:9200`. Bare-metal hosts outside Kubernetes need an explicitly reachable private endpoint/proxy; cluster DNS alone does not make it reachable.

Verify the actual installed Filebeat version and compatibility before changing its output: the inspected FHS role defaults to 7.x while the separate local Docker prototype uses 9.3.3. This chart does not upgrade those agents. Use version-appropriate `filebeat setup` to install templates/pipelines and a finite lifecycle retention policy. On this single-node installation set log-index replicas to zero; otherwise normal log indices can remain yellow waiting for a second node. Record expected daily indexed growth, retention, and disk watermark headroom rather than assuming the 20Gi starting claim is sufficient. Logstash is not required for direct Filebeat output.

## Verification scope

Helm lint/template and rendered-resource checks passed, including disabled-Kibana rendering, image sources, persistent claim, Secret references, and bounded setup. No physical cluster deployment, image pull, live Elastic upgrade, or log delivery test was performed.

Sources: [Docker Hub Elasticsearch](https://hub.docker.com/_/elasticsearch), [Docker Hub Kibana](https://hub.docker.com/_/kibana), [Elastic node storage requirements](https://www.elastic.co/docs/reference/elasticsearch/configuration-reference/node-settings), [Docker prerequisites](https://www.elastic.co/docs/deploy-manage/deploy/self-managed/install-elasticsearch-docker-prod), [built-in users](https://www.elastic.co/docs/deploy-manage/users-roles/cluster-or-deployment-auth/built-in-users), [change-password API](https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-security-change-password), [Filebeat direct output](https://www.elastic.co/docs/reference/beats/filebeat/elasticsearch-output).
