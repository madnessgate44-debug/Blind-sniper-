#!/usr/bin/env python3
"""Offline issue intake. Body template: ```json
{"task_id":"...","agent_id":"...","objective":"...","payload":{},"require_tool_use":false}
```"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from blind_sniper_daemon import DaemonError, PrivateTaskStore, TASK_ID, _atomic_private_json

FIELDS = {"task_id", "agent_id", "objective", "payload", "require_tool_use"}
MAX_BODY = 16 * 1024
MAX_PAYLOAD = 8 * 1024
FENCE = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


DELIVERY_ID = re.compile(r"^[A-Za-z0-9._:-]{0,128}$")


def _safe_number(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0


def _safe_text(value: Any, limit: int = 200) -> str:
    return value[:limit] if isinstance(value, str) else ""


def _reject(reason: str, repository: str = "", number: Any = 0, delivery: str = "") -> dict[str, Any]:
    repository = _safe_text(repository)
    number = _safe_number(number)
    delivery = delivery if DELIVERY_ID.fullmatch(delivery or "") else ""
    return {"outcome": "rejected", "reason_code": reason, "repository": repository,
            "issue_number": number, "delivery_id": delivery, "task_envelope": None}


def validate_issue_event(event: dict, config: dict) -> dict:
    """Validate an issue event and return a safe daemon task envelope or reason code."""
    repository = _safe_text((event.get("repository") or {}).get("full_name", ""))
    issue = event.get("issue") if isinstance(event.get("issue"), dict) else {}
    number = issue.get("number", 0)
    delivery = str(event.get("delivery_id") or config.get("delivery_id", ""))
    if not DELIVERY_ID.fullmatch(delivery):
        delivery = ""
    if event.get("action") not in ("opened", "edited"):
        return _reject("unsupported_action", repository, number, delivery)
    if repository != config.get("repo", config.get("repository")):
        return _reject("repository_mismatch", repository, number, delivery)
    if not _safe_number(number):
        return _reject("invalid_issue_number", repository, 0, delivery)
    if "pull_request" in issue:
        return _reject("pull_request", repository, number, delivery)
    if issue.get("state", "open") == "closed":
        return _reject("closed_issue", repository, number, delivery)
    if (event.get("repository") or {}).get("fork") is not False:
        return _reject("fork_repository", repository, number, delivery)
    author = (issue.get("user") or {}).get("login")
    if author not in config.get("allowlist", config.get("allowed_authors", [])):
        return _reject("untrusted_author", repository, number, delivery)
    body = issue.get("body")
    if not isinstance(body, str):
        return _reject("missing_body", repository, number, delivery)
    if len(body.encode("utf-8")) > MAX_BODY:
        return _reject("body_too_large", repository, number, delivery)
    blocks = FENCE.findall(body)
    if not blocks:
        return _reject("missing_template", repository, number, delivery)
    try:
        data = json.loads(blocks[0])
    except (ValueError, TypeError):
        return _reject("invalid_json", repository, number, delivery)
    if not isinstance(data, dict):
        return _reject("invalid_template", repository, number, delivery)
    if set(data) - FIELDS:
        return _reject("unknown_keys", repository, number, delivery)
    if set(data) != FIELDS:
        return _reject("missing_fields", repository, number, delivery)
    if not isinstance(data["task_id"], str) or not TASK_ID.fullmatch(data["task_id"]):
        return _reject("invalid_task_id", repository, number, delivery)
    if data["agent_id"] not in config.get("agent_registry", config.get("agents", [])):
        return _reject("unknown_agent", repository, number, delivery)
    if not isinstance(data["objective"], str) or not data["objective"].strip():
        return _reject("invalid_objective", repository, number, delivery)
    if not isinstance(data["payload"], dict) or len(canonical(data["payload"])) > MAX_PAYLOAD:
        return _reject("invalid_payload", repository, number, delivery)
    if not isinstance(data["require_tool_use"], bool):
        return _reject("invalid_require_tool_use", repository, number, delivery)
    return {"outcome": "accepted", "reason_code": "accepted", "repository": repository,
            "issue_number": number, "delivery_id": delivery, "task_envelope": data}


def _private_dir(path: Path) -> Path:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink() or not path.is_dir():
        raise ValueError("unsafe private directory")
    os.chmod(path, 0o700)
    return path


def _exclusive_json(path: Path, value: dict[str, Any]) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            fd = -1
            json.dump(value, f, ensure_ascii=False, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
    finally:
        if fd >= 0:
            os.close(fd)


def write_task(store_task_dir: str | Path, envelope: dict, *, state_dir: str | Path,
               repository: str = "", issue_number: int = 0, delivery_id: str = "") -> dict[str, Any]:
    """Write one accepted task and a private idempotency record and receipt."""
    now = datetime.now(timezone.utc).isoformat()
    canonical_digest = hashlib.sha256(canonical(envelope)).hexdigest()
    base = Path(state_dir)
    intake = _private_dir(base / "intake")
    receipts = _private_dir(intake / "receipts")
    index = _private_dir(intake / "index")
    if not _safe_number(issue_number):
        raise ValueError("invalid issue number")
    index_path = index / f"{hashlib.sha256((repository + '#' + str(issue_number)).encode()).hexdigest()}.json"
    reason = "accepted"
    lock_fd = os.open(intake / ".lock", os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)  # serialize concurrent deliveries of the same event
        if index_path.exists():
            previous = json.loads(index_path.read_text(encoding="utf-8"))
            if previous.get("payload_digest") == canonical_digest:
                reason = "idempotent"
            else:
                reason = "changed_payload"
        else:
            task_dir = Path(store_task_dir)
            if task_dir.is_symlink() or not task_dir.is_dir():
                reason = "invalid_task_store"
            else:
                task_path = task_dir / f"{envelope['task_id']}.json"
                try:
                    _exclusive_json(task_path, envelope)
                    # Build the index only after the exclusive task write succeeds.
                    _exclusive_json(index_path, {"repository": repository, "issue_number": issue_number,
                                                 "delivery_id": delivery_id, "payload_digest": canonical_digest,
                                                 "task_id": envelope["task_id"]})
                except FileExistsError:
                    reason = "task_id_collision"
                except (OSError, KeyError, TypeError, ValueError):
                    reason = "task_write_failed"
    except (OSError, ValueError, json.JSONDecodeError):
        reason = "index_error"
    finally:
        os.close(lock_fd)
    outcome = "accepted" if reason in ("accepted", "idempotent") else "rejected"
    return _write_receipt(receipts, {"repository": repository, "issue_number": issue_number, "task_id": envelope.get("task_id"),
               "delivery_id": delivery_id, "timestamp": now, "payload_digest": canonical_digest,
               "outcome": outcome, "reason_code": reason})


def _write_receipt(receipts: Path, receipt: dict[str, Any]) -> dict[str, Any]:
    """One receipt file per distinct outcome, so a later rejection never replaces an acceptance."""
    key = "|".join(str(receipt.get(k, "")) for k in ("delivery_id", "outcome", "reason_code", "payload_digest"))
    name = f"{_safe_number(receipt.get('issue_number'))}-{hashlib.sha256(key.encode()).hexdigest()[:12]}.json"
    _atomic_private_json(receipts / name, receipt)
    return receipt


def write_rejection(state_dir: str | Path, result: dict) -> dict[str, Any]:
    """Record a validation rejection (reason code only). Writes no task file."""
    receipts = _private_dir(_private_dir(Path(state_dir) / "intake") / "receipts")
    return _write_receipt(receipts, {
        "repository": _safe_text(result.get("repository")), "issue_number": _safe_number(result.get("issue_number")),
        "task_id": None, "delivery_id": result.get("delivery_id", ""),
        "timestamp": datetime.now(timezone.utc).isoformat(), "payload_digest": None,
        "outcome": "rejected", "reason_code": _safe_text(result.get("reason_code"), 64)})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-path", required=True)
    parser.add_argument("--config-path", required=True)
    parser.add_argument("--state-dir", required=True)
    args = parser.parse_args()
    try:
        event = json.loads(Path(args.event_path).read_text(encoding="utf-8"))
        config = json.loads(Path(args.config_path).read_text(encoding="utf-8"))
        result = validate_issue_event(event, config)
        if result["outcome"] == "accepted":
            store = PrivateTaskStore(Path(args.state_dir))
            receipt = write_task(store.task_dir, result["task_envelope"], state_dir=args.state_dir,
                                 repository=result["repository"], issue_number=result["issue_number"],
                                 delivery_id=result["delivery_id"])
        else:
            receipt = write_rejection(args.state_dir, result)
        print(json.dumps({k: receipt[k] for k in ("repository", "issue_number", "task_id", "delivery_id",
                                                  "timestamp", "payload_digest", "outcome", "reason_code")},
                         sort_keys=True))
        return 0 if receipt["outcome"] == "accepted" else 1
    except (OSError, ValueError, json.JSONDecodeError, DaemonError) as exc:
        print(json.dumps({"outcome": "rejected", "reason_code": "intake_error"}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
