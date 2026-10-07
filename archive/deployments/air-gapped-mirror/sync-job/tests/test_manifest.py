import pytest

from mirror_sync.manifest import ManifestError, load_git_repo_manifest


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
    dest: org/widgets
  - name: tooling
    url: git://example.com/tooling.git
    dest: vendor/tooling.git
""")
        entries = load_git_repo_manifest(path)
        assert [e.name for e in entries] == ["widgets", "tooling"]
        # `.git` is appended when it's missing, left alone when it isn't.
        assert [e.dest for e in entries] == ["org/widgets.git", "vendor/tooling.git"]

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
        with pytest.raises(ManifestError, match="relative"):
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
    dest: same
  - name: two
    url: https://example.com/two.git
    dest: same.git
""")
        with pytest.raises(ManifestError, match="duplicate"):
            load_git_repo_manifest(path)

    def test_missing_top_level_key_rejected(self, tmp_path):
        path = write(tmp_path, "repos.yaml", "somethingelse: []\n")
        with pytest.raises(ManifestError, match="repos"):
            load_git_repo_manifest(path)

    def test_empty_manifest_is_valid(self, tmp_path):
        """An empty repo list is a legitimate steady state, not an error --
        the ConfigMap renders `repos: []` when nothing is configured yet."""
        path = write(tmp_path, "repos.yaml", "repos: []\n")
        assert load_git_repo_manifest(path) == []
