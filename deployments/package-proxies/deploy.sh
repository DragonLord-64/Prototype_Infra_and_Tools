#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
PROFILE="${MINIKUBE_PROFILE:-monitoring}"
VERSION="${PROXY_IMAGE_VERSION:-0.0.3}"
SOURCE_DIR="${PROTOTYPING_REPO:-$REPO_ROOT/../ska-mid-cbf-prototyping}"

if [[ ! -d "$SOURCE_DIR/src" || ! -d "$SOURCE_DIR/images" ]]; then
  printf 'Prototyping source not found at %s\n' "$SOURCE_DIR" >&2
  printf 'Set PROTOTYPING_REPO to its checkout directory.\n' >&2
  exit 1
fi

minikube -p "$PROFILE" status >/dev/null

build_and_load() {
  local name="$1"
  local dockerfile="$2"
  local image="local/$name:$VERSION"

  docker build \
    --platform linux/amd64 \
    --provenance=false \
    --load \
    --tag "$image" \
    --file "$SOURCE_DIR/$dockerfile" \
    "$SOURCE_DIR"
  minikube -p "$PROFILE" image load --overwrite=true "$image"
}

build_and_load ska-mid-cbf-git-proxy images/ska-mid-cbf-git-proxy/Dockerfile
build_and_load ska-mid-cbf-apt-cacher-ng images/ska-mid-cbf-apt-cacher-ng/Dockerfile
build_and_load ska-mid-cbf-devpi images/ska-mid-cbf-devpi/Dockerfile

minikube -p "$PROFILE" kubectl -- apply -f "$SCRIPT_DIR/minikube.yaml"
minikube -p "$PROFILE" kubectl -- rollout status deployment/git-proxy -n proxy-cache --timeout=180s
minikube -p "$PROFILE" kubectl -- rollout status deployment/apt-proxy -n proxy-cache --timeout=180s
minikube -p "$PROFILE" kubectl -- rollout status deployment/pip-proxy -n proxy-cache --timeout=180s

node_ip="$(minikube -p "$PROFILE" ip)"
printf '\nGit proxy: http://%s:30128\n' "$node_ip"
printf 'APT proxy: http://%s:30142\n' "$node_ip"
printf 'pip index: http://%s:30141/root/pypi/+simple/\n' "$node_ip"
