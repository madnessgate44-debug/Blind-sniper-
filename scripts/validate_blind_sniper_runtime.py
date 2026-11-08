#!/usr/bin/env python3
"""Validate Blind Sniper's versioned runtime registries without third-party dependencies."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / "chatgpt-home"
RUNTIME = HOME / "runtime"
FAILURES: list[str] = []


def fail(message: str) -> None:
    FAILURES.append(message)


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            fail(f"{path.relative_to(ROOT)}: root must be an object")
            return {}
        return data
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"{path.relative_to(ROOT)}: {exc}")
        return {}


def check_unique(items: list[dict], key: str, label: str) -> None:
    values = [item.get(key) for item in items]
    if len(values) != len(set(values)):
        fail(f"{label}: duplicate {key} values")


def main() -> int:
    caps = load_json(RUNTIME / "capabilities.json")
    profiles = load_json(RUNTIME / "profiles.json")
    agents = load_json(RUNTIME / "agents.json")
    workflows = load_json(RUNTIME / "workflows.json")
    skills = load_json(RUNTIME / "skills.index.json")
    task = load_json(RUNTIME / "templates" / "TASK_ENVELOPE.json")
    receipt = load_json(RUNTIME / "templates" / "RUN_RECEIPT.json")

    adapters = caps.get("adapters", [])
    profile_rows = profiles.get("profiles", [])
    agent_rows = agents.get("agents", [])
    workflow_rows = workflows.get("workflows", [])
    skill_names = skills.get("skills", [])

    check_unique(adapters, "id", "adapters")
    check_unique(profile_rows, "id", "profiles")
    check_unique(agent_rows, "id", "agents")
    check_unique(workflow_rows, "id", "workflows")
    if len(skill_names) != len(set(skill_names)):
        fail("skills.index.json: duplicate skill names")

    adapter_ids = {row.get("id") for row in adapters}
    profile_ids = {row.get("id") for row in profile_rows}
    agent_ids = {row.get("id") for row in agent_rows}
    skill_set = set(skill_names)
    workflow_ids = {row.get("id") for row in workflow_rows}

    if profiles.get("default_profile") not in profile_ids:
        fail("profiles.json: default_profile does not exist")
    if agents.get("controller") not in agent_ids:
        fail("agents.json: controller does not exist")

    for row in profile_rows:
        unknown = set(row.get("skills", [])) - skill_set
        if unknown:
            fail(f"profile {row.get('id')}: unknown skills {sorted(unknown)}")
        unknown_agents = set(row.get("agents", [])) - agent_ids
        if unknown_agents:
            fail(f"profile {row.get('id')}: unknown agents {sorted(unknown_agents)}")
        if row.get("workflow") not in workflow_ids:
            fail(f"profile {row.get('id')}: unknown workflow {row.get('workflow')}")

    for row in workflow_rows:
        unknown_adapters = set(row.get("adapters", [])) - adapter_ids
        if unknown_adapters:
            fail(f"workflow {row.get('id')}: unknown adapters {sorted(unknown_adapters)}")

    mirror = HOME / "openhands-library" / ".agents"
    for skill in skill_names:
        if skill in skills.get("path_rules", {}):
            path = HOME / "openhands-library" / ".agents" / "skills" / f"{skill}.md"
        else:
            path = mirror / "skills" / skill / "SKILL.md"
        if not path.is_file():
            fail(f"missing mirrored skill: {path.relative_to(ROOT)}")

    expected_skill_count = skills.get("source", {}).get("declared_skill_files")
    if expected_skill_count != len(skill_names):
        fail(f"skills.index.json: declared count {expected_skill_count} != indexed {len(skill_names)}")

    for required in ("task_id", "objective", "repository", "acceptance_criteria", "verification_commands"):
        if required not in task:
            fail(f"TASK_ENVELOPE.json: missing {required}")
    for required in ("task_id", "run_id", "executor", "commands", "verification", "blockers"):
        if required not in receipt:
            fail(f"RUN_RECEIPT.json: missing {required}")

    # Safety invariants: no profile may silently default to unrestricted access.
    serialized_profiles = json.dumps(profiles).lower()
    if "danger-full-access" in serialized_profiles or "bypass-approvals" in serialized_profiles:
        fail("profiles.json: unsafe full-access/bypass default detected")
    if any(row.get("status") == "available_in_current_session" and not row.get("tools") for row in adapters):
        fail("capabilities.json: available adapter has no declared tools")

    if FAILURES:
        print(f"FAIL: {len(FAILURES)} runtime registry error(s)")
        for item in FAILURES:
            print(f"- {item}")
        return 1

    print("PASS: runtime registries parse and cross-reference cleanly")
    print(f"profiles={len(profile_rows)} agents={len(agent_rows)} adapters={len(adapters)} workflows={len(workflow_rows)} skills={len(skill_names)}")
    print("PASS: all mirrored skill paths exist")
    print("PASS: safety invariants hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
