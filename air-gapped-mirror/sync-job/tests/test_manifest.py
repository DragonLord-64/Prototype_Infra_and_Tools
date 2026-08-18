import pytest

from mirror_sync.manifest import (
    ManifestError,
    load_git_repo_manifest,
    load_tarball_manifest,
)


def write(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content)
    return path


class TestGitRepoManifest:
    def test_valid_entries(self, tmp_path):
        path = write(tmp_path, "repos.yaml", """
repos:
  - name: widgets
    url: https://example.com/widgets.git
    dest: widgets
  - name: gadgets
    url: git://example.com/gadgets.git
    dest: sub/gadgets.git
""")
        entries = load_git_repo_manifest(path)
        assert [e.name for e in entries] == ["widgets", "gadgets"]
        # .git suffix is appended when missing, left alone when present
        assert entries[0].dest == "widgets.git"
        assert entries[1].dest == "sub/gadgets.git"

    def test_missing_field_rejected(self, tmp_path):
        path = write(tmp_path, "repos.yaml", """
repos:
  - name: widgets
    url: https://example.com/widgets.git
""")
        with pytest.raises(ManifestError, match="dest"):
            load_git_repo_manifest(path)

    def test_path_traversal_rejected(self, tmp_path):
        path = write(tmp_path, "repos.yaml", """
repos:
  - name: evil
    url: https://example.com/evil.git
    dest: ../../etc/evil
""")
        with pytest.raises(ManifestError, match=r"\.\."):
            load_git_repo_manifest(path)

    def test_absolute_dest_rejected(self, tmp_path):
        path = write(tmp_path, "repos.yaml", """
repos:
  - name: evil
    url: https://example.com/evil.git
    dest: /etc/evil
""")
        with pytest.raises(ManifestError, match="absolute"):
            load_git_repo_manifest(path)

    def test_bad_scheme_rejected(self, tmp_path):
        path = write(tmp_path, "repos.yaml", """
repos:
  - name: evil
    url: file:///etc/passwd
    dest: evil
""")
        with pytest.raises(ManifestError, match="scheme"):
            load_git_repo_manifest(path)

    def test_duplicate_dest_rejected(self, tmp_path):
        path = write(tmp_path, "repos.yaml", """
repos:
  - name: one
    url: https://example.com/one.git
    dest: shared
  - name: two
    url: https://example.com/two.git
    dest: shared
""")
        with pytest.raises(ManifestError, match="duplicate"):
            load_git_repo_manifest(path)

    def test_missing_top_level_key_rejected(self, tmp_path):
        path = write(tmp_path, "repos.yaml", "not_repos: []\n")
        with pytest.raises(ManifestError, match="repos"):
            load_git_repo_manifest(path)


class TestTarballManifest:
    def test_valid_entries(self, tmp_path):
        path = write(tmp_path, "tarballs.yaml", """
files:
  - url: https://example.com/tool.tar.gz
    dest: tools/tool.tar.gz
""")
        entries = load_tarball_manifest(path)
        assert entries[0].dest == "tools/tool.tar.gz"

    def test_git_scheme_rejected_for_tarballs(self, tmp_path):
        path = write(tmp_path, "tarballs.yaml", """
files:
  - url: git://example.com/tool.tar.gz
    dest: tools/tool.tar.gz
""")
        with pytest.raises(ManifestError, match="scheme"):
            load_tarball_manifest(path)

    def test_traversal_rejected(self, tmp_path):
        path = write(tmp_path, "tarballs.yaml", """
files:
  - url: https://example.com/tool.tar.gz
    dest: ../outside.tar.gz
""")
        with pytest.raises(ManifestError):
            load_tarball_manifest(path)
