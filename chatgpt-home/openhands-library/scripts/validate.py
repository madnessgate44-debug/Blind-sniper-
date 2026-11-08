#!/usr/bin/env python3
"""Validate the account-library plugin.

Checks every manifest, skill, sub-agent and hook, and fails (exit 1) on any
violation so the same script can gate CI and a local pre-commit run.

Checks:
  * every manifest is valid JSON with the required keys;
  * every SKILL.md / agent .md has valid YAML frontmatter;
  * a skill's `name` is lowercase-hyphenated and equals its folder (or file stem
    for a path-triggered rule);
  * `description` is present and non-empty;
  * frontmatter scalars that YAML would misread (a bare number, or a value
    containing a colon) are quoted;
  * sub-agent tool names are real, and sub-agents do not wire plugin `skills:`;
  * hooks reference existing scripts and known events;
  * the counts stated in plugin.json match reality;
  * no file exceeds its size limit (SKILL.md < 3000 words).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - CI installs PyYAML
    print("PyYAML is required: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
AGENTS = ROOT / ".agents"
SKILLS = AGENTS / "skills"
AGENTS_DIR = AGENTS / "dev.openhands" / "agents"
HOOKS_DIR = AGENTS / "dev.openhands" / "hooks"
FAILURES: list[str] = []

VALID_TOOLS = {"terminal", "file_editor", "task_tracker", "browser_tool_set"}
KNOWN_HOOK_EVENTS = {
    "pre_tool_use",
    "post_tool_use",
    "user_prompt_submit",
    "session_start",
    "session_end",
    "stop",
}
SKILL_WORD_LIMIT = 3000
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# The one skill allowed to declare neither `triggers:` nor `paths:`, so it loads
# always-active on every turn.
ALWAYS_ACTIVE_SKILL = "owner-policy"


def fail(msg: str) -> None:
    FAILURES.append(msg)


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def check_json(path: Path, required: list[str]) -> dict:
    if not path.exists():
        fail(f"missing {rel(path)}")
        return {}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        fail(f"{rel(path)}: invalid JSON ({e})")
        return {}
    for key in required:
        if key not in data:
            fail(f"{rel(path)}: missing required key '{key}'")
    return data


def split_frontmatter(path: Path) -> tuple[str, str] | None:
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n?", text, re.S)
    if not m:
        return None
    return m.group(1), text


def check_quoting(path: Path, raw_fm: str) -> None:
    """Flag scalars YAML would misread: a bare number, or an unquoted colon."""
    for line in raw_fm.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("- "):
            # list items are checked for a leading bare number below
            if stripped.startswith("- "):
                value = stripped[2:].strip()
                if re.fullmatch(r"-?\d+(\.\d+)?", value):
                    fail(f"{rel(path)}: unquoted numeric list value '{value}' (quote it)")
            continue
        key, _, value = stripped.partition(":")
        value = value.strip()
        if not value or value in (">", "|"):
            continue
        if value[0] in "\"'" and value[-1] == value[0]:
            continue
        if re.fullmatch(r"-?\d+(\.\d+)?", value):
            fail(f"{rel(path)}: unquoted numeric value for '{key.strip()}' ('{value}'); quote it")
        if ": " in value:
            fail(f"{rel(path)}: unquoted value for '{key.strip()}' contains a colon; quote it")


def parse_frontmatter(path: Path) -> dict | None:
    parts = split_frontmatter(path)
    if parts is None:
        fail(f"{rel(path)}: no YAML frontmatter")
        return None
    raw_fm, _ = parts
    try:
        data = yaml.safe_load(raw_fm)
    except yaml.YAMLError as e:
        fail(f"{rel(path)}: invalid YAML frontmatter ({e})")
        return None
    if not isinstance(data, dict):
        fail(f"{rel(path)}: frontmatter is not a mapping")
        return None
    check_quoting(path, raw_fm)
    return data


def check_description(path: Path, fm: dict) -> None:
    desc = fm.get("description")
    if not isinstance(desc, str) or not desc.strip():
        fail(f"{rel(path)}: missing or empty description")


def check_skills() -> int:
    count = 0
    for entry in sorted(SKILLS.iterdir()):
        path = entry / "SKILL.md" if entry.is_dir() else entry
        if not path.exists() or path.suffix != ".md":
            continue
        expected = entry.name if entry.is_dir() else entry.stem
        fm = parse_frontmatter(path)
        if fm is None:
            continue
        name = fm.get("name")
        if name != expected:
            fail(f"{rel(path)}: name '{name}' != '{expected}'")
        if isinstance(name, str) and not NAME_RE.match(name):
            fail(f"{rel(path)}: name '{name}' is not lowercase-hyphenated")
        check_description(path, fm)
        if "triggers" not in fm and "paths" not in fm:
            # Exactly one skill is allowed to be trigger-less: `owner-policy`,
            # which is intentionally always-active (its text sits in
            # <REPO_CONTEXT> on every turn). Any other trigger-less skill is a
            # mistake, because always-active text costs context every turn.
            if name != ALWAYS_ACTIVE_SKILL:
                fail(
                    f"{rel(path)}: needs 'triggers:' or 'paths:' "
                    f"(only '{ALWAYS_ACTIVE_SKILL}' may be trigger-less)"
                )
        # `paths:` wins over `triggers:` and silently drops the triggers, so
        # declaring both is almost always a mistake.
        if "paths" in fm and "triggers" in fm:
            fail(f"{rel(path)}: declares both 'paths:' and 'triggers:'; 'paths:' wins, drop one")
        words = len(path.read_text().split())
        if words > SKILL_WORD_LIMIT:
            fail(
                f"{rel(path)}: {words} words exceeds the {SKILL_WORD_LIMIT}-word limit; "
                "move detail into references/ and link it from SKILL.md"
            )
        count += 1
    return count


def check_agents() -> int:
    count = 0
    for path in sorted(AGENTS_DIR.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        fm = parse_frontmatter(path)
        if fm is None:
            continue
        name = fm.get("name")
        if name != path.stem:
            fail(f"{rel(path)}: name '{name}' != '{path.stem}'")
        if isinstance(name, str) and not NAME_RE.match(name):
            fail(f"{rel(path)}: name '{name}' is not lowercase-hyphenated")
        check_description(path, fm)
        tools = fm.get("tools") or []
        if not isinstance(tools, list):
            fail(f"{rel(path)}: 'tools' must be a list")
            tools = []
        unknown = [t for t in tools if t not in VALID_TOOLS]
        if unknown:
            fail(f"{rel(path)}: unknown tool(s) {unknown}; valid names are {sorted(VALID_TOOLS)}")
        if fm.get("skills"):
            fail(
                f"{rel(path)}: sub-agent 'skills:' resolve against the workspace, not this "
                "plugin; remove them to avoid a load failure"
            )
        count += 1
    return count


def check_hooks() -> int:
    hooks_path = HOOKS_DIR / "hooks.json"
    hooks = check_json(hooks_path, [])
    if not hooks:
        return 0
    unknown = set(hooks) - KNOWN_HOOK_EVENTS
    if unknown:
        fail(f"{rel(hooks_path)}: unknown hook events {sorted(unknown)}")
    count = 0
    for event, matchers in hooks.items():
        for matcher in matchers:
            for hook in matcher.get("hooks", []):
                if not hook.get("command"):
                    fail(f"{rel(hooks_path)}: a hook has no command")
                count += 1
                for m in re.finditer(r"([\w.-]+\.(?:py|sh))", hook.get("command", "")):
                    if not (HOOKS_DIR / m.group(1)).exists():
                        fail(f"{rel(hooks_path)}: references missing script {m.group(1)}")
    return count


def check_counts(skills: int, agents: int, hooks: int) -> None:
    plugin = check_json(AGENTS / "plugin.json", ["$schema", "name", "version"])
    if plugin and not str(plugin.get("$schema", "")).startswith("https://agent-plugins.org/schemas/"):
        fail("plugin.json: $schema must be the agent-plugins.org 1.0.0 identifier")
    desc = str(plugin.get("description", "")) if plugin else ""
    # Only enforce counts that are actually stated in the description.
    for pattern, actual, label in (
        (r"(\d+)\s+skills", skills, "skills"),
        (r"(\d+)\s+sub-agents", agents, "sub-agents"),
        (r"(\d+)\s+lifecycle hooks", hooks, "hooks"),
    ):
        m = re.search(pattern, desc)
        if m and int(m.group(1)) != actual:
            fail(f"plugin.json: description says {m.group(1)} {label} but there are {actual}")
    marketplace = check_json(AGENTS / ".plugin" / "marketplace.json", ["name", "owner", "plugins"])
    if marketplace and not marketplace.get("plugins"):
        fail(
            ".plugin/marketplace.json: declares no plugin, so sub-agents and hooks "
            "will NOT load (a marketplace alone loads only skills)"
        )


def main() -> int:
    skills = check_skills()
    agents = check_agents()
    hooks = check_hooks()
    check_counts(skills, agents, hooks)

    print(f"skills: {skills}  sub-agents: {agents}  hooks: {hooks}")
    if FAILURES:
        print(f"\n{len(FAILURES)} FAILURE(S):")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("OK: manifests, frontmatter, skills, sub-agents and hooks are valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
