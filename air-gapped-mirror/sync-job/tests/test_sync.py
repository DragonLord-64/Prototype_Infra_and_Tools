import subprocess
from pathlib import Path

from mirror_sync.manifest import GitRepoEntry
from mirror_sync.sync import (
    describe_changes,
    mirror_git_repos,
    run_sync,
    sync_forever,
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


# ---- run_sync reads the manifest every pass ----

class TestRunSyncRereadsManifest:
    def test_manifest_edit_is_picked_up_without_restart(self, tmp_path):
        """The ConfigMap is remounted in place, so a pass must re-read the
        file rather than caching entries from a previous pass."""
        manifest = tmp_path / "git-repos.yaml"
        manifest.write_text("""
repos:
  - name: first
    url: https://example.com/first.git
    dest: first
""")
        run = FakeRun()
        config = {"git_manifest": str(manifest), "git_repos_root": str(tmp_path / "repos")}

        assert run_sync(config, run=run)["git"].cloned == ["first"]

        manifest.write_text("""
repos:
  - name: first
    url: https://example.com/first.git
    dest: first
  - name: second
    url: https://example.com/second.git
    dest: second
""")

        second = run_sync(config, run=run)
        assert second["git"].cloned == ["second"]   # the new one
        assert second["git"].updated == ["first"]   # the existing one


# ---- describe_changes / sync_forever ----

class _Report:
    """Minimal stand-in for GitSyncReport."""
    def __init__(self, cloned=(), updated=(), failed=()):
        self.cloned = list(cloned)
        self.updated = list(updated)
        self.failed = list(failed)


def _result(**kw):
    return {"git": _Report(**kw)}


class TestDescribeChanges:
    def test_steady_state_is_silent(self):
        # Nothing new: repos merely re-fetched. This is what almost every
        # pass looks like, so it must not log.
        assert describe_changes(_result(updated=["widgets"])) == ""

    def test_reports_new_content(self):
        assert "cloned widgets" in describe_changes(_result(cloned=["widgets"]))

    def test_reports_failures(self):
        assert "FAILED git widgets" in describe_changes(_result(failed=["widgets"]))


class TestSyncForever:
    def test_keeps_going_after_a_failing_pass(self):
        """A failing pass must not escape the loop -- if this process exits,
        the mirror silently stops updating."""
        calls = []

        def flaky(config):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("manifest unreadable")
            return _result(cloned=["widgets"])

        sync_forever({"interval_seconds": 0}, sleep=lambda _: None,
                     run_once=flaky, iterations=3)

        assert len(calls) == 3  # kept going past the exception

    def test_sleeps_the_configured_interval_between_passes(self):
        slept = []
        sync_forever({"interval_seconds": 60}, sleep=slept.append,
                     run_once=lambda c: _result(), iterations=3)
        # Sleeps between passes, not after the last one.
        assert slept == [60, 60]
