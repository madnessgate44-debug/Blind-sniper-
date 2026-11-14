#!/usr/bin/env python3
"""Deterministic, approval-gated knowledge proposal builder.

Consumes only validated native observations and writes immutable Markdown
proposals to a private directory outside the public repository. It never
promotes a proposal to approved knowledge.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from datetime import datetime
from pathlib import Path
from typing import Any

from blind_sniper_memory import MemoryError, _ensure_private_external_path, build_observation

MAX_JOURNAL_BYTES = 20 * 1024 * 1024
TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
PAGE_ID_RE = re.compile(r"^task-[a-f0-9]{20}$")


class KnowledgeError(ValueError):
    """Invalid observation journal or unsafe knowledge operation."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _read_observations(journal_path: str | Path) -> list[dict[str, Any]]:
    path = Path(journal_path).expanduser().resolve(strict=True)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise KnowledgeError("observation journal must be a regular singly-linked file")
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise KnowledgeError("observation journal must be owner-only (0600)")
    if info.st_size > MAX_JOURNAL_BYTES:
        raise KnowledgeError("observation journal exceeds the size limit")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            raw = json.loads(line)
            record = build_observation(
                observation_id=raw["observation_id"],
                event_type=raw["event_type"],
                occurred_at=raw["occurred_at"],
                source=raw["source"],
                source_ref=raw["source_ref"],
                project_id=raw["project_id"],
                classification=raw["classification"],
                content=raw["content"],
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, MemoryError) as exc:
            raise KnowledgeError(f"invalid observation at line {line_number}") from exc
        if raw != record:
            raise KnowledgeError(f"observation integrity mismatch at line {line_number}")
        rows.append(record)
    return rows


def _render_proposal(task_id: str, observations: list[dict[str, Any]], prior_ids: list[str]) -> tuple[str, str]:
    ordered = sorted(observations, key=lambda item: (item["occurred_at"], item["observation_id"]))
    observation_ids = [item["observation_id"] for item in ordered]
    digests = [item["content_digest"] for item in ordered]
    page_id = "task-" + hashlib.sha256(task_id.encode("utf-8")).hexdigest()[:20]
    proposal_id = hashlib.sha256(_canonical({"page_id": page_id, "observation_ids": observation_ids, "digests": digests})).hexdigest()
    classification = "private_owner" if any(item["classification"] == "private_owner" for item in ordered) else "public_project"
    metadata = {
        "page_id": page_id,
        "proposal_id": proposal_id,
        "title": f"Task lifecycle: {task_id}",
        "project_id": ordered[0]["project_id"],
        "classification": classification,
        "created_at": ordered[0]["occurred_at"],
        "updated_at": ordered[-1]["occurred_at"],
        "source_observation_ids": observation_ids,
        "status": "proposed",
        "supersedes": sorted(set(prior_ids)),
    }
    lines = [
        "---",
        json.dumps(metadata, sort_keys=True, ensure_ascii=False),
        "---",
        "",
        f"# {metadata['title']}",
        "",
        "This is a deterministic proposal derived from validated lifecycle metadata.",
        "It is not approved knowledge and must not be used for retrieval until reviewed.",
        "",
        "## Evidence",
        "",
    ]
    for item in ordered:
        content = item["content"]
        fields = [
            f"- Event: `{item['event_type']}`",
            f"  - Time: `{item['occurred_at']}`",
            f"  - Agent: `{content.get('agent_id', 'unknown')}`",
            f"  - Status: `{content.get('status', 'unknown')}`",
        ]
        if isinstance(content.get("attempt"), int):
            fields.append(f"  - Attempt: `{content['attempt']}`")
        if content.get("result_digest"):
            fields.append(f"  - Result digest: `{content['result_digest']}`")
        fields.append(f"  - Observation: `{item['observation_id']}`")
        lines.extend(fields)
    lines.append("")
    lines.append("> Approval required. No automatic promotion or supersession is performed.")
    return page_id, "\n".join(lines) + "\n"


def build_proposals(journal_path: str | Path, knowledge_dir: str | Path) -> dict[str, int]:
    """Create immutable proposed pages grouped by task; return created/duplicate counts."""
    observations = _read_observations(journal_path)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in observations:
        task_id = item["content"].get("task_id")
        if isinstance(task_id, str) and TASK_ID_RE.fullmatch(task_id):
            grouped.setdefault(task_id, []).append(item)

    created = duplicates = 0
    for task_id, items in sorted(grouped.items()):
        page_id = "task-" + hashlib.sha256(task_id.encode("utf-8")).hexdigest()[:20]
        directory = Path(knowledge_dir).expanduser().absolute()
        safe_probe = _ensure_private_external_path(directory / ".knowledge-probe")
        directory = safe_probe.parent
        prior = sorted(directory.glob(f"{page_id}--*.md"))
        prior_ids = [path.stem.split("--", 1)[1] for path in prior]
        _, markdown = _render_proposal(task_id, items, prior_ids)
        metadata_line = markdown.splitlines()[1]
        proposal_id = json.loads(metadata_line)["proposal_id"]
        target = directory / f"{page_id}--{proposal_id}.md"
        safe_target = _ensure_private_external_path(target)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            fd = os.open(safe_target, flags, 0o600)
        except FileExistsError:
            duplicates += 1
            continue
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(markdown)
                handle.flush()
                os.fsync(handle.fileno())
            created += 1
        except Exception:
            try:
                safe_target.unlink(missing_ok=True)
            finally:
                raise
    return {"created": created, "duplicates": duplicates, "tasks_seen": len(grouped)}


def approve_proposal(
    proposal_path: str | Path,
    approved_dir: str | Path,
    *,
    reviewer: str,
    expected_proposal_id: str,
) -> str:
    """Create an immutable approved copy after an explicit reviewer action."""
    if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer.strip()) > 128:
        raise KnowledgeError("reviewer must be a non-empty bounded identifier")
    source = Path(proposal_path).expanduser().absolute()
    source = _ensure_private_external_path(source)
    source = source.resolve(strict=True)
    source_info = source.stat()
    if not stat.S_ISREG(source_info.st_mode) or source_info.st_nlink != 1:
        raise KnowledgeError("proposal must be a regular singly-linked file")
    if stat.S_IMODE(source_info.st_mode) & 0o077:
        raise KnowledgeError("proposal must be owner-only (0600)")
    lines = source.read_text(encoding="utf-8").splitlines()
    if len(lines) < 4 or lines[0] != "---" or lines[2] != "---":
        raise KnowledgeError("proposal frontmatter is invalid")
    try:
        metadata = json.loads(lines[1])
    except json.JSONDecodeError as exc:
        raise KnowledgeError("proposal metadata is invalid") from exc
    if metadata.get("status") != "proposed":
        raise KnowledgeError("only proposed pages can be approved")
    if metadata.get("proposal_id") != expected_proposal_id:
        raise KnowledgeError("proposal identity changed; review the current version")
    if not PAGE_ID_RE.fullmatch(str(metadata.get("page_id", ""))):
        raise KnowledgeError("proposal page_id is invalid")
    metadata["status"] = "approved"
    metadata["approved_by"] = reviewer.strip()
    metadata["approved_at"] = datetime.now().astimezone().isoformat()
    metadata["approved_from"] = source.name
    approved_dir_path = Path(approved_dir).expanduser().absolute()
    safe_probe = _ensure_private_external_path(approved_dir_path / ".approval-probe")
    target = safe_probe.parent / source.name
    safe_target = _ensure_private_external_path(target)
    markdown = "\\n".join(["---", json.dumps(metadata, sort_keys=True, ensure_ascii=False), "---", *lines[3:]]) + "\\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(safe_target, flags, 0o600)
    except FileExistsError:
        return "DUPLICATE"
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(markdown)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        safe_target.unlink(missing_ok=True)
        raise
    return "APPROVED"


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--journal", required=True)
    parser.add_argument("--knowledge-dir", required=True)
    args = parser.parse_args()
    result = build_proposals(args.journal, args.knowledge_dir)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
