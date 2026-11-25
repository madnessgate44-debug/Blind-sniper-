#!/usr/bin/env python3
"""Watcher one-shot: read current state, diff against a cursor, deduplicate, classify, deliver.

Implements the Watcher contract (chatgpt-home/agents/watcher.md) as ONE bounded pass.
It is not a monitor: nothing here schedules itself, polls, or runs in the background.
Continuous monitoring exists only if a real trigger (workflow_dispatch, an approved
schedule, a host daemon) invokes this pass, and this file never claims otherwise.

Cursor rule from the contract: the cursor is persisted only after delivery succeeded,
so a failed delivery is retried on the next pass and never lost or double-reported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

STATUS_RANK = {"failure": 3, "cancelled": 2, "success": 0}


class WatcherError(RuntimeError):
    pass


def classify(prev: dict | None, cur: dict) -> str | None:
    """Return an event class for a changed item, or None when nothing meaningful changed."""
    if prev is None:
        return "new"
    if prev.get("status") != cur.get("status") or prev.get("conclusion") != cur.get("conclusion"):
        conclusion = cur.get("conclusion")
        if conclusion == "failure":
            return "failed"
        if conclusion == "success":
            return "recovered" if prev.get("conclusion") == "failure" else "succeeded"
        return "changed"
    return None


def fingerprint(item: dict) -> str:
    stable = {k: item.get(k) for k in ("id", "status", "conclusion")}
    return hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest()[:16]


def load_cursor(path: Path) -> dict:
    if not path.exists():
        return {"items": {}, "delivered": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WatcherError(f"cursor file is corrupt, refusing to guess: {exc}") from exc
    if not isinstance(data, dict) or "items" not in data:
        raise WatcherError("cursor file has unexpected shape")
    data.setdefault("delivered", [])
    return data


def save_cursor(path: Path, cursor: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(cursor, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def run_once(*, target: str, correlation_id: str, fetch: Callable[[], list[dict]],
             deliver: Callable[[dict], None], cursor_path: Path, stop_after: int = 200,
             now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> dict:
    """One pass. Returns the digest. Raises (cursor untouched) if delivery fails."""
    cursor = load_cursor(cursor_path)
    items = fetch()
    if len(items) > stop_after:
        raise WatcherError(f"source returned {len(items)} items, over the stop condition {stop_after}")
    events, next_items = [], dict(cursor["items"])
    seen_delivered = set(cursor["delivered"])
    for item in items:
        key = str(item["id"])
        kind = classify(cursor["items"].get(key), item)
        next_items[key] = {"status": item.get("status"), "conclusion": item.get("conclusion")}
        fp = fingerprint(item)
        if kind is None or fp in seen_delivered:
            continue
        events.append({"source_id": key, "class": kind, "status": item.get("status"),
                       "conclusion": item.get("conclusion"), "url": item.get("url"), "fingerprint": fp})
    digest = {
        "generated_at": now().isoformat(), "target": target, "correlation_id": correlation_id,
        "scope": "one bounded pass; not continuous monitoring",
        "items_read": len(items), "events": events,
        "blockers": [],
    }
    if events:
        deliver(digest)  # raises on failure: cursor must stay put
    delivered = sorted(seen_delivered | {e["fingerprint"] for e in events})[-1000:]
    save_cursor(cursor_path, {"items": next_items, "delivered": delivered})
    return digest


def github_runs_fetcher(repo: str, workflow: str, token: str | None = None) -> Callable[[], list[dict]]:
    def fetch() -> list[dict]:
        url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/runs?per_page=20"
        request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "blind-sniper-watcher"})
        if token:
            request.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(request, timeout=20) as response:  # read-only GET
            data = json.load(response)
        return [{"id": r["id"], "status": r["status"], "conclusion": r.get("conclusion"), "url": r["html_url"]}
                for r in data.get("workflow_runs", [])]
    return fetch


def file_deliverer(path: Path) -> Callable[[dict], None]:
    def deliver(digest: dict) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(digest, sort_keys=True) + "\n")
    return deliver


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", required=True)
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--cursor", required=True)
    parser.add_argument("--digest-file", required=True)
    parser.add_argument("--stop-after", type=int, default=200)
    args = parser.parse_args(argv)
    try:
        digest = run_once(
            target=f"{args.repo}:{args.workflow}", correlation_id=args.correlation_id,
            fetch=github_runs_fetcher(args.repo, args.workflow, os.environ.get("GITHUB_TOKEN")),
            deliver=file_deliverer(Path(args.digest_file)), cursor_path=Path(args.cursor), stop_after=args.stop_after,
        )
    except (WatcherError, OSError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"events": len(digest["events"]), "items_read": digest["items_read"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
