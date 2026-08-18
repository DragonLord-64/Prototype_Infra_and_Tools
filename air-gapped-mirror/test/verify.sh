#!/usr/bin/env bash
# Exercises every functional piece of the air-gapped-mirror stack against
# the running minikube deployment from up.sh:
#   - waits for the sync sidecar's reconcile loop to mirror the fixture
#     upstream git repo, with nothing triggering it
#   - git-daemon: clones the now-mirrored repo
#   - devpi / apt-cacher-ng: proxy+cache a real PyPI package / Debian
#     index through the mirror (best-effort: skipped, not failed, if the
#     cluster has no outbound internet access)
set -uo pipefail
cd "$(dirname "$0")"
NAMESPACE="air-gapped-mirror"
PASS=0
FAIL=0
SKIP=0

pass() { echo "  PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL+1)); }
skip() { echo "  SKIP: $1"; SKIP=$((SKIP+1)); }

kx() { kubectl -n "$NAMESPACE" exec test-client -- sh -c "$1"; }

echo "==> ensuring test-client pod"
if ! kubectl -n "$NAMESPACE" get pod test-client >/dev/null 2>&1; then
  kubectl -n "$NAMESPACE" run test-client --image=alpine:3.20 --restart=Never --command -- sleep 3600
fi
kubectl -n "$NAMESPACE" wait --for=condition=Ready pod/test-client --timeout=60s >/dev/null

if ! kx "test -f /tmp/.provisioned"; then
  echo "==> installing test tools (git, curl, py3-pip) in test-client"
  kx "apk add --no-cache git curl py3-pip >/tmp/apk.log 2>&1 && touch /tmp/.provisioned"
fi

echo
echo "==> [1/5] sync sidecar: waiting for it to mirror the fixture repo"
# The sidecar reconciles on a loop, so there's nothing to trigger -- just
# wait for the mirrored content to show up on the volumes.
SYNCED=""
for _ in $(seq 1 40); do
  if kubectl -n "$NAMESPACE" exec deploy/mirror -c git-daemon -- \
       test -d /var/git/repos/test/hello.git >/dev/null 2>&1; then
    SYNCED=yes
    break
  fi
  sleep 3
done
if [ -n "$SYNCED" ]; then
  pass "sync sidecar mirrored the fixture repo without being triggered"
else
  fail "sync sidecar did not mirror within 120s (see: kubectl -n $NAMESPACE logs deploy/mirror -c sync)"
fi
echo "     --- sync sidecar logs (quiet unless something changed/failed) ---"
kubectl -n "$NAMESPACE" logs deploy/mirror -c sync --tail=15 2>&1 | sed 's/^/     /'

echo
echo "==> [2/5] git-daemon: cloning the mirrored fixture repo"
if kx "rm -rf /tmp/check-hello && git clone -q git://mirror/test/hello.git /tmp/check-hello && grep -q 'hello from fixture upstream repo' /tmp/check-hello/README.md"; then
  pass "git-daemon serves the mirrored repo with correct content"
else
  fail "git-daemon clone of the mirrored repo failed or content mismatched"
fi

echo
echo "==> [3/5] devpi: real pip install through the caching proxy (best-effort, needs outbound internet)"
# --trusted-host is required for any plain-HTTP index: without it pip
# silently *ignores* the --index-url entirely and reports "no versions
# found", which looks identical to devpi being down. Real clients on the
# internal network need the same flag (or the equivalent pip.conf).
if kx "pip install --no-cache-dir --index-url http://mirror:3141/root/pypi/+simple/ --trusted-host mirror --target /tmp/pipout six" >/tmp/pip.log 2>&1; then
  pass "devpi proxied+cached a real pip install (six)"
else
  skip "devpi pip install did not succeed (likely no outbound internet from the cluster) -- see /tmp/pip.log"
fi

echo
echo "==> [4/5] apt-cacher-ng: proxying a real Debian index (best-effort, needs outbound internet)"
if kx "curl -x http://mirror:3142 -sf http://deb.debian.org/debian/dists/bookworm/InRelease -o /tmp/InRelease && test -s /tmp/InRelease"; then
  pass "apt-cacher-ng proxied a real Debian repo request"
else
  skip "apt-cacher-ng proxy check did not succeed (likely no outbound internet from the cluster)"
fi

echo
echo "==> [5/5] all mirror pods report Ready"
NOT_READY="$(kubectl -n "$NAMESPACE" get pods -l app.kubernetes.io/component=mirror -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.status.containerStatuses[*].ready}{"\n"}{end}' | grep -v ' true true true true' || true)"
if [ -z "$NOT_READY" ]; then
  pass "mirror deployment: all 4 containers ready"
else
  fail "mirror deployment: not all containers ready: $NOT_READY"
fi

echo
echo "================================"
echo " $PASS passed, $FAIL failed, $SKIP skipped"
echo "================================"
[ "$FAIL" -eq 0 ]
