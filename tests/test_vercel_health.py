"""Contract tests for the read-only Vercel health endpoint."""
import json
import tomllib
import unittest
from pathlib import Path

from api.health import health_payload


class VercelHealthTests(unittest.TestCase):
    def test_vercel_python_entrypoint_is_explicit_and_resolvable(self):
        root = Path(__file__).resolve().parents[1]
        config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(config["tool"]["vercel"]["entrypoint"], "api.health:handler")
        self.assertTrue((root / "api" / "health.py").is_file())

    def test_reports_only_the_host_capability(self):
        payload = health_payload()
        self.assertEqual(payload["service"], "blind-sniper")
        self.assertEqual(payload["component"], "vercel-http-host")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["execution_mode"], "event-driven")
        self.assertEqual(payload["worker"], "not_activated")
        self.assertIs(payload["task_execution_enabled"], False)

    def test_explains_the_closed_execution_gate(self):
        payload = health_payload()
        self.assertIn("private durable storage", payload["reason"])
        self.assertIn("model provider", payload["reason"])

    def test_payload_is_json_serializable(self):
        self.assertIsInstance(json.loads(json.dumps(health_payload())), dict)


if __name__ == "__main__":
    unittest.main()
