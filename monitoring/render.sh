#!/usr/bin/env bash
# Local manifest rendering only: no install, upgrade, apply, or cluster access.
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
namespace=${MONITORING_NAMESPACE:-mid-cbf-monitoring}
charts="$root/reference/umbrella/charts"
case ${1:-all} in
  prometheus) helm template monitoring-prometheus "$charts/prometheus-29.35.0.tgz" -n "$namespace" -f "$root/values/prometheus.yaml" ;;
  telegraf) helm template switch-telegraf "$charts/telegraf-1.8.77.tgz" -n "$namespace" -f "$root/values/telegraf.yaml" ;;
  elasticsearch) helm template logging "$root/elastic-small" -n "$namespace" -f "$root/values/elasticsearch.yaml" ;;
  elastic) helm template logging "$root/elastic-small" -n "$namespace" -f "$root/values/elasticsearch.yaml" -f "$root/values/kibana.yaml" ;;
  grafana) helm template optional-grafana "$charts/grafana-13.2.7.tgz" -n "$namespace" -f "$root/values/grafana.yaml" ;;
  all) for component in prometheus telegraf elastic; do "$0" "$component"; printf '\n---\n'; done ;;
  *) printf 'Usage: %s [all|prometheus|telegraf|elasticsearch|elastic|grafana]\n' "$0" >&2; exit 2 ;;
esac
