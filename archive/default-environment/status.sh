#!/usr/bin/env bash
set -euo pipefail

readonly profile="${MINIKUBE_PROFILE:-monitoring}"

printf 'Kubernetes workloads\n'
minikube -p "$profile" kubectl -- get pods -A

printf '\nHost/test containers\n'
docker ps --filter label=org.ska.app.group=logging \
  --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
docker ps --filter name=air-gapped-playbook-test \
  --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'

readonly node_ip="$(minikube -p "$profile" ip)"
test_server_ip="$(docker inspect air-gapped-playbook-test \
  --format '{{with index .NetworkSettings.Networks "monitoring"}}{{.IPAddress}}{{end}}' \
  2>/dev/null || true)"
printf '\nGrafana: http://%s:30300\n' "$node_ip"
printf 'Kibana:   http://127.0.0.1:5601\n'
printf 'NetBox:   kubectl -n netbox port-forward service/netbox 8000:80\n'
printf 'Prometheus (from Minikube): http://%s:9090\n' "${test_server_ip:-192.168.49.3}"
