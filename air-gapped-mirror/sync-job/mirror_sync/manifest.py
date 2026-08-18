"""Loaders/validators for the manifests stored in the config repo.

Two manifests drive the sync job:
  * a Git repo manifest (name/url/dest -> mirrored as bare repos)
  * a tarball/binary manifest (url/dest -> downloaded into the nginx tree)

All destination paths are validated as relative, traversal-free paths since
they land directly in directory trees served over plain HTTP -- a bad
manifest entry must not be able to write outside its root.
"""
from __future__ import annotations

import dataclasses
from pathlib import PurePosixPath
from typing import List

import yaml


class ManifestError(ValueError):
    pass


@dataclasses.dataclass(frozen=True)
class GitRepoEntry:
    name: str
    url: str
    dest: str  # relative path under the bare-repo root, e.g. "org/project.git"


@dataclasses.dataclass(frozen=True)
class TarballEntry:
    url: str
    dest: str  # relative path under the nginx-served root


_ALLOWED_FETCH_SCHEMES = ("http://", "https://")
_ALLOWED_GIT_SCHEMES = ("http://", "https://", "git://", "ssh://", "git@")


def load_git_repo_manifest(path) -> List[GitRepoEntry]:
    entries: List[GitRepoEntry] = []
    seen_dest = set()
    for i, raw in enumerate(_load_yaml_list(path, key="repos")):
        name = _require_str(raw, "name", i)
        url = _require_str(raw, "url", i)
        dest = _require_str(raw, "dest", i)
        if not url.startswith(_ALLOWED_GIT_SCHEMES):
            raise ManifestError(f"repos[{i}] ({name}): unsupported url scheme: {url!r}")
        dest = _validate_relative_dest(dest, f"repos[{i}] ({name})")
        if not dest.endswith(".git"):
            dest = f"{dest}.git"
        if dest in seen_dest:
            raise ManifestError(f"repos[{i}] ({name}): duplicate dest {dest!r}")
        seen_dest.add(dest)
        entries.append(GitRepoEntry(name=name, url=url, dest=dest))
    return entries


def load_tarball_manifest(path) -> List[TarballEntry]:
    entries: List[TarballEntry] = []
    seen_dest = set()
    for i, raw in enumerate(_load_yaml_list(path, key="files")):
        url = _require_str(raw, "url", i)
        dest = _require_str(raw, "dest", i)
        if not url.startswith(_ALLOWED_FETCH_SCHEMES):
            raise ManifestError(f"files[{i}]: unsupported url scheme: {url!r}")
        dest = _validate_relative_dest(dest, f"files[{i}]")
        if dest in seen_dest:
            raise ManifestError(f"files[{i}]: duplicate dest {dest!r}")
        seen_dest.add(dest)
        entries.append(TarballEntry(url=url, dest=dest))
    return entries


def _validate_relative_dest(dest: str, field: str) -> str:
    path = PurePosixPath(dest)
    if path.is_absolute():
        raise ManifestError(f"{field}: dest must be relative, got absolute path: {dest!r}")
    if ".." in path.parts:
        raise ManifestError(f"{field}: dest must not contain '..': {dest!r}")
    return dest


def _load_yaml_list(path, key):
    with open(path, "r") as f:
        doc = yaml.safe_load(f) or {}
    if not isinstance(doc, dict) or key not in doc:
        raise ManifestError(f"{path}: expected a top-level mapping with a {key!r} list")
    items = doc[key]
    if not isinstance(items, list):
        raise ManifestError(f"{path}: {key!r} must be a list")
    return items


def _require_str(raw, field, index) -> str:
    if not isinstance(raw, dict) or field not in raw:
        raise ManifestError(f"entry[{index}]: missing required field {field!r}")
    value = raw[field]
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"entry[{index}]: field {field!r} must be a non-empty string")
    return value.strip()
