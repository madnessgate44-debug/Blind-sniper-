#!/usr/bin/env python3
"""Blind Sniper's registry-driven task planner and guarded lifecycle engine.

This engine plans and validates orchestration. It does not impersonate external
agents, invoke unregistered adapters, or bypass host/Owner permissions.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "chatgpt-home" / "runtime"

PROFILE_BY_WORKFLOW = {
    "research-and-synthesis": "research",
    "inspect-plan-implement-verify": "engineering",
    "independent-review": "review",
    "release-gate": "release",
    "recovery-and-reconciliation": "recovery",
    "task-control-loop": "blind-sniper",
}
AGENTS_BY_WORKFLOW = {
    "research-and-synthesis": ["researcher", "planner"],
    "inspect-plan-implement-verify": ["planner", "engineer", "qa-verifier", "reviewer"],
    "independent-review": ["reviewer", "qa-verifier", "shadow-auditor"],
    "release-gate": ["release-manager", "qa-verifier"],
    "recovery-and-reconciliation": ["recovery", "watcher"],
    "task-control-loop": ["blind-sniper", "planner"],
}
SKILL_KEYWORDS = {
    "github-workspace": {"github", "repository", "repo", "branch", "pull", "request", "issue", "commit"},
    "workflow-authoring": {"workflow", "orchestration", "orchestrate", "dispatch", "agent", "runtime", "skill"},
    "test-and-evidence": {"test", "tests", "verify", "verification", "ci", "acceptance", "evidence", "validate"},
    "security-and-permissions": {"security", "secret", "credential", "permission", "privacy", "auth"},
    "web-research": {"research", "search", "compare", "source", "investigate"},
    "engineering-execution-os": {"engineering", "implement", "implementation", "code", "build", "fix", "bug"},
    "owner-policy": {"owner", "approval", "authorize", "authority", "risk"},
    "zero-cost-gate": {"cost", "paid", "budget", "free", "subscription"},
    "blind-sniper-continuity": {"continuity", "resume", "memory", "session", "checkpoint"},
    "memory-and-continuity": {"memory", "session", "checkpoint", "continuity"},
    "scope-discipline": {"scope", "constraint", "non-goal", "boundary"},
}
HIGH_RISK_ACTIONS = {
    "merge", "production_deploy", "deploy", "secret_mutation",
    "permission_change", "paid_provisioning", "production_data_mutation",
    "delete", "irreversible",
}
STATES = (
    "REQUESTED", "INSPECTING", "SPECIFIED", "PLANNED", "EXECUTING",
    "VERIFYING", "REVIEWING", "CLOSED", "BLOCKED", "CANCELLED",
    "FAILED", "OWNER-DECISION",
)
TRANSITIONS = {
    "REQUESTED": {"INSPECTING", "BLOCKED", "CANCELLED", "FAILED", "OWNER-DECISION"},
    "INSPECTING": {"SPECIFIED", "BLOCKED", "CANCELLED", "FAILED", "OWNER-DECISION"},
    "SPECIFIED": {"PLANNED", "BLOCKED", "CANCELLED", "FAILED", "OWNER-DECISION"},
    "PLANNED": {"EXECUTING", "BLOCKED", "CANCELLED", "FAILED", "OWNER-DECISION"},
    "EXECUTING": {"VERIFYING", "BLOCKED", "CANCELLED", "FAILED", "OWNER-DECISION"},
    "VERIFYING": {"REVIEWING", "BLOCKED", "FAILED", "OWNER-DECISION"},
    "REVIEWING": {"CLOSED", "BLOCKED", "FAILED", "OWNER-DECISION"},
    "CLOSED": set(), "BLOCKED": set(), "CANCELLED": set(),
    "FAILED": set(), "OWNER-DECISION": set(),
}


class RuntimeErrorBase(ValueError):
    """Invalid registry, task contract, or lifecycle transition."""


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeErrorBase(f"Cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeErrorBase(f"{path} must contain a JSON object")
    return value


def load_registries(root: Path = ROOT) -> dict[str, dict[str, Any]]:
    runtime = root / "chatgpt-home" / "runtime"
    names = ("capabilities", "profiles", "agents", "workflows", "skills.index")
    result = {name: read_json(runtime / f"{name}.json") for name in names}
    return result


def tokenize(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_-]+", value.lower()))


def capability_state(status: str) -> str:
    value = status.lower()
    if "not_registered" in value or value.startswith("blocked") or "blocked_" in value:
        return "BLOCKED"
    if "unverified" in value or "not_verified" in value:
        return "UNVERIFIED"
    if "partial" in value or "reported" in value or "receiver_unverified" in value:
        return "PARTIAL"
    if value == "available_in_current_session":
        return "AVAILABLE"
    return "UNVERIFIED"


def choose_workflow(task: dict[str, Any], workflows: list[dict[str, Any]]) -> str:
    known = {row.get("id") for row in workflows}
    requested = task.get("workflow")
    if requested:
        if requested not in known:
            raise RuntimeErrorBase(f"Unknown workflow: {requested}")
        return requested

    text = " ".join([
        str(task.get("objective", "")),
        str(task.get("task_type", "")),
        " ".join(map(str, task.get("requested_actions", []))),
    ]).lower()
    if any(word in text for word in ("review", "audit", "inspect diff", "security review")):
        candidate = "independent-review"
    elif any(word in text for word in ("deploy", "release", "merge")):
        candidate = "release-gate"
    elif any(word in text for word in ("recover", "restore", "reconcile", "continuity failure")):
        candidate = "recovery-and-reconciliation"
    elif any(word in text for word in ("research", "investigate", "compare", "look up")):
        candidate = "research-and-synthesis"
    elif any(word in text for word in ("implement", "build", "fix", "code", "test", "engineering", "repository")):
        candidate = "inspect-plan-implement-verify"
    else:
        candidate = "task-control-loop"
    if candidate not in known:
        raise RuntimeErrorBase(f"Workflow registry is missing routed workflow: {candidate}")
    return candidate


def resolve_skill_path(skill: str, index: dict[str, Any]) -> str:
    native = index.get("native_skill_paths", {})
    if skill in native:
        return native[skill]
    rules = index.get("path_rules", {})
    if skill in rules:
        return str(rules[skill])
    return f"chatgpt-home/openhands-library/.agents/skills/{skill}/SKILL.md"


def build_plan(task: dict[str, Any], root: Path = ROOT) -> dict[str, Any]:
    if not isinstance(task, dict) or not str(task.get("objective", "")).strip():
        raise RuntimeErrorBase("Task must include a non-empty objective")
    registries = load_registries(root)
    caps = registries["capabilities"]
    profiles = registries["profiles"].get("profiles", [])
    agents = registries["agents"].get("agents", [])
    workflows = registries["workflows"].get("workflows", [])
    skill_index = registries["skills.index"]

    workflow_id = choose_workflow(task, workflows)
    workflow = next(row for row in workflows if row["id"] == workflow_id)
    profile_id = task.get("profile") or PROFILE_BY_WORKFLOW.get(workflow_id, "blind-sniper")
    profile = next((row for row in profiles if row.get("id") == profile_id), None)
    if profile is None:
        raise RuntimeErrorBase(f"Unknown operating profile: {profile_id}")

    adapters = {row.get("id"): row for row in caps.get("adapters", [])}
    required_adapters = []
    for adapter_id in workflow.get("adapters", []):
        adapter = adapters.get(adapter_id)
        if adapter is None:
            raise RuntimeErrorBase(f"Workflow {workflow_id} references unknown adapter {adapter_id}")
        declared_capabilities = set(adapter.get("capabilities", []))
        required_capabilities = set(workflow.get("required_capabilities", {}).get(adapter_id, []))
        missing_capabilities = sorted(required_capabilities - declared_capabilities)
        status = capability_state(str(adapter.get("status", "")))
        if missing_capabilities:
            status = "BLOCKED"
        required_adapters.append({
            "id": adapter_id,
            "status": status,
            "source_status": adapter.get("status"),
            "capabilities": sorted(declared_capabilities),
            "required_capabilities": sorted(required_capabilities),
            "missing_capabilities": missing_capabilities,
        })

    states = {item["status"] for item in required_adapters}
    readiness = "BLOCKED" if states & {"BLOCKED", "UNVERIFIED"} else (
        "PARTIAL" if "PARTIAL" in states else "READY"
    )

    agent_index = {row.get("id"): row for row in agents}
    preferred_agents = AGENTS_BY_WORKFLOW.get(workflow_id, ["blind-sniper", "planner"])
    selected_agents = []
    for agent_id in preferred_agents:
        if agent_id not in profile.get("agents", []):
            continue
        row = agent_index.get(agent_id)
        if row is None:
            raise RuntimeErrorBase(f"Profile {profile_id} references missing agent {agent_id}")
        path = row.get("path") or row.get("native_contract_path")
        selected_agents.append({
            "id": agent_id,
            "role": row.get("role"),
            "status": row.get("status"),
            "contract_path": path,
            "contract_loaded_by_host": False,
        })
    if not selected_agents:
        raise RuntimeErrorBase(f"No eligible agents for workflow {workflow_id} in profile {profile_id}")

    available_skills = set(profile.get("skills", []))
    requested_skills = task.get("skills")
    if requested_skills is not None:
        unknown = set(requested_skills) - available_skills
        if unknown:
            raise RuntimeErrorBase(f"Requested skills are outside profile {profile_id}: {sorted(unknown)}")
        selected_skill_ids = list(dict.fromkeys(requested_skills))
    else:
        words = tokenize(str(task["objective"]))
        scored = []
        for skill in profile.get("skills", []):
            score = len(words & (tokenize(skill.replace("-", " ")) | SKILL_KEYWORDS.get(skill, set())))
            if score:
                scored.append((score, skill))
        selected_skill_ids = [skill for _, skill in sorted(scored, key=lambda item: (-item[0], item[1]))[:6]]
        if not selected_skill_ids:
            selected_skill_ids = [skill for skill in ("owner-policy", "scope-discipline", "test-and-evidence") if skill in available_skills]
        if not selected_skill_ids:
            selected_skill_ids = profile.get("skills", [])[:3]

    skill_rows = []
    for skill in selected_skill_ids:
        path = resolve_skill_path(skill, skill_index)
        if not (root / path).is_file():
            raise RuntimeErrorBase(f"Selected skill file does not exist: {path}")
        skill_rows.append({
            "id": skill,
            "path": path,
            "activation": "host_must_read_contract",
            "automatic_execution": False,
        })

    requested_actions = {str(x).lower() for x in task.get("requested_actions", [])}
    approval_actions = sorted(requested_actions & HIGH_RISK_ACTIONS)
    if workflow_id == "release-gate":
        approval_actions = sorted(set(approval_actions) | {"merge_or_deploy"})
    approved_actions = set((task.get("owner_approval") or {}).get("approved_actions", []))
    pending_approvals = [action for action in approval_actions if action not in approved_actions]

    steps = []
    previous = None
    for position, step in enumerate(workflow.get("steps", []), start=1):
        steps.append({
            "position": position,
            "id": step,
            "status": "PENDING",
            "depends_on": [previous] if previous else [],
        })
        previous = step

    task_id = str(task.get("task_id", "")).strip()
    if not task_id:
        raise RuntimeErrorBase("Task must include task_id; use a stable caller-generated correlation ID")

    next_action = "BLOCKED_BY_CAPABILITY" if readiness == "BLOCKED" else (
        "WAIT_FOR_OWNER_APPROVAL" if pending_approvals else
        "EXECUTE_WITH_HOST" if readiness == "READY" else "HOST_ASSISTED_EXECUTION"
    )
    return {
        "schema_version": "1.0.0",
        "task_id": task_id,
        "objective": str(task["objective"]).strip(),
        "repository": task.get("repository"),
        "base_commit": task.get("base_commit"),
        "profile": profile_id,
        "workflow": workflow_id,
        "execution_readiness": readiness,
        "next_action": next_action,
        "required_adapters": required_adapters,
        "selected_agents": selected_agents,
        "selected_skills": skill_rows,
        "approval": {
            "required_actions": approval_actions,
            "approved_actions": sorted(approved_actions),
            "pending_actions": pending_approvals,
            "satisfied": not pending_approvals,
        },
        "steps": steps,
        "constraints": {
            "forbidden_actions": task.get("forbidden_actions", [
                "merge", "production_deploy", "secret_mutation",
                "permission_change", "paid_provisioning", "production_data_mutation",
            ]),
            "external_execution_performed": False,
            "host_must_recheck_tools_and_permissions": True,
        },
    }


def create_task_state(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "task_id": plan["task_id"],
        "status": "REQUESTED",
        "plan": plan,
        "events": [{
            "from": None,
            "to": "REQUESTED",
            "at": datetime.now(timezone.utc).isoformat(),
            "evidence": "Task plan created; no external execution performed.",
        }],
    }


def transition_task(
    state: dict[str, Any],
    target: str,
    evidence: dict[str, Any] | None = None,
    approved_actions: list[str] | None = None,
) -> dict[str, Any]:
    evidence = evidence or {}
    current = state.get("status")
    if target not in STATES:
        raise RuntimeErrorBase(f"Unknown task state: {target}")
    if target not in TRANSITIONS.get(current, set()):
        raise RuntimeErrorBase(f"Invalid transition: {current} -> {target}")

    plan = state.get("plan", {})
    approved = set(approved_actions or [])
    pending = set(plan.get("approval", {}).get("pending_actions", []))
    if target == "EXECUTING":
        if plan.get("execution_readiness") == "BLOCKED":
            raise RuntimeErrorBase("Execution blocked: a required adapter or capability is blocked or unverified")
        if pending - approved:
            raise RuntimeErrorBase(f"Execution blocked: explicit Owner approval is pending for {sorted(pending - approved)}")
    if target == "REVIEWING" and evidence.get("verification_passed") is not True:
        raise RuntimeErrorBase("Cannot enter REVIEWING without verification_passed=true")
    if target == "CLOSED" and evidence.get("review_verdict") != "PASS":
        raise RuntimeErrorBase("Cannot close without an independent PASS review verdict")

    updated = dict(state)
    updated["events"] = list(state.get("events", []))
    updated["status"] = target
    updated["events"].append({
        "from": current,
        "to": target,
        "at": datetime.now(timezone.utc).isoformat(),
        "evidence": evidence,
        "approved_actions": sorted(approved),
    })
    if target == "EXECUTING" and approved:
        updated["plan"] = dict(plan)
        approval = dict(plan.get("approval", {}))
        approval["approved_actions"] = sorted(set(approval.get("approved_actions", [])) | approved)
        approval["pending_actions"] = sorted(pending - approved)
        approval["satisfied"] = not approval["pending_actions"]
        updated["plan"]["approval"] = approval
    return updated


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Blind Sniper registry-driven orchestration planner")
    sub = parser.add_subparsers(dest="command", required=True)
    plan_parser = sub.add_parser("plan", help="route a task through the registries")
    plan_parser.add_argument("--task-file", required=True)
    plan_parser.add_argument("--output", required=True)
    move_parser = sub.add_parser("transition", help="advance a guarded task lifecycle state")
    move_parser.add_argument("--state-file", required=True)
    move_parser.add_argument("--to", required=True, choices=STATES)
    move_parser.add_argument("--output", required=True)
    move_parser.add_argument("--evidence-file")
    move_parser.add_argument("--approve-action", action="append", default=[], help="Exact consequential action approved by the Owner; repeat for multiple actions")
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            task = read_json(Path(args.task_file))
            plan = build_plan(task)
            write_json(Path(args.output), create_task_state(plan))
            print(json.dumps({"task_id": plan["task_id"], "workflow": plan["workflow"],
                              "profile": plan["profile"], "readiness": plan["execution_readiness"],
                              "next_action": plan["next_action"]}, indent=2))
        else:
            state = read_json(Path(args.state_file))
            evidence = read_json(Path(args.evidence_file)) if args.evidence_file else {}
            updated = transition_task(state, args.to, evidence, args.approve_action)
            write_json(Path(args.output), updated)
            print(json.dumps({"task_id": updated["task_id"], "status": updated["status"]}, indent=2))
        return 0
    except (RuntimeErrorBase, OSError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
