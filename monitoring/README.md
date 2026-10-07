# Monitoring setup

A **Helm chart** contains Kubernetes resource templates. A **values file** supplies settings to a chart; it is not a deployment by itself. We use normal upstream charts for Prometheus/Telegraf and one small local [Elasticsearch/Kibana chart](charts/elasticsearch-kibana/Chart.yaml), so its required templates are right here rather than hidden in the archive.

| Values | Chart |
| --- | --- |
| [prometheus.yaml](prometheus.yaml) | prometheus-community/prometheus29.35.0 |
| [telegraf.yaml](telegraf.yaml) | influxdata/telegraf1.8.77 |
| [elasticsearch.yaml](elasticsearch.yaml) + [kibana.yaml](kibana.yaml) | charts/elasticsearch-kibana0.2.0, one release |
| [grafana.yaml](grafana.yaml) | Optional Grafana13.2.7 reference; leave the running Grafana alone |

Telegraf collects switch **metrics**; central Prometheus scrapes Telegraf plus the eight servers' node/custom exporters, and Grafana displays them. Existing host Filebeat collects **logs** and sends them to Elasticsearch; Kibana searches those logs. Filebeat does not send logs to Prometheus, and Logstash is not needed here.

## 1. Review the settings

Use namespace **mid-cbf-monitoring** and confirmed Ceph RBD class **bds1**. Prometheus requests **50G** and retains up to fifteen days, with a **37GB** retained-block limit (about39.7decimalGB). WAL/head/compaction need the remaining space;37GB is not a hard total-disk quota. Confirm pool capacity before deploying. The eight server addresses are explicit in prometheus.yaml; node_exporter uses9100 and the custom exporter uses **9101 provisionally**. No exporters are installed on servers by these charts.

The local chart is a **fresh Elasticsearch/Kibana9.5.5 installation**, using pinned official Docker Hub images. Do not attach older Elasticsearch data volumes to it. Prepare Elasticsearch's node requirement (`vm.max_map_count`, currently1048576) through existing provisioning; this chart does not change host settings.

## 2. Create the Elastic Secret

Run this on your controller only when ready, with the intended Kubernetes context/namespace. No real credentials belong in Git:

```sh
umask 077
credentials_dir=$(mktemp -d)
openssl rand -hex 24 | tr -d '\n' > "$credentials_dir/elastic-password"
openssl rand -hex 24 | tr -d '\n' > "$credentials_dir/kibana-password"
openssl rand -hex 32 | tr -d '\n' > "$credentials_dir/kibana-encryption-key"
kubectl -n mid-cbf-monitoring create secret generic elastic-credentials \
  --from-file=elastic-password="$credentials_dir/elastic-password" \
  --from-file=kibana-password="$credentials_dir/kibana-password" \
  --from-file=kibana-encryption-key="$credentials_dir/kibana-encryption-key"
```

Create the namespace separately if it does not exist. Save those values in your password manager, then remove the private temporary files. Reuse the Secret across upgrades. The chart configures Kibana's service user automatically. Changing the Secret alone does not rotate an existing Elasticsearch user's stored password.

## 3. Install only the components you choose

From the repository root, first review each command with `helm template` instead of `helm upgrade --install`. Chart downloads happen on the controller; image pulls happen on cluster nodes. Review the current release ownership before updating an existing service.

```sh
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add influxdata https://helm.influxdata.com
helm repo update
helm upgrade --install monitoring-prometheus prometheus-community/prometheus \
  --version 29.35.0 -n mid-cbf-monitoring -f monitoring/prometheus.yaml
helm upgrade --install switch-telegraf influxdata/telegraf \
  --version 1.8.77 -n mid-cbf-monitoring -f monitoring/telegraf.yaml
helm upgrade --install logging monitoring/charts/elasticsearch-kibana \
  -n mid-cbf-monitoring -f monitoring/elasticsearch.yaml -f monitoring/kibana.yaml \
  --wait --wait-for-jobs --timeout 10m
```

Keep both Elastic overlays whenever Kibana is desired. Applying only Elasticsearch values to that same release sets Kibana disabled. Existing Grafana is neither installed nor upgraded by these commands. Add a Prometheus data source there manually: `http://monitoring-prometheus.mid-cbf-monitoring.svc:9090`. Prometheus/Telegraf endpoints currently have no authentication configured; Telegraf has no UI/default login.

For initial Kibana access, run `kubectl -n mid-cbf-monitoring port-forward service/logging-elastic-kibana 5601:5601` and sign in at localhost5601 as `elastic` with the saved administrator password. Use that administrator for bootstrap, not permanent Filebeat ingestion.

## 4. Give Filebeat a real reachable endpoint and publishing account

`logging-elastic.mid-cbf-monitoring.svc:9200` is cluster-local. Bare-metal servers generally cannot use that DNS/ClusterIP. Choose a private reachable proxy or, if your cluster supports it, set `elasticsearch.service.type: LoadBalancer` in elasticsearch.yaml and use the actual assigned private address. No address is guessed. HTTP here is authenticated but unencrypted; keep it on the trusted private network or add TLS before wider exposure. Port-forwarding is only for initial setup, not continuous Filebeat delivery.

First check `filebeat version` on the hosts. The inspected FHS role defaults to7.x; this chart runs9.5.5. Verify compatibility or plan an explicit agent upgrade—none is performed automatically. Filebeat9 disables the old `log` input; use version-appropriate `filestream` configuration and migration guidance.

Load Filebeat's templates/lifecycle once with a compatible agent and temporary setup credentials. Filebeat's keystore avoids putting the administrator password in command history; create one with `sudo filebeat keystore create` only if none exists, then add `ES_SETUP_PASSWORD` interactively. On that host:

```sh
sudo filebeat keystore add ES_SETUP_PASSWORD
sudo filebeat setup --index-management \
  -E output.logstash.enabled=false \
  -E 'output.elasticsearch.hosts=["http://PRIVATE_ES_ENDPOINT:9200"]' \
  -E output.elasticsearch.username=elastic \
  -E 'output.elasticsearch.password=${ES_SETUP_PASSWORD}' \
  -E setup.template.enabled=true \
  -E setup.template.settings.index.number_of_replicas=0
```

If using Filebeat modules, also preload their ingest pipelines. Set finite log retention in Kibana's Index Lifecycle Policies to fit the20Gi starting volume. The administrator credential is for this setup step only; remove its keystore entry afterwards using `filebeat keystore remove ES_SETUP_PASSWORD`.

Create a dedicated publisher once. In another terminal, temporarily run `kubectl -n mid-cbf-monitoring port-forward service/logging-elastic 9200:9200`. These curl commands prompt for the saved `elastic` password and do not print a new password:

```sh
ES_URL=http://127.0.0.1:9200
curl --fail --user elastic -X PUT "$ES_URL/_security/role/filebeat_writer" \
  -H 'Content-Type: application/json' \
  --data '{"cluster":["monitor","read_ilm","read_pipeline"],"indices":[{"names":["filebeat-*"],"privileges":["auto_configure","create_doc"]}]}'
umask 077
filebeat_credentials_dir=$(mktemp -d)
openssl rand -hex 24 > "$filebeat_credentials_dir/filebeat-password"
printf '{"password":"%s","roles":["filebeat_writer"]}\n' \
  "$(cat "$filebeat_credentials_dir/filebeat-password")" > "$filebeat_credentials_dir/filebeat-user.json"
curl --fail --user elastic -X PUT "$ES_URL/_security/user/filebeat_writer" \
  -H 'Content-Type: application/json' --data-binary "@$filebeat_credentials_dir/filebeat-user.json"
```

Keep the publishing password in Ansible Vault and remove its private temporary files afterwards. That role is scoped to default `filebeat-*` indices; custom index names require corresponding permissions.

## 5. Point existing Filebeat at Elasticsearch

The current FHS `geerlingguy.filebeat` role supports these output variables:

```yaml
filebeat_output_elasticsearch_enabled: true
filebeat_output_elasticsearch_hosts:
  - "http://PRIVATE_ES_ENDPOINT:9200"
filebeat_output_elasticsearch_auth:
  username: filebeat_writer
  password: "{{ vault_filebeat_password }}"
filebeat_output_logstash_enabled: false
```

Use a version-compatible input/template. For a manually managed Filebeat9 config, the relevant runtime settings are:

```yaml
filebeat.inputs:
  - type: filestream
    id: server-logs
    paths: ["/var/log/*.log"]
output.elasticsearch:
  hosts: ["http://PRIVATE_ES_ENDPOINT:9200"]
  username: filebeat_writer
  password: "${FILEBEAT_PASSWORD}"
setup.template.enabled: false
setup.ilm.check_exists: false
```

Supply `FILEBEAT_PASSWORD` through that host's protected environment/keystore. Disable any old Logstash output. The role's default template does not expose those final setup flags as variables; use its supported `filebeat_template` override when supplying a custom runtime template. Input/state migration needs its own review to avoid rereading existing logs.

Sources: [publisher permissions](https://www.elastic.co/docs/reference/beats/filebeat/privileges-to-publish-events), [setup permissions](https://www.elastic.co/docs/reference/beats/filebeat/privileges-to-setup-beats), [filestream migration](https://www.elastic.co/docs/reference/beats/filebeat/migrate-to-filestream), [direct Elasticsearch output](https://www.elastic.co/docs/reference/beats/filebeat/elasticsearch-output).
