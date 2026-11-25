import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "blind-sniper-daemon-once-smoke.yml"


class DaemonOnceSmokeTests(unittest.TestCase):
    def test_workflow_is_manual_secretless_and_uploads_only_aggregate_health(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        for forbidden in ("schedule:", "cron:", "pull_request", "push:", "secrets.", "id-token", "contents: write"):
            self.assertNotIn(forbidden, text)
        self.assertIn("contents: read", text)
        self.assertIn("path: artifacts/daemon-once-smoke/daemon-once-smoke.json", text)
        paths = [l.strip() for l in text.splitlines() if l.strip().startswith("path:")]
        self.assertEqual(paths, ["path: artifacts/daemon-once-smoke/daemon-once-smoke.json"])

    def test_smoke_completes_one_synthetic_task_and_writes_aggregate_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "run_blind_sniper_daemon_once_smoke.py"), "--output-dir", tmp],
                capture_output=True, text=True, timeout=120,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            files = sorted(p.name for p in Path(tmp).iterdir())
            self.assertEqual(files, ["daemon-once-smoke.json"])
            data = json.loads((Path(tmp) / "daemon-once-smoke.json").read_text(encoding="utf-8"))
            self.assertEqual(data["status"], "HEALTHY")
            self.assertEqual(data["counts"]["completed"], 1)
            self.assertNotIn("STUB-OK", json.dumps(data))
            self.assertNotIn("SMOKE-1", json.dumps(data))


if __name__ == "__main__":
    unittest.main()
