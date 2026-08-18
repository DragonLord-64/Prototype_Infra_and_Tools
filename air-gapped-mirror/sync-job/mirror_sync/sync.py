"""Reconciliation loop for the mirror.

Deliberately dumb: every `interval` seconds, re-read the manifests from the
config repo at HEAD and reconcile -- mirror git repos, download any tarball
we don't already have. No forge API, no webhooks, no change detection, no
state carried between passes. The config repo *is* the desired state; each
pass just makes the disk match it.

Everything mirrored is public open source and so is the config repo, so
this needs no credentials at all -- a plain `git clone` is the whole
input, and the loop is unaffected by the forge being down or an event
being missed.

Quiet by design: a pass that changes nothing logs nothing, so at one pass a
minute the log stays empty until something actually happens or breaks.

Side effects (subprocess runner, HTTP downloader) are injectable so this
can be unit tested without a network or a real git binary; see
tests/test_sync.py and tests/test_integration.py.
"""
from __future__ import annotations

import dataclasses
import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, List

import requests

from .manifest import (
    GitRepoEntry,
    TarballEntry,
    load_git_repo_manifest,
    load_tarball_manifest,
)

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = 60


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


# ---- Tarball/binary mirroring ----

@dataclasses.dataclass
class TarballSyncReport:
    downloaded: List[str] = dataclasses.field(default_factory=list)
    skipped: List[str] = dataclasses.field(default_factory=list)
    failed: List[str] = dataclasses.field(default_factory=list)


def sync_tarballs(entries: List[TarballEntry], artifacts_root,
                   download: Callable[[str, Path], None]) -> TarballSyncReport:
    """Existing files are left alone (immutable once mirrored -- a new
    version gets a new dest path). New ones download to a temp file and
    get renamed into place atomically.
    """
    report = TarballSyncReport()
    artifacts_root = Path(artifacts_root).resolve()
    artifacts_root.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        dest = (artifacts_root / entry.dest).resolve()
        try:
            dest.relative_to(artifacts_root)  # belt-and-suspenders vs. manifest.py's own check
        except ValueError:
            logger.error("refusing to write outside artifacts root: %s", entry.dest)
            report.failed.append(entry.dest)
            continue

        if dest.exists():
            report.skipped.append(entry.dest)
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(dir=str(dest.parent), prefix=".download-")
        os.close(tmp_fd)
        try:
            download(entry.url, Path(tmp_path))
            # mkstemp() creates the temp file 0600 -- nginx's worker process
            # (a different, non-root uid) needs to read it back out.
            os.chmod(tmp_path, 0o644)
            os.replace(tmp_path, dest)
            report.downloaded.append(entry.dest)
        except Exception:
            logger.exception("failed to download %s", entry.url)
            report.failed.append(entry.dest)
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    return report


def download_to_file(url: str, dest: Path) -> None:
    with requests.get(url, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)


# ---- orchestration ----

def _checkout_config_repo(url: str, branch: str, dest: Path, run=subprocess.run) -> None:
    # capture_output, not inherited stdio: git writes "From <url> / * branch
    # main -> FETCH_HEAD / HEAD is now at ..." to stderr on *every* fetch,
    # which at one pass a minute is thousands of lines a day saying nothing
    # happened. Failures re-raise with the captured stderr attached, so
    # quiet doesn't mean undiagnosable.
    def git(*args):
        try:
            run(list(args), check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            stderr = (getattr(exc, "stderr", "") or "").strip()
            raise RuntimeError(f"{' '.join(args)} failed: {stderr}") from exc

    # dest itself always exists on the first run too -- it's a k8s volume
    # mount point (PVC or emptyDir), created by the kubelet before the
    # container starts. Check for an actual git repo there, not just a
    # directory, or the first run tries `git fetch` on a non-repo and fails.
    if (dest / ".git").exists():
        git("git", "-C", str(dest), "fetch", "origin", branch)
        git("git", "-C", str(dest), "reset", "--hard", f"origin/{branch}")
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        git("git", "clone", "--branch", branch, "--depth", "1", url, str(dest))


def run_sync(config: Dict[str, Any]) -> Dict[str, Any]:
    """One reconciliation pass. Nothing is remembered between passes -- the
    config repo at HEAD is the whole input."""
    config_repo_path = Path(config["config_repo_path"])
    _checkout_config_repo(config["config_repo_url"], config["config_repo_branch"], config_repo_path)

    git_entries = load_git_repo_manifest(config_repo_path / config["git_manifest"])
    tarball_entries = load_tarball_manifest(config_repo_path / config["tarball_manifest"])

    git_report = mirror_git_repos(git_entries, config["git_repos_root"])
    tarball_report = sync_tarballs(tarball_entries, config["artifacts_root"], download=download_to_file)

    return {"git": git_report, "tarballs": tarball_report}


def config_from_env() -> Dict[str, Any]:
    return {
        "config_repo_url": os.environ["CONFIG_REPO_URL"],
        "config_repo_branch": os.environ.get("CONFIG_REPO_BRANCH", "main"),
        "config_repo_path": os.environ.get("CONFIG_REPO_PATH", "/var/mirror/config-repo"),
        "git_manifest": os.environ.get("GIT_MANIFEST", "git-repos.yaml"),
        "tarball_manifest": os.environ.get("TARBALL_MANIFEST", "tarballs.yaml"),
        "git_repos_root": os.environ.get("GIT_REPOS_ROOT", "/var/git/repos"),
        "artifacts_root": os.environ.get("ARTIFACTS_ROOT", "/var/mirror/files"),
        "interval_seconds": int(os.environ.get("SYNC_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS)),
    }


def describe_changes(result: Dict[str, Any]) -> str:
    """A one-line summary of what a pass actually changed, or "" if it was a
    no-op. Steady state is a no-op, and we don't log those."""
    git, tarballs = result["git"], result["tarballs"]
    parts = []
    if git.cloned:
        parts.append(f"cloned {', '.join(git.cloned)}")
    if tarballs.downloaded:
        parts.append(f"downloaded {', '.join(tarballs.downloaded)}")
    if git.failed:
        parts.append(f"FAILED git {', '.join(git.failed)}")
    if tarballs.failed:
        parts.append(f"FAILED tarballs {', '.join(tarballs.failed)}")
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
            # Includes a config repo that won't clone, which is the normal
            # "misconfigured on day one" case -- keep retrying so it starts
            # working on its own once the URL is fixed.
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
    logger.info("mirroring %s every %ss", config["config_repo_url"], config["interval_seconds"])
    sync_forever(config)


if __name__ == "__main__":
    main()
