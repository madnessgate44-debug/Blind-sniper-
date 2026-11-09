#!/usr/bin/env python3
"""Validate the Codex-style host configuration templates.

The templates in chatgpt-home/config/*.toml.example are the "works like Codex"
surface: a least-privilege Codex host profile per operating mode. This checker
parses them for real (tomllib) and proves three things the environment check only
spot-checks as text:

1. Every template is valid TOML.
2. Every template is safe: approval is on-request, the sandbox is read-only or
   workspace-write, no dangerous bypass value appears, and no credential-like
   value is present.
3. Every profile's declared config_template exists, parses, and its sandbox_mode
   matches the profile's declared sandbox posture (read-only modes -> read-only;
   the write mode -> workspace-write).

It never activates anything; a passing template is still a template, not a
running Codex host.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "chatgpt-home" / "config"
PROFILES_PATH = ROOT / "chatgpt-home" / "runtime" / "profiles.json"

SAFE_APPROVAL = "on-request"
SAFE_SANDBOX = {"read-only", "workspace-write"}
DANGEROUS = re.compile(r"danger-full-access|dangerously-bypass-approvals-and-sandbox")
CREDENTIAL = re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{30,}")
SECRET_KEYS = {"api_key", "apikey", "token", "secret", "password", "credential"}


def expected_sandbox(profile_sandbox: str) -> str:
    return "workspace-write" if "write" in profile_sandbox else "read-only"


def scan_values(obj, path=""):
    """Yield (path, value) for every leaf, including values nested in arrays."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield from scan_values(value, f"{path}.{key}" if path else key)
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            yield from scan_values(value, f"{path}[{index}]")
    else:
        yield path, obj


def validate_template(path: Path) -> tuple[list[str], dict]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        return [f"INVALID_TOML: {path.name}: {exc}"], {}

    if data.get("approval_policy") != SAFE_APPROVAL:
        errors.append(f"UNSAFE_APPROVAL: {path.name} approval_policy={data.get('approval_policy')!r}")
    sandbox = data.get("sandbox_mode")
    if sandbox not in SAFE_SANDBOX:
        errors.append(f"UNSAFE_SANDBOX: {path.name} sandbox_mode={sandbox!r}")
    if DANGEROUS.search(text):
        errors.append(f"DANGEROUS_SETTING: {path.name}")
    for key, value in scan_values(data):
        leaf = re.sub(r"\[\d+\]$", "", key.rsplit(".", 1)[-1]).lower()
        if leaf in SECRET_KEYS and isinstance(value, str) and value:
            errors.append(f"SECRET_VALUE: {path.name} sets {key}")
        if isinstance(value, str) and CREDENTIAL.search(value):
            errors.append(f"CREDENTIAL_PATTERN: {path.name} at {key}")
    return errors, {"sandbox_mode": sandbox, "approval_policy": data.get("approval_policy"),
                    "sections": sorted(k for k, v in data.items() if isinstance(v, dict))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    errors: list[str] = []
    report: dict[str, dict] = {}

    templates = sorted(CONFIG_DIR.glob("*.toml.example"))
    if not templates:
        errors.append("NO_TEMPLATES: chatgpt-home/config has no *.toml.example files")
    for path in templates:
        template_errors, info = validate_template(path)
        errors.extend(template_errors)
        report[path.name] = info

    profiles = json.loads(PROFILES_PATH.read_text(encoding="utf-8")).get("profiles", [])
    for profile in profiles:
        rel = profile.get("config_template")
        pid = profile.get("id")
        if not rel:
            errors.append(f"PROFILE_NO_TEMPLATE: {pid}")
            continue
        path = ROOT / rel
        if not path.is_file():
            errors.append(f"PROFILE_TEMPLATE_MISSING: {pid} -> {rel}")
            continue
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            errors.append(f"PROFILE_TEMPLATE_INVALID: {pid} -> {rel}: {exc}")
            continue
        want = expected_sandbox(profile.get("sandbox", ""))
        got = data.get("sandbox_mode")
        if got != want:
            errors.append(f"SANDBOX_MISMATCH: profile {pid} declares sandbox={profile.get('sandbox')!r} "
                          f"(expect {want}) but {Path(rel).name} has sandbox_mode={got!r}")

    if args.json:
        print(json.dumps({"templates": report, "errors": errors}, indent=2))
        return 1 if errors else 0
    if errors:
        print("\n".join(errors))
        return 1
    print(f"PASS: {len(templates)} Codex config templates parse, are least-privilege, "
          f"and match {len(profiles)} profile sandbox postures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
