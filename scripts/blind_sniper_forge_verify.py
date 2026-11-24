#!/usr/bin/env python3
"""Verify a Forge-exported patch artifact against a repository-local fixture target.

Bounded adapter for the `forge-patch-verify` executor command. Forge (Firstborn)
exports a unified-diff patch scoped to a mission's planned files; this script
applies one such artifact to a fresh copy of a repo-local fixture target and
runs a fixed allowlist of checks against the patched copy.

Safety contract:
- Input comes only from the fixed, in-repository file
  `.blind-sniper/forge-verify/input.json` with an exact key set.
- `patch_path` and `target_dir` must resolve inside this repository; absolute
  paths and `..` escapes are refused. Nothing outside the repository is read
  and nothing inside the repository is written: all application happens in a
  temporary copy.
- Checks are selected by ID from CHECK_ALLOWLIST only; the task input can
  narrow the set, never extend it. No network access, no shell strings.
- Exit code 0 means the patch applied and every selected check passed.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / ".blind-sniper" / "forge-verify" / "input.json"

COMMAND_TIMEOUT_SECONDS = 300


def check_node_check(work: Path) -> subprocess.CompletedProcess:
    """Syntax-check every JavaScript file in the patched copy."""
    files = sorted(work.rglob("*.js"))
    if not files:
        return subprocess.CompletedProcess([], 1, "", "no .js files found in target copy")
    outputs = []
    for path in files:
        result = subprocess.run(
            ["node", "--check", str(path)],
            cwd=work, env={"PATH": "/usr/bin:/bin:/usr/local/bin"},
            capture_output=True, text=True,
            timeout=COMMAND_TIMEOUT_SECONDS, check=False,
        )
        outputs.append(f"node --check {path.relative_to(work)}: exit {result.returncode}")
        if result.returncode != 0:
            outputs.append(result.stdout + result.stderr)
            return subprocess.CompletedProcess([], result.returncode, "\n".join(outputs), "")
    return subprocess.CompletedProcess([], 0, "\n".join(outputs), "")


def check_node_test(work: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["node", "--test"],
        cwd=work, env={"PATH": "/usr/bin:/bin:/usr/local/bin"},
        capture_output=True, text=True,
        timeout=COMMAND_TIMEOUT_SECONDS, check=False,
    )


CHECK_ALLOWLIST = {
    "node-check": check_node_check,
    "node-test": check_node_test,
}


def fail(message: str) -> int:
    print(f"FORGE_PATCH_VERIFY_ERROR: {message}")
    return 2


def resolve_inside_repo(raw: object, field: str) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise RuntimeError(f"{field} must be a non-empty string")
    candidate = (ROOT / raw).resolve()
    if not candidate.is_relative_to(ROOT):
        raise RuntimeError(f"{field} must remain inside the repository")
    return candidate


def load_input() -> dict:
    if not INPUT_PATH.exists():
        raise RuntimeError(f"Input file missing: {INPUT_PATH.relative_to(ROOT)}")
    data = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != {"patch_path", "target_dir", "checks"}:
        raise RuntimeError("Input must contain exactly patch_path, target_dir and checks")
    checks = data["checks"]
    if (
        not isinstance(checks, list)
        or not checks
        or any(not isinstance(c, str) or c not in CHECK_ALLOWLIST for c in checks)
        or len(checks) != len(set(checks))
    ):
        raise RuntimeError(
            f"checks must be a non-empty de-duplicated subset of {sorted(CHECK_ALLOWLIST)}"
        )
    data["patch_path"] = resolve_inside_repo(data["patch_path"], "patch_path")
    data["target_dir"] = resolve_inside_repo(data["target_dir"], "target_dir")
    if not data["patch_path"].is_file():
        raise RuntimeError("patch_path does not name a file inside the repository")
    if not data["target_dir"].is_dir():
        raise RuntimeError("target_dir does not name a directory inside the repository")
    return data


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=cwd,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin"},
        capture_output=True,
        text=True,
        timeout=COMMAND_TIMEOUT_SECONDS,
        check=False,
    )


def main() -> int:
    try:
        spec = load_input()
    except Exception as exc:
        return fail(f"{type(exc).__name__}: {exc}")

    with tempfile.TemporaryDirectory(prefix="blind-sniper-forge-verify-") as tmp:
        work = Path(tmp) / "target"
        shutil.copytree(spec["target_dir"], work)
        check = run(["git", "apply", "--check", str(spec["patch_path"])], cwd=work)
        if check.returncode != 0:
            print(check.stdout + check.stderr)
            print("RESULT: FAIL (patch does not apply cleanly)")
            return 1
        applied = run(["git", "apply", str(spec["patch_path"])], cwd=work)
        if applied.returncode != 0:
            print(applied.stdout + applied.stderr)
            print("RESULT: FAIL (patch application failed)")
            return 1
        print(f"APPLIED: {spec['patch_path'].relative_to(ROOT)}")
        for check_id in spec["checks"]:
            result = CHECK_ALLOWLIST[check_id](work)
            print(result.stdout + result.stderr)
            status = "PASS" if result.returncode == 0 else "FAIL"
            print(f"CHECK {check_id}: {status} (exit {result.returncode})")
            if result.returncode != 0:
                print("RESULT: FAIL")
                return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
