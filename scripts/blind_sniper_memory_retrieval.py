#!/usr/bin/env python3
"""Bounded deterministic lexical retrieval over explicitly approved memory pages."""
from __future__ import annotations

import json
import re
import stat
from pathlib import Path
from typing import Any


class RetrievalError(ValueError):
    """Invalid query, page metadata or retrieval scope."""


def _tokens(value: str) -> set[str]:
    return {token.casefold() for token in re.findall(r"[^\W_]+", value, flags=re.UNICODE) if len(token) > 1}


def _read_page(path: Path) -> tuple[dict[str, Any], str]:
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise RetrievalError("knowledge page must be a regular singly-linked file")
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise RetrievalError("knowledge page must be owner-only (0600)")
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) < 4 or lines[0] != "---" or lines[2] != "---":
        raise RetrievalError(f"invalid knowledge frontmatter: {path.name}")
    try:
        metadata = json.loads(lines[1])
    except json.JSONDecodeError as exc:
        raise RetrievalError(f"invalid knowledge metadata: {path.name}") from exc
    if not isinstance(metadata, dict):
        raise RetrievalError(f"invalid knowledge metadata: {path.name}")
    return metadata, "\n".join(lines[3:]).strip()


def search_approved_pages(
    query: str,
    approved_dir: str | Path,
    *,
    project_id: str,
    scope: str = "owner",
    max_results: int = 5,
    max_context_bytes: int = 8000,
) -> dict[str, Any]:
    """Search approved pages only, scoped to one project and bounded context."""
    if not isinstance(query, str) or not query.strip():
        raise RetrievalError("query must be a non-empty string")
    if not isinstance(project_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", project_id):
        raise RetrievalError("project_id is invalid")
    if scope not in {"owner", "public"}:
        raise RetrievalError("scope must be owner or public")
    if isinstance(max_results, bool) or not 1 <= max_results <= 20:
        raise RetrievalError("max_results must be between 1 and 20")
    if isinstance(max_context_bytes, bool) or not 256 <= max_context_bytes <= 65536:
        raise RetrievalError("max_context_bytes must be between 256 and 65536")
    terms = _tokens(query)
    if not terms:
        raise RetrievalError("query contains no searchable terms")

    directory = Path(approved_dir).expanduser().resolve(strict=True)
    if not directory.is_dir() or stat.S_IMODE(directory.stat().st_mode) & 0o077:
        raise RetrievalError("approved knowledge directory must be owner-only")
    candidates: list[dict[str, Any]] = []
    allowed = {"public_project"} if scope == "public" else {"public_project", "private_owner"}
    for path in sorted(directory.glob("*.md"), key=lambda item: item.name):
        metadata, body = _read_page(path)
        if metadata.get("status") != "approved":
            continue
        if metadata.get("project_id") != project_id or metadata.get("classification") not in allowed:
            continue
        page_terms = _tokens(str(metadata.get("title", "")) + " " + body)
        score = len(terms & page_terms)
        if score:
            candidates.append({
                "page_id": metadata.get("page_id", ""),
                "title": metadata.get("title", path.stem),
                "project_id": project_id,
                "classification": metadata["classification"],
                "updated_at": metadata.get("updated_at", ""),
                "source_observation_ids": metadata.get("source_observation_ids", []),
                "supersedes": metadata.get("supersedes", []),
                "score": score,
                "body": body,
            })
    candidates.sort(key=lambda item: (-item["score"], item["page_id"]))
    selected = candidates[:max_results]
    results: list[dict[str, Any]] = []
    context_parts: list[str] = []
    used = 0
    truncated = False
    for item in selected:
        citation = {
            key: item[key] for key in (
                "page_id", "title", "project_id", "classification",
                "updated_at", "source_observation_ids", "supersedes", "score",
            )
        }
        results.append(citation)
        rendered = f"## {item['title']}\n\n{item['body']}\n\n[page_id: {item['page_id']}]"
        encoded = rendered.encode("utf-8")
        separator = "\n\n".encode("utf-8") if context_parts else b""
        remaining = max_context_bytes - used - len(separator)
        if remaining <= 0:
            truncated = True
            break
        if len(encoded) > remaining:
            excerpt = encoded[:remaining].decode("utf-8", errors="ignore").rstrip()
            if excerpt:
                context_parts.append(excerpt)
                used += len(excerpt.encode("utf-8"))
            truncated = True
            break
        context_parts.append(rendered)
        used += len(separator) + len(encoded)
    return {
        "results": results,
        "context": "\n\n".join(context_parts),
        "context_bytes": used,
        "truncated": truncated or len(candidates) > len(results),
        "scope": scope,
        "project_id": project_id,
    }
