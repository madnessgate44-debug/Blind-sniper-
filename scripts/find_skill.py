#!/usr/bin/env python3
"""Find Blind Sniper skills by describing a need, and audit the skill catalog.

This is the "walk through to find skills" entry point. It is read-only and
deterministic: it catalogs every skill declared in
chatgpt-home/runtime/skills.index.json (native + OpenHands reference mirror),
parses each SKILL.md frontmatter, and scores matches against a free-text query.

Examples:
    python scripts/find_skill.py "review a pull request for security bugs"
    python scripts/find_skill.py --profile engineering --list
    python scripts/find_skill.py --validate
    python scripts/find_skill.py "database schema change" --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "chatgpt-home" / "runtime" / "skills.index.json"
PROFILES_PATH = ROOT / "chatgpt-home" / "runtime" / "profiles.json"

STOPWORDS = {"the", "a", "an", "to", "for", "of", "and", "or", "with", "on", "in", "is", "it",
             "this", "that", "my", "our", "we", "i", "be", "by", "at", "as", "when", "how", "do"}
TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> set[str]:
    return {tok for tok in TOKEN_RE.findall(text.lower()) if len(tok) > 1 and tok not in STOPWORDS}


def parse_frontmatter(path: Path) -> dict[str, Any]:
    """Return {name, description, triggers, error} for a SKILL.md file."""
    if not path.is_file():
        return {"error": "missing_file"}
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        return {"error": "no_frontmatter"}
    block = match.group(1)
    name = description = ""
    triggers: list[str] = []
    for line in block.splitlines():
        if line.startswith("name:"):
            name = line.split(":", 1)[1].strip()
        elif line.startswith("description:"):
            description = line.split(":", 1)[1].strip().strip('"').replace('\\"', '"')
    trigger_match = re.search(r"^triggers:\s*\n((?:\s*-\s*.+\n?)+)", block, re.MULTILINE)
    if trigger_match:
        triggers = [item.strip().lstrip("-").strip().strip('"')
                    for item in trigger_match.group(1).splitlines() if item.strip()]
    elif re.search(r"^triggers:", block, re.MULTILINE):
        inline = re.search(r"^triggers:\s*(.+)$", block, re.MULTILINE)
        if inline:
            triggers = [t.strip() for t in inline.group(1).split(",") if t.strip()]
    return {"name": name, "description": description, "triggers": triggers}


def load_catalog(index: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    native_paths = index.get("native_skill_paths", {})
    path_rules = index.get("path_rules", {})
    for skill in index.get("native_skills", []):
        rel = native_paths.get(skill) or f"chatgpt-home/skills/{skill}/SKILL.md"
        rows.append(_row(skill, "native", rel))
    for skill in index.get("skills", []):
        rel = path_rules.get(skill) or f"chatgpt-home/openhands-library/.agents/skills/{skill}/SKILL.md"
        rows.append(_row(skill, "openhands_mirror", rel))
    return rows


def _row(skill: str, source: str, rel: str) -> dict[str, Any]:
    meta = parse_frontmatter(ROOT / rel)
    return {
        "id": skill,
        "source": source,
        "path": rel,
        "description": meta.get("description", ""),
        "triggers": meta.get("triggers", []),
        "error": meta.get("error"),
    }


def profile_skills(profile_id: str) -> list[str]:
    data = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
    for profile in data.get("profiles", []):
        if profile.get("id") == profile_id:
            return list(profile.get("skills", []))
    raise SystemExit(f"Unknown profile: {profile_id}. Known: "
                     f"{[p['id'] for p in data.get('profiles', [])]}")


def score(row: dict[str, Any], query_tokens: set[str]) -> int:
    haystack = tokenize(f"{row['id'].replace('-', ' ')} {row['description']} {' '.join(row['triggers'])}")
    return len(query_tokens & haystack)


def search(catalog: list[dict[str, Any]], query: str, allowed: list[str] | None = None) -> list[dict[str, Any]]:
    tokens = tokenize(query)
    ranked = []
    for row in catalog:
        if allowed is not None and row["id"] not in allowed:
            continue
        value = score(row, tokens)
        if value:
            ranked.append((value, row))
    ranked.sort(key=lambda item: (-item[0], item[1]["id"]))
    return [row for _, row in ranked]


def validate(catalog: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """Return (errors, notes). Errors fail the audit; notes are informational."""
    errors: list[str] = []
    notes: list[str] = []
    by_id: dict[str, list[str]] = {}
    for row in catalog:
        by_id.setdefault(row["id"], []).append(row["source"])
        if row["error"] == "missing_file":
            errors.append(f"MISSING_FILE: {row['id']} -> {row['path']}")
        elif row["error"] == "no_frontmatter":
            errors.append(f"NO_FRONTMATTER: {row['id']} -> {row['path']}")
        elif not row["description"]:
            errors.append(f"NO_DESCRIPTION: {row['id']} -> {row['path']}")
    for skill, sources in by_id.items():
        if len(sources) > 1 and len(set(sources)) == 1:
            errors.append(f"DUPLICATE_ID: {skill} declared {len(sources)}x in {sources[0]}")
        elif len(sources) > 1:
            # Native-first shadowing: the runtime resolves the native file. Informational.
            notes.append(f"SHADOWED: {skill} exists as {sorted(set(sources))}; native wins at runtime")
    return errors, notes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?", help="Describe what you need to do")
    parser.add_argument("--list", action="store_true", help="List all skills")
    parser.add_argument("--profile", help="Restrict to the skills available to a profile id")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--validate", action="store_true", help="Audit the catalog and exit")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    args = parser.parse_args()

    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    catalog = load_catalog(index)

    if args.validate:
        errors, notes = validate(catalog)
        for note in notes:
            print(f"note: {note}")
        if errors:
            print("\n".join(errors))
            return 1
        native = sum(1 for row in catalog if row["source"] == "native")
        mirror = sum(1 for row in catalog if row["source"] == "openhands_mirror")
        print(f"PASS: {len(catalog)} skills indexed ({native} native, {mirror} mirror); "
              "every entry has a file with a description.")
        return 0

    allowed = profile_skills(args.profile) if args.profile else None
    if args.profile:
        catalog = [row for row in catalog if row["id"] in allowed]

    if args.list or not args.query:
        for row in catalog:
            print(f"{row['id']:<32} [{row['source']}]")
        return 0

    results = search(catalog, args.query, allowed)[: args.limit]
    if args.json:
        print(json.dumps({"query": args.query, "profile": args.profile, "results": results}, indent=2))
        return 0
    if not results:
        print(f"No skill matched: {args.query!r}")
        return 1
    for row in results:
        print(f"{row['id']}  [{row['source']}]  {row['path']}")
        if row["description"]:
            print(f"    {row['description']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
