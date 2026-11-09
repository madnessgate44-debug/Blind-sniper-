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
    authority = load_json(RUNTIME / "authority.json")

    delegations = authority.get("delegations", [])
    check_unique(delegations, "id", "authority delegations")
    active_delegations = [row for row in delegations if row.get("status") == "active"]
    if len(active_delegations) != 1:
        fail("authority.json: expected exactly one active standing delegation")
    elif active_delegations[0].get("repository") != "madnessgate44-debug/Blind-sniper-":
        fail("authority.json: active delegation repository scope is incorrect")
    else:
        actions = set(active_delegations[0].get("actions", []))
        forbidden = set(active_delegations[0].get("forbidden_actions", []))
        required_actions = {"merge", "merge_to_main", "default_branch_push", "ci_cd_edit", "workflow_edit", "deploy", "production_deploy", "release", "delete"}
        if not required_actions.issubset(actions):
            fail(f"authority.json: missing delegated actions {sorted(required_actions - actions)}")
        if actions & (forbidden | {"force_push", "delete_branch", "credential_export", "secret_export", "disable_branch_protection", "unbounded_shell"}):
            fail("authority.json: delegated actions overlap forbidden host actions")
        if not {"secret_mutation", "permission_change", "paid_provisioning", "production_data_mutation"}.issubset(forbidden):
            fail("authority.json: required exclusions are missing")
    adapters = caps.get("adapters", [])
    profile_rows = profiles.get("profiles", [])
    agent_rows = agents.get("agents", [])
    workflow_rows = workflows.get("workflows", [])
    skill_names = skills.get("skills", [])
    native_skill_names = skills.get("native_skills", [])
    all_skill_names = set(skill_names) | set(native_skill_names)

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
    default_profile = next((row for row in profile_rows if row.get("id") == profiles.get("default_profile")), None)
    default_agents = set(workflows.get("default_agent_selection", []))
    if default_agents - agent_ids:
        fail(f"workflows.json: unknown default agents {sorted(default_agents - agent_ids)}")
    if default_profile and not default_agents.issubset(set(default_profile.get("agents", []))):
        fail("workflows.json: default agent selection exceeds default profile allowlist")

    for row in profile_rows:
        unknown = set(row.get("skills", [])) - all_skill_names
        if unknown:
            fail(f"profile {row.get('id')}: unknown skills {sorted(unknown)}")
        unknown_agents = set(row.get("agents", [])) - agent_ids
        if unknown_agents:
            fail(f"profile {row.get('id')}: unknown agents {sorted(unknown_agents)}")
        if row.get("workflow") not in workflow_ids:
            fail(f"profile {row.get('id')}: unknown workflow {row.get('workflow')}")

    profile_workflows = {}
    for profile in profile_rows:
        profile_workflows.setdefault(profile.get("workflow"), []).append(profile)

    for row in workflow_rows:
        unknown_adapters = set(row.get("adapters", [])) - adapter_ids
        if unknown_adapters:
            fail(f"workflow {row.get('id')}: unknown adapters {sorted(unknown_adapters)}")
        unknown_agents = set(row.get("agents", [])) - agent_ids
        if unknown_agents:
            fail(f"workflow {row.get('id')}: unknown agents {sorted(unknown_agents)}")
        if row.get("agents"):
            matches = profile_workflows.get(row.get("id"), [])
            if len(matches) != 1:
                fail(f"workflow {row.get('id')}: expected exactly one profile binding, found {len(matches)}")
            elif not set(row.get("agents", [])).issubset(set(matches[0].get("agents", []))):
                fail(f"workflow {row.get('id')}: workflow agents exceed profile agent allowlist")
        routing = row.get("routing")
        if routing is not None:
            if not isinstance(routing.get("priority"), int) or not routing.get("keywords"):
                fail(f"workflow {row.get('id')}: routing requires integer priority and non-empty keywords")
            if len(routing.get("keywords", [])) != len(set(routing.get("keywords", []))):
                fail(f"workflow {row.get('id')}: duplicate routing keywords")

    mirror = HOME / "openhands-library" / ".agents"
    for skill in skill_names:
        if skill in skills.get("path_rules", {}):
            path = HOME / "openhands-library" / ".agents" / "skills" / f"{skill}.md"
        else:
            path = mirror / "skills" / skill / "SKILL.md"
        if not path.is_file():
            fail(f"missing mirrored skill: {path.relative_to(ROOT)}")

    for skill, path_text in skills.get("native_skill_paths", {}).items():
        path = ROOT / path_text
        if skill not in native_skill_names or not path.is_file():
            fail(f"missing native skill path or index mismatch: {path_text}")

    for row in agent_rows:
        native_path = row.get("path") or row.get("native_contract_path")
        if native_path and not (ROOT / native_path).is_file():
            fail(f"agent {row.get('id')}: missing native contract {native_path}")

    for row in workflow_rows:
        contract = row.get("native_contract_path")
        if contract and not (ROOT / contract).is_file():
            fail(f"workflow {row.get('id')}: missing native contract {contract}")

    expected_skill_count = skills.get("source", {}).get("declared_skill_files")
    if expected_skill_count != len(skill_names):
        fail(f"skills.index.json: declared OpenHands count {expected_skill_count} != indexed {len(skill_names)}")
    native_expected = skills.get("native_source", {}).get("declared_skill_files")
    if native_expected != len(native_skill_names):
        fail(f"skills.index.json: declared native count {native_expected} != indexed {len(native_skill_names)}")

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
    print(f"profiles={len(profile_rows)} agents={len(agent_rows)} adapters={len(adapters)} workflows={len(workflow_rows)} native_skills={len(native_skill_names)} openhands_skills={len(skill_names)}")
    print("PASS: all mirrored skill paths exist")
    print("PASS: safety invariants hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
