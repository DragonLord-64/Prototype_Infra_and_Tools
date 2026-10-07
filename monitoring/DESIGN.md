# Historical design background

This earlier planning snapshot is retained for provenance. The current interface is [visible component values](README.md); it leaves running Grafana alone.

# Minimal cluster management design

Read-only design, October 6, 2026; no cluster changes made.

## Recommendation

Keep one copyable `cluster-management/` folder containing monitoring Helm chart/values, dashboards, alert rules, logging templates, image inventory, and redeployment/backup instructions. Keep NetBox as a separate release in the same folder so monitoring changes do not recreate its database.

Reuse existing Prometheus/Grafana services first. Add independent component enable flags and external service endpoints; do not install duplicate instances or try to seize existing Helm-owned resources. Migrate into an umbrella release only with an explicit release/storage migration plan. Existing SKA prototype uses the standalone Prometheus chart, so its `serverFiles` and `server` values cannot be pasted unchanged into kube-prometheus-stack.

For initial low-volume logging: one Elasticsearch StatefulSet with persistent storage, one Kibana Deployment, and Filebeat sending directly to Elasticsearch. Logstash is unnecessary until a concrete transformation/routing/queue requirement justifies it. [Elastic direct-output documentation](https://www.elastic.co/docs/reference/beats/filebeat/elasticsearch-output).

Continue Ansible-installed Filebeat on bare-metal hosts. Add a Filebeat DaemonSet only for Kubernetes container logs; ensure host/cluster inputs do not collect the same files twice. Persist Filebeat registry/checkpoint state on each node. [Elastic Kubernetes deployment](https://www.elastic.co/docs/reference/beats/filebeat/running-on-kubernetes).

## Actual repository evidence

Latest public SKA prototyping switch-monitoring branch: John So's `switch-monitoring-john`. Prometheus is in Kubernetes and scrapes `switch-telegraf:9273`, not a host Prometheus server. Persistence is explicitly disabled; retention is six hours; CPU request/limit 500m/2; memory request/limit 2Gi/4Gi. Both TSDB block-duration flags are forced to one hour. Scrapes and rules run every 30 seconds. Switch interface/VLAN telemetry is sampled every ten seconds; chassis every thirty seconds. Telegraf has no tracked explicit resource bounds or persistence; its metric buffer limit is 10,000. A dashboard exists, but Grafana deployment/storage is not captured in these branch assets.

No NetBox string in any of 255 reachable commits in freshly fetched public SKA prototyping history. Separate local Prototype Infra and Tools DOES contain NetBox Helm values/deploy script and persistent PostgreSQL (4Gi) and Valkey (1Gi), but its README leaves chart pinning, backups, and production sizing for follow-up.

Separate local Prototype Infra logging uses Docker Elasticsearch/Kibana and Filebeat 9.3.3. This is not evidence of the user's actual cluster version. Current FHS Baremetal development snapshot instead has `geerlingguy.filebeat` role 3.7.1 and `playbooks/development/filebeat_setup.yml`; role defaults select 7.x, disable Elasticsearch output, and enable Logstash output. Inspect effective inventory overrides and installed package version before choosing compatibility or migration. The Ansible role version is not the Filebeat binary version.

## Images without cluster access to docker.elastic.co

Docker Hub's [Elasticsearch](https://hub.docker.com/_/elasticsearch) and [Kibana](https://hub.docker.com/_/kibana) are Docker Official Images maintained by Elastic. [elastic/filebeat](https://hub.docker.com/r/elastic/filebeat) identifies itself as Elastic-maintained.

The live Docker Hub API verified matching 9.3.3 tags (local prototype version) and matching currently listed 9.5.3 tags across all three repositories. No automatic upgrade is proposed. Latest 9.5.5 was present for Elasticsearch/Filebeat but absent for Kibana at check time; do not choose latest tags independently.

| Registry image | Verified 9.3.3 multiarchitecture digest |
| --- | --- |
| docker.io/library/elasticsearch:9.3.3 | sha256:1d9ddbe28380c3305ef24c4364168030e4b8ce44834121f7c7dbdaedd2bb9cdf |
| docker.io/library/kibana:9.3.3 | sha256:7eb49c105e45085b1d44d0e78ceb152e479432b68a8a8f2dd71abe128eaa9b7e |
| docker.io/elastic/filebeat:9.3.3 | sha256:2ea4af46a22a02a4eaf04b329cc229e92320452ec51cb281b83733f85f5aa2e9 |

Metadata confirms publication, not successful pulls from the user's cluster, image signature validation, or support for every older tag. Identify the actual older version and check that exact tag. If absent, mirror reviewed upstream images by digest using a machine with permitted upstream connectivity into an accessible registry; retain source/digest provenance.

For a small installation, local Helm templates avoid an additional operator image. Do not base a new 9.x deployment on the [archived Elastic Helm charts](https://github.com/elastic/helm-charts). ECK is Elastic's recommended managed Kubernetes path, but adds an operator/CRDs and requires verifying its image registry and injected init containers too. In either case render every normal/init/helper/test/hook image and confirm none points at docker.elastic.co. Chart download access is a different dependency from node image pulls. Avoid runtime plugin downloads and Kibana package installation requirements in the minimal path.

## Storage and performance

First enable persistent Prometheus storage on a suitable storage class, with time AND size retention. Size using observed sample ingestion and active series, not guessed device counts. Prometheus documents a rough 1–2 bytes per stored sample plus WAL/head/index/compaction overhead; leave retention size below about 80–85% of the PVC. Prefer appropriate POSIX block-backed storage, not an unverified NFS class. [Prometheus storage documentation](https://prometheus.io/docs/prometheus/latest/storage/).

Remove forced one-hour block settings unless measurements justify them; they are not a substitute for fixing series churn or memory. Match ten-second switch sampling to the actual required resolution: a thirty-second scrape cannot preserve all intermediate ten-second counter samples. Keep chassis/topology collection slower when acceptable. Strip changing timestamps and unconstrained strings before labeling metrics, but do not blindly drop LLDP identity needed for topology. Count active series and inspect exporter freshness separately from scrape availability.

Preserve the current 2Gi request/4Gi limit as a measured starting point for Prometheus, then tune from actual working set, active series, ingestion, scrape durations, and query load. No universal storage size or Telegraf resource claim is justified by the repo alone.

Local logging prototype's 2Gi Elasticsearch container/1Gi heap and 1Gi Kibana are a low-volume test reference, not a guaranteed production budget. Reserve extra node headroom and observe heap/GC, indexing rate, queues/retries, and indexed daily disk growth. Choose Elastic retention from indexed growth times days plus overhead; configure lifecycle deletion/rollover and retain free disk for watermarks. Single-node log indices need zero replicas; a PVC is persistence, not backup or high availability. Retain Elasticsearch snapshots outside its PVC.

Node Ansible should prepare Elasticsearch host prerequisites rather than a privileged Helm helper. The current [Elastic production documentation](https://www.elastic.co/docs/deploy-manage/deploy/self-managed/install-elasticsearch-docker-prod) calls for vm.max_map_count 1048576; choose version-appropriate settings after identifying the installed version. Keep Grafana dashboards/data sources in Git; persist any UI-managed state or document it as replaceable.

## Before implementation

Need actual Elastic/Filebeat versions and image references, storage class and capacity, desired metrics/log retention, current Helm release ownership, cluster CPU/memory headroom, and logs to collect. Make authentication/TLS/secrets explicit rather than copying the local unauthenticated lab defaults. Then validate the rendered image inventory and storage plan before testing install/upgrade and log delivery. No full Helm implementation has started.
