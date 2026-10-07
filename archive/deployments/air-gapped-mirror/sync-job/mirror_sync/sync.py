"""Reconciliation loop for the mirror.

Deliberately dumb: every `interval` seconds, re-read the git-repo manifest
and reconcile -- clone what's missing, fetch what isn't. No change
detection, no state carried between passes. The manifest *is* the desired
state; each pass just makes the disk match it.

The manifest is a file mounted from a ConfigMap, so `helm upgrade` is the
whole config path. The kubelet refreshes the mounted file in place, so a
changed repo list is picked up by a later pass without restarting the pod.
Nothing is cloned to find the config and nothing needs a credential.

Quiet by design: a pass that changes nothing logs nothing, so at one pass a
minute the log stays empty until something actually happens or breaks.

The subprocess runner is injectable so this can be unit tested without a
real git binary; see tests/test_sync.py and tests/test_integration.py.
"""
from __future__ import annotations

import dataclasses
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List

from .manifest import GitRepoEntry, load_git_repo_manifest

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = 60
DEFAULT_MANIFEST_PATH = "/etc/mirror/git-repos.yaml"


# ---- Git repo mirroring ----

@dataclasses.dataclass
class GitSyncReport:
    cloned: List[str] = dataclasses.field(default_factory=list)
    updated: List[str] = dataclasses.field(default_factory=list)
    failed: List[str] = dataclasses.field(default_factory=list)


def mirror_git_repos(entries: List[GitRepoEntry], repos_root, run=subprocess.run) -> GitSyncReport:
    """git clone --mirror new entries, git remote update existing ones."""
    report = GitSyncReport()
    repos_root = Path(repos_root)
    repos_root.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        dest = repos_root / entry.dest
        try:
            if dest.exists():
                run(["git", "remote", "update", "--prune"], cwd=str(dest),
                    check=True, capture_output=True, text=True)
                report.updated.append(entry.name)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                run(["git", "clone", "--mirror", entry.url, str(dest)],
                    check=True, capture_output=True, text=True)
                report.cloned.append(entry.name)
        except subprocess.CalledProcessError as exc:
            logger.error("git sync failed for %s: %s", entry.name, getattr(exc, "stderr", ""))
            report.failed.append(entry.name)
    return report


# ---- orchestration ----

def run_sync(config: Dict[str, Any], run=subprocess.run) -> Dict[str, Any]:
    """One reconciliation pass. Nothing is remembered between passes -- the
    manifest on disk is the whole input, re-read every time so a ConfigMap
    edit takes effect without a restart."""
    entries = load_git_repo_manifest(config["git_manifest"])
    return {"git": mirror_git_repos(entries, config["git_repos_root"], run=run)}


def config_from_env() -> Dict[str, Any]:
    return {
        "git_manifest": os.environ.get("GIT_MANIFEST", DEFAULT_MANIFEST_PATH),
        "git_repos_root": os.environ.get("GIT_REPOS_ROOT", "/var/git/repos"),
        "interval_seconds": int(os.environ.get("SYNC_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS)),
    }


def describe_changes(result: Dict[str, Any]) -> str:
    """A one-line summary of what a pass actually changed, or "" if it was a
    no-op. Steady state is a no-op, and we don't log those."""
    git = result["git"]
    parts = []
    if git.cloned:
        parts.append(f"cloned {', '.join(git.cloned)}")
    if git.failed:
        parts.append(f"FAILED git {', '.join(git.failed)}")
    return "; ".join(parts)


def sync_forever(config: Dict[str, Any], sleep=time.sleep, run_once=run_sync,
                 iterations: int = 0) -> None:
    """Reconcile every `interval_seconds`, forever.

    Nothing here may raise: this process dying means the mirror silently
    stops updating, and a CrashLoopBackOff would then throttle restarts
    just when things are already broken. Every failure is logged and
    retried on the next pass instead.

    `iterations` caps the number of passes (0 = unlimited); tests use it.
    """
    interval = config["interval_seconds"]
    count = 0
    while True:
        try:
            changes = describe_changes(run_once(config))
            if changes:
                logger.info("%s", changes)
        except Exception:
            # Includes a manifest that won't parse, which is the normal
            # "typo in values.yaml" case -- keep retrying so it starts
            # working on its own once the ConfigMap is fixed.
            logger.exception("sync pass failed; retrying in %ss", interval)

        count += 1
        if iterations and count >= iterations:
            return
        sleep(interval)


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)s %(message)s")
    config = config_from_env()
    # The one routine line we do emit, so an operator can tell the loop is
    # alive and at what cadence. After this, silence means "nothing changed".
    logger.info("mirroring %s every %ss", config["git_manifest"], config["interval_seconds"])
    sync_forever(config)


if __name__ == "__main__":
    main()
