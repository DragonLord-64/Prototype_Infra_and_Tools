"""Reconciliation + orchestration for the sync CronJob.

Polls GitLab for MRs merged since the last run (audit log only -- the sync
pod has no public endpoint for webhooks, so this is how "what changed"
gets tracked), then always reconciles from the manifests at HEAD: mirrors
git repos, downloads new tarballs, regenerates authorized_keys.

Side effects (subprocess runner, HTTP downloader, GitLab session) are
injectable so this can be unit tested without a network or a real git
binary; see tests/test_sync.py and tests/test_integration.py.
"""
from __future__ import annotations

import dataclasses
import datetime
import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import quote

import requests

from .manifest import (
    GitRepoEntry,
    SshKeyEntry,
    TarballEntry,
    load_authorized_keys_manifest,
    load_git_repo_manifest,
    load_tarball_manifest,
)

logger = logging.getLogger(__name__)


# ---- GitLab polling (audit trail; no webhook is reachable) ----

@dataclasses.dataclass(frozen=True)
class MergedMergeRequest:
    iid: int
    title: str
    merged_at: str
    web_url: str


class GitLabClient:
    def __init__(self, base_url: str, project: str, token: Optional[str] = None,
                 session=None, timeout: float = 30):
        self.base_url = base_url.rstrip("/")
        self.project = project
        self.token = token
        self.timeout = timeout
        self.session = session or requests.Session()

    def fetch_merged_mrs(self, since_iid: Optional[int] = None, per_page: int = 100) -> List[MergedMergeRequest]:
        """Return merged MRs with iid > since_iid, oldest first."""
        url = f"{self.base_url}/api/v4/projects/{quote(self.project, safe='')}/merge_requests"
        headers = {"Accept": "application/json"}
        if self.token:
            headers["PRIVATE-TOKEN"] = self.token
        params = {"state": "merged", "order_by": "created_at", "sort": "asc", "per_page": per_page}

        results: List[MergedMergeRequest] = []
        page = 1
        while True:
            params["page"] = page
            resp = self.session.get(url, headers=headers, params=params, timeout=self.timeout)
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            for raw in batch:
                if since_iid is not None and raw["iid"] <= since_iid:
                    continue
                results.append(MergedMergeRequest(
                    iid=raw["iid"], title=raw.get("title", ""),
                    merged_at=raw.get("merged_at") or "", web_url=raw.get("web_url", ""),
                ))
            if len(batch) < per_page:
                break
            page += 1
        return results


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


# ---- authorized_keys regeneration ----

AUTHORIZED_KEYS_HEADER = (
    "# Managed by the air-gapped mirror sync job -- do not edit by hand.\n"
    "# Source of truth: the public-keys manifest in the private config repo.\n"
)


def regenerate_authorized_keys(entries: List[SshKeyEntry], output_path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [AUTHORIZED_KEYS_HEADER] + [f"{e.key}\n" for e in sorted(entries, key=lambda e: e.name)]
    tmp_path = output_path.with_name(output_path.name + ".tmp")
    tmp_path.write_text("".join(lines))
    tmp_path.chmod(0o600)
    os.replace(tmp_path, output_path)  # atomic: no half-written file for a connecting client


# ---- state (last-seen MR, across runs) ----

DEFAULT_STATE: Dict[str, Any] = {"last_mr_iid": 0, "last_synced_at": None}


def load_state(path) -> Dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return dict(DEFAULT_STATE)
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        logger.warning("state file at %s unreadable, starting from defaults", path)
        return dict(DEFAULT_STATE)
    state = dict(DEFAULT_STATE)
    if isinstance(data, dict):
        state.update(data)
    return state


def save_state(path, state: Dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(json.dumps(state, indent=2, sort_keys=True))
    tmp_path.replace(path)


# ---- orchestration ----

def _checkout_config_repo(url: str, branch: str, dest: Path, run=subprocess.run) -> None:
    if dest.exists():
        run(["git", "-C", str(dest), "fetch", "origin", branch], check=True)
        run(["git", "-C", str(dest), "reset", "--hard", f"origin/{branch}"], check=True)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--branch", branch, "--depth", "1", url, str(dest)], check=True)


def run_sync(config: Dict[str, Any]) -> Dict[str, Any]:
    state_path = Path(config["state_path"])
    state = load_state(state_path)

    client = GitLabClient(config["gitlab_url"], config["gitlab_project"], token=config.get("gitlab_token"))
    merged = client.fetch_merged_mrs(since_iid=state.get("last_mr_iid") or None)
    for mr in merged:
        logger.info("merged since last run: !%s %s (%s)", mr.iid, mr.title, mr.web_url)

    config_repo_path = Path(config["config_repo_path"])
    _checkout_config_repo(config["config_repo_url"], config["config_repo_branch"], config_repo_path)

    git_entries = load_git_repo_manifest(config_repo_path / config["git_manifest"])
    tarball_entries = load_tarball_manifest(config_repo_path / config["tarball_manifest"])
    key_entries = load_authorized_keys_manifest(config_repo_path / config["keys_manifest"])

    git_report = mirror_git_repos(git_entries, config["git_repos_root"])
    tarball_report = sync_tarballs(tarball_entries, config["artifacts_root"], download=download_to_file)
    regenerate_authorized_keys(key_entries, config["authorized_keys_path"])

    if merged:
        state["last_mr_iid"] = max(state.get("last_mr_iid") or 0, max(mr.iid for mr in merged))
    state["last_synced_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save_state(state_path, state)

    return {
        "merged_mrs": [mr.iid for mr in merged],
        "git": git_report,
        "tarballs": tarball_report,
        "keys_synced": len(key_entries),
    }


def config_from_env() -> Dict[str, Any]:
    return {
        "gitlab_url": os.environ.get("GITLAB_URL", "https://gitlab.com"),
        "gitlab_project": os.environ["GITLAB_PROJECT"],
        "gitlab_token": os.environ.get("GITLAB_TOKEN"),
        "config_repo_url": os.environ["CONFIG_REPO_URL"],
        "config_repo_branch": os.environ.get("CONFIG_REPO_BRANCH", "main"),
        "config_repo_path": os.environ.get("CONFIG_REPO_PATH", "/var/mirror/config-repo"),
        "git_manifest": os.environ.get("GIT_MANIFEST", "git-repos.yaml"),
        "tarball_manifest": os.environ.get("TARBALL_MANIFEST", "tarballs.yaml"),
        "keys_manifest": os.environ.get("KEYS_MANIFEST", "authorized_keys.yaml"),
        "git_repos_root": os.environ.get("GIT_REPOS_ROOT", "/var/git/repos"),
        "artifacts_root": os.environ.get("ARTIFACTS_ROOT", "/var/mirror/files"),
        "authorized_keys_path": os.environ.get("AUTHORIZED_KEYS_PATH", "/var/mirror/ssh/uploader"),
        "state_path": os.environ.get("STATE_PATH", "/var/mirror/state/sync-state.json"),
    }


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    result = run_sync(config_from_env())
    logger.info("sync complete: %s", result)


if __name__ == "__main__":
    main()
