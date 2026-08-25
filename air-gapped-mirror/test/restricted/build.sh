#!/usr/bin/env bash
# Builds the four mirror images with the restricted-network Dockerfile
# overlays in this directory, tagging them exactly as ../up.sh does
# (air-gapped-mirror/<name>:test) so the rest of the test flow is unchanged.
#
# Usage:  ./build.sh [path/to/extra-ca.crt]
#
# The optional CA bundle is baked into the sync-job image. Pass it when the
# network re-terminates TLS (a corporate/sandbox egress proxy); without it,
# mirroring an https:// upstream fails with "certificate signer not trusted".
# It is not needed for git:// upstreams such as the in-cluster fixture.
set -euo pipefail
cd "$(dirname "$0")"

ROOT="$(cd ../.. && pwd)"
CA="${1:-}"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

stage() {  # stage <component>  -> copies the real build context, plus extra-ca.crt
  rm -rf "$STAGE/$1"
  cp -r "$ROOT/$1" "$STAGE/$1"
  if [ -n "$CA" ]; then cp "$CA" "$STAGE/$1/extra-ca.crt"; else : > "$STAGE/$1/extra-ca.crt"; fi
}

for c in git-daemon apt-cacher-ng sync-job devpi; do
  echo "==> building air-gapped-mirror/$c:test (restricted overlay)"
  stage "$c"
  docker build -t "air-gapped-mirror/$c:test" -f "$c.Dockerfile" "$STAGE/$c"
done

echo "==> done:"
docker images --format '  {{.Repository}}:{{.Tag}}  {{.Size}}' | grep '^  air-gapped-mirror/' | sort
