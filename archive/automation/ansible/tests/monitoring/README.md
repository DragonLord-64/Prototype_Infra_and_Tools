# Machine-local monitoring test

This test installs Prometheus and node_exporter as native OpenRC services in
the persistent `air-gapped-playbook-test` container. Prometheus scrapes the
co-located exporter at `127.0.0.1:9100` and listens on all interfaces at port
9090 so Grafana in the Minikube cluster can use it as a data source.

Run after creating the test server with `../filebeat/up.sh`:

```sh
./automation/ansible/tests/monitoring/run.sh
```

The playbook is intentionally Alpine-specific and isolated under `tests/`; it
does not change the production Filebeat role or production playbooks.
