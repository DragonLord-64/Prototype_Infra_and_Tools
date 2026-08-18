import subprocess
from pathlib import Path

from mirror_sync.manifest import GitRepoEntry, SshKeyEntry, TarballEntry
from mirror_sync.sync import (
    GitLabClient,
    MergedMergeRequest,
    load_state,
    mirror_git_repos,
    regenerate_authorized_keys,
    save_state,
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


# ---- regenerate_authorized_keys ----

class TestRegenerateAuthorizedKeys:
    def test_writes_sorted_deterministic_content(self, tmp_path):
        entries = [
            SshKeyEntry(name="bob", key="ssh-rsa BBBB bob@work"),
            SshKeyEntry(name="alice", key="ssh-ed25519 AAAA alice@laptop"),
        ]
        out = tmp_path / "ssh" / "uploader"

        regenerate_authorized_keys(entries, out)

        content = out.read_text()
        assert content.index("ssh-ed25519 AAAA alice@laptop") < content.index("ssh-rsa BBBB bob@work")
        assert content.startswith("# Managed by the air-gapped mirror sync job")

    def test_written_atomically_no_tmp_file_left_behind(self, tmp_path):
        out = tmp_path / "ssh" / "uploader"
        regenerate_authorized_keys([SshKeyEntry(name="alice", key="ssh-ed25519 AAAA alice")], out)

        assert out.exists()
        assert not (tmp_path / "ssh" / "uploader.tmp").exists()

    def test_permissions_restricted(self, tmp_path):
        out = tmp_path / "ssh" / "uploader"
        regenerate_authorized_keys([SshKeyEntry(name="alice", key="ssh-ed25519 AAAA alice")], out)

        assert (out.stat().st_mode & 0o777) == 0o600

    def test_overwrites_removed_keys(self, tmp_path):
        out = tmp_path / "ssh" / "uploader"
        regenerate_authorized_keys([SshKeyEntry(name="alice", key="ssh-ed25519 AAAA alice")], out)
        regenerate_authorized_keys([SshKeyEntry(name="bob", key="ssh-rsa BBBB bob")], out)

        content = out.read_text()
        assert "alice" not in content
        assert "bob" in content


# ---- GitLabClient.fetch_merged_mrs ----

class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class FakeSession:
    """Records requests and serves canned pages, keyed by page number."""

    def __init__(self, pages):
        self.pages = pages
        self.requests = []

    def get(self, url, headers=None, params=None, timeout=None):
        self.requests.append({"url": url, "headers": headers, "params": dict(params)})
        return FakeResponse(self.pages.get(params["page"], []))


def mr(iid, title="a change"):
    return {"iid": iid, "title": title, "merged_at": "2026-01-01T00:00:00Z",
            "web_url": f"https://gitlab.com/x/-/merge_requests/{iid}"}


class TestFetchMergedMrs:
    def test_returns_all_when_no_since_iid(self):
        session = FakeSession({1: [mr(1), mr(2)]})
        client = GitLabClient("https://gitlab.com", "group/project", session=session)

        results = client.fetch_merged_mrs()

        assert [r.iid for r in results] == [1, 2]

    def test_filters_by_since_iid(self):
        session = FakeSession({1: [mr(1), mr(2), mr(3)]})
        client = GitLabClient("https://gitlab.com", "group/project", session=session)

        results = client.fetch_merged_mrs(since_iid=1)

        assert [r.iid for r in results] == [2, 3]

    def test_paginates_until_short_page(self):
        session = FakeSession({1: [mr(1), mr(2)], 2: [mr(3)]})
        client = GitLabClient("https://gitlab.com", "group/project", session=session)

        results = client.fetch_merged_mrs(per_page=2)

        assert [r.iid for r in results] == [1, 2, 3]
        assert len(session.requests) == 2

    def test_stops_on_empty_page(self):
        session = FakeSession({1: []})
        client = GitLabClient("https://gitlab.com", "group/project", session=session)

        assert client.fetch_merged_mrs() == []
        assert len(session.requests) == 1

    def test_project_path_is_url_encoded(self):
        session = FakeSession({1: []})
        client = GitLabClient("https://gitlab.com", "group/sub/project", session=session)

        client.fetch_merged_mrs()

        assert "group%2Fsub%2Fproject" in session.requests[0]["url"]

    def test_sends_private_token_header_when_configured(self):
        session = FakeSession({1: []})
        client = GitLabClient("https://gitlab.com", "group/project", token="secret-pat", session=session)

        client.fetch_merged_mrs()

        assert session.requests[0]["headers"]["PRIVATE-TOKEN"] == "secret-pat"

    def test_omits_token_header_when_not_configured(self):
        session = FakeSession({1: []})
        client = GitLabClient("https://gitlab.com", "group/project", session=session)

        client.fetch_merged_mrs()

        assert "PRIVATE-TOKEN" not in session.requests[0]["headers"]


# ---- state ----

class TestLoadState:
    def test_missing_file_returns_defaults(self, tmp_path):
        assert load_state(tmp_path / "does-not-exist.json") == {"last_mr_iid": 0, "last_synced_at": None}

    def test_corrupt_file_falls_back_to_defaults(self, tmp_path):
        path = tmp_path / "state.json"
        path.write_text("{not valid json")

        assert load_state(path) == {"last_mr_iid": 0, "last_synced_at": None}

    def test_missing_keys_are_backfilled_with_defaults(self, tmp_path):
        path = tmp_path / "state.json"
        path.write_text('{"last_mr_iid": 42}')

        state = load_state(path)

        assert state["last_mr_iid"] == 42
        assert state["last_synced_at"] is None


class TestSaveState:
    def test_round_trip(self, tmp_path):
        path = tmp_path / "nested" / "state.json"
        save_state(path, {"last_mr_iid": 7, "last_synced_at": "2026-01-01T00:00:00+00:00"})

        state = load_state(path)

        assert state["last_mr_iid"] == 7
        assert state["last_synced_at"] == "2026-01-01T00:00:00+00:00"

    def test_no_tmp_file_left_behind(self, tmp_path):
        path = tmp_path / "state.json"
        save_state(path, {"last_mr_iid": 1})

        assert path.exists()
        assert not (tmp_path / "state.json.tmp").exists()

    def test_overwrites_previous_state(self, tmp_path):
        path = tmp_path / "state.json"
        save_state(path, {"last_mr_iid": 1})
        save_state(path, {"last_mr_iid": 2})

        assert load_state(path)["last_mr_iid"] == 2
