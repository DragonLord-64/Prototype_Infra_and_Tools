#!/bin/sh
set -eu

docker exec air-gapped-playbook-test sh -c \
  'timeout 30 sh -c "until docker info >/dev/null 2>&1; do sleep 1; done"'

docker exec \
  --workdir /work/automation/ansible \
  air-gapped-playbook-test \
  ansible-playbook \
  --inventory tests/filebeat/inventory.ini \
  playbooks/install-filebeat.yml \
  --extra-vars @tests/filebeat/vars.yml
