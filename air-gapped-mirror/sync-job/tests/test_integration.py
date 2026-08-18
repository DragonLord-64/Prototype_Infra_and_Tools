"""End-to-end test of run_sync() against a real git-daemon.

The "public git upstream" is served by a real `git daemon` over git:// (the
same protocol the design's git-daemon component speaks), and the manifest is
a real file on disk, standing in for the mounted ConfigMap. This exercises
the actual subprocess/filesystem/network code paths, not just the pure logic
covered in the other test files.
"""
from __future__ import annotations

import socket
import subprocess
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


def build_config(tmp_path, git_daemon) -> tuple:
    """Write the manifest the chart's ConfigMap would mount, and point the
    sync job at it."""
    base_path, port = git_daemon
    upstream_work = publish_bare_repo(base_path, "widgets")

    manifest = tmp_path / "git-repos.yaml"
    manifest.write_text(f"""
repos:
  - name: widgets
    url: git://127.0.0.1:{port}/widgets.git
    dest: widgets
""")
    config = {
        "git_manifest": str(manifest),
        "git_repos_root": str(tmp_path / "pod" / "git-repos"),
        "interval_seconds": 0,
    }
    return config, upstream_work


class TestRunSyncEndToEnd:
    def test_first_run_populates_everything(self, tmp_path, git_daemon):
        config, _ = build_config(tmp_path, git_daemon)

        result = sync.run_sync(config)

        assert result["git"].cloned == ["widgets"]
        assert result["git"].failed == []

        mirrored_repo = Path(config["git_repos_root"]) / "widgets.git"
        assert mirrored_repo.is_dir()
        log = subprocess.run(["git", "log", "--oneline"], cwd=mirrored_repo,
                              check=True, capture_output=True, text=True, env=GIT_ENV)
        assert "initial" in log.stdout

    def test_second_pass_is_idempotent(self, tmp_path, git_daemon):
        config, _ = build_config(tmp_path, git_daemon)

        sync.run_sync(config)
        second = sync.run_sync(config)

        assert second["git"].updated == ["widgets"]
        assert second["git"].cloned == []

    def test_loop_reconciles_repeatedly_against_real_repos(self, tmp_path, git_daemon):
        """sync_forever driving the real run_sync, not a stub: three passes
        over a real git daemon must leave the mirror correct and must not
        raise out of the loop."""
        config, _ = build_config(tmp_path, git_daemon)

        sync.sync_forever(config, sleep=lambda _: None, iterations=3)

        assert (Path(config["git_repos_root"]) / "widgets.git").is_dir()

    def test_new_upstream_commit_is_picked_up_on_update(self, tmp_path, git_daemon):
        config, upstream_work = build_config(tmp_path, git_daemon)
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
