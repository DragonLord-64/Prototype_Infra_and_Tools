#!/usr/bin/env bash
set -euo pipefail

readonly script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly repo_root="$(cd -- "$script_dir/.." && pwd)"
readonly secrets_file="${DEFAULT_ENV_FILE:-$script_dir/default-environment.env}"

die() { printf 'error: %s\n' "$*" >&2; exit 1; }
require() { command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"; }

require docker
require helm
require minikube
require openssl
require python3

if [[ ! -f "$secrets_file" ]]; then
  umask 077
  {
    printf 'NETBOX_ADMIN_PASSWORD=%q\n' "$(openssl rand -base64 24)"
    printf 'NETBOX_API_TOKEN=%q\n' "$(openssl rand -hex 20)"
  } > "$secrets_file"
  printf 'Generated NetBox credentials in %s\n' "$secrets_file"
fi

# shellcheck disable=SC1090
source "$secrets_file"
export NETBOX_ADMIN_PASSWORD NETBOX_API_TOKEN
export MINIKUBE_PROFILE="${MINIKUBE_PROFILE:-monitoring}"

"$repo_root/platform/minikube/setup.sh"
"$repo_root/deployments/package-proxies/deploy.sh"
"$repo_root/automation/ansible/setup.sh"
"$repo_root/automation/ansible/deploy-minikube-logging.sh"
"$repo_root/automation/ansible/tests/filebeat/up.sh"
"$repo_root/automation/ansible/tests/proxy-client/run.sh"
"$repo_root/automation/ansible/tests/filebeat/run.sh"
"$repo_root/automation/ansible/tests/monitoring/run.sh"
"$repo_root/deployments/grafana/deploy.sh"
"$repo_root/deployments/netbox/deploy.sh"
"$script_dir/status.sh"
