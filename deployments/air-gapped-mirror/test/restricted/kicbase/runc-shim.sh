#!/bin/sh
# runc shim for running minikube inside this sandbox. Two spec fixups that
# the sandbox makes unavoidable, applied before the real runc sees them:
#   * process.oomScoreAdj < 0  -- lowering oom_score_adj is EPERM here even
#     for root, so every pod sandbox otherwise dies with
#     "can not get final child's PID from pipe: EOF"
#   * RLIMIT_NOFILE above the sandbox hard limit -- kicbase asks dockerd for
#     1048576, which EPERMs against this sandbox's 20000 ceiling
# `runc create/run` takes the spec as <bundle>/config.json; `runc exec` takes
# just the process block via --process. Both need the same fixups, or
# `kubectl exec` fails where pod startup succeeds.
bundle=""
procfile=""
prev=""
for a in "$@"; do
  case "$prev" in
    --bundle|-b) bundle="$a";;
    --process|-p) procfile="$a";;
  esac
  prev="$a"
done
[ -z "$bundle" ] && bundle="$(pwd)"
[ -n "$procfile" ] && [ -f "$procfile" ] && spec_files="$procfile" || spec_files=""
[ -f "$bundle/config.json" ] && spec_files="$spec_files $bundle/config.json"
for f in $spec_files; do
  MAXNOFILE=$(ulimit -Hn) python3 - "$f" <<"PY" 2>/dev/null || true
import json, os, sys
p = sys.argv[1]
cap = int(os.environ.get("MAXNOFILE") or 20000)
with open(p) as f:
    spec = json.load(f)
# config.json wraps the process block; a --process file *is* the process block.
proc = spec.get("process") if isinstance(spec.get("process"), dict) else spec
changed = False
if proc.get("oomScoreAdj", 0) < 0:
    proc["oomScoreAdj"] = 0
    changed = True
for rl in proc.get("rlimits") or []:
    if rl.get("type") == "RLIMIT_NOFILE":
        for k in ("hard", "soft"):
            if rl.get(k, 0) > cap:
                rl[k] = cap
                changed = True
if changed:
    with open(p, "w") as f:
        json.dump(spec, f)
PY
done
exec /usr/bin/runc.real "$@"
