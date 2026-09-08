#!/usr/bin/env bash
# Full teardown: deletes the whole minikube profile (VM/container, disk,
# every image loaded into it). Nothing from this test setup is left
# running or consuming resources afterwards.
set -euo pipefail
PROFILE="air-mirror-test"
sudo -g docker minikube -p "$PROFILE" delete
echo "==> torn down. Re-run ./up.sh to redeploy from scratch."
