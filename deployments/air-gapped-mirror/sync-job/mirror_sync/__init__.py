"""Sync job for the air-gapped mirror system.

Reads a manifest of Git repos from a mounted ConfigMap and reconciles the
mirror pod's bare-repo volume to match.
"""
