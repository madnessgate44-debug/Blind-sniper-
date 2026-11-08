#!/usr/bin/env python3
"""Smoke-test the plugin through the real OpenHands SDK loader.

`validate.py` checks the files' shape with plain YAML/JSON parsing. This script
loads the plugin with the same loader OpenHands uses, so it catches the failure
mode the plain checks cannot: a component that is well-formed on disk but
silently dropped at load time (the documented "one malformed file drops a
component" trap).

Checks:
  * ``Plugin.load(".agents")`` succeeds;
  * the number of skills the loader returns equals the number of skill files on
    disk (a mismatch means the loader dropped one);
  * same for sub-agents;
  * the hooks config is present and every hook command resolves to a script
    that exists in the plugin.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

AGENTS = Path(__file__).resolve().parent.parent / ".agents"
SKILLS = AGENTS / "skills"
AGENTS_DIR = AGENTS / "dev.openhands" / "agents"
HOOKS_JSON = AGENTS / "dev.openhands" / "hooks" / "hooks.json"

FAILURES: list[str] = []


def fail(msg: str) -> None:
    FAILURES.append(msg)


def skill_files() -> int:
    n = 0
    for entry in SKILLS.iterdir():
        if entry.is_dir() and (entry / "SKILL.md").exists():
            n += 1
        elif entry.suffix == ".md":
            n += 1
    return n


def agent_files() -> int:
    return sum(1 for p in AGENTS_DIR.glob("*.md") if p.name.lower() != "readme.md")


def main() -> int:
    try:
        from openhands.sdk.plugin import Plugin
    except ImportError:
        print("openhands-sdk is not installed; cannot run the loader smoke test", file=sys.stderr)
        return 1

    plugin = Plugin.load(str(AGENTS))
    print(f"loaded plugin: {plugin.name} {plugin.version}")
    print(f"  skills: {len(plugin.skills)}  sub-agents: {len(plugin.agents)}  hooks: {bool(plugin.hooks)}")

    disk_skills = skill_files()
    if len(plugin.skills) != disk_skills:
        fail(f"loader returned {len(plugin.skills)} skills but {disk_skills} exist on disk")

    disk_agents = agent_files()
    if len(plugin.agents) != disk_agents:
        fail(f"loader returned {len(plugin.agents)} sub-agents but {disk_agents} exist on disk")

    if not plugin.skills:
        fail("loader returned no skills")
    if not plugin.agents:
        fail("loader returned no sub-agents")
    if not plugin.hooks:
        fail("loader returned no hooks")

    # Every skill must map to a real trigger. A skill with trigger=None is
    # "always active" (its full text sits in <REPO_CONTEXT> on every turn).
    # Exactly one skill is allowed to be trigger-less on purpose: `owner-policy`.
    # Any other trigger-less skill is almost certainly a mistake.
    always_active = "owner-policy"
    seen_always_active = False
    for skill in plugin.skills:
        trigger = getattr(skill, "trigger", None)
        if trigger is None:
            if skill.name == always_active:
                seen_always_active = True
            else:
                fail(f"skill {skill.name} has no trigger (would load always-active)")
        elif skill.name in ("content-vs-brand", "docs-evidence-format", "no-schedule-claims"):
            if type(trigger).__name__ != "PathTrigger":
                fail(f"path rule {skill.name} loaded as {type(trigger).__name__}, expected PathTrigger")
    if not seen_always_active:
        fail(f"the {always_active} skill did not load as always-active (trigger=None)")

    hooks = json.loads(HOOKS_JSON.read_text())
    hook_count = 0
    for matchers in hooks.values():
        for matcher in matchers:
            for hook in matcher.get("hooks", []):
                hook_count += 1
                for name in ("guard.py", "quality_gate.sh", "backlog_gate.sh"):
                    if name in hook.get("command", "") and not (AGENTS / "dev.openhands" / "hooks" / name).exists():
                        fail(f"hook command references missing script {name}")
    if hook_count == 0:
        fail("hooks.json declares no hooks")

    if FAILURES:
        print(f"\n{len(FAILURES)} FAILURE(S):")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("OK: the plugin loads through the SDK with every component present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
