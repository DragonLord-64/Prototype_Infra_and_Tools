#!/usr/bin/env python
#md5sum="6e4bcb214131b4be3f5c505651a5d1bc"
"""Serve unchanged to every switch. Run --checksum after editing this file."""
from __future__ import print_function
import hashlib
import os
import re
import sys

# Optional: paste the controller's RSA PUBLIC key here (ssh-rsa AAAA... comment).
# No private key or hashing is needed. admin/admin remains available initially.
SSH_PUBLIC_KEY = ""


def configuration():
    lines = [
        "no password strength-check",
        "username admin password 0 admin role network-admin",
        "feature ssh",
        "interface mgmt0",
        "  vrf member management",
        "  ip address dhcp",
        "  no shutdown",
    ]
    if SSH_PUBLIC_KEY:
        key = SSH_PUBLIC_KEY.split()
        if len(key) < 2 or key[0] != "ssh-rsa" or not re.match(r"^[A-Za-z0-9+/]+={0,2}$", key[1]):
            raise ValueError("Expected an OpenSSH RSA public key")
        # Discard the comment; only the algorithm and public key go to NX-OS.
        lines.insert(3, "username admin sshkey " + " ".join(key[:2]))
    return "\n".join(lines) + "\n"


def bootstrap():
    try:
        from cli import cli
    except ImportError:
        from cisco import cli
    config = configuration()
    with open("/bootflash/poap-ssh.cfg", "w") as output:
        output.write(config)
    os.chmod("/bootflash/poap-ssh.cfg", 0o600)
    # NX-OS replays this during POAP completion. No serial/IP mapping required.
    cli("copy bootflash:poap-ssh.cfg scheduled-config")


def update_checksum():
    path = os.path.abspath(__file__)
    with open(path, "rb") as source:
        lines = source.readlines()
    body = b"".join(line for line in lines if not line.startswith(b"#md5sum="))
    header = ('#md5sum="%s"\n' % hashlib.md5(body).hexdigest()).encode("ascii")
    with open(path, "wb") as output:
        for line in lines:
            output.write(header if line.startswith(b"#md5sum=") else line)


if __name__ == "__main__":
    if sys.argv[1:] == ["--checksum"]:
        update_checksum()
    elif sys.argv[1:]:
        sys.exit("Usage: poap_script.py [--checksum]")
    else:
        try:
            bootstrap()
        except Exception:
            # CLI exception text may include account configuration.
            sys.stderr.write("POAP SSH bootstrap failed\n")
            sys.exit(1)
