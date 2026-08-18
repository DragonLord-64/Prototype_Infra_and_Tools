"""Sync job for the air-gapped mirror system.

Reads a manifest of Git repos, tarballs/binaries, and SSH public keys from
the private GitLab config repo and reconciles the mirror pod's shared
volumes to match.
"""
