#!/bin/sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/../../../.." && pwd)

docker build \
  --tag air-gapped-filebeat-test:local \
  "$repo_root/automation/ansible/tests/filebeat"

if docker container inspect air-gapped-playbook-test >/dev/null 2>&1; then
  docker container rm --force air-gapped-playbook-test
fi

docker run --detach \
  --name air-gapped-playbook-test \
  --privileged \
  --network elastic \
  --workdir /work/automation/ansible \
  --mount "type=bind,source=$repo_root,target=/work,readonly" \
  air-gapped-filebeat-test:local

docker network connect monitoring air-gapped-playbook-test

