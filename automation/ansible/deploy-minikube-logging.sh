#!/usr/bin/env bash
set -euo pipefail

readonly script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly ansible_playbook="${ANSIBLE_PLAYBOOK:-$script_dir/.venv/bin/ansible-playbook}"

if [[ "$EUID" -ne 0 ]]; then
  exec sudo -g "${DOCKER_GROUP:-docker}" "$0" "$@"
fi

[[ -x "$ansible_playbook" ]] || {
  printf 'error: run automation/ansible/setup.sh first\n' >&2
  exit 1
}

"$ansible_playbook" \
  --inventory "$script_dir/inventory.minikube.ini" \
  "$script_dir/playbooks/deploy-minicube-logging.yml" \
  --extra-vars "@$script_dir/minicube-vars.yml"
