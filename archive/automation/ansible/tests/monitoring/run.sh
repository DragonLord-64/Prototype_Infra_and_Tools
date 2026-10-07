#!/bin/sh
set -eu

docker exec air-gapped-playbook-test sh -c \
  'timeout 30 sh -c "until rc-status -a >/dev/null 2>&1; do sleep 1; done"'

docker exec \
  --workdir /work/automation/ansible \
  air-gapped-playbook-test \
  ansible-playbook \
  --inventory tests/filebeat/inventory.ini \
  tests/monitoring/install.yml
