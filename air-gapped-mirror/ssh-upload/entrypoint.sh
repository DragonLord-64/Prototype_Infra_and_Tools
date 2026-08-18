#!/bin/sh
set -eu

mkdir -p /run/sshd

# authorized_keys/uploader lives on the same shared volume the sync job
# writes to (see AUTHORIZED_KEYS_PATH in sync-job/mirror_sync/main.py).
# sshd requires strict permissions on it and its parent directory.
if [ -f /etc/ssh/authorized_keys/uploader ]; then
  chmod 600 /etc/ssh/authorized_keys/uploader
fi
chmod 755 /etc/ssh/authorized_keys

exec /usr/sbin/sshd -D -e
