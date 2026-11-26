#!/usr/bin/env python3
"""Offline GitHub issue intake into the private task store.

Trust boundary (R1): this module never trusts identity text inside the issue body, and it does
not trust a bare event file. The caller supplies the raw delivery bytes, the X-GitHub-Delivery id
and the X-Hub-Signature-256 header. The HMAC secret is read from the environment variable named
by config["webhook_secret_env"] and is never stored here. A missing secret, a missing header or a
bad signature rejects the event (fail closed). This CLI is not a network ingress: it must only be
fed a delivery that a trusted receiver on the private host already received from GitHub. No such
receiver exists yet, so this is not live authenticated GitHub intake.

Persistence is transactional. The task is staged under a name the daemon never reads, the
idempotency index is written, and only then is the task published with a no-overwrite hard link.
That link is the commit point. Any failure before it rolls back and leaves no task visible.

Body template: ```json
{"task_id":"...","agent_id":"...","objective":"...","payload":{},"require_tool_use":false}
```"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import hmac
import json
import os
import re
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
MAX_EVENT_BYTES = 256 * 1024
FENCE = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)
DELIVERY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SIGNATURE = re.compile(r"^sha256=[0-9a-f]{64}$")
STAGING_PREFIX = ".intake-staging-"


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _safe_number(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0


def _safe_text(value: Any, limit: int = 200) -> str:
    return value[:limit] if isinstance(value, str) else ""


def _reject(reason: str, repository: Any = "", number: Any = 0, delivery: Any = "") -> dict[str, Any]:
    delivery = delivery if isinstance(delivery, str) and DELIVERY_ID.fullmatch(delivery) else ""
    return {"outcome": "rejected", "reason_code": reason, "repository": _safe_text(repository),
            "issue_number": _safe_number(number), "delivery_id": delivery, "task_envelope": None}


def verify_signature(raw: bytes, signature_header: Any, secret: Any) -> bool:
    """Constant-time check of a GitHub X-Hub-Signature-256 value over the raw delivery bytes."""
    if not isinstance(secret, str) or not secret or not isinstance(signature_header, str):
        return False
    if not SIGNATURE.fullmatch(signature_header):
        return False
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def validate_issue_event(event: Any, config: Any, *, delivery_id: Any) -> dict:
    """Validate an already authenticated issue event. Returns a task envelope or a reason code.

    delivery_id is required: it is the X-GitHub-Delivery value conveyed by the trusted caller,
    never a field read from the event body.
    """
    if not isinstance(delivery_id, str) or not DELIVERY_ID.fullmatch(delivery_id):
        return _reject("invalid_delivery_id")
    if not isinstance(event, dict) or not isinstance(config, dict):
        return _reject("malformed_event", delivery=delivery_id)
    repo_obj, issue = event.get("repository"), event.get("issue")
    if not isinstance(repo_obj, dict) or not isinstance(issue, dict):
        return _reject("malformed_event", delivery=delivery_id)
    repository = repo_obj.get("full_name")
    number = issue.get("number")
    if not isinstance(repository, str):
        return _reject("malformed_event", delivery=delivery_id)
    if event.get("action") not in ("opened", "edited"):
        return _reject("unsupported_action", repository, number, delivery_id)
    if repository != config.get("repository"):
        return _reject("repository_mismatch", repository, number, delivery_id)
    if not _safe_number(number):
        return _reject("invalid_issue_number", repository, 0, delivery_id)
    if "pull_request" in issue:
        return _reject("pull_request", repository, number, delivery_id)
    if issue.get("state") != "open":
        return _reject("closed_issue", repository, number, delivery_id)
    if repo_obj.get("fork") is not False:
        return _reject("fork_repository", repository, number, delivery_id)
    user = issue.get("user")
    author = user.get("login") if isinstance(user, dict) else None
    allowed = config.get("allowed_authors")
    if not isinstance(author, str) or not isinstance(allowed, list) or author not in allowed:
        return _reject("untrusted_author", repository, number, delivery_id)
    body = issue.get("body")
    if not isinstance(body, str):
        return _reject("missing_body", repository, number, delivery_id)
    if len(body.encode("utf-8")) > MAX_BODY:
        return _reject("body_too_large", repository, number, delivery_id)
    blocks = FENCE.findall(body)
    if not blocks:
        return _reject("missing_template", repository, number, delivery_id)
    try:
        data = json.loads(blocks[0])
    except (ValueError, TypeError):
        return _reject("invalid_json", repository, number, delivery_id)
    if not isinstance(data, dict):
        return _reject("invalid_template", repository, number, delivery_id)
    if set(data) - FIELDS:
        return _reject("unknown_keys", repository, number, delivery_id)
    if set(data) != FIELDS:
        return _reject("missing_fields", repository, number, delivery_id)
    if not isinstance(data["task_id"], str) or not TASK_ID.fullmatch(data["task_id"]):
        return _reject("invalid_task_id", repository, number, delivery_id)
    agents = config.get("agents")
    if not isinstance(agents, list) or data["agent_id"] not in agents:
        return _reject("unknown_agent", repository, number, delivery_id)
    if not isinstance(data["objective"], str) or not data["objective"].strip():
        return _reject("invalid_objective", repository, number, delivery_id)
    if not isinstance(data["payload"], dict) or len(canonical(data["payload"])) > MAX_PAYLOAD:
        return _reject("invalid_payload", repository, number, delivery_id)
    if not isinstance(data["require_tool_use"], bool):
        return _reject("invalid_require_tool_use", repository, number, delivery_id)
    return {"outcome": "accepted", "reason_code": "accepted", "repository": repository,
            "issue_number": number, "delivery_id": delivery_id, "task_envelope": data}


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


def _write_receipt(receipts: Path, receipt: dict[str, Any]) -> dict[str, Any]:
    """Receipts are immutable evidence: one file per distinct event, created exclusively."""
    key = "|".join(str(receipt.get(k, "")) for k in ("delivery_id", "outcome", "reason_code", "payload_digest"))
    name = f"{_safe_number(receipt.get('issue_number'))}-{hashlib.sha256(key.encode()).hexdigest()[:12]}.json"
    try:
        _exclusive_json(receipts / name, receipt)
    except FileExistsError:
        pass  # the identical event was already recorded; the existing receipt stays untouched
    return receipt


def _intake_dirs(state_dir: str | Path) -> tuple[Path, Path, Path]:
    intake = _private_dir(Path(state_dir) / "intake")
    return intake, _private_dir(intake / "receipts"), _private_dir(intake / "index")


def sweep_staging(task_dir: str | Path) -> int:
    """Remove staging leftovers from an interrupted intake. The daemon never reads these names."""
    removed = 0
    for path in Path(task_dir).glob(STAGING_PREFIX + "*"):
        try:
            path.unlink()
            removed += 1
        except OSError:
            pass
    return removed


def write_task(store_task_dir: str | Path, envelope: dict, *, state_dir: str | Path,
               repository: str = "", issue_number: int = 0, delivery_id: str = "") -> dict[str, Any]:
    """Publish one accepted task atomically with its idempotency record, then write a receipt."""
    if not _safe_number(issue_number):
        raise ValueError("invalid issue number")
    if not isinstance(delivery_id, str) or not DELIVERY_ID.fullmatch(delivery_id):
        raise ValueError("invalid delivery id")
    canonical_digest = hashlib.sha256(canonical(envelope)).hexdigest()
    intake, receipts, index = _intake_dirs(state_dir)
    index_path = index / f"{hashlib.sha256((repository + '#' + str(issue_number)).encode()).hexdigest()}.json"
    task_dir = Path(store_task_dir)
    reason = "accepted"
    lock_fd = os.open(intake / ".lock", os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)  # serialize deliveries across threads and processes
        if task_dir.is_symlink() or not task_dir.is_dir():
            reason = "invalid_task_store"
        elif sweep_staging(task_dir) >= 0 and index_path.exists():
            previous = json.loads(index_path.read_text(encoding="utf-8"))
            reason = "idempotent" if previous.get("payload_digest") == canonical_digest else "changed_payload"
        else:
            reason = _publish(task_dir, index_path, envelope, repository, issue_number, delivery_id,
                              canonical_digest)
    except (OSError, ValueError, KeyError, TypeError):
        reason = "index_error"
    finally:
        os.close(lock_fd)
    outcome = "accepted" if reason in ("accepted", "idempotent") else "rejected"
    return _write_receipt(receipts, {
        "repository": _safe_text(repository), "issue_number": issue_number, "task_id": envelope.get("task_id"),
        "delivery_id": delivery_id, "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload_digest": canonical_digest, "outcome": outcome, "reason_code": reason})


def _publish(task_dir: Path, index_path: Path, envelope: dict, repository: str, issue_number: int,
             delivery_id: str, digest: str) -> str:
    """stage -> index -> link (commit point). Everything before the link rolls back on any failure."""
    final = task_dir / f"{envelope['task_id']}.json"
    staging = task_dir / f"{STAGING_PREFIX}{os.getpid()}-{envelope['task_id']}"
    index_created = False
    try:
        if os.path.lexists(final):
            return "task_id_collision"
        _exclusive_json(staging, envelope)
        _exclusive_json(index_path, {"repository": repository, "issue_number": issue_number,
                                     "delivery_id": delivery_id, "payload_digest": digest,
                                     "task_id": envelope["task_id"]})
        index_created = True
        try:
            os.link(staging, final)  # fails if the task id exists; never overwrites
        except FileExistsError:
            index_path.unlink()
            index_created = False
            return "task_id_collision"
        return "accepted"
    except BaseException:
        if index_created:
            try:
                index_path.unlink()
            except OSError:
                pass
        raise
    finally:
        try:
            staging.unlink()
        except OSError:
            pass


def write_rejection(state_dir: str | Path, result: dict) -> dict[str, Any]:
    """Record a validation rejection (reason code only). Writes no task file."""
    _, receipts, _ = _intake_dirs(state_dir)
    return _write_receipt(receipts, {
        "repository": _safe_text(result.get("repository")), "issue_number": _safe_number(result.get("issue_number")),
        "task_id": None, "delivery_id": result.get("delivery_id", ""),
        "timestamp": datetime.now(timezone.utc).isoformat(), "payload_digest": None,
        "outcome": "rejected", "reason_code": _safe_text(result.get("reason_code"), 64)})


def process_delivery(raw: bytes, *, delivery_id: Any, signature: Any, config: Any, state_dir: str | Path,
                     env: dict[str, str] | None = None) -> dict[str, Any]:
    """Authenticate, validate and persist one delivery. Returns the receipt (reason code only)."""
    environ = os.environ if env is None else env
    if not isinstance(config, dict):
        return write_rejection(state_dir, _reject("malformed_event", delivery=delivery_id))
    secret = environ.get(str(config.get("webhook_secret_env") or ""), "")
    if not isinstance(delivery_id, str) or not DELIVERY_ID.fullmatch(delivery_id):
        return write_rejection(state_dir, _reject("invalid_delivery_id"))
    if not secret:
        return write_rejection(state_dir, _reject("signature_secret_unavailable", delivery=delivery_id))
    if len(raw) > MAX_EVENT_BYTES:
        return write_rejection(state_dir, _reject("event_too_large", delivery=delivery_id))
    if not verify_signature(raw, signature, secret):
        return write_rejection(state_dir, _reject("bad_signature", delivery=delivery_id))
    try:
        event = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return write_rejection(state_dir, _reject("malformed_event", delivery=delivery_id))
    result = validate_issue_event(event, config, delivery_id=delivery_id)
    if result["outcome"] != "accepted":
        return write_rejection(state_dir, result)
    store = PrivateTaskStore(Path(state_dir))
    return write_task(store.task_dir, result["task_envelope"], state_dir=state_dir,
                      repository=result["repository"], issue_number=result["issue_number"],
                      delivery_id=delivery_id)


def main() -> int:
    parser = argparse.ArgumentParser(description="Intake one trusted GitHub issue delivery (not a network ingress).")
    parser.add_argument("--event-path", required=True, help="raw delivery body exactly as received")
    parser.add_argument("--delivery-id", required=True, help="X-GitHub-Delivery value from the trusted receiver")
    parser.add_argument("--signature", required=True, help="X-Hub-Signature-256 value from the trusted receiver")
    parser.add_argument("--config-path", required=True)
    parser.add_argument("--state-dir", required=True)
    args = parser.parse_args()
    try:
        raw = Path(args.event_path).read_bytes()
        config = json.loads(Path(args.config_path).read_text(encoding="utf-8"))
        receipt = process_delivery(raw, delivery_id=args.delivery_id, signature=args.signature,
                                   config=config, state_dir=args.state_dir)
        print(json.dumps({k: receipt.get(k) for k in ("repository", "issue_number", "task_id", "delivery_id",
                                                      "timestamp", "payload_digest", "outcome", "reason_code")},
                         sort_keys=True))
        return 0 if receipt["outcome"] == "accepted" else 1
    except (OSError, ValueError, DaemonError):
        print(json.dumps({"outcome": "rejected", "reason_code": "intake_error"}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
