# Monitoring setup

A **Helm chart** contains Kubernetes resource templates. A **values file** supplies settings to a chart; it is not a deployment by itself. We use normal upstream charts for Prometheus/Telegraf and one small local [Elasticsearch/Kibana chart](charts/elasticsearch-kibana/Chart.yaml), so its required templates are right here rather than hidden in the archive.

| Values | Chart |
| --- | --- |
| [prometheus.yaml](prometheus.yaml) | prometheus-community/prometheus 29.35.0 |
| [telegraf.yaml](telegraf.yaml) | influxdata/telegraf 1.8.77 |
| [elasticsearch.yaml](elasticsearch.yaml) + [kibana.yaml](kibana.yaml) | charts/elasticsearch-kibana 0.4.0, one release |
| [grafana.yaml](grafana.yaml) | Optional Grafana 13.2.7 reference; leave the running Grafana alone |

Telegraf collects switch **metrics**; central Prometheus scrapes Telegraf plus the eight servers' node/custom exporters, and Grafana displays them. Existing host Filebeat collects **logs** and sends them to Elasticsearch; Kibana searches those logs. Filebeat does not send logs to Prometheus, and Logstash is not needed here.

## 1. Review the settings

Use namespace **mid-cbf-monitoring** and confirmed Ceph RBD class **bds1**. Prometheus requests **50G** and retains up to fifteen days, with a **37GB** retained-block limit (about 39.7 decimal GB). WAL/head/compaction need the remaining space; 37GB is not a hard total-disk quota. Confirm pool capacity before deploying. The eight server addresses are explicit in prometheus.yaml; node_exporter uses port 9100 and the custom exporter uses **9101 provisionally**. No exporters are installed on servers by these charts.

The local chart is a **fresh Elasticsearch/Kibana 9.5.5 installation**, using pinned official Docker Hub images. Do not attach older Elasticsearch data volumes to it. Prepare Elasticsearch's node requirement (`vm.max_map_count`, currently 1048576) through existing provisioning; this chart does not change host settings.

## 2. Create the Elastic Secret

Run this on your controller only when ready, with the intended Kubernetes context/namespace. No real credentials belong in Git:

```sh
umask 077
credentials_dir=$(mktemp -d)
openssl rand -hex 24 | tr -d '\n' > "$credentials_dir/elastic-password"
openssl rand -hex 24 | tr -d '\n' > "$credentials_dir/kibana-password"
openssl rand -hex 24 | tr -d '\n' > "$credentials_dir/filebeat-password"
openssl rand -hex 32 | tr -d '\n' > "$credentials_dir/kibana-encryption-key"
kubectl -n mid-cbf-monitoring create secret generic elastic-credentials \
  --from-file=elastic-password="$credentials_dir/elastic-password" \
  --from-file=kibana-password="$credentials_dir/kibana-password" \
  --from-file=filebeat-password="$credentials_dir/filebeat-password" \
  --from-file=kibana-encryption-key="$credentials_dir/kibana-encryption-key"
```

If the namespace does not exist, first run `kubectl create namespace mid-cbf-monitoring`. Save those values in your password manager. `elastic-password` is your initial browser login as `elastic`; `kibana-password` is Kibana's internal Elasticsearch login; `filebeat-password` is shared by your eight Filebeat publishers; the encryption key is not a login password. Store the **same Filebeat password value** in Ansible Vault as `vault_filebeat_password`, then remove the private temporary files. Do not copy the whole Kubernetes Secret into playbooks or put plaintext passwords in Git.

The active Elasticsearch values enable `filebeat.enabled`: the chart creates the `filebeat_writer` role/user automatically from `elastic-credentials/filebeat-password`. Chart defaults leave this optional feature disabled for existing users. The setup Job also works when Kibana is disabled. All enabled setup steps must succeed for the Job to complete. Reuse the Secret across upgrades. Changing `filebeat-password` or `kibana-password` in the Secret requires a **Helm upgrade** to reconcile Elasticsearch's stored password; also update the eight hosts when rotating Filebeat's password. Changing `elastic-password` in the Secret does not rotate an existing administrator account.

If `elastic-credentials` already exists, keep its original administrator/Kibana values and add `filebeat-password` to it through your existing Secret-management workflow before enabling this feature. A missing key fails the setup Job.

## 3. Install only the components you choose

From the repository root, preview Elastic locally; this creates nothing in the cluster:

```sh
helm template logging monitoring/charts/elasticsearch-kibana \
  -n mid-cbf-monitoring -f monitoring/elasticsearch.yaml -f monitoring/kibana.yaml
```

Then run only the installation commands for components you choose. Chart downloads happen on the controller; image pulls happen on cluster nodes. Check release ownership before updating an existing service.

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

For initial Kibana access, run `kubectl -n mid-cbf-monitoring port-forward service/logging-elastic-kibana 5601:5601` and sign in at localhost:5601 as `elastic` with the saved administrator password. Use that administrator for bootstrap, not permanent Filebeat ingestion.

## Kibana ingress

The [Kibana overlay](kibana.yaml) enables ingress with placeholders. Before deploying, replace `kibana.ingress.className: replace-me` with your installed ingress class and `kibana.ingress.host: kibana.example.invalid` with your Kibana hostname. Run `kubectl get ingressclass` to inspect available classes. An ingress controller must already be installed; the chart creates only the routing resource. Point the hostname's DNS record at that controller's address.

For HTTPS, set `kibana.ingress.tlsSecretName` to a TLS Secret in `mid-cbf-monitoring` containing your hostname's certificate/key, or configure your controller's certificate automation through `kibana.ingress.annotations`. An empty TLS Secret name renders no TLS configuration. Use HTTPS before sending login credentials across an untrusted network. The backend is the existing Kibana Service on port 5601; Elasticsearch remains cluster-internal with these values.

Deploy using the existing `helm upgrade --install logging` command with both Elastic overlays. Check routing with `kubectl -n mid-cbf-monitoring get ingress`. To keep using port-forwarding instead, add `--set kibana.ingress.enabled=false` to that command. Chart defaults disable ingress; applying the Kibana overlay enables it.

## PDU push receiver on the existing Telegraf

The [Telegraf values](telegraf.yaml) add an HTTP JSON receiver on TCP **8080**, path **`/pdu`**, alongside the existing Cisco gRPC listener on 57000 and Prometheus metrics on 9273. All three use the existing `switch-telegraf` Service; no additional collector is installed. After upgrading Telegraf, use `kubectl -n mid-cbf-monitoring get service switch-telegraf` to find its assigned private LoadBalancer address. Configure a compatible Raritan Data Push destination as `http://PRIVATE_TELEGRAF_ADDRESS:8080/pdu` using POST (PUT is also accepted). Permit that port from the PDUs on your private network. This receiver has no authentication or TLS; keep its exposure restricted to that network.

For an initial connection test, run the following from a machine that can reach the Service:

```sh
curl --fail-with-body -i -X POST \
  -H 'Content-Type: application/json' \
  --data-binary '{"pdu_id":"connectivity-test","power_watts":123}' \
  http://PRIVATE_TELEGRAF_ADDRESS:8080/pdu
```

The listener is configured for the default HTTP 204 success response. Within the normal collection interval, look in `http://PRIVATE_TELEGRAF_ADDRESS:9273/metrics` for a metric such as `pdu_power_watts` with `pdu_id="connectivity-test"`. Central Prometheus already scrapes this Telegraf output. This test inserts a synthetic measurement; it does not validate actual PDU readings.

The initial generic JSON parser accepts numeric fields and uses an optional `pdu_id` string as a distinguishing tag. It is **not durable raw-message capture**: incompatible JSON can be rejected or yield no useful measurements. Receiving requests alone does not establish correct units, sensor identities, or dashboards. Refine parsing and tags later against the actual PX firmware payload so different PDUs and sensors remain distinguishable. A PDU sample is not required to deploy the listener, but actual Raritan format compatibility is still unverified.

Source: [Telegraf HTTP Listener v2 configuration](https://docs.influxdata.com/telegraf/v1/input-plugins/http_listener_v2/).

## 4. Give Filebeat a real reachable endpoint and publishing account

`logging-elastic.mid-cbf-monitoring.svc:9200` is cluster-local. Bare-metal servers generally cannot use that DNS/ClusterIP. Choose a private reachable proxy or, if your cluster supports it, set `elasticsearch.service.type: LoadBalancer` in elasticsearch.yaml and use the actual assigned private address. No address is guessed. HTTP here is authenticated but unencrypted; keep it on the trusted private network or add TLS before wider exposure. Port-forwarding is only for initial setup, not continuous Filebeat delivery.

First check `filebeat version` on the hosts. The inspected FHS role defaults to 7.x; this chart runs 9.5.5. Verify compatibility or plan an explicit agent upgrade—none is performed automatically. Filebeat 9 disables the old `log` input; use version-appropriate `filestream` configuration and migration guidance.

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

If using Filebeat modules, also preload their ingest pipelines. Set finite log retention in Kibana's Index Lifecycle Policies to fit the 20 Gi starting volume. The administrator credential is for this setup step only; remove its keystore entry afterwards using `filebeat keystore remove ES_SETUP_PASSWORD`.

The chart has already created the dedicated `filebeat_writer` publisher using your saved `filebeat-password`; no manual user-creation curl commands are needed. It can publish to default `filebeat-*` indices/data streams, but cannot perform the administrator setup above. Custom index names require matching role permissions. The setup Job makes idempotent PUT requests on each install/upgrade, retries while Elasticsearch starts, and is limited to ten minutes.

Check that bootstrap succeeded (the Job suffix is the Helm release revision):

```sh
kubectl -n mid-cbf-monitoring get jobs
kubectl -n mid-cbf-monitoring logs job/logging-elastic-setup-1
```

For a first install, expect `logging-elastic-setup-1` to show `Complete` and the message `Elasticsearch service users configured`. After upgrades, use the latest revision's Job name. Credentials are not printed. Only start publishing after bootstrap and Filebeat template/lifecycle setup succeed.

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

Use a version-compatible input/template. For a manually managed Filebeat 9 config, the relevant runtime settings are:

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

Finally, in Kibana open **Data Views** from management or global search, create a data view matching `filebeat-*` with `@timestamp` as its time field, then open **Discover** and select it to search the incoming logs.

Sources: [publisher permissions](https://www.elastic.co/docs/reference/beats/filebeat/privileges-to-publish-events), [setup permissions](https://www.elastic.co/docs/reference/beats/filebeat/privileges-to-setup-beats), [filestream migration](https://www.elastic.co/docs/reference/beats/filebeat/migrate-to-filestream), [direct Elasticsearch output](https://www.elastic.co/docs/reference/beats/filebeat/elasticsearch-output), [Kibana data views](https://www.elastic.co/docs/explore-analyze/find-and-organize/data-views/create-data-view).
