#!/usr/bin/env python3
"""One-command connector self-check (read-only, redacted receipts).

Exercises files, git and (only with --live-public) the public GitHub reader through
ConnectorRegistry. The terminal connector is not exercised (its only tool mutates).
Skipped or unverified checks are reported as such and never count as success.
Overall result is "pass" only if every executed check passed; the authenticated path
is always reported as "unverified"."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.blind_sniper_connectors import (BUILTIN_SPECS, ConnectorRegistry, ConnectorStatus,
                                              _utc_now_iso)
from scripts.blind_sniper_github_readonly import GitHubReadOnlyConnector
from scripts.blind_sniper_native_connectors import FilesConnector, GitConnector


def _registry(connector):
    ops = [t["name"] for t in connector.tools()]
    base = BUILTIN_SPECS.get(connector.connector_id) or BUILTIN_SPECS["github"]
    spec = replace(base, auth_kind="local_none", env_vars=[], token_env_var=None, operations=ops)
    reg = ConnectorRegistry(specs={connector.connector_id: spec}, env={}, connectors=[connector])
    reg._statuses[connector.connector_id] = ConnectorStatus(
        connector_id=connector.connector_id, auth_status="verified", health="healthy",
        last_verified_at=_utc_now_iso(), operations_available=ops)
    return reg


def _check(name, connector, tool, args, ok):
    try:
        reg = _registry(connector)
        result = reg.call("engineer", connector.connector_id, tool, args,
                          [f"{connector.connector_id}.{tool}"], timeout_s=15)
        if isinstance(result, dict) and result.get("failure_kind") == "not_authorized":
            return {"check": name, "status": "blocked_by_policy",
                    "reason": "no role grants this connector in the registry role table"}
        if not isinstance(result, dict) or str(result.get("status", "")).upper() == "FAIL":
            return {"check": name, "status": "fail",
                    "error": str(result.get("failure_kind", "failed")) if isinstance(result, dict) else "bad_result"}
        passed = bool(ok(result))
        # Receipt is redacted: digest and size only, never the content.
        blob = json.dumps(result, sort_keys=True, default=str).encode()
        return {"check": name, "status": "pass" if passed else "fail",
                "result_sha256": hashlib.sha256(blob).hexdigest()[:16], "result_bytes": len(blob)}
    except Exception as exc:  # report the class only, never message text
        return {"check": name, "status": "fail", "error": type(exc).__name__}


def run(root: Path, repo: str, live_public: bool) -> dict:
    files, git = FilesConnector(root), GitConnector(root)
    checks = [
        _check("files.list_dir", files, "list_dir", {"path": "."}, lambda r: "scripts" in r.get("entries", [])),
        _check("files.read_file", files, "read_file", {"path": "scripts/blind_sniper_connector_selfcheck.py"},
               lambda r: bool(r.get("content") or r.get("text") or r.get("size") or r.get("sha256"))),
        _check("git.status", git, "status", {}, lambda r: bool(r)),
        _check("git.log", git, "log", {"limit": 1}, lambda r: bool(r)),
    ]
    skipped = [{"check": "terminal.run_command", "status": "skipped", "reason": "only tool mutates"},
               {"check": "authenticated_integration", "status": "unverified",
                "reason": "no credential path tested"}]
    if live_public:
        gh = GitHubReadOnlyConnector(repo)
        checks.append(_check("github.pr_status (live public, unauthenticated)", gh, "pr_status",
                             {"number": 94}, lambda r: r.get("number") == 94))
    else:
        skipped.append({"check": "github.pr_status", "status": "skipped",
                        "reason": "network off; pass --live-public"})
    any_fail = any(c["status"] == "fail" for c in checks)
    # "pass" is never reported: the authenticated path is always unverified.
    return {"overall": "fail" if any_fail else "incomplete", "checks": checks + skipped,
            "note": "incomplete: blocked, skipped and unverified items are NOT healthy"}


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--live-public", action="store_true")
    p.add_argument("--repo", default="madnessgate44-debug/Blind-sniper-")
    p.add_argument("--root", default=str(ROOT))
    a = p.parse_args(argv)
    out = run(Path(a.root), a.repo, a.live_public)
    print(json.dumps(out, indent=2))
    return 0 if out["overall"] != "fail" else 1


if __name__ == "__main__":
    sys.exit(main())
