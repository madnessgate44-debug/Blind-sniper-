"""Tests for the skill finder and the skill adapter.

These exercise the real catalog in chatgpt-home/runtime/skills.index.json and the
real SKILL.md files. They never mutate the repository: the adapter's write path is
tested against a temporary copy of the index.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import adapt_skill  # noqa: E402
import find_skill  # noqa: E402


class SkillFinderTest(unittest.TestCase):
    def setUp(self) -> None:
        index = json.loads(find_skill.INDEX_PATH.read_text(encoding="utf-8"))
        self.catalog = find_skill.load_catalog(index)

    def test_catalog_covers_native_and_mirror(self) -> None:
        sources = {row["source"] for row in self.catalog}
        self.assertEqual(sources, {"native", "openhands_mirror"})
        self.assertEqual(len(self.catalog), 47)

    def test_validate_passes_with_only_shadow_notes(self) -> None:
        errors, notes = find_skill.validate(self.catalog)
        self.assertEqual(errors, [])
        shadowed = {note.split()[1] for note in notes}
        self.assertEqual(shadowed, {"git-workflow", "multi-session-pr-coordination", "owner-policy"})

    def test_search_returns_relevant_skill_first(self) -> None:
        results = find_skill.search(self.catalog, "review a pull request for security bugs")
        self.assertTrue(results)
        self.assertIn("code-review-rubric", [row["id"] for row in results[:3]])

    def test_profile_filter_limits_results(self) -> None:
        allowed = find_skill.profile_skills("engineering")
        results = find_skill.search(self.catalog, "database migration", allowed)
        self.assertTrue(all(row["id"] in allowed for row in results))

    def test_frontmatter_parsing_recovers_description_and_triggers(self) -> None:
        meta = find_skill.parse_frontmatter(ROOT / "chatgpt-home/skills/test-and-evidence/SKILL.md")
        self.assertEqual(meta["name"], "test-and-evidence")
        self.assertIn("verify", meta["triggers"])
        self.assertTrue(meta["description"])


class SkillAdapterTest(unittest.TestCase):
    def test_dry_run_contract_has_native_frontmatter_and_sections(self) -> None:
        source_rel, text = adapt_skill.resolve_source("database-migrations")
        contract = adapt_skill.build_contract("database-migrations", source_rel, text, "sql runner")
        for marker in ["name: database-migrations", "triggers:", "risk:", "required_tools: sql runner"]:
            self.assertIn(marker, contract)
        for heading in ["## Purpose", "## Prerequisites", "## Permissions", "## Procedure",
                        "## Evidence", "## Failure handling", "## Completion criteria"]:
            self.assertIn(heading, contract)
        # Provenance must be recorded and the draft must not claim activation.
        self.assertIn("openhands-library", contract)
        self.assertIn("does not activate anything", contract)

    def test_resolve_source_rejects_unknown(self) -> None:
        with self.assertRaises(SystemExit):
            adapt_skill.resolve_source("definitely-not-a-real-skill-xyz")

    def test_write_registers_skill_in_a_temp_index(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            index_copy = Path(temp) / "skills.index.json"
            index_copy.write_text(adapt_skill.INDEX_PATH.read_text(encoding="utf-8"), encoding="utf-8")
            original = adapt_skill.INDEX_PATH
            try:
                adapt_skill.INDEX_PATH = index_copy
                changed = adapt_skill.register_in_index("adapted-demo", "chatgpt-home/skills/adapted-demo/SKILL.md")
                self.assertTrue(changed)
                data = json.loads(index_copy.read_text(encoding="utf-8"))
                self.assertIn("adapted-demo", data["native_skills"])
                self.assertEqual(data["native_skill_paths"]["adapted-demo"],
                                 "chatgpt-home/skills/adapted-demo/SKILL.md")
                # Idempotent: a second call makes no further change.
                self.assertFalse(adapt_skill.register_in_index(
                    "adapted-demo", "chatgpt-home/skills/adapted-demo/SKILL.md"))
            finally:
                adapt_skill.INDEX_PATH = original


if __name__ == "__main__":
    unittest.main()
