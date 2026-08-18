import subprocess
from pathlib import Path

import pytest

from mirror_sync.manifest import GitRepoEntry, TarballEntry
from mirror_sync.sync import (
    _checkout_config_repo,
    describe_changes,
    mirror_git_repos,
    sync_forever,
    sync_tarballs,
)


# ---- mirror_git_repos ----

class FakeRun:
    """Stand-in for subprocess.run that records calls and can be told to fail."""

    def __init__(self, fail_for=()):
        self.calls = []
        self.fail_for = set(fail_for)

    def __call__(self, cmd, **kwargs):
        self.calls.append(cmd)
        target = cmd[-1]
        if any(f in target for f in self.fail_for):
            raise subprocess.CalledProcessError(1, cmd, output="", stderr="boom")
        if "clone" in cmd:
            # Simulate `git clone --mirror` creating the bare repo dir so a
            # second run of the same manifest sees it as "existing".
            Path(target).mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")


class TestMirrorGitRepos:
    def test_clones_new_repo(self, tmp_path):
        run = FakeRun()
        entries = [GitRepoEntry(name="widgets", url="https://example.com/widgets.git", dest="widgets.git")]

        report = mirror_git_repos(entries, tmp_path / "repos", run=run)

        assert report.cloned == ["widgets"]
        assert report.updated == report.failed == []
        assert ["git", "clone", "--mirror", "https://example.com/widgets.git",
                str(tmp_path / "repos" / "widgets.git")] in run.calls

    def test_updates_existing_repo(self, tmp_path):
        repos_root = tmp_path / "repos"
        (repos_root / "widgets.git").mkdir(parents=True)
        run = FakeRun()
        entries = [GitRepoEntry(name="widgets", url="https://example.com/widgets.git", dest="widgets.git")]

        report = mirror_git_repos(entries, repos_root, run=run)

        assert report.updated == ["widgets"]
        assert report.cloned == []
        assert run.calls == [["git", "remote", "update", "--prune"]]

    def test_second_run_updates_instead_of_reclones(self, tmp_path):
        run = FakeRun()
        entries = [GitRepoEntry(name="widgets", url="https://example.com/widgets.git", dest="widgets.git")]
        repos_root = tmp_path / "repos"

        first = mirror_git_repos(entries, repos_root, run=run)
        second = mirror_git_repos(entries, repos_root, run=run)

        assert first.cloned == ["widgets"]
        assert second.updated == ["widgets"]

    def test_clone_failure_is_reported_not_raised(self, tmp_path):
        run = FakeRun(fail_for=["widgets.git"])
        entries = [GitRepoEntry(name="widgets", url="https://example.com/widgets.git", dest="widgets.git")]

        report = mirror_git_repos(entries, tmp_path / "repos", run=run)

        assert report.failed == ["widgets"]
        assert report.cloned == []

    def test_one_failure_does_not_block_others(self, tmp_path):
        run = FakeRun(fail_for=["broken.git"])
        entries = [
            GitRepoEntry(name="broken", url="https://example.com/broken.git", dest="broken.git"),
            GitRepoEntry(name="ok", url="https://example.com/ok.git", dest="ok.git"),
        ]

        report = mirror_git_repos(entries, tmp_path / "repos", run=run)

        assert report.failed == ["broken"]
        assert report.cloned == ["ok"]


# ---- sync_tarballs ----

def fake_download_writer(content: bytes):
    def _download(url, dest: Path):
        dest.write_bytes(content)
    return _download


def failing_download(url, dest: Path):
    raise ConnectionError("upstream unreachable")


class TestSyncTarballs:
    def test_downloads_new_file(self, tmp_path):
        entries = [TarballEntry(url="https://example.com/tool.tar.gz", dest="tools/tool.tar.gz")]

        report = sync_tarballs(entries, tmp_path / "files", download=fake_download_writer(b"payload"))

        assert report.downloaded == ["tools/tool.tar.gz"]
        assert (tmp_path / "files" / "tools" / "tool.tar.gz").read_bytes() == b"payload"

    def test_skips_existing_file_without_downloading(self, tmp_path):
        artifacts_root = tmp_path / "files"
        existing = artifacts_root / "tool.tar.gz"
        existing.parent.mkdir(parents=True)
        existing.write_bytes(b"original")
        entries = [TarballEntry(url="https://example.com/tool.tar.gz", dest="tool.tar.gz")]
        calls = []

        report = sync_tarballs(entries, artifacts_root, download=lambda url, dest: calls.append(url))

        assert report.skipped == ["tool.tar.gz"]
        assert calls == []
        assert existing.read_bytes() == b"original"  # untouched

    def test_failed_download_does_not_leave_partial_file(self, tmp_path):
        entries = [TarballEntry(url="https://example.com/tool.tar.gz", dest="tool.tar.gz")]

        report = sync_tarballs(entries, tmp_path / "files", download=failing_download)

        assert report.failed == ["tool.tar.gz"]
        assert not (tmp_path / "files" / "tool.tar.gz").exists()
        assert list((tmp_path / "files").iterdir()) == []

    def test_refuses_to_escape_artifacts_root(self, tmp_path):
        # manifest.py normally blocks '..' in dest; this is sync_tarballs's
        # own belt-and-suspenders check on whatever it's handed.
        entries = [TarballEntry(url="https://example.com/evil", dest="../escape.txt")]

        report = sync_tarballs(entries, tmp_path / "files", download=fake_download_writer(b"x"))

        assert report.failed == ["../escape.txt"]
        assert not (tmp_path / "escape.txt").exists()


# ---- describe_changes / sync_forever ----

class _Report:
    """Minimal stand-in for the Git/Tarball report dataclasses."""
    def __init__(self, cloned=(), updated=(), downloaded=(), skipped=(), failed=()):
        self.cloned = list(cloned)
        self.updated = list(updated)
        self.downloaded = list(downloaded)
        self.skipped = list(skipped)
        self.failed = list(failed)


def _result(**kw):
    return {"git": _Report(**kw.get("git", {})),
            "tarballs": _Report(**kw.get("tarballs", {}))}


class TestDescribeChanges:
    def test_steady_state_is_silent(self):
        # Nothing new: repos merely re-fetched, tarballs already present.
        # This is what almost every pass looks like, so it must not log.
        assert describe_changes(_result(git={"updated": ["widgets"]},
                                        tarballs={"skipped": ["tools/tool.txt"]})) == ""

    def test_reports_new_content(self):
        out = describe_changes(_result(git={"cloned": ["widgets"]},
                                        tarballs={"downloaded": ["tools/tool.txt"]}))
        assert "cloned widgets" in out
        assert "downloaded tools/tool.txt" in out

    def test_reports_failures(self):
        out = describe_changes(_result(git={"failed": ["widgets"]}))
        assert "FAILED git widgets" in out


class TestSyncForever:
    def test_keeps_going_after_a_failing_pass(self):
        """A failing pass must not escape the loop -- if this process exits,
        the mirror silently stops updating."""
        calls = []

        def flaky(config):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("config repo unreachable")
            return _result(git={"cloned": ["widgets"]})

        sync_forever({"interval_seconds": 0}, sleep=lambda _: None,
                     run_once=flaky, iterations=3)

        assert len(calls) == 3  # kept going past the exception

    def test_sleeps_the_configured_interval_between_passes(self):
        slept = []
        sync_forever({"interval_seconds": 60}, sleep=slept.append,
                     run_once=lambda c: _result(), iterations=3)
        # Sleeps between passes, not after the last one.
        assert slept == [60, 60]


# ---- _checkout_config_repo ----

class TestCheckoutConfigRepo:
    def test_captures_git_output_so_steady_state_is_silent(self, tmp_path):
        """git chatters to stderr on every fetch. At one pass a minute that
        buries real events, so the output must be captured, not inherited."""
        calls = []

        def fake_run(args, **kwargs):
            calls.append(kwargs)
            return subprocess.CompletedProcess(args, 0, "", "")

        _checkout_config_repo("https://example.com/c.git", "main",
                              tmp_path / "checkout", run=fake_run)

        assert calls, "expected git to be invoked"
        assert all(kw.get("capture_output") for kw in calls)

    def test_failure_surfaces_git_stderr(self, tmp_path):
        """Quiet must not mean undiagnosable -- the reason has to survive."""
        def fake_run(args, **kwargs):
            raise subprocess.CalledProcessError(
                128, args, output="", stderr="fatal: Authentication failed")

        with pytest.raises(RuntimeError, match="Authentication failed"):
            _checkout_config_repo("https://example.com/c.git", "main",
                                  tmp_path / "checkout", run=fake_run)
