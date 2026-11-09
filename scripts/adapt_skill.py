#!/usr/bin/env python3
"""Adapt an external skill into a native Blind Sniper skill contract.

This is the "adapt skills" entry point. Given a source SKILL.md (a path, or a
skill id already in the index), it generates a native contract that conforms to
the native skill schema enforced by scripts/check-blind-sniper-environment.mjs:
frontmatter (name, description, triggers, risk, required_tools) plus the
Purpose / Prerequisites / Permissions / Procedure / Evidence / Failure handling
/ Completion criteria sections.

The generated contract is a DRAFT scaffold: the description and triggers are
carried over from the source, and the body sections are placeholders for the
maintainer to fill. It never copies a source verbatim and never claims the
adapted skill is active.

Dry run by default (prints the contract). With --write it creates
chatgpt-home/skills/<id>/SKILL.md and registers the skill in
chatgpt-home/runtime/skills.index.json.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from find_skill import INDEX_PATH, parse_frontmatter  # noqa: E402

NATIVE_SKILLS_DIR = ROOT / "chatgpt-home" / "skills"
ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

CONTRACT_TEMPLATE = """---
name: {skill_id}
description: {description}
triggers: {triggers}
risk: medium
required_tools: {required_tools}
---

# {title} Skill

> Adapted from `{source_rel}` ({provenance}). DRAFT scaffold — review every
> section, set the real risk level, and confirm the permissions before relying
> on it. This file records an adaptation; it does not activate anything.

## Purpose
{description}

## Prerequisites
- Read the environment manifest and the profiles that may use this skill.
- Confirm the tools named in `required_tools` are actually available to the host.

## Permissions
Read-only by default. Any mutation stays inside the standing Owner delegation for
the exact repository and action; paid provisioning, credential/secret mutation and
account or permission changes remain outside the grant.

## Procedure
1. Identify the exact need this skill serves and the acceptance criteria.
2. Inspect existing native and mirror skills to avoid duplication.
3. Define the steps, inputs, outputs and failure handling for this skill.
4. Add the concrete procedure steps here (replace this placeholder list).

## Evidence
Changed paths, the command(s) run, their exit codes, and any artifact or CI run.

## Failure handling
State what to do when a step fails or a required tool is unavailable; never mark
the skill active because a file exists.

## Completion criteria
The skill is indexed, validated, permission-scoped, and its behavior is verified
by at least one reproducible check.
"""


def resolve_source(source: str) -> tuple[str, str]:
    """Return (repo-relative path, text) for a source skill id or file path."""
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    native_paths = index.get("native_skill_paths", {})
    path_rules = index.get("path_rules", {})
    candidates: list[str] = []
    if source in native_paths:
        candidates.append(native_paths[source])
    if source in path_rules:
        candidates.append(path_rules[source])
    candidates.append(f"chatgpt-home/skills/{source}/SKILL.md")
    candidates.append(f"chatgpt-home/openhands-library/.agents/skills/{source}/SKILL.md")
    candidates.append(source)  # explicit path

    for rel in candidates:
        path = (ROOT / rel) if not Path(rel).is_absolute() else Path(rel)
        if path.is_file():
            return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path), path.read_text(encoding="utf-8")
    raise SystemExit(f"Source not found for {source!r}. Tried: {candidates}")


def source_provenance(source_rel: str) -> str:
    if "openhands-library" in source_rel:
        return "OpenHands reference mirror, madnessgate44-debug/Openhands"
    return "in-repository source"


def build_contract(skill_id: str, source_rel: str, text: str, required_tools: str) -> str:
    meta = parse_frontmatter(ROOT / source_rel) if (ROOT / source_rel).is_file() else {}
    description = (meta.get("description") or "").strip().strip('"') or "TODO: describe this skill."
    triggers = meta.get("triggers") or []
    triggers_text = ", ".join(triggers) if triggers else f"{skill_id.replace('-', ', ')}"
    title = " ".join(word.capitalize() for word in skill_id.split("-"))
    return CONTRACT_TEMPLATE.format(
        skill_id=skill_id,
        description=description,
        triggers=triggers_text,
        required_tools=required_tools,
        title=title,
        source_rel=source_rel,
        provenance=source_provenance(source_rel),
    )


def register_in_index(skill_id: str, rel_path: str) -> bool:
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    changed = False
    if skill_id not in index.get("native_skills", []):
        index.setdefault("native_skills", []).append(skill_id)
        changed = True
    if index.setdefault("native_skill_paths", {}).get(skill_id) != rel_path:
        index["native_skill_paths"][skill_id] = rel_path
        changed = True
    if changed:
        INDEX_PATH.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Source skill id (in the index) or a path to a SKILL.md")
    parser.add_argument("--id", dest="skill_id", help="New native skill id (default: source name)")
    parser.add_argument("--required-tools", default="TODO: list the tools this skill needs")
    parser.add_argument("--write", action="store_true", help="Write the contract and register it (default: dry run)")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing native skill")
    args = parser.parse_args()

    source_rel, text = resolve_source(args.source)
    meta = parse_frontmatter(ROOT / source_rel) if (ROOT / source_rel).is_file() else {}
    skill_id = args.skill_id or meta.get("name") or Path(source_rel).parent.name
    if not ID_RE.match(skill_id):
        raise SystemExit(f"Invalid skill id {skill_id!r}; use lower-case hyphenated words.")

    contract = build_contract(skill_id, source_rel, text, args.required_tools)
    rel_out = f"chatgpt-home/skills/{skill_id}/SKILL.md"
    dest = ROOT / rel_out

    if not args.write:
        print(contract)
        print(f"\n# dry run: would write {rel_out} and register '{skill_id}' in skills.index.json",
              file=sys.stderr)
        return 0

    if dest.exists() and not args.force:
        raise SystemExit(f"{rel_out} already exists; pass --force to overwrite.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(contract, encoding="utf-8")
    registered = register_in_index(skill_id, rel_out)
    print(f"wrote {rel_out}")
    print(f"index {'updated' if registered else 'already contained'} '{skill_id}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
