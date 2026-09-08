#!/usr/bin/env bash
set -euo pipefail

readonly script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly profile="${MINIKUBE_PROFILE:-monitoring}"
readonly namespace="grafana"
readonly admin_user="${GRAFANA_ADMIN_USER:-admin}"

generated_password=""
prometheus_url="${PROMETHEUS_URL:-}"

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

command -v minikube >/dev/null 2>&1 || die "minikube is required"
minikube -p "$profile" status >/dev/null || die "Minikube profile '$profile' is not running"

kubectl() {
  minikube -p "$profile" kubectl -- "$@"
}

kubectl create namespace "$namespace" --dry-run=client -o yaml | kubectl apply -f -

if [[ -z "$prometheus_url" ]] && command -v docker >/dev/null 2>&1; then
  test_server_ip="$(docker inspect air-gapped-playbook-test \
    --format '{{with index .NetworkSettings.Networks "monitoring"}}{{.IPAddress}}{{end}}' \
    2>/dev/null || true)"
  [[ -z "$test_server_ip" ]] || prometheus_url="http://$test_server_ip:9090"
fi
prometheus_url="${prometheus_url:-http://192.168.49.3:9090}"

datasource_file="$(mktemp)"
trap 'rm -f "$datasource_file"' EXIT
printf '%s\n' \
  'apiVersion: 1' \
  'datasources:' \
  '  - name: Prometheus' \
  '    uid: prometheus' \
  '    type: prometheus' \
  '    access: proxy' \
  "    url: $prometheus_url" \
  '    isDefault: true' \
  '    editable: true' \
  '    jsonData:' \
  '      httpMethod: POST' \
  '      prometheusType: Prometheus' > "$datasource_file"
kubectl -n "$namespace" create configmap grafana-datasources \
  --from-file="prometheus.yaml=$datasource_file" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl -n "$namespace" create configmap grafana-dashboard-provider \
  --from-file="provider.yaml=$script_dir/provisioning/dashboards.yaml" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl -n "$namespace" create configmap grafana-dashboards \
  --from-file="$script_dir/dashboards/node-exporter-overview.json" \
  --dry-run=client -o yaml | kubectl apply -f -

if ! kubectl -n "$namespace" get secret grafana-admin >/dev/null 2>&1; then
  if [[ -z "${GRAFANA_ADMIN_PASSWORD:-}" ]]; then
    command -v openssl >/dev/null 2>&1 || die "openssl is required to generate the initial password"
    generated_password="$(openssl rand -base64 24)"
  fi

  kubectl -n "$namespace" create secret generic grafana-admin \
    --from-literal="admin-user=$admin_user" \
    --from-literal="admin-password=${GRAFANA_ADMIN_PASSWORD:-$generated_password}"
fi

kubectl apply -f "$script_dir/grafana.yaml"
kubectl -n "$namespace" rollout restart deployment/grafana
kubectl -n "$namespace" rollout status deployment/grafana --timeout=5m

readonly node_ip="$(minikube -p "$profile" ip)"
printf '\nGrafana is ready at http://%s:30300\n' "$node_ip"
printf 'Prometheus data source: %s\n' "$prometheus_url"
printf 'Admin user: %s\n' "$admin_user"
if [[ -n "$generated_password" ]]; then
  printf 'Generated admin password: %s\n' "$generated_password"
  printf 'Save this password now; subsequent runs preserve the existing Secret.\n'
else
  printf 'The existing Grafana admin Secret was preserved.\n'
fi
