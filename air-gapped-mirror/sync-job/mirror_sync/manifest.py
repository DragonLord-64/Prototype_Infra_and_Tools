"""Loaders/validators for the manifests stored in the private config repo.

Three manifests drive the sync job:
  * a Git repo manifest (name/url/dest -> mirrored as bare repos)
  * a tarball/binary manifest (url/dest -> downloaded into the nginx tree)
  * an authorized_keys manifest (name/key -> regenerated for the SCP user)

All destination paths are validated as relative, traversal-free paths since
they land directly in directory trees served over plain HTTP or reachable
by SFTP -- a bad manifest entry must not be able to write outside its root.
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


@dataclasses.dataclass(frozen=True)
class SshKeyEntry:
    name: str
    key: str  # full authorized_keys line, e.g. "ssh-ed25519 AAAA... alice"


_ALLOWED_FETCH_SCHEMES = ("http://", "https://")
_ALLOWED_GIT_SCHEMES = ("http://", "https://", "git://", "ssh://", "git@")
_ALLOWED_KEY_TYPES = (
    "ssh-ed25519",
    "ssh-rsa",
    "ecdsa-sha2-nistp256",
    "ecdsa-sha2-nistp384",
    "ecdsa-sha2-nistp521",
    "sk-ssh-ed25519@openssh.com",
    "sk-ecdsa-sha2-nistp256@openssh.com",
)


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


def load_authorized_keys_manifest(path) -> List[SshKeyEntry]:
    entries: List[SshKeyEntry] = []
    seen_names = set()
    for i, raw in enumerate(_load_yaml_list(path, key="keys")):
        name = _require_str(raw, "name", i)
        key = _require_str(raw, "key", i)
        if not key.startswith(_ALLOWED_KEY_TYPES):
            raise ManifestError(f"keys[{i}] ({name}): unrecognized key type")
        if len(key.split()) < 2:
            raise ManifestError(f"keys[{i}] ({name}): malformed public key")
        if name in seen_names:
            raise ManifestError(f"keys[{i}]: duplicate name {name!r}")
        seen_names.add(name)
        entries.append(SshKeyEntry(name=name, key=key))
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
