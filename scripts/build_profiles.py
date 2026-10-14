#!/usr/bin/env python3
"""Build encrypted sing-box profiles from private configuration snapshots."""

from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any


PROFILE_SOURCES = {
    "main-http-dns": "proxy.json",
    "feiniaoyun-http-dns": "feiniaoyun.json",
    "vps-backup-http-dns": "backup-vps.json",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"configuration root must be an object: {path}")
    return value


def inbound_is_platform_specific(rule: dict[str, Any]) -> bool:
    value = rule.get("inbound")
    tags = [value] if isinstance(value, str) else value if isinstance(value, list) else []
    return any(
        isinstance(tag, str)
        and (tag.startswith("mixed") or tag.startswith("tproxy"))
        for tag in tags
    )


def remove_routing_marks(value: Any) -> None:
    if isinstance(value, dict):
        value.pop("routing_mark", None)
        for child in value.values():
            remove_routing_marks(child)
    elif isinstance(value, list):
        for child in value:
            remove_routing_marks(child)


def merge_rule_sets(
    dns_route: dict[str, Any], source_route: dict[str, Any], fallback_detour: str
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    tags: set[str] = set()
    for rule_set in [*source_route.get("rule_set", []), *dns_route.get("rule_set", [])]:
        if not isinstance(rule_set, dict):
            continue
        tag = rule_set.get("tag")
        if not isinstance(tag, str) or tag in tags:
            continue
        tags.add(tag)
        item = copy.deepcopy(rule_set)
        if item.get("download_detour") == "proxy_via_running_box":
            item["download_detour"] = fallback_detour
        merged.append(item)
    return merged


def merge_unique_rules(
    dns_rules: list[Any], source_rules: list[Any]
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rule in [*dns_rules, *source_rules]:
        if not isinstance(rule, dict):
            continue
        key = json.dumps(rule, sort_keys=True, separators=(",", ":"))
        if key in seen:
            continue
        seen.add(key)
        result.append(copy.deepcopy(rule))
    return result


def build_profile(source: dict[str, Any], dns_source: dict[str, Any]) -> dict[str, Any]:
    profile = copy.deepcopy(source)
    source_inbounds = profile.get("inbounds", [])
    inbounds: list[dict[str, Any]] = []
    for inbound in source_inbounds:
        if not isinstance(inbound, dict) or inbound.get("type") != "http":
            continue
        item = copy.deepcopy(inbound)
        item["listen"] = "0.0.0.0"
        item["listen_port"] = 7890
        inbounds.append(item)
    if not inbounds:
        raise ValueError("profile has no HTTP inbound")

    dns_inbound = next(
        (
            inbound
            for inbound in dns_source.get("inbounds", [])
            if isinstance(inbound, dict) and inbound.get("tag") == "dns-in"
        ),
        None,
    )
    if dns_inbound is None:
        raise ValueError("DNS configuration has no dns-in inbound")
    dns_inbound = copy.deepcopy(dns_inbound)
    dns_inbound["listen"] = "0.0.0.0"
    dns_inbound["listen_port"] = 5353
    inbounds.append(dns_inbound)
    profile["inbounds"] = inbounds

    profile["dns"] = copy.deepcopy(dns_source["dns"])

    outbounds = [
        copy.deepcopy(outbound)
        for outbound in profile.get("outbounds", [])
        if isinstance(outbound, dict)
    ]
    tags = {outbound.get("tag") for outbound in outbounds}
    for outbound in dns_source.get("outbounds", []):
        if not isinstance(outbound, dict):
            continue
        tag = outbound.get("tag")
        if tag not in tags:
            outbounds.append(copy.deepcopy(outbound))
            tags.add(tag)
    remove_routing_marks(outbounds)
    profile["outbounds"] = outbounds

    source_route = copy.deepcopy(profile.get("route", {}))
    dns_route = copy.deepcopy(dns_source.get("route", {}))
    filtered_source_rules = []
    for rule in source_route.get("rules", []):
        if not isinstance(rule, dict):
            continue
        if inbound_is_platform_specific(rule):
            continue
        filtered_source_rules.append(rule)
    profile["route"] = source_route
    profile["route"]["rules"] = merge_unique_rules(
        dns_route.get("rules", []), filtered_source_rules
    )
    profile["route"]["rule_set"] = merge_rule_sets(
        dns_route, source_route, profile["route"].get("final", "direct")
    )
    profile["route"]["default_domain_resolver"] = "ali_bootstrap"

    experimental = profile.setdefault("experimental", {})
    cache_file = experimental.setdefault("cache_file", {})
    cache_file["enabled"] = True
    cache_file["path"] = "/var/lib/singbox/cache.db"

    return profile


def encrypt_profile(
    profile: dict[str, Any], output: Path, password_file: Path, gpg: str
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir="/tmp", prefix="singbox-profile-", suffix=".json", delete=False
    ) as plaintext:
        json.dump(profile, plaintext, ensure_ascii=False, indent=2)
        plaintext.write("\n")
        plaintext_path = Path(plaintext.name)
    encrypted_path = output.with_suffix(output.suffix + ".tmp")
    try:
        command = [
            gpg,
            "--batch",
            "--yes",
            "--quiet",
            "--no-options",
            "--no-auto-check-trustdb",
            "--pinentry-mode",
            "loopback",
            "--passphrase-file",
            str(password_file),
            "--symmetric",
            "--cipher-algo",
            "AES256",
            "--s2k-digest-algo",
            "SHA512",
            "--output",
            str(encrypted_path),
            str(plaintext_path),
        ]
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        if result.returncode != 0:
            raise RuntimeError("GPG encryption failed")
        os.chmod(encrypted_path, 0o600)
        os.replace(encrypted_path, output)
    finally:
        plaintext_path.unlink(missing_ok=True)
        encrypted_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--password-file", type=Path, required=True)
    parser.add_argument("--gpg", default="gpg")
    args = parser.parse_args()

    if not args.password_file.is_file():
        raise SystemExit("password file does not exist")
    dns_source = load_json(args.input_dir / "dns.json")
    for profile_name, source_name in PROFILE_SOURCES.items():
        source = load_json(args.input_dir / source_name)
        profile = build_profile(source, dns_source)
        output = args.output_dir / f"{profile_name}.json.gpg"
        encrypt_profile(profile, output, args.password_file, args.gpg)
        print(profile_name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
