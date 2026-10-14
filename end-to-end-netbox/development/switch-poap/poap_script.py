#!/usr/bin/env python
#md5sum="c716bdd3edb126cd2b1a06bde78c019d"
"""Serve unchanged to every switch. Run --checksum after editing this file."""
from __future__ import print_function
import hashlib
import os
import re
import sys
import subprocess
try:
    from urllib.parse import urlsplit
except ImportError:  # NX-OS images with Python 2.7
    from urlparse import urlsplit

# Optional: paste the controller's RSA PUBLIC key here (ssh-rsa AAAA... comment).
# No private key or hashing is needed. admin/admin remains available initially.
SSH_PUBLIC_KEY = ""

# Set to the full HTTP(S) URL of switch_inventory.yaml beside this script.
# Empty disables lookup and preserves the original DHCP bootstrap.
INVENTORY_URL = ""
# NX-OS maps VRFs to Linux namespaces. Blank explicitly uses inherited routing.
INVENTORY_VRF = os.environ.get("POAP_VRF", "management")
# Required for an off-subnet Ansible controller; blank means on-link only.
MANAGEMENT_GATEWAY = ""
MAX_INVENTORY_BYTES = 65536
CONNECT_TIMEOUT_SECONDS = 5
FETCH_TIMEOUT_SECONDS = 15


def ipv4_number(value):
    if not re.match(r"(?:0|[1-9][0-9]{0,2})(?:\.(?:0|[1-9][0-9]{0,2})){3}\Z", value):
        raise ValueError("Expected a dotted IPv4 address")
    octets = [int(part) for part in value.split(".")]
    if any(part > 255 for part in octets) or octets[0] in (0, 127) or octets[0] >= 224:
        raise ValueError("Expected a unicast IPv4 address")
    return sum(part << shift for part, shift in zip(octets, (24, 16, 8, 0)))


def validate_address(address, gateway=""):
    if not re.match(r"[0-9.]+/(?:[1-9]|[12][0-9]|30)\Z", address):
        raise ValueError("Expected IPv4 CIDR with prefix 1..30")
    host, prefix = address.split("/")
    number = ipv4_number(host)
    mask = (0xffffffff << (32 - int(prefix))) & 0xffffffff
    network, broadcast = number & mask, (number & mask) | (0xffffffff ^ mask)
    if number in (network, broadcast):
        raise ValueError("Network or broadcast address")
    if gateway:
        router = ipv4_number(gateway)
        if router & mask != network or router in (number, network, broadcast):
            raise ValueError("Gateway must be a distinct host in the management subnet")
    return address


def parse_inventory(payload):
    """Strict flat YAML mapping, deliberately not a general YAML loader."""
    if len(payload) > MAX_INVENTORY_BYTES:
        raise ValueError("Inventory too large")
    text = payload.decode("utf-8")
    # Only safe plain/quoted scalar serial: CIDR pairs, comments, and a single
    # optional document envelope. No aliases, tags, nesting, lists, or escapes.
    scalar = r"(?:[A-Za-z0-9_.-]+|'[A-Za-z0-9_.-]+'|\"[A-Za-z0-9_.-]+\")"
    value = r"(?:[0-9./]+|'[0-9./]+'|\"[0-9./]+\")"
    pair = re.compile(r"(" + scalar + r"):[ ]+(" + value + r")[ ]*(?:[ ]#.*)?\Z")
    records, ips = {}, set()
    started, ended = False, False
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line == "---" and not started and not ended:
            started = True
            continue
        if line == "..." and started and not ended:
            ended = True
            continue
        match = pair.match(line)
        if ended or not match:
            raise ValueError("Unsupported inventory YAML")
        started = True
        serial, address = [item.strip("\"'") for item in match.groups()]
        validate_address(address)
        ip = address.split("/")[0]
        if serial in records or ip in ips:
            raise ValueError("Duplicate inventory serial or IP")
        records[serial] = address
        ips.add(ip)
    if not records:
        raise ValueError("Empty inventory")
    return records


def fetch_inventory(url):
    if any(ord(char) <= 32 or ord(char) >= 127 for char in url):
        raise ValueError("Invalid inventory URL")
    parsed = urlsplit(url)
    if (parsed.scheme not in ("http", "https") or not parsed.hostname or
            parsed.username is not None or parsed.password is not None or parsed.fragment):
        raise ValueError("Expected an HTTP(S) URL without credentials or fragment")
    # No shell interpolation, redirects, curlrc, retries, or persistent cache.
    # The bounded pipe read also limits bodies without Content-Length on old curl.
    command = ["curl", "-q", "--globoff", "--fail", "--silent", "--show-error",
               "--connect-timeout", str(CONNECT_TIMEOUT_SECONDS),
               "--max-time", str(FETCH_TIMEOUT_SECONDS),
               "--max-filesize", str(MAX_INVENTORY_BYTES),
               "--write-out", "\n%{http_code}", "--url", url]
    if INVENTORY_VRF:
        if not re.match(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}\Z", INVENTORY_VRF):
            raise ValueError("Invalid inventory VRF")
        command = ["ip", "netns", "exec", INVENTORY_VRF] + command
    with open(os.devnull, "wb") as errors:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors)
        try:
            result = process.stdout.read(MAX_INVENTORY_BYTES + 5)
            if len(result) > MAX_INVENTORY_BYTES + 4:
                raise ValueError("Inventory too large")
            if process.wait() != 0 or not result.endswith(b"\n200"):
                raise ValueError("Inventory download failed")
            payload = result[:-4]
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
            process.stdout.close()
    return payload


def inventory_address():
    if not INVENTORY_URL:
        return None
    try:
        serial = os.environ.get("POAP_SERIAL", "").strip()
        if not serial or not re.match(r"[A-Za-z0-9_.-]+\Z", serial):
            raise ValueError("Missing POAP serial")
        address = parse_inventory(fetch_inventory(INVENTORY_URL)).get(serial)
        if address is None:
            raise ValueError("Serial not in inventory")
        validate_address(address, MANAGEMENT_GATEWAY)
        print("POAP inventory matched; scheduling static management address")
        return address
    except Exception:
        # Do not log response bodies, URLs, serials, or exception details.
        sys.stderr.write("POAP inventory unavailable or invalid; keeping DHCP\n")
        return None


def configuration(address=None):
    if address is not None:
        validate_address(address, MANAGEMENT_GATEWAY)
    lines = [
        "no password strength-check",
        "username admin password 0 admin role network-admin",
        "feature ssh",
        "interface mgmt0",
        "  vrf member management",
        "  ip address " + (address if address is not None else "dhcp"),
        "  no shutdown",
    ]
    if address is not None and MANAGEMENT_GATEWAY:
        lines.extend(["vrf context management",
                      "  ip route 0.0.0.0/0 " + MANAGEMENT_GATEWAY])
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
    config = configuration(inventory_address())
    with open("/bootflash/poap-ssh.cfg", "w") as output:
        output.write(config)
    os.chmod("/bootflash/poap-ssh.cfg", 0o600)
    # NX-OS replays this during POAP completion; lookup never changes live mgmt0.
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

