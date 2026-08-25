#!/usr/bin/env bash
# Exercises the git mirror against a real public upstream (this repository on
# GitHub) rather than the hand-seeded in-cluster fixture, so what gets proven
# is the full path: https clone of a real remote -> bare mirror on the volume
# -> git:// clone by an air-gapped client.
#
# Requires the chart to have been installed with values-real-repo.yaml layered
# on (see that file). Run ./verify.sh first for the fixture-level checks.
#
# Usage: ./verify-real-repo.sh
set -uo pipefail
cd "$(dirname "$0")"

NAMESPACE="air-gapped-mirror"
# Same override as verify.sh -- see that script.
CLIENT_IMAGE="${CLIENT_IMAGE:-alpine:3.20}"
UPSTREAM="https://github.com/DragonLord-64/Prototype_Infra_and_Tools.git"
DEST="github.com/DragonLord-64/Prototype_Infra_and_Tools"
PASS=0
FAIL=0

pass() { echo "  PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL+1)); }
kx()   { kubectl -n "$NAMESPACE" exec test-client -- sh -c "$1"; }

echo "==> ensuring test-client pod"
if ! kubectl -n "$NAMESPACE" get pod test-client >/dev/null 2>&1; then
  kubectl -n "$NAMESPACE" run test-client --image="$CLIENT_IMAGE" \
    --image-pull-policy=IfNotPresent --restart=Never --command -- sleep 3600
fi
kubectl -n "$NAMESPACE" wait --for=condition=Ready pod/test-client --timeout=60s >/dev/null
kx "command -v git >/dev/null" >/dev/null 2>&1 || \
  kx "apk add --no-cache git >/tmp/apk.log 2>&1"

echo
echo "==> [1/5] sync sidecar: waiting for the real upstream to be mirrored"
SYNCED=""
for _ in $(seq 1 60); do
  if kubectl -n "$NAMESPACE" exec deploy/mirror -c git-daemon -- \
       test -f "/var/git/repos/$DEST.git/HEAD" >/dev/null 2>&1; then
    SYNCED=yes; break
  fi
  sleep 5
done
if [ -n "$SYNCED" ]; then
  pass "sync sidecar mirrored $UPSTREAM without being triggered"
else
  fail "real upstream not mirrored within 300s (kubectl -n $NAMESPACE logs deploy/mirror -c sync)"
  echo "================================"; echo " $PASS passed, $FAIL failed"; exit 1
fi

echo
echo "==> [2/5] git-daemon: clone the mirrored real repo over git://"
if kx "rm -rf /tmp/real && git clone -q git://mirror/$DEST.git /tmp/real"; then
  pass "clone over git:// succeeded"
else
  fail "clone over git:// failed"
fi

echo
echo "==> [3/5] content: the clone is really this repository"
# Files that exist in this repo and nowhere in the fixture -- a mirror that
# silently served an empty or wrong repo would fail here.
if kx "test -f /tmp/real/air-gapped-mirror/chart/Chart.yaml && \
       test -f /tmp/real/air-gapped-mirror/sync-job/mirror_sync/sync.py && \
       test -f /tmp/real/netbox-import/netbox_import/sync.py"; then
  pass "cloned tree contains this repository's real files"
else
  fail "cloned tree does not look like this repository"
fi
echo "     commits on the default branch: $(kx 'git -C /tmp/real rev-list --count HEAD' 2>/dev/null | tr -d '\r')"

echo
echo "==> [4/5] refs: every upstream ref is present in the mirror, at the same SHA"
# Compared against the real GitHub remote, not against a recorded snapshot.
UP="$(git ls-remote "$UPSTREAM" 'refs/heads/*' 'refs/tags/*' 2>/dev/null | sort)"
MIRROR="$(kx "git ls-remote git://mirror/$DEST.git 'refs/heads/*' 'refs/tags/*'" 2>/dev/null | tr -d '\r' | sort)"
if [ -z "$UP" ]; then
  fail "could not reach $UPSTREAM from this host to compare against"
elif [ "$UP" = "$MIRROR" ]; then
  pass "all $(echo "$UP" | wc -l | tr -d ' ') upstream branch/tag refs match the mirror exactly"
else
  fail "ref mismatch between upstream and mirror"
  diff <(echo "$UP") <(echo "$MIRROR") | head -20 | sed 's/^/       /'
fi

echo
echo "==> [5/5] incremental update: a new upstream commit is picked up"
# The reconcile loop is a plain `git remote update` -- this proves it actually
# fetches new objects on later passes, not just on the initial clone.
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
LOCAL_SHA="$(git rev-parse HEAD 2>/dev/null)"
UP_SHA="$(git ls-remote "$UPSTREAM" "refs/heads/$BRANCH" 2>/dev/null | cut -f1)"
if [ -z "$UP_SHA" ]; then
  echo "     branch '$BRANCH' is not pushed upstream yet -- nothing to pick up"
  fail "no upstream commit available to test incremental fetch (push '$BRANCH' first, then re-run)"
else
  echo "     waiting for the mirror to catch up to $BRANCH @ ${UP_SHA:0:12}"
  GOT=""
  for _ in $(seq 1 40); do
    M="$(kx "git ls-remote git://mirror/$DEST.git refs/heads/$BRANCH" 2>/dev/null | tr -d '\r' | cut -f1)"
    if [ "$M" = "$UP_SHA" ]; then GOT=yes; break; fi
    sleep 5
  done
  if [ -n "$GOT" ]; then
    pass "mirror converged on the current upstream tip of $BRANCH (${UP_SHA:0:12})"
  else
    fail "mirror did not converge on $BRANCH @ ${UP_SHA:0:12} within 200s"
  fi
  [ "$LOCAL_SHA" = "$UP_SHA" ] || echo "     note: local HEAD ${LOCAL_SHA:0:12} differs from the pushed tip"
fi

echo
echo "================================"
echo " $PASS passed, $FAIL failed"
echo "================================"
[ "$FAIL" -eq 0 ]
