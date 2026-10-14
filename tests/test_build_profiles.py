import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "build_profiles.py"
SPEC = importlib.util.spec_from_file_location("build_profiles", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BuildProfileTests(unittest.TestCase):
    def setUp(self):
        self.source = {
            "log": {"level": "info"},
            "dns": {"servers": [{"type": "udp", "tag": "old"}]},
            "inbounds": [
                {"type": "http", "tag": "http-in", "listen_port": 7890},
                {"type": "mixed", "tag": "mixed-in", "listen_port": 7891},
                {"type": "tproxy", "tag": "tproxy-in", "listen_port": 12345},
            ],
            "outbounds": [
                {"type": "direct", "tag": "direct"},
                {
                    "type": "vless",
                    "tag": "node2",
                    "server": "node.example",
                    "routing_mark": "0xff",
                },
            ],
            "route": {
                "rules": [
                    {"inbound": "mixed-in", "outbound": "direct"},
                    {"inbound": "tproxy-in", "action": "sniff"},
                    {"protocol": "bittorrent", "outbound": "direct"},
                ],
                "rule_set": [{"tag": "geoip-cn", "type": "remote"}],
                "final": "direct",
            },
        }
        self.dns = {
            "dns": {
                "servers": [
                    {"type": "udp", "tag": "ali_bootstrap", "server": "223.5.5.5"}
                ],
                "final": "ali_bootstrap",
            },
            "inbounds": [{"type": "direct", "tag": "dns-in", "listen_port": 53}],
            "outbounds": [
                {"type": "direct", "tag": "direct"},
                {
                    "type": "http",
                    "tag": "proxy_via_running_box",
                    "server": "127.0.0.1",
                    "server_port": 7890,
                },
            ],
            "route": {
                "rules": [{"protocol": "dns", "action": "hijack-dns"}],
                "rule_set": [
                    {
                        "tag": "geosite-cn",
                        "type": "remote",
                        "download_detour": "proxy_via_running_box",
                    }
                ],
            },
        }

    def test_build_profile_keeps_http_and_adds_dns(self):
        profile = MODULE.build_profile(self.source, self.dns)

        self.assertEqual(
            [(item["tag"], item["type"], item["listen_port"]) for item in profile["inbounds"]],
            [("http-in", "http", 7890), ("dns-in", "direct", 5353)],
        )
        self.assertEqual(profile["route"]["default_domain_resolver"], "ali_bootstrap")
        self.assertEqual(profile["route"]["rule_set"][1]["download_detour"], "direct")
        self.assertEqual(
            {item["tag"] for item in profile["outbounds"]},
            {"direct", "node2", "proxy_via_running_box"},
        )

    def test_build_profile_removes_transparent_proxy_rules_and_marks(self):
        profile = MODULE.build_profile(self.source, self.dns)

        self.assertFalse(any("tproxy" in item["type"] for item in profile["inbounds"]))
        self.assertFalse(any("mixed" in item["type"] for item in profile["inbounds"]))
        self.assertFalse(any("routing_mark" in item for item in profile["outbounds"]))
        self.assertEqual(
            profile["route"]["rules"],
            [
                {"protocol": "dns", "action": "hijack-dns"},
                {"protocol": "bittorrent", "outbound": "direct"},
            ],
        )

    def test_profile_encryption_round_trip(self):
        profile = MODULE.build_profile(self.source, self.dns)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            password = root / "password"
            encrypted = root / "profile.json.gpg"
            decrypted = root / "profile.json"
            password.write_text("test-password\\n", encoding="utf-8")

            MODULE.encrypt_profile(profile, encrypted, password, "gpg")
            subprocess.run(
                [
                    "gpg",
                    "--batch",
                    "--quiet",
                    "--no-options",
                    "--no-auto-check-trustdb",
                    "--pinentry-mode",
                    "loopback",
                    "--passphrase-file",
                    str(password),
                    "--decrypt",
                    "--output",
                    str(decrypted),
                    str(encrypted),
                ],
                check=True,
                capture_output=True,
            )
            self.assertEqual(json.loads(decrypted.read_text()), profile)


if __name__ == "__main__":
    unittest.main()
