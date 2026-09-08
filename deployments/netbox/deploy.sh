#!/usr/bin/env bash
set -euo pipefail

readonly namespace="${NETBOX_NAMESPACE:-netbox}"
readonly release="${NETBOX_RELEASE:-netbox}"
readonly chart="${NETBOX_CHART:-oci://ghcr.io/netbox-community/netbox-chart/netbox}"
readonly script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v helm >/dev/null 2>&1; then
  echo "helm is required (https://helm.sh/docs/intro/install/)" >&2
  exit 1
fi

: "${NETBOX_ADMIN_PASSWORD:?Set NETBOX_ADMIN_PASSWORD before deploying}"
: "${NETBOX_API_TOKEN:?Set NETBOX_API_TOKEN before deploying}"

helm upgrade --install "${release}" "${chart}" \
  --namespace "${namespace}" \
  --create-namespace \
  --values "${script_dir}/values.yaml" \
  --set-string superuser.password="${NETBOX_ADMIN_PASSWORD}" \
  --set-string superuser.apiToken="${NETBOX_API_TOKEN}" \
  --wait \
  --timeout 15m

kubectl --namespace "${namespace}" get pods,service,pvc
