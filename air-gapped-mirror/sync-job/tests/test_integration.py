"""End-to-end test of run_sync() against a real git-daemon and a real HTTP server.

Everything network-shaped is swapped for a local stand-in: the "config
repo" is a real bare git repo cloned over file://
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
    """A bare repo containing the two manifests, standing in for the
    real config repo. Cloned locally via file:// purely as test-harness
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


def build_config(tmp_path, git_daemon, http_server) -> dict:
    base_path, port = git_daemon
    upstream_work = publish_bare_repo(base_path, "widgets")
    config_repo = make_config_repo(
        tmp_path / "config-repo-remote.git",
        git_repo_url=f"git://127.0.0.1:{port}/widgets.git",
        tarball_url=f"{http_server}/tool.txt",
    )
    config = {
        "config_repo_url": f"file://{config_repo}",
        "config_repo_branch": "main",
        "config_repo_path": str(tmp_path / "pod" / "config-repo"),
        "git_manifest": "git-repos.yaml",
        "tarball_manifest": "tarballs.yaml",
        "git_repos_root": str(tmp_path / "pod" / "git-repos"),
        "artifacts_root": str(tmp_path / "pod" / "files"),
        "interval_seconds": 0,
    }
    return config, upstream_work


class TestRunSyncEndToEnd:
    def test_first_run_populates_everything(self, tmp_path, git_daemon, http_server):
        config, _ = build_config(tmp_path, git_daemon, http_server)

        result = sync.run_sync(config)

        assert result["git"].cloned == ["widgets"]
        assert result["git"].failed == []
        assert result["tarballs"].downloaded == ["tools/tool.txt"]

        mirrored_repo = Path(config["git_repos_root"]) / "widgets.git"
        assert mirrored_repo.is_dir()
        log = subprocess.run(["git", "log", "--oneline"], cwd=mirrored_repo,
                              check=True, capture_output=True, text=True, env=GIT_ENV)
        assert "initial" in log.stdout

        tarball = Path(config["artifacts_root"]) / "tools" / "tool.txt"
        assert tarball.read_text() == "a mirrored tool\n"

    def test_second_pass_is_idempotent(self, tmp_path, git_daemon, http_server):
        config, _ = build_config(tmp_path, git_daemon, http_server)

        sync.run_sync(config)
        second = sync.run_sync(config)

        assert second["git"].updated == ["widgets"]
        assert second["git"].cloned == []
        assert second["tarballs"].skipped == ["tools/tool.txt"]
        assert second["tarballs"].downloaded == []

    def test_loop_reconciles_repeatedly_against_real_repos(self, tmp_path, git_daemon, http_server):
        """sync_forever driving the real run_sync, not a stub: three passes
        over a real git daemon must leave the mirror correct and must not
        raise out of the loop."""
        config, _ = build_config(tmp_path, git_daemon, http_server)

        sync.sync_forever(config, sleep=lambda _: None, iterations=3)

        mirrored_repo = Path(config["git_repos_root"]) / "widgets.git"
        assert mirrored_repo.is_dir()
        assert (Path(config["artifacts_root"]) / "tools" / "tool.txt").exists()

    def test_new_upstream_commit_is_picked_up_on_update(self, tmp_path, git_daemon, http_server):
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
