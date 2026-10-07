#!/usr/bin/env bash
# Spin up a minikube cluster running the air-gapped-mirror stack (git,
# apt, and pip mirroring) plus a self-contained fixture upstream git repo,
# so the sync job's real logic can be exercised without any external
# dependency.
# Idempotent: safe to re-run to redeploy after code changes.
#
# Usage: ./up.sh
# Then:  ./verify.sh   (run the functional checks)
#        ./down.sh     (tear everything down)
set -euo pipefail
cd "$(dirname "$0")"

PROFILE="air-mirror-test"
NAMESPACE="air-gapped-mirror"
ROOT="$(cd .. && pwd)"

# This host's docker group membership doesn't apply to the shell's cached
# session, so every docker/minikube invocation runs with an explicit
# docker-group gid instead of relying on `docker` working bare.
DOCKER="sudo -g docker docker"
MINIKUBE="sudo -g docker minikube -p $PROFILE"

if ! $MINIKUBE status >/dev/null 2>&1; then
  echo "==> starting minikube profile '$PROFILE'"
  $MINIKUBE start --driver=docker --cpus=3 --memory=4096mb --disk-size=20g
else
  echo "==> minikube profile '$PROFILE' already running"
fi
$MINIKUBE update-context >/dev/null

echo "==> building images"
for img in git-daemon devpi apt-cacher-ng sync-job; do
  $DOCKER build -t "air-gapped-mirror/$img:test" "$ROOT/$img"
done

# `minikube image load` will NOT replace a tag that a container on the node
# still references -- it fails that one image and leaves the old layers in
# place, so a redeploy silently runs the *previous* build of your code.
# Clear the referencing containers first, then replace each tag outright.
echo "==> releasing old images"
kubectl -n "$NAMESPACE" scale deployment mirror --replicas=0 >/dev/null 2>&1 || true
kubectl -n "$NAMESPACE" wait --for=delete pod -l app.kubernetes.io/component=mirror --timeout=60s >/dev/null 2>&1 || true
$MINIKUBE ssh -- "docker container prune -f" >/dev/null 2>&1 || true

echo "==> loading images into minikube"
for img in git-daemon devpi apt-cacher-ng sync-job; do
  $MINIKUBE image rm "air-gapped-mirror/$img:test" >/dev/null 2>&1 || true
  $MINIKUBE image load "air-gapped-mirror/$img:test"
done
# Base image used as-is (the fixture's alpine initContainer) -- load once
# so redeploys don't depend on the node having internet.
$DOCKER pull alpine:3.20
$MINIKUBE image load alpine:3.20

echo "==> applying the test fixture"
kubectl apply -f manifests/00-namespace.yaml
kubectl apply -f manifests/10-fixtures.yaml

# The mirror itself is deployed through the same Helm chart used in
# production -- only values-test.yaml differs -- so this exercises the
# chart, not a parallel copy of the manifests that could drift from it.
echo "==> installing the chart"
helm upgrade --install mirror ../chart \
  --namespace "$NAMESPACE" \
  -f values-test.yaml

echo "==> waiting for the fixture to roll out"
kubectl -n "$NAMESPACE" rollout status deployment/fixture-git --timeout=120s

echo "==> waiting for the mirror deployment to roll out"
kubectl -n "$NAMESPACE" rollout status deployment/mirror --timeout=180s

echo "==> up. Run ./verify.sh to exercise each component, ./down.sh to tear down."
