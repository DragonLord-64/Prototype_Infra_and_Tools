"""Offline POAP inventory tests; no NX-OS, credentials, or external network.

Run with Python 3: python3 -m unittest discover -s end-to-end-netbox/tests -v
The production script targets Python 2.7 syntax; that runtime is unverified. These tests use the
Python 3 standard library and exercise curl against loopback only when installed.
"""

import contextlib
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import types
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock


SCRIPT_PATH = (Path(__file__).resolve().parents[1] / "development" /
               "switch-poap" / "poap_script.py")
SPEC = importlib.util.spec_from_file_location("poap_script_under_test", SCRIPT_PATH)
poap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(poap)

INVENTORY = b"SN-001: 192.0.2.10/24\nSN-002: 198.51.100.20/24\n"


class ArtifactTests(unittest.TestCase):
    def test_checksum_header_matches_script(self):
        lines = SCRIPT_PATH.read_bytes().splitlines(keepends=True)
        headers = [line for line in lines if line.startswith(b"#md5sum=")]
        body = b"".join(line for line in lines if not line.startswith(b"#md5sum="))
        self.assertEqual(headers, [('\x23md5sum="%s"\n' % hashlib.md5(body).hexdigest()).encode("ascii")])

    def test_example_inventory_is_supported(self):
        records = poap.parse_inventory(SCRIPT_PATH.with_name("switch_inventory.example.yaml").read_bytes())
        self.assertEqual(records["EXAMPLE001"], "192.0.2.10/24")


class InventoryParsingTests(unittest.TestCase):
    def test_plain_flat_mapping(self):
        self.assertEqual(poap.parse_inventory(INVENTORY), {
            "SN-001": "192.0.2.10/24", "SN-002": "198.51.100.20/24"})

    def test_quotes_comments_blank_lines_and_document_markers(self):
        payload = (b"# Inventory\n---\n\n'SN-001': \"192.0.2.10/24\" # first\n"
                   b'"SN_002": \'198.51.100.20/24\'\n'
                   b"SN.003: 203.0.113.30/24   \n...\n# End\n\n")
        self.assertEqual(poap.parse_inventory(payload), {
            "SN-001": "192.0.2.10/24", "SN_002": "198.51.100.20/24",
            "SN.003": "203.0.113.30/24"})

    def test_rejects_malformed_nested_or_unsafe_yaml(self):
        invalid = [
            b"", b"# only comments\n", b"---\n...\n",
            b" SN-001: 192.0.2.10/24\n",  # nesting/indentation
            b"- SN-001: 192.0.2.10/24\n",  # list
            b"SN-001:\n  address: 192.0.2.10/24\n",
            b"SN-001: {address: 192.0.2.10/24}\n",
            b"SN-001: [192.0.2.10/24]\n",
            b"SN-001: &ip 192.0.2.10/24\nSN-002: *ip\n",
            b"SN-001: !!str 192.0.2.10/24\n",
            b"SN-001: !!python/object/apply:os.system ['false']\n",
            b"SN-001: |\n  192.0.2.10/24\n",
            b"SN-001: >\n  192.0.2.10/24\n",
            b"SN-001:192.0.2.10/24\n",
            b"SN-001:\t192.0.2.10/24\n",
            b"SN-001: 192.0.2.10/24; feature telnet\n",
            b"SN-001: 192.0.2.10/24#not-a-comment\n",
            b"'SN\\n001': 192.0.2.10/24\n",
            b"SN-001: \"192.0.2.10/24\\nfeature telnet\"\n",
            b"SN-001: 192.0.2.10/24\x00\n",
            b"SN-001: 192.0.2.10/24\n---\nSN-002: 192.0.2.11/24\n",
            b"---\n---\nSN-001: 192.0.2.10/24\n",
            b"...\nSN-001: 192.0.2.10/24\n",
            b"SN-001: 192.0.2.10/24\n...\nSN-002: 192.0.2.11/24\n",
            b"SN-001: 192.0.2.10/24\n...\n...\n",
            b"\xffSN-001: 192.0.2.10/24\n",
        ]
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                poap.parse_inventory(payload)

    def test_duplicate_serial_or_ip_rejects_whole_inventory(self):
        for extra in (b"SN-001: 192.0.2.11/24\n",
                      b"'SN-001': 192.0.2.11/24\n",
                      b"SN-003: 192.0.2.10/24\n",
                      b"SN-003: 192.0.2.10/25\n"):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                poap.parse_inventory(INVENTORY + extra)

    def test_size_limit_applies_before_parsing(self):
        with mock.patch.object(poap, "MAX_INVENTORY_BYTES", len(INVENTORY)):
            self.assertEqual(len(poap.parse_inventory(INVENTORY)), 2)
            with self.assertRaises(ValueError):
                poap.parse_inventory(INVENTORY + b"\n")


class AddressValidationTests(unittest.TestCase):
    def test_valid_addresses_with_or_without_gateway(self):
        self.assertEqual(poap.validate_address("192.0.2.10/24"), "192.0.2.10/24")
        self.assertEqual(poap.validate_address("192.0.2.10/24", "192.0.2.1"),
                         "192.0.2.10/24")
        self.assertEqual(poap.validate_address("192.0.2.1/30", "192.0.2.2"),
                         "192.0.2.1/30")

    def test_invalid_address_or_prefix(self):
        for address in ("192.0.2.10", "192.0.2.10/0", "192.0.2.10/31",
                        "192.0.2.10/32", "192.0.2.10/33", "192.0.2.10/024",
                        "192.0.2.0/24", "192.0.2.255/24", "192.0.2.256/24",
                        "192.00.2.10/24", "127.0.0.1/8", "0.1.2.3/8",
                        "224.0.0.1/24", "255.255.255.255/24", "::1/24",
                        "192.0.2.10/24\n", "192.0.2.10/24;feature telnet"):
            with self.subTest(address=address), self.assertRaises(ValueError):
                poap.validate_address(address)

    def test_invalid_gateway(self):
        for gateway in ("198.51.100.1", "192.0.2.10", "192.0.2.0",
                        "192.0.2.255", "192.0.2.256", "192.0.2.1/24",
                        "192.0.02.1", "127.0.0.1", "::1", "192.0.2.1\n",
                        "192.0.2.1; feature telnet"):
            with self.subTest(gateway=gateway), self.assertRaises(ValueError):
                poap.validate_address("192.0.2.10/24", gateway)


class InventoryLookupTests(unittest.TestCase):
    def setUp(self):
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(mock.patch.object(poap, "INVENTORY_URL",
                                              "https://inventory.example/switches.yaml"))
        stack.enter_context(mock.patch.object(poap, "MANAGEMENT_GATEWAY", ""))
        stack.enter_context(mock.patch.dict(os.environ, {"POAP_SERIAL": "SN-001"}))
        self.stdout = stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.stderr = stack.enter_context(contextlib.redirect_stderr(io.StringIO()))

    def test_matching_serial_selects_static_address(self):
        with mock.patch.object(poap, "fetch_inventory", return_value=INVENTORY) as fetch:
            self.assertEqual(poap.inventory_address(), "192.0.2.10/24")
            fetch.assert_called_once_with(poap.INVENTORY_URL)

    def test_serial_is_trimmed_but_case_sensitive(self):
        with mock.patch.object(poap, "fetch_inventory", return_value=INVENTORY):
            with mock.patch.dict(os.environ, {"POAP_SERIAL": "  SN-001\n"}):
                self.assertEqual(poap.inventory_address(), "192.0.2.10/24")
            with mock.patch.dict(os.environ, {"POAP_SERIAL": "sn-001"}):
                self.assertIsNone(poap.inventory_address())

    def test_disabled_lookup_does_not_fetch(self):
        with mock.patch.object(poap, "INVENTORY_URL", ""), \
                mock.patch.object(poap, "fetch_inventory") as fetch:
            self.assertIsNone(poap.inventory_address())
            fetch.assert_not_called()

    def test_missing_or_unsafe_serial_does_not_fetch(self):
        for serial in ("", " ", "SN-001;feature telnet", "SN-001\nSN-002"):
            with self.subTest(serial=serial), \
                    mock.patch.dict(os.environ, {"POAP_SERIAL": serial}), \
                    mock.patch.object(poap, "fetch_inventory") as fetch:
                self.assertIsNone(poap.inventory_address())
                fetch.assert_not_called()

    def test_unmatched_malformed_duplicate_and_unsafe_inventory_fall_back(self):
        payloads = (b"OTHER: 192.0.2.20/24\n", b"not yaml", b"",
                    INVENTORY + b"SN-001: 192.0.2.11/24\n",
                    INVENTORY + b"BAD: 192.0.2.255/24\n",
                    b"SN-001: !!python/object/apply:os.system ['false']\n")
        for payload in payloads:
            with self.subTest(payload=payload), \
                    mock.patch.object(poap, "fetch_inventory", return_value=payload):
                self.assertIsNone(poap.inventory_address())

    def test_invalid_gateway_falls_back(self):
        with mock.patch.object(poap, "fetch_inventory", return_value=INVENTORY), \
                mock.patch.object(poap, "MANAGEMENT_GATEWAY", "198.51.100.1"):
            self.assertIsNone(poap.inventory_address())

    def test_download_exception_falls_back_without_leaking_details(self):
        with mock.patch.object(poap, "fetch_inventory",
                               side_effect=OSError("private response SN-001")):
            self.assertIsNone(poap.inventory_address())
        self.assertIn("keeping DHCP", self.stderr.getvalue())
        for private in ("SN-001", "inventory.example", "private response"):
            self.assertNotIn(private, self.stderr.getvalue() + self.stdout.getvalue())


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(mock.patch.object(poap, "MANAGEMENT_GATEWAY", ""))
        stack.enter_context(mock.patch.object(poap, "SSH_PUBLIC_KEY", ""))

    def assert_bootstrap_config(self, config, address):
        self.assertIn("username admin password 0 admin role network-admin\n", config)
        self.assertIn("feature ssh\n", config)
        self.assertIn("interface mgmt0\n  vrf member management\n", config)
        self.assertIn("  ip address " + address + "\n  no shutdown\n", config)

    def test_dhcp_configuration_preserves_admin_and_ssh(self):
        self.assert_bootstrap_config(poap.configuration(), "dhcp")

    def test_static_configuration_without_gateway_is_on_link_only(self):
        config = poap.configuration("192.0.2.10/24")
        self.assert_bootstrap_config(config, "192.0.2.10/24")
        self.assertNotIn("ip route", config)

    def test_static_gateway_uses_management_vrf(self):
        with mock.patch.object(poap, "MANAGEMENT_GATEWAY", "192.0.2.1"):
            config = poap.configuration("192.0.2.10/24")
            self.assertIn("vrf context management\n  ip route 0.0.0.0/0 192.0.2.1\n",
                          config)
            self.assertNotIn("ip route", poap.configuration())

    def test_public_key_comment_is_not_inserted_into_configuration(self):
        with mock.patch.object(poap, "SSH_PUBLIC_KEY", "ssh-rsa AAAAB3NzaA== note\ntext"):
            config = poap.configuration()
        self.assertIn("username admin sshkey ssh-rsa AAAAB3NzaA==\n", config)
        self.assertNotIn("note", config)
        self.assertNotIn("text", config)

    def test_invalid_public_key_is_rejected(self):
        for key in ("ssh-ed25519 AAAA", "ssh-rsa", "ssh-rsa AAAA;feature", "private"):
            with self.subTest(key=key), mock.patch.object(poap, "SSH_PUBLIC_KEY", key), \
                    self.assertRaises(ValueError):
                poap.configuration()

    def test_bootstrap_writes_protected_config_and_only_schedules_it(self):
        for address in (None, "192.0.2.10/24"):
            with self.subTest(address=address):
                cli_module = types.ModuleType("cli")
                cli_module.cli = mock.Mock()
                output = mock.mock_open()
                with mock.patch.dict(sys.modules, {"cli": cli_module}), \
                        mock.patch.object(poap, "inventory_address", return_value=address), \
                        mock.patch("builtins.open", output), \
                        mock.patch.object(poap.os, "chmod") as chmod:
                    poap.bootstrap()
                output.assert_called_once_with("/bootflash/poap-ssh.cfg", "w")
                config = output().write.call_args.args[0]
                self.assert_bootstrap_config(config, address or "dhcp")
                chmod.assert_called_once_with("/bootflash/poap-ssh.cfg", 0o600)
                cli_module.cli.assert_called_once_with(
                    "copy bootflash:poap-ssh.cfg scheduled-config")

    def test_bootstrap_supports_cisco_cli_import(self):
        cisco_module = types.ModuleType("cisco")
        cisco_module.cli = mock.Mock()
        with mock.patch.dict(sys.modules, {"cli": None, "cisco": cisco_module}), \
                mock.patch.object(poap, "inventory_address", return_value=None), \
                mock.patch("builtins.open", mock.mock_open()), \
                mock.patch.object(poap.os, "chmod"):
            poap.bootstrap()
        cisco_module.cli.assert_called_once_with(
            "copy bootflash:poap-ssh.cfg scheduled-config")


@mock.patch.object(poap, "INVENTORY_VRF", "")
class FetchUnitTests(unittest.TestCase):
    def process(self, payload=INVENTORY + b"\n200", exit_code=0, running=False):
        process = mock.Mock()
        process.stdout.read.return_value = payload
        process.wait.return_value = exit_code
        process.poll.return_value = None if running else exit_code
        return process

    def test_curl_uses_literal_argument_list_and_bounded_transfer(self):
        process = self.process()
        url = "https://inventory.example/switches.yaml?x=$(id)&y=1"
        with mock.patch.object(poap.subprocess, "Popen", return_value=process) as popen:
            self.assertEqual(poap.fetch_inventory(url), INVENTORY)
        command = popen.call_args.args[0]
        options = popen.call_args.kwargs
        self.assertIsInstance(command, list)
        self.assertEqual(command[:2], ["curl", "-q"])
        self.assertFalse(options.get("shell", False))
        self.assertEqual(options["stdout"], subprocess.PIPE)
        self.assertEqual(command[-2:], ["--url", url])
        for option, value in (("--connect-timeout", poap.CONNECT_TIMEOUT_SECONDS),
                              ("--max-time", poap.FETCH_TIMEOUT_SECONDS),
                              ("--max-filesize", poap.MAX_INVENTORY_BYTES)):
            self.assertEqual(command[command.index(option) + 1], str(value))
        self.assertIn("--fail", command)
        self.assertIn("--globoff", command)
        self.assertNotIn("--location", command)
        self.assertNotIn("-L", command)
        self.assertNotIn("--retry", command)
        process.stdout.read.assert_called_once_with(poap.MAX_INVENTORY_BYTES + 5)
        process.stdout.close.assert_called_once_with()
        process.kill.assert_not_called()

    def test_curl_uses_validated_vrf_namespace(self):
        for vrf in ("management", "default", "provisioning-1"):
            process = self.process()
            with mock.patch.object(poap, "INVENTORY_VRF", vrf), \
                    mock.patch.object(poap.subprocess, "Popen", return_value=process) as popen:
                poap.fetch_inventory("https://inventory.example/a")
            self.assertEqual(popen.call_args.args[0][:6],
                             ["ip", "netns", "exec", vrf, "curl", "-q"])
        for vrf in ("--bad", "management;id", "management\n", "a/b"):
            with mock.patch.object(poap, "INVENTORY_VRF", vrf), \
                    mock.patch.object(poap.subprocess, "Popen") as popen, \
                    self.assertRaises(ValueError):
                poap.fetch_inventory("https://inventory.example/a")
            popen.assert_not_called()

    def test_invalid_urls_are_rejected_without_starting_curl(self):
        for url in ("", "file:///tmp/inventory", "ftp://inventory.example/a",
                    "https:///inventory", "https://user:password@inventory.example/a",
                    "https://inventory.example/a#part", "https://inventory.example/a b",
                    "https://inventory.example/\n", "https://inventory.example/é"):
            with self.subTest(url=url), mock.patch.object(poap.subprocess, "Popen") as popen:
                with self.assertRaises(ValueError):
                    poap.fetch_inventory(url)
                popen.assert_not_called()

    def test_missing_curl_raises_and_lookup_keeps_dhcp(self):
        with mock.patch.object(poap.subprocess, "Popen",
                               side_effect=FileNotFoundError("curl")), \
                mock.patch.object(poap, "INVENTORY_URL", "https://inventory.example/a"), \
                mock.patch.dict(os.environ, {"POAP_SERIAL": "SN-001"}), \
                contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(OSError):
                poap.fetch_inventory(poap.INVENTORY_URL)
            self.assertIsNone(poap.inventory_address())

    def test_only_http_200_is_accepted(self):
        for status in (b"301", b"302", b"204", b"206", b"500"):
            process = self.process(payload=INVENTORY + b"\n" + status)
            with self.subTest(status=status), \
                    mock.patch.object(poap.subprocess, "Popen", return_value=process), \
                    self.assertRaises(ValueError):
                poap.fetch_inventory("https://inventory.example/a")

    def test_nonzero_curl_exit_is_rejected(self):
        for code in (22, 28):  # HTTP failure and timeout
            process = self.process(exit_code=code)
            with self.subTest(code=code), \
                    mock.patch.object(poap.subprocess, "Popen", return_value=process), \
                    self.assertRaises(ValueError):
                poap.fetch_inventory("https://inventory.example/a")
            process.stdout.close.assert_called_once_with()

    def test_oversized_pipe_read_kills_and_reaps_curl(self):
        process = self.process(payload=b"x" * (poap.MAX_INVENTORY_BYTES + 5), running=True)
        with mock.patch.object(poap.subprocess, "Popen", return_value=process), \
                self.assertRaises(ValueError):
            poap.fetch_inventory("https://inventory.example/a")
        process.kill.assert_called_once_with()
        process.wait.assert_called_once_with()
        process.stdout.close.assert_called_once_with()


class LoopbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/slow":
            time.sleep(0.3)
        if self.path == "/missing":
            self.send_error(404)
            return
        if self.path == "/oversize":
            body = b"x" * (poap.MAX_INVENTORY_BYTES + 1)
        elif self.path == "/unbounded":
            body = b"x" * (poap.MAX_INVENTORY_BYTES + 4096)
        else:
            body = INVENTORY
        self.send_response(200)
        if self.path != "/unbounded":
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # Expected when curl times out or refuses an oversized body.

    def log_message(self, *args):
        pass


@unittest.skipUnless(shutil.which("curl"), "curl is not installed")
@mock.patch.object(poap, "INVENTORY_VRF", "")
class CurlLoopbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), LoopbackHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = "http://127.0.0.1:%d" % cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        # Keep loopback requests away from any configured corporate proxy.
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(mock.patch.dict(os.environ, {
            "NO_PROXY": "127.0.0.1", "no_proxy": "127.0.0.1"}))

    def test_real_curl_downloads_inventory(self):
        self.assertEqual(poap.fetch_inventory(self.base_url + "/ok"), INVENTORY)

    def test_real_curl_rejects_http_404(self):
        with self.assertRaises(ValueError):
            poap.fetch_inventory(self.base_url + "/missing")

    def test_real_curl_timeout_is_bounded(self):
        start = time.monotonic()
        with mock.patch.object(poap, "FETCH_TIMEOUT_SECONDS", 0.05), \
                self.assertRaises(ValueError):
            poap.fetch_inventory(self.base_url + "/slow")
        self.assertLess(time.monotonic() - start, 2)

    def test_real_curl_rejects_oversized_response(self):
        for endpoint in ("/oversize", "/unbounded"):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                poap.fetch_inventory(self.base_url + endpoint)

    def test_download_result_drives_admin_ssh_and_scheduled_management(self):
        cli_module = types.ModuleType("cli")
        cli_module.cli = mock.Mock()
        for endpoint, expected in (("/ok", "192.0.2.10/24"), ("/missing", "dhcp"),
                                   ("/slow", "dhcp"), ("/oversize", "dhcp"),
                                   ("/unbounded", "dhcp")):
            output = mock.mock_open()
            with self.subTest(endpoint=endpoint), \
                    mock.patch.object(poap, "INVENTORY_URL", self.base_url + endpoint), \
                    mock.patch.object(poap, "FETCH_TIMEOUT_SECONDS",
                                      0.05 if endpoint == "/slow" else 2), \
                    mock.patch.object(poap, "MANAGEMENT_GATEWAY", ""), \
                    mock.patch.object(poap, "SSH_PUBLIC_KEY", ""), \
                    mock.patch.dict(os.environ, {"POAP_SERIAL": "SN-001"}), \
                    mock.patch.dict(sys.modules, {"cli": cli_module}), \
                    mock.patch("builtins.open", output), \
                    mock.patch.object(poap.os, "chmod") as chmod, \
                    contextlib.redirect_stderr(io.StringIO()), \
                    contextlib.redirect_stdout(io.StringIO()):
                # Preserve real /dev/null access for Popen, while intercepting
                # only the bootflash configuration write.
                real_open = io.open
                output.side_effect = lambda path, *args, **kwargs: (
                    real_open(path, *args, **kwargs) if path == os.devnull
                    else output.return_value)
                cli_module.cli.reset_mock()
                poap.bootstrap()
                config = output.return_value.write.call_args.args[0]
                self.assertIn("  ip address " + expected + "\n", config)
                self.assertIn("username admin password 0 admin role network-admin\n", config)
                self.assertIn("feature ssh\n", config)
                chmod.assert_called_once_with("/bootflash/poap-ssh.cfg", 0o600)
                cli_module.cli.assert_called_once_with(
                    "copy bootflash:poap-ssh.cfg scheduled-config")


if __name__ == "__main__":
    unittest.main()
