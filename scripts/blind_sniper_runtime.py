#!/usr/bin/env python3
"""Blind Sniper's registry-driven task planner and guarded lifecycle engine.

This engine plans and validates orchestration. It does not impersonate external
agents, invoke unregistered adapters, or bypass host/Owner permissions.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from blind_sniper_ledger import GitHubContentsLedger, LedgerError, TaskLedger

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "chatgpt-home" / "runtime"

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
    "production_deploy", "secret_mutation",
    "permission_change", "paid_provisioning", "production_data_mutation",
    "delete", "irreversible", "merge", "merge_to_main", "default_branch_push",
    "force_push", "delete_branch", "ci_cd_edit", "workflow_edit", "deploy",
}
ROUTINE_ACTIONS = {
    "read", "inspect", "research", "analyze", "write_file", "create_branch",
    "open_pr", "run_tests", "format", "lint",
}
AUTHORIZED_REPOSITORY = "madnessgate44-debug/Blind-sniper-"
EXPECTED_DELEGATION_ID = "owner-standing-delegation-2026-11-09"
DELEGABLE_ACTIONS = {
    "merge", "merge_to_main", "default_branch_push", "ci_cd_edit",
    "workflow_edit", "deploy", "production_deploy", "release", "delete",
}
DELEGATION_EXCLUSIONS = {
    "secret_mutation", "permission_change", "paid_provisioning", "production_data_mutation",
}
HOST_FORBIDDEN_ACTIONS = [
    "force_push", "delete_branch", "credential_export", "secret_export",
    "disable_branch_protection", "unbounded_shell",
]
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


def load_authority_policy(root: Path = ROOT) -> dict[str, Any]:
    """Load the machine-readable, repository-scoped standing delegation."""
    policy = read_json(root / "chatgpt-home" / "runtime" / "authority.json")
    if policy.get("schema_version") != "1.0.0":
        raise RuntimeErrorBase("authority.json has an unsupported schema_version")
    delegations = policy.get("delegations")
    if not isinstance(delegations, list):
        raise RuntimeErrorBase("authority.json delegations must be a list")
    ids = [str(row.get("id", "")).strip() for row in delegations if isinstance(row, dict)]
    if len(ids) != len(delegations) or not all(ids) or len(ids) != len(set(ids)):
        raise RuntimeErrorBase("authority.json requires unique, non-empty delegation IDs")
    active_repositories = set()
    for row in delegations:
        repository = str(row.get("repository", "")).strip()
        actions = row.get("actions")
        forbidden = row.get("forbidden_actions", [])
        if repository != AUTHORIZED_REPOSITORY or row.get("id") != EXPECTED_DELEGATION_ID:
            raise RuntimeErrorBase("authority.json delegation identity or repository scope is not recognized")
        if row.get("grantor") != "repository-owner" or row.get("delegate") != "blind-sniper":
            raise RuntimeErrorBase("authority.json delegation grantor/delegate identity is not recognized")
        if row.get("status") not in {"active", "revoked"}:
            raise RuntimeErrorBase("authority.json delegation requires active/revoked status")
        if not isinstance(actions, list) or not all(isinstance(item, str) and item.strip() for item in actions):
            raise RuntimeErrorBase(f"authority.json delegation {row['id']} has invalid actions")
        if len(actions) != len(set(actions)):
            raise RuntimeErrorBase(f"authority.json delegation {row['id']} has duplicate actions")
        if set(actions) != DELEGABLE_ACTIONS:
            raise RuntimeErrorBase(f"authority.json delegation {row['id']} action allowlist does not match the reviewed code policy")
        if not isinstance(forbidden, list) or not all(isinstance(item, str) and item.strip() for item in forbidden):
            raise RuntimeErrorBase(f"authority.json delegation {row['id']} has invalid forbidden_actions")
        if len(forbidden) != len(set(forbidden)) or not DELEGATION_EXCLUSIONS.issubset(set(forbidden)):
            raise RuntimeErrorBase(f"authority.json delegation {row['id']} omits required exclusions or duplicates exclusions")
        if set(actions) & (set(forbidden) | set(HOST_FORBIDDEN_ACTIONS)):
            raise RuntimeErrorBase(f"authority.json delegation {row['id']} attempts to authorize a forbidden action")
        if row.get("status") == "active":
            if repository in active_repositories:
                raise RuntimeErrorBase(f"authority.json has multiple active delegations for {repository}")
            active_repositories.add(repository)
    return policy


def delegated_approval_actions(
    repository: str | None,
    requested_actions: set[str],
    policy: dict[str, Any],
) -> tuple[set[str], str | None]:
    """Resolve only explicitly allowlisted actions for an exact repository match."""
    target = str(repository or "").strip()
    if not target:
        return set(), None
    for row in policy.get("delegations", []):
        if row.get("status") != "active" or row.get("repository") != target:
            continue
        allowed = set(row.get("actions", []))
        forbidden = set(row.get("forbidden_actions", [])) | set(HOST_FORBIDDEN_ACTIONS)
        approved = (requested_actions & allowed) - forbidden
        if "merge_or_deploy" in requested_actions and {"merge", "deploy"}.issubset(allowed) and not ({"merge", "deploy"} & forbidden):
            approved.add("merge_or_deploy")
        return approved, str(row.get("id"))
    return set(), None


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
    matches = []
    for row in workflows:
        rule = row.get("routing", {})
        matched = [
            keyword for keyword in rule.get("keywords", [])
            if re.search(r"(?<![a-z0-9])" + re.escape(str(keyword).lower()) + r"(?![a-z0-9])", text)
        ]
        if matched:
            matches.append((int(rule.get("priority", 0)), len(matched), row["id"]))
    if matches:
        return max(matches)[2]
    if "task-control-loop" not in known:
        raise RuntimeErrorBase("Workflow registry has no task-control-loop fallback")
    return "task-control-loop"


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
    profiles_registry = registries["profiles"]
    profiles = profiles_registry.get("profiles", [])
    agents = registries["agents"].get("agents", [])
    workflow_registry = registries["workflows"]
    workflows = workflow_registry.get("workflows", [])
    skill_index = registries["skills.index"]

    workflow_id = choose_workflow(task, workflows)
    workflow = next(row for row in workflows if row["id"] == workflow_id)
    # The profile bound to the selected workflow is host policy; task JSON cannot select it.
    matching_profiles = [row for row in profiles if row.get("workflow") == workflow_id]
    if len(matching_profiles) > 1:
        raise RuntimeErrorBase(f"Workflow {workflow_id} maps to multiple operating profiles")
    if matching_profiles:
        profile = matching_profiles[0]
    else:
        default_profile_id = profiles_registry.get("default_profile")
        profile = next((row for row in profiles if row.get("id") == default_profile_id), None)
    if profile is None:
        raise RuntimeErrorBase("Runtime default operating profile is missing")
    profile_id = profile["id"]

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
    preferred_agents = workflow.get("agents") or workflow_registry.get("default_agent_selection", [])
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

    requested_actions = {str(x).strip().lower() for x in task.get("requested_actions", []) if str(x).strip()}
    # Anything not explicitly classified as routine is high-risk by default.
    approval_actions = sorted(requested_actions - ROUTINE_ACTIONS)
    if workflow_id == "release-gate":
        approval_actions = sorted(set(approval_actions) | {"merge_or_deploy"})
    # Task envelopes are untrusted. Standing authority is loaded only from the
    # checked-in host policy, never from task-supplied approval/delegation fields.
    authority_policy = load_authority_policy(root)
    approved_actions, delegation_id = delegated_approval_actions(
        task.get("repository"), set(approval_actions), authority_policy
    )
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
        "authority_delegation": ({
            "id": delegation_id,
            "repository": task.get("repository"),
            "source": "chatgpt-home/runtime/authority.json",
            "applied_actions": sorted(approved_actions),
        } if delegation_id and approved_actions else None),
        "approval": {
            "required_actions": approval_actions,
            "approved_actions": sorted(approved_actions),
            "pending_actions": pending_approvals,
            "satisfied": not pending_approvals,
            "authority_source": "standing_delegation" if approved_actions else ("explicit_owner_approval_required" if pending_approvals else "none"),
        },
        "steps": steps,
        "constraints": {
            "forbidden_actions": list(HOST_FORBIDDEN_ACTIONS),
            "external_execution_performed": False,
            "host_must_recheck_tools_and_permissions": True,
        },
    }


def create_task_state(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "task_id": plan["task_id"],
        "implementer_id": "blind-sniper",
        "status": "REQUESTED",
        "plan": plan,
        "events": [{
            "from": None,
            "to": "REQUESTED",
            "at": datetime.now(timezone.utc).isoformat(),
            "evidence": "Task plan created; no external execution performed.",
        }],
    }


def validate_owner_approval(record: dict[str, Any], task_id: str, now: datetime | None = None) -> dict[str, str]:
    if not isinstance(record, dict):
        raise RuntimeErrorBase("Owner approval record must be an object")
    approval_id = str(record.get("approval_id", "")).strip()
    record_task = str(record.get("task_id", "")).strip()
    action = str(record.get("action", "")).strip().lower()
    approver = str(record.get("approver", "")).strip()
    words = str(record.get("verbatim_words", "")).strip()
    timestamp = str(record.get("timestamp", "")).strip()
    expires_at = str(record.get("expires_at", "")).strip()
    if not approval_id or record_task != task_id:
        raise RuntimeErrorBase("Owner approval must have a unique approval_id bound to this task")
    if not action or approver != "OWNER" or not words or task_id not in words or action not in words.lower():
        raise RuntimeErrorBase("Owner approval must identify Ahmed, the exact action, and task ID in verbatim words")
    try:
        issued = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeErrorBase("Owner approval requires valid timestamp and expires_at values") from exc
    if issued.tzinfo is None or expiry.tzinfo is None or expiry <= issued:
        raise RuntimeErrorBase("Owner approval timestamps must be offset-aware and expiry must follow issuance")
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise RuntimeErrorBase("Approval validation time must include a timezone")
    if issued > instant or expiry <= instant:
        raise RuntimeErrorBase("Owner approval is expired or not yet valid")
    return {"approval_id": approval_id, "task_id": task_id, "action": action}


def ensure_approvals_unused(ledger, records: list[dict[str, Any]]) -> None:
    requested = {str(record.get("approval_id", "")).strip() for record in records}
    if not requested or "" in requested:
        raise RuntimeErrorBase("Every Owner approval requires an approval_id")
    used = set()
    for event in ledger.events():
        payload = event.get("payload", {})
        for record in payload.get("approval_records", []):
            used.add(str(record.get("approval_id", "")))
        imported = payload.get("import_approval")
        if isinstance(imported, dict):
            used.add(str(imported.get("approval_id", "")))
    replayed = requested & used
    if replayed:
        raise RuntimeErrorBase(f"Owner approval already consumed: {sorted(replayed)}")


def transition_task(
    state: dict[str, Any],
    target: str,
    evidence: dict[str, Any] | None = None,
    approved_actions: list[str] | None = None,
    approval_records: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    evidence = evidence or {}
    current = state.get("status")
    if target not in STATES:
        raise RuntimeErrorBase(f"Unknown task state: {target}")
    if target not in TRANSITIONS.get(current, set()):
        raise RuntimeErrorBase(f"Invalid transition: {current} -> {target}")

    plan = state.get("plan", {})
    approved = set()
    pending = set(plan.get("approval", {}).get("pending_actions", []))
    if target == "EXECUTING":
        forbidden = set(plan.get("constraints", {}).get("forbidden_actions", HOST_FORBIDDEN_ACTIONS))
        if pending & forbidden:
            raise RuntimeErrorBase(f"Execution blocked: host policy forbids {sorted(pending & forbidden)}")
        if plan.get("execution_readiness") == "BLOCKED":
            raise RuntimeErrorBase("Execution blocked: a required adapter or capability is blocked or unverified")
    for record in approval_records or []:
        validated = validate_owner_approval(record, str(state.get("task_id", "")), now)
        action = validated["action"]
        if action not in pending:
            raise RuntimeErrorBase(f"Owner approval does not match a pending action: {action}")
        approved.add(action)
    if target == "EXECUTING" and pending - approved:
        raise RuntimeErrorBase(f"Execution blocked: explicit Owner approval is pending for {sorted(pending - approved)}")
    if target == "REVIEWING" and evidence.get("verification_passed") is not True:
        raise RuntimeErrorBase("Cannot enter REVIEWING without verification_passed=true")
    if target == "CLOSED":
        reviewer = str(evidence.get("reviewer_id", "")).strip()
        implementer = str(state.get("implementer_id", "")).strip()
        if evidence.get("review_verdict") != "PASS" or not reviewer or reviewer == implementer:
            raise RuntimeErrorBase("Cannot close without a PASS from a reviewer distinct from the implementer")
        if evidence.get("task_id") != state.get("task_id") or not re.fullmatch(r"[0-9a-f]{40}", str(evidence.get("commit_sha", ""))) or not str(evidence.get("ci_run_id", "")).strip():
            raise RuntimeErrorBase("Cannot close without matching task ID, full commit SHA, and CI run ID")

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


def recover_task_state(ledger_source: str | Path | TaskLedger | GitHubContentsLedger, task_id: str) -> dict[str, Any]:
    """Reconstruct the latest committed task snapshot from a verified local or GitHub ledger."""
    ledger = ledger_source if hasattr(ledger_source, "task_history") else TaskLedger(ledger_source)
    try:
        history = ledger.task_history(task_id)
    except LedgerError:
        raise
    latest = None
    for event in history["events"]:
        snapshot = event.get("payload", {}).get("state")
        if isinstance(snapshot, dict):
            latest = snapshot
    if latest is None:
        raise RuntimeErrorBase(f"Ledger has no recoverable state snapshot for task {task_id}")
    return latest


def persist_task_state(
    ledger: TaskLedger | GitHubContentsLedger,
    state: dict[str, Any],
    *,
    event_type: str,
    idempotency_key: str,
    extra_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Commit a complete state snapshot and approval receipts before checkpoint write."""
    payload = {"state": state, **(extra_payload or {})}
    return ledger.append(
        task_id=state["task_id"],
        event_type=event_type,
        payload=payload,
        idempotency_key=idempotency_key,
    )


def add_ledger_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--ledger", default=".blind-sniper/state/events.jsonl")
    parser.add_argument("--github-ledger", action="store_true", help="Use GitHub Contents API compare-and-swap storage")
    parser.add_argument("--github-owner")
    parser.add_argument("--github-repo")
    parser.add_argument("--github-branch")
    parser.add_argument("--github-path", default=".blind-sniper/state/events.jsonl")
    parser.add_argument("--github-token-env", default="GITHUB_TOKEN")


def configure_ledger(args) -> TaskLedger | GitHubContentsLedger:
    if not args.github_ledger:
        return TaskLedger(args.ledger)
    token = os.environ.get(args.github_token_env, "")
    if not token:
        raise RuntimeErrorBase(f"GitHub ledger requires token in environment variable {args.github_token_env}")
    required = (args.github_owner, args.github_repo, args.github_branch)
    if not all(value and value.strip() for value in required):
        raise RuntimeErrorBase("--github-ledger requires --github-owner, --github-repo and --github-branch")
    return GitHubContentsLedger(
        owner=args.github_owner,
        repo=args.github_repo,
        path=args.github_path,
        branch=args.github_branch,
        token=token,
    )


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
    add_ledger_arguments(plan_parser)
    move_parser = sub.add_parser("transition", help="advance a guarded task lifecycle state")
    move_parser.add_argument("--state-file", required=True)
    move_parser.add_argument("--to", required=True, choices=STATES)
    move_parser.add_argument("--output", required=True)
    move_parser.add_argument("--evidence-file")
    move_parser.add_argument("--approval-record-file", help="Host-supplied JSON file containing action, approver, verbatim_words, and timestamp approval records")
    move_parser.add_argument("--lease-owner", help="Owner ID of the active task lease required for EXECUTING")
    add_ledger_arguments(move_parser)
    recover_parser = sub.add_parser("recover", help="rebuild the latest task checkpoint from the verified native ledger")
    add_ledger_arguments(recover_parser)
    recover_parser.add_argument("--task-id", required=True)
    recover_parser.add_argument("--output", required=True)
    claim_parser = sub.add_parser("claim", help="claim or renew a task lease in the local ledger")
    add_ledger_arguments(claim_parser)
    claim_parser.add_argument("--task-id", required=True)
    claim_parser.add_argument("--owner-id", required=True)
    claim_parser.add_argument("--lease-seconds", type=int, default=300)
    claim_parser.add_argument("--idempotency-key", required=True)
    release_parser = sub.add_parser("release", help="release a task lease owned by this runner")
    add_ledger_arguments(release_parser)
    release_parser.add_argument("--task-id", required=True)
    release_parser.add_argument("--owner-id", required=True)
    release_parser.add_argument("--idempotency-key", required=True)
    status_parser = sub.add_parser("lease-status", help="inspect the current task lease")
    add_ledger_arguments(status_parser)
    status_parser.add_argument("--task-id", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            task = read_json(Path(args.task_file))
            plan = build_plan(task)
            state = create_task_state(plan)
            ledger = configure_ledger(args)
            try:
                ledger.task_history(state["task_id"])
            except LedgerError as exc:
                if not str(exc).startswith("Unknown task_id:"):
                    raise
            else:
                raise RuntimeErrorBase(f"Task {state['task_id']} already exists in the ledger; use recover")
            ledger_event = persist_task_state(
                ledger, state, event_type="TASK_CREATED",
                idempotency_key=f"{state['task_id']}:created",
            )
            write_json(Path(args.output), state)
            print(json.dumps({"task_id": plan["task_id"], "workflow": plan["workflow"],
                              "profile": plan["profile"], "readiness": plan["execution_readiness"],
                              "next_action": plan["next_action"], "ledger_commit": ledger_event.get("commit_sha")}, indent=2))
        elif args.command == "transition":
            checkpoint = read_json(Path(args.state_file))
            ledger = configure_ledger(args)
            try:
                state = recover_task_state(ledger, checkpoint["task_id"])
            except LedgerError as exc:
                if not str(exc).startswith("Unknown task_id:"):
                    raise
                # Legacy import is a controlled recovery operation, never a trust-on-first-use path.
                state = checkpoint
                if state.get("status") != "REQUESTED":
                    raise RuntimeErrorBase("Legacy import requires status REQUESTED")
                plan = state.get("plan")
                if not isinstance(plan, dict):
                    raise RuntimeErrorBase("Legacy import requires a complete plan")
                derived = build_plan({
                    "task_id": state.get("task_id"),
                    "objective": plan.get("objective"),
                    "repository": plan.get("repository"),
                    "base_commit": plan.get("base_commit"),
                })
                if derived != plan:
                    raise RuntimeErrorBase("Legacy import plan does not re-derive identically from its objective")
                approval_records = read_json(Path(args.approval_record_file)).get("approvals", []) if args.approval_record_file else []
                import_records = [record for record in approval_records if str(record.get("action", "")).lower() == "task_import"]
                if len(import_records) != 1:
                    raise RuntimeErrorBase("Legacy import requires exactly one explicit Owner approval for task_import")
                import_approval = validate_owner_approval(import_records[0], state["task_id"])
                ensure_approvals_unused(ledger, import_records)
                persist_task_state(
                    ledger, state, event_type="TASK_IMPORTED",
                    idempotency_key=f"{state['task_id']}:imported",
                    extra_payload={"import_approval": import_records[0]},
                )
            approval_records = read_json(Path(args.approval_record_file)).get("approvals", []) if args.approval_record_file else []
            approval_records = [record for record in approval_records if str(record.get("action", "")).lower() != "task_import"]
            if args.to == state.get("status"):
                if state.get("status") in {"EXECUTING", "VERIFYING", "REVIEWING"}:
                    if not args.lease_owner or args.lease_owner != state.get("implementer_id"):
                        raise RuntimeErrorBase("Same-state post-EXECUTING retry requires the active lease owner")
                    lease = ledger.lease_status(state["task_id"])
                    if not lease or lease.get("owner_id") != args.lease_owner:
                        raise RuntimeErrorBase("Same-state post-EXECUTING retry requires an active lease")
                updated = state
            else:
                post_execution = state.get("status") in {"EXECUTING", "VERIFYING", "REVIEWING"}
                lease_required = post_execution or args.to == "EXECUTING"
                if lease_required:
                    if not args.lease_owner:
                        raise RuntimeErrorBase("An active task lease and --lease-owner are required for every post-EXECUTING transition")
                    if post_execution and args.lease_owner != state.get("implementer_id"):
                        raise RuntimeErrorBase("Post-EXECUTING transition lease owner must match the task implementer")
                    lease = ledger.lease_status(state["task_id"])
                    if not lease or lease.get("owner_id") != args.lease_owner:
                        raise RuntimeErrorBase("Transition requires an active lease held by --lease-owner")
                evidence = read_json(Path(args.evidence_file)) if args.evidence_file else {}
                if approval_records:
                    ensure_approvals_unused(ledger, approval_records)
                updated = transition_task(state, args.to, evidence, approval_records=approval_records)
                if args.to == "EXECUTING":
                    updated["implementer_id"] = args.lease_owner
                transition_number = len(updated.get("events", [])) - 1
                transition_key = f"{updated['task_id']}:transition:{transition_number}:{args.to}"
                if lease_required:
                    ledger_event = ledger.append_transition_if_lease(
                        task_id=updated["task_id"],
                        owner_id=args.lease_owner,
                        payload={"state": updated, "approval_records": approval_records},
                        idempotency_key=transition_key,
                    )
                else:
                    ledger_event = persist_task_state(
                        ledger, updated, event_type="TASK_TRANSITIONED",
                        idempotency_key=transition_key,
                        extra_payload={"approval_records": approval_records},
                    )
            write_json(Path(args.output), updated)
            print(json.dumps({"task_id": updated["task_id"], "status": updated["status"],
                              "ledger_commit": (ledger_event.get("commit_sha") if "ledger_event" in locals() else None)}, indent=2))
        elif args.command == "recover":
            ledger = configure_ledger(args)
            state = recover_task_state(ledger, args.task_id)
            write_json(Path(args.output), state)
            print(json.dumps({"task_id": state["task_id"], "status": state["status"],
                              "event_count": len(state.get("events", [])),
                              "ledger_commit": None}, indent=2))
        elif args.command == "claim":
            ledger = configure_ledger(args)
            ledger.task_history(args.task_id)
            result = ledger.claim_task(
                task_id=args.task_id, owner_id=args.owner_id,
                lease_seconds=args.lease_seconds, idempotency_key=args.idempotency_key,
            )
            if not result["claimed"]:
                raise RuntimeErrorBase(f"Task lease held by {result.get('owner_id')} until {result.get('lease_expires_at')}")
            print(json.dumps({"task_id": args.task_id, "owner_id": result["owner_id"],
                              "lease_expires_at": result["lease_expires_at"],
                              "event_created": result["event_created"]}, indent=2))
        elif args.command == "release":
            ledger = configure_ledger(args)
            result = ledger.release_task(
                task_id=args.task_id, owner_id=args.owner_id,
                idempotency_key=args.idempotency_key,
            )
            if not result["released"]:
                raise RuntimeErrorBase("No active task lease is owned by this runner")
            print(json.dumps({"task_id": args.task_id, "released": True,
                              "event_created": result["event_created"]}, indent=2))
        else:
            lease = configure_ledger(args).lease_status(args.task_id)
            print(json.dumps({"task_id": args.task_id, "lease": lease}, indent=2))
        return 0
    except (RuntimeErrorBase, LedgerError, OSError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
