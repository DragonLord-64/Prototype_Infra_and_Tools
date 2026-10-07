#!/usr/bin/env bash
set -euo pipefail

docker container inspect air-gapped-playbook-test >/dev/null 2>&1 || {
  printf 'error: create the test server with tests/filebeat/up.sh first\n' >&2
  exit 1
}

docker exec \
  --workdir /work/automation/ansible \
  air-gapped-playbook-test \
  ansible-playbook \
  --inventory tests/filebeat/inventory.ini \
  playbooks/setup-proxy-source.yml \
  --extra-vars cluster_name=monitoring \
  --extra-vars git_proxy_port=30128 \
  --extra-vars apt_proxy_port=30142 \
  --extra-vars pip_proxy_port=30141
