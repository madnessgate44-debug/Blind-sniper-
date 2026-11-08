"""Unit tests for the Blind Sniper runtime registry validator."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_blind_sniper_runtime.py"


class RuntimeRegistryTests(unittest.TestCase):
    def test_validator_passes_on_repository_state(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS: runtime registries parse", result.stdout)

    def test_expected_capability_boundaries_are_explicit(self):
        import json
        registry = json.loads((ROOT / "chatgpt-home/runtime/capabilities.json").read_text())
        adapters = {item["id"]: item for item in registry["adapters"]}
        self.assertEqual(adapters["forge_browser_mcp"]["status"], "endpoint_remote_smoke_reported_connector_not_registered")
        self.assertEqual(adapters["openhands_dispatch"]["status"], "partially_verified")
        self.assertIn("TinyFish", registry["exclusions"][0])
        skills = json.loads((ROOT / "chatgpt-home/runtime/skills.index.json").read_text())
        self.assertEqual(len(skills["native_skills"]), 10)
        self.assertEqual(len(skills["skills"]), 33)
        agents = json.loads((ROOT / "chatgpt-home/runtime/agents.json").read_text())
        self.assertTrue(any(a["id"] == "shadow-auditor" for a in agents["agents"]))
        self.assertTrue(any(a["id"] == "shadow" for a in agents["agents"]))
        self.assertFalse(any(a["id"] == "ghost" for a in agents["agents"]))
        self.assertEqual(adapters["shadow_provider_pool"]["status"], "blocked_pool_not_loaded")
        self.assertEqual(adapters["forge_browser_mcp"]["status"], "endpoint_remote_smoke_verified_connector_not_registered")

    def test_profiles_do_not_enable_unrestricted_sandbox(self):
        import json
        data = json.loads((ROOT / "chatgpt-home/runtime/profiles.json").read_text())
        for profile in data["profiles"]:
            self.assertNotIn("danger-full-access", profile["sandbox"])


if __name__ == "__main__":
    unittest.main()
