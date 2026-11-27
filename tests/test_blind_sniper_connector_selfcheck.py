import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import blind_sniper_connector_selfcheck as sc
from scripts.blind_sniper_native_connectors import FilesConnector


def by_name(out):
    return {c["check"]: c for c in out["checks"]}


class TestSelfCheck(unittest.TestCase):
    def test_offline_run_is_incomplete_never_pass(self):
        out = sc.run(ROOT, "o/r", live_public=False)
        c = by_name(out)
        self.assertEqual(out["overall"], "incomplete")
        self.assertEqual(c["files.list_dir"]["status"], "pass")
        self.assertEqual(c["files.read_file"]["status"], "pass")
        self.assertEqual(c["github.pr_status"]["status"], "skipped")
        self.assertEqual(c["terminal.run_command"]["status"], "skipped")
        self.assertEqual(c["authenticated_integration"]["status"], "unverified")
        for g in ("git.status", "git.log"):
            self.assertEqual(c[g]["status"], "pass")

    def test_receipts_are_redacted(self):
        text = json.dumps(sc.run(ROOT, "o/r", live_public=False))
        for snippet in ((ROOT / "README.md").read_text()[:60], str(ROOT)):
            self.assertNotIn(snippet, text)

    def test_failure_is_reported_as_fail_without_message_text(self):
        r = sc._check("x", FilesConnector(ROOT), "read_file", {"path": "no/such/file.txt"},
                      lambda r: True)
        self.assertEqual(r["status"], "fail")
        self.assertNotIn("no/such", json.dumps(r))

    def test_failed_check_makes_overall_fail_and_exit_nonzero(self):
        orig = sc._check
        try:
            sc._check = lambda *a, **k: {"check": "forced", "status": "fail"}
            self.assertEqual(sc.run(ROOT, "o/r", False)["overall"], "fail")
        finally:
            sc._check = orig

    def test_exception_is_reported_by_class_only(self):
        class Bad:
            connector_id = "files"
            def tools(self):
                raise RuntimeError("SECRET-token-123")
        r = sc._check("x", Bad(), "list_dir", {}, lambda r: True)
        self.assertEqual(r, {"check": "x", "status": "fail", "error": "RuntimeError"})

    def test_passing_check_requires_the_predicate(self):
        r = sc._check("x", FilesConnector(ROOT), "list_dir", {"path": "."}, lambda r: False)
        self.assertEqual(r["status"], "fail")


if __name__ == "__main__":
    unittest.main()
