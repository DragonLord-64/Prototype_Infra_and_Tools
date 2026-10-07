#!/bin/sh
# devpi-init only runs once; the serverdir on the mounted volume is what
# makes state (cached packages) survive container restarts.
set -eu

SERVERDIR="${DEVPI_SERVERDIR:-/var/devpi}"

if [ ! -d "$SERVERDIR/.nodeinfo" ] && [ ! -f "$SERVERDIR/.nodeinfo" ]; then
  devpi-init --serverdir "$SERVERDIR"
fi

exec devpi-server --serverdir "$SERVERDIR" --host 0.0.0.0 --port 3141
