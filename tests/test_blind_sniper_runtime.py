"""Unit tests for the Blind Sniper runtime registry validator."""
from __future__ import annotations

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
        self.assertNotIn("forge_browser_mcp", adapters)
        self.assertEqual(adapters["chatgpt_history_export"]["status"], "blocked_no_native_export_action")
        self.assertEqual(adapters["ephemeral_execution"]["status"], "available_in_current_session")
        self.assertNotIn("openhands_dispatch", adapters)
        self.assertEqual(adapters["native_model_runtime"]["status"], "not_implemented_pending_p0")
        self.assertIn("native_task_queue", adapters)
        self.assertIn("agent_browser_cli", adapters)
        self.assertFalse(any("openhands-conversation-export" in p["skills"] for p in json.loads((ROOT / "chatgpt-home/runtime/profiles.json").read_text())["profiles"]))
        self.assertIn("TinyFish", registry["exclusions"][0])
        skills = json.loads((ROOT / "chatgpt-home/runtime/skills.index.json").read_text())
        self.assertEqual(len(skills["native_skills"]), 14)
        self.assertIn("github-research", skills["native_skills"])
        self.assertEqual(len(skills["skills"]), 33)
        agents = json.loads((ROOT / "chatgpt-home/runtime/agents.json").read_text())
        agent_ids = {a["id"] for a in agents["agents"]}
        reference_ids = {a["id"] for a in agents.get("reference_profiles", [])}
        self.assertEqual(len(reference_ids), 4)
        self.assertTrue({"factory-orchestrator", "harness-controller", "independent-reviewer", "worker-executor"}.issubset(reference_ids))
        self.assertFalse(reference_ids & agent_ids)
        self.assertTrue({"shadow", "watcher"}.issubset(agent_ids))
        self.assertFalse({"ghost", "openhands", "forge", "shadow-auditor"} & agent_ids)
        self.assertNotIn("shadow_provider_pool", adapters)
        self.assertEqual(
            agent_ids,
            {"blind-sniper", "researcher", "planner", "engineer", "reviewer", "qa-verifier", "recovery", "watcher", "shadow", "release-manager"},
        )
        contracts = {a["id"]: a.get("path") or a.get("native_contract_path") for a in agents["agents"]}
        self.assertEqual(contracts["watcher"], "chatgpt-home/agents/watcher.md")
        self.assertEqual(contracts["shadow"], "chatgpt-home/agents/shadow.md")
        workflows = json.loads((ROOT / "chatgpt-home/runtime/workflows.json").read_text())
        workflow_agents = {w["id"]: set(w.get("agents", [])) for w in workflows["workflows"]}
        self.assertIn("shadow", workflow_agents["independent-review"])
        self.assertIn("watcher", workflow_agents["recovery-and-reconciliation"])
        self.assertEqual(len(workflows["workflows"]), 18)
        workflow_adapters = {w["id"]: set(w.get("adapters", [])) for w in workflows["workflows"]}
        self.assertIn("native_model_runtime", workflow_adapters["native-model-agent-execution"])
        self.assertIn("agent_browser_cli", workflow_adapters["native-browser-interaction"])
        self.assertFalse(any({"forge_browser_mcp", "openhands_dispatch"} & used for used in workflow_adapters.values()))
        self.assertEqual(sum(w.get("contract_mode") == "native_contract" for w in workflows["workflows"]), 11)
        self.assertEqual(sum(w.get("contract_mode") == "registry_only" for w in workflows["workflows"]), 7)
        self.assertTrue(all(w.get("registry_only_reason") for w in workflows["workflows"] if w.get("contract_mode") == "registry_only"))

    def test_profiles_do_not_enable_unrestricted_sandbox(self):
        import json
        data = json.loads((ROOT / "chatgpt-home/runtime/profiles.json").read_text())
        for profile in data["profiles"]:
            self.assertNotIn("danger-full-access", profile["sandbox"])


if __name__ == "__main__":
    unittest.main()
