"""End-to-end test of run_sync() against a real git-daemon and a real HTTP server.

Everything network-shaped is swapped for a local stand-in: the "GitLab API"
is faked out, the "config repo" is a real bare git repo cloned over file://
(only the test harness's own setup uses that transport -- see note below),
the "public git upstream" is served by a real `git daemon` over git://
(the same protocol the design's git-daemon component speaks), and "the
public tarball" is served by a throwaway http.server thread. This exercises
the actual subprocess/filesystem/network code paths, not just the pure
logic covered in the other test files.
"""
from __future__ import annotations

import functools
import http.server
import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest

import mirror_sync.sync as sync
from mirror_sync.sync import MergedMergeRequest

GIT_ENV = {
    "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.com",
    "PATH": "/usr/bin:/bin",
}


def run_git(args, cwd):
    subprocess.run(["git", *args], cwd=str(cwd), check=True,
                    capture_output=True, text=True, env=GIT_ENV)


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def git_daemon(tmp_path):
    """A real `git daemon` (same binary/protocol as the design's git-daemon
    container) serving bare repos dropped under its base path on git://.
    """
    base_path = tmp_path / "git-daemon-repos"
    base_path.mkdir()
    port = free_port()
    proc = subprocess.Popen(
        ["git", "daemon", "--reuseaddr", "--export-all",
         f"--base-path={base_path}", "--listen=127.0.0.1", f"--port={port}",
         str(base_path)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        deadline = time.time() + 10
        last_err = None
        while time.time() < deadline:
            probe = subprocess.run(
                ["git", "ls-remote", f"git://127.0.0.1:{port}/nonexistent.git"],
                capture_output=True, text=True, env=GIT_ENV,
            )
            # Any response (even "repository not found") means the daemon is up.
            if probe.returncode in (0, 128):
                break
            last_err = probe.stderr
            time.sleep(0.1)
        else:
            pytest.fail(f"git daemon on port {port} never came up: {last_err}")
        yield base_path, port
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def publish_bare_repo(base_path: Path, name: str) -> Path:
    """Create a working tree with one commit, publish it as a bare repo
    under the git-daemon's base path, and return the working tree (so the
    test can push further commits into the bare repo later).
    """
    work = base_path.parent / f"{name}-work"
    work.mkdir()
    run_git(["init", "-q", "-b", "main"], cwd=work)
    (work / "README.md").write_text("hello\n")
    run_git(["add", "README.md"], cwd=work)
    run_git(["commit", "-q", "-m", "initial"], cwd=work)

    bare = base_path / f"{name}.git"
    run_git(["clone", "-q", "--bare", str(work), str(bare)], cwd=base_path)
    return work


def make_config_repo(path: Path, *, git_repo_url: str, tarball_url: str) -> Path:
    """A bare repo containing the three manifests, standing in for the
    private GitLab repo. Cloned locally via file:// purely as test-harness
    plumbing to get the manifests onto disk -- not something the design
    itself ever does (git_repo_url below is what's actually validated
    against the manifest's scheme allowlist).
    """
    work = path.parent / (path.name + "-work")
    work.mkdir(parents=True)
    run_git(["init", "-q", "-b", "main"], cwd=work)

    (work / "git-repos.yaml").write_text(f"""
repos:
  - name: widgets
    url: {git_repo_url}
    dest: widgets
""")
    (work / "tarballs.yaml").write_text(f"""
files:
  - url: {tarball_url}
    dest: tools/tool.txt
""")
    (work / "authorized_keys.yaml").write_text("""
keys:
  - name: alice
    key: "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIabc alice@laptop"
""")
    run_git(["add", "."], cwd=work)
    run_git(["commit", "-q", "-m", "add manifests"], cwd=work)
    run_git(["clone", "-q", "--bare", str(work), str(path)], cwd=path.parent)
    return path


@pytest.fixture
def http_server(tmp_path):
    """Serves tmp_path/served over HTTP on localhost, for tarball downloads."""
    served_dir = tmp_path / "served"
    served_dir.mkdir()
    (served_dir / "tool.txt").write_text("a mirrored tool\n")

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(served_dir))
    server = http.server.HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.fixture
def no_gitlab(monkeypatch):
    """The design has no real GitLab reachable in tests; fake merged-MR polling."""
    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        def fetch_merged_mrs(self, since_iid=None):
            return [MergedMergeRequest(iid=1, title="add widgets mirror",
                                        merged_at="2026-01-01T00:00:00Z",
                                        web_url="https://gitlab.example/x/-/merge_requests/1")]

    monkeypatch.setattr(sync, "GitLabClient", FakeClient)


def build_config(tmp_path, git_daemon, http_server) -> dict:
    base_path, port = git_daemon
    upstream_work = publish_bare_repo(base_path, "widgets")
    config_repo = make_config_repo(
        tmp_path / "config-repo-remote.git",
        git_repo_url=f"git://127.0.0.1:{port}/widgets.git",
        tarball_url=f"{http_server}/tool.txt",
    )
    config = {
        "gitlab_url": "https://gitlab.example",
        "gitlab_project": "org/mirror-config",
        "gitlab_token": None,
        "config_repo_url": f"file://{config_repo}",
        "config_repo_branch": "main",
        "config_repo_path": str(tmp_path / "pod" / "config-repo"),
        "git_manifest": "git-repos.yaml",
        "tarball_manifest": "tarballs.yaml",
        "keys_manifest": "authorized_keys.yaml",
        "git_repos_root": str(tmp_path / "pod" / "git-repos"),
        "artifacts_root": str(tmp_path / "pod" / "files"),
        "authorized_keys_path": str(tmp_path / "pod" / "ssh" / "uploader"),
        "state_path": str(tmp_path / "pod" / "state" / "sync-state.json"),
    }
    return config, upstream_work


class TestRunSyncEndToEnd:
    def test_first_run_populates_everything(self, tmp_path, git_daemon, http_server, no_gitlab):
        config, _ = build_config(tmp_path, git_daemon, http_server)

        result = sync.run_sync(config)

        assert result["merged_mrs"] == [1]
        assert result["git"].cloned == ["widgets"]
        assert result["git"].failed == []
        assert result["tarballs"].downloaded == ["tools/tool.txt"]
        assert result["keys_synced"] == 1

        mirrored_repo = Path(config["git_repos_root"]) / "widgets.git"
        assert mirrored_repo.is_dir()
        log = subprocess.run(["git", "log", "--oneline"], cwd=mirrored_repo,
                              check=True, capture_output=True, text=True, env=GIT_ENV)
        assert "initial" in log.stdout

        tarball = Path(config["artifacts_root"]) / "tools" / "tool.txt"
        assert tarball.read_text() == "a mirrored tool\n"

        keys_file = Path(config["authorized_keys_path"])
        assert "alice" in keys_file.read_text()
        assert (keys_file.stat().st_mode & 0o777) == 0o600

        assert Path(config["state_path"]).exists()

    def test_second_run_is_idempotent(self, tmp_path, git_daemon, http_server, no_gitlab):
        config, _ = build_config(tmp_path, git_daemon, http_server)

        sync.run_sync(config)
        second = sync.run_sync(config)

        assert second["git"].updated == ["widgets"]
        assert second["git"].cloned == []
        assert second["tarballs"].skipped == ["tools/tool.txt"]
        assert second["tarballs"].downloaded == []

    def test_state_advances_last_mr_iid(self, tmp_path, git_daemon, http_server, no_gitlab):
        config, _ = build_config(tmp_path, git_daemon, http_server)

        sync.run_sync(config)

        from mirror_sync.sync import load_state
        state = load_state(config["state_path"])
        assert state["last_mr_iid"] == 1
        assert state["last_synced_at"] is not None

    def test_new_upstream_commit_is_picked_up_on_update(self, tmp_path, git_daemon, http_server, no_gitlab):
        config, upstream_work = build_config(tmp_path, git_daemon, http_server)
        sync.run_sync(config)

        (upstream_work / "NEW.md").write_text("more content\n")
        run_git(["add", "NEW.md"], cwd=upstream_work)
        run_git(["commit", "-q", "-m", "second commit"], cwd=upstream_work)
        base_path, _ = git_daemon
        run_git(["push", "-q", str(base_path / "widgets.git"), "main:main"], cwd=upstream_work)

        sync.run_sync(config)

        mirrored_repo = Path(config["git_repos_root"]) / "widgets.git"
        log = subprocess.run(["git", "log", "--oneline"], cwd=mirrored_repo,
                              check=True, capture_output=True, text=True, env=GIT_ENV)
        assert "second commit" in log.stdout
