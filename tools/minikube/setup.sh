#!/usr/bin/env bash
set -euo pipefail

# Re-run this script whenever the local cluster needs to be created or reconciled.
# Every setting can be overridden for a one-off run, for example:
#   MINIKUBE_CPUS=2 MINIKUBE_MEMORY=3072 ./tools/minikube/setup.sh

MINIKUBE_VERSION="${MINIKUBE_VERSION:-v1.39.0}"
MINIKUBE_PROFILE="${MINIKUBE_PROFILE:-monitoring}"
MINIKUBE_CPUS="${MINIKUBE_CPUS:-4}"
MINIKUBE_MEMORY="${MINIKUBE_MEMORY:-4096}"
INSTALL_DIR="${MINIKUBE_INSTALL_DIR:-/usr/local/bin}"

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

require() {
  command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

install_minikube() {
  local machine_arch minikube_arch download_url temp_dir installed_version expected_checksum

  installed_version=""
  if command -v minikube >/dev/null 2>&1; then
    installed_version="$(minikube version --short 2>/dev/null || true)"
  fi
  if [[ "$installed_version" == "$MINIKUBE_VERSION" ]]; then
    printf 'Minikube %s is already installed.\n' "$MINIKUBE_VERSION"
    return
  fi

  machine_arch="$(uname -m)"
  case "$machine_arch" in
    x86_64) minikube_arch="amd64" ;;
    aarch64|arm64) minikube_arch="arm64" ;;
    *) die "unsupported architecture: $machine_arch" ;;
  esac

  require curl
  require sha256sum
  temp_dir="$(mktemp -d)"
  download_url="https://github.com/kubernetes/minikube/releases/download/${MINIKUBE_VERSION}/minikube-linux-${minikube_arch}"

  printf 'Downloading Minikube %s for %s...\n' "$MINIKUBE_VERSION" "$minikube_arch"
  curl --fail --location --retry 3 --output "$temp_dir/minikube" "$download_url"
  curl --fail --location --retry 3 --output "$temp_dir/minikube.sha256" "${download_url}.sha256"
  read -r expected_checksum _ < "$temp_dir/minikube.sha256"
  printf '%s  %s\n' "$expected_checksum" "$temp_dir/minikube" \
    | sha256sum --check --status \
    || die "Minikube checksum verification failed"

  if [[ -w "$INSTALL_DIR" ]]; then
    install -m 0755 "$temp_dir/minikube" "$INSTALL_DIR/minikube"
  else
    require sudo
    sudo install -m 0755 "$temp_dir/minikube" "$INSTALL_DIR/minikube"
  fi
  printf 'Installed %s.\n' "$(minikube version --short)"
  rm -rf "$temp_dir"
}

check_docker() {
  require docker
  if ! docker info >/dev/null 2>&1; then
    die "Docker is not available to this user. Start Docker and grant the user access to its socket (usually by joining the docker group), then open a new login session."
  fi
}

main() {
  install_minikube
  check_docker

  printf 'Starting/reconciling Minikube profile %s...\n' "$MINIKUBE_PROFILE"
  minikube start \
    --profile "$MINIKUBE_PROFILE" \
    --driver docker \
    --container-runtime containerd \
    --cpus "$MINIKUBE_CPUS" \
    --memory "$MINIKUBE_MEMORY"

  printf '\nWaiting for the Kubernetes node to become Ready...\n'
  minikube --profile "$MINIKUBE_PROFILE" kubectl -- \
    wait --for=condition=Ready "node/$MINIKUBE_PROFILE" --timeout=120s
  printf '\nCluster nodes:\n'
  minikube --profile "$MINIKUBE_PROFILE" kubectl -- get nodes -o wide
  printf '\nMinikube profile %s is ready.\n' "$MINIKUBE_PROFILE"
}

main "$@"
