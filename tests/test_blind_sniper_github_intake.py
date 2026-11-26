"""Offline unit tests for GitHub issue intake."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from blind_sniper_daemon import PrivateTaskStore
from blind_sniper_github_intake import validate_issue_event, write_rejection, write_task

CONFIG = {"repository": "madnessgate44-debug/Blind-sniper-", "allowed_authors": ["trusted"],
          "agents": ["researcher"]}
TASK = {"task_id": "BS-GH-INTAKE-001", "agent_id": "researcher", "objective": "Review intake",
        "payload": {"case": "fixture"}, "require_tool_use": False}


def event(task=None, **changes):
    body = "```json\n" + json.dumps(task or TASK) + "\n```"
    result = {"action": "opened", "delivery_id": "delivery-1",
              "repository": {"full_name": CONFIG["repository"], "fork": False},
              "issue": {"number": 90, "state": "open", "user": {"login": "trusted"}, "body": body}}
    for key, value in changes.items():
        result[key] = value
    return result


class GitHubIntakeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.workspace = root / "repo"
        self.workspace.mkdir()
        self.state = root / "private-state"
        self.store = PrivateTaskStore(self.state, workspace_root=self.workspace)

    def intake(self, ev=None, task=None, number=90, delivery="delivery-1"):
        val = validate_issue_event(ev or event(task), CONFIG)
        self.assertEqual(val["outcome"], "accepted", val)
        return write_task(self.store.task_dir, val["task_envelope"], state_dir=self.state,
                          repository=val["repository"], issue_number=number, delivery_id=delivery)

    def test_valid_event_creates_one_exact_private_task_and_daemon_reads_it(self):
        with patch("blind_sniper_model_worker.ModelWorker.run", side_effect=AssertionError("model touched")), \
             patch("blind_sniper_tool_runtime.NativeToolRuntime.execute", side_effect=AssertionError("tool touched")):
            self.intake()
        paths = list(self.store.task_dir.glob("*.json"))
        self.assertEqual(len(paths), 1)
        self.assertEqual(json.loads(paths[0].read_text()), TASK)
        self.assertEqual(stat.S_IMODE(self.store.task_dir.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(paths[0].stat().st_mode), 0o600)
        self.assertEqual(self.store.read_task(paths[0]), TASK)

    def test_duplicate_delivery_is_idempotent(self):
        first = self.intake()
        edited = event()
        edited["action"] = "edited"
        second_result = validate_issue_event(edited, CONFIG)
        second = write_task(self.store.task_dir, second_result["task_envelope"], state_dir=self.state,
                            repository=second_result["repository"], issue_number=90, delivery_id="delivery-1")
        self.assertEqual(first["payload_digest"], second["payload_digest"])
        self.assertEqual(len(list(self.store.task_dir.glob("*.json"))), 1)

    def test_changed_payload_rejected_without_overwrite(self):
        self.intake()
        changed = dict(TASK, payload={"case": "changed"})
        receipt = write_task(self.store.task_dir, changed, state_dir=self.state,
                             repository=CONFIG["repository"], issue_number=90, delivery_id="delivery-2")
        self.assertEqual(receipt["outcome"], "rejected")
        self.assertEqual(json.loads(next(self.store.task_dir.glob("*.json")).read_text()), TASK)

    def test_task_id_collision_with_another_issue(self):
        self.intake()
        receipt = write_task(self.store.task_dir, TASK, state_dir=self.state,
                             repository=CONFIG["repository"], issue_number=91, delivery_id="delivery-2")
        self.assertEqual(receipt["reason_code"], "task_id_collision")

    def test_rejects_event_variants_and_bad_templates(self):
        cases = []
        e = event(); e["issue"]["pull_request"] = {}; cases.append((e, "pull_request"))
        e = event(); e["repository"]["fork"] = True; cases.append((e, "fork_repository"))
        e = event(); e["issue"]["user"]["login"] = "other"; cases.append((e, "untrusted_author"))
        e = event(); e["issue"]["state"] = "closed"; cases.append((e, "closed_issue"))
        e = event(); e["action"] = "created"; cases.append((e, "unsupported_action"))
        e = event(); e["issue"]["body"] = "```json\n{}\n```"; cases.append((e, "missing_fields"))
        e = event(dict(TASK, tool_allowlist=[])); cases.append((e, "unknown_keys"))
        e = event(); e["issue"]["body"] = "x" * (16 * 1024 + 1); cases.append((e, "body_too_large"))
        e = event(); e["issue"]["body"] = "```json\n{bad}\n```"; cases.append((e, "invalid_json"))
        e = event(dict(TASK, agent_id="unknown")); cases.append((e, "unknown_agent"))
        e = event(dict(TASK, payload={"x": "a" * 9000})); cases.append((e, "invalid_payload"))
        e = event(dict(TASK, browser_approval_reference="no")); cases.append((e, "unknown_keys"))
        e = event(dict(TASK, task_id="bad/id")); cases.append((e, "invalid_task_id"))
        e = event(); del e["repository"]; cases.append((e, "repository_mismatch"))
        for ev, reason in cases:
            with self.subTest(reason=reason):
                self.assertEqual(validate_issue_event(ev, CONFIG)["reason_code"], reason)

    def test_receipt_has_no_body_or_payload(self):
        receipt = self.intake()
        files = list((self.state / "intake" / "receipts").glob("90-*.json"))
        self.assertEqual(len(files), 1)
        path = files[0]
        raw = path.read_text()
        self.assertEqual(json.loads(raw), receipt)
        self.assertNotIn("fixture", raw)
        self.assertNotIn("Review intake", raw)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(receipt["payload_digest"], hashlib.sha256(json.dumps(TASK, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest())

    def test_rejection_receipt_keeps_reason_and_writes_no_task(self):
        ev = event(); ev["issue"]["user"]["login"] = "other"
        result = validate_issue_event(ev, CONFIG)
        receipt = write_rejection(self.state, result)
        self.assertEqual((receipt["outcome"], receipt["reason_code"]), ("rejected", "untrusted_author"))
        self.assertEqual(list(self.store.task_dir.glob("*.json")), [])

    def test_later_rejection_does_not_replace_acceptance_receipt(self):
        self.intake()
        write_task(self.store.task_dir, dict(TASK, payload={"case": "changed"}), state_dir=self.state,
                   repository=CONFIG["repository"], issue_number=90, delivery_id="delivery-2")
        outcomes = sorted(json.loads(p.read_text())["outcome"] for p in (self.state / "intake" / "receipts").glob("*.json"))
        self.assertEqual(outcomes, ["accepted", "rejected"])

    def test_hostile_issue_number_cannot_escape_receipt_dir(self):
        ev = event(); ev["issue"]["number"] = "../../escape"
        result = validate_issue_event(ev, CONFIG)
        self.assertEqual(result["outcome"], "rejected")
        write_rejection(self.state, result)
        self.assertFalse((self.state.parent / "escape.json").exists())
        self.assertFalse(any(p.name.startswith("..") for p in self.state.rglob("*")))
        with self.assertRaises(ValueError):
            write_task(self.store.task_dir, TASK, state_dir=self.state, repository="r", issue_number="../x")

    def test_cli_accept_then_replay_then_reject_exit_codes_and_no_body_in_output(self):
        import subprocess
        root = Path(self.tmp.name)
        cfg = root / "cfg.json"; cfg.write_text(json.dumps(CONFIG))
        def run(ev):
            p = root / "ev.json"; p.write_text(json.dumps(ev))
            return subprocess.run([sys.executable, str(ROOT / "scripts" / "blind_sniper_github_intake.py"),
                                   "--event-path", str(p), "--config-path", str(cfg), "--state-dir", str(self.state)],
                                  capture_output=True, text=True)
        first = run(event())
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(run(event()).returncode, 0)
        self.assertEqual(len(list(self.store.task_dir.glob("*.json"))), 1)
        bad = event(); bad["issue"]["user"]["login"] = "other"
        rejected = run(bad)
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("untrusted_author", rejected.stdout)
        for out in (first.stdout, rejected.stdout, first.stderr, rejected.stderr):
            self.assertNotIn("Review intake", out)
            self.assertNotIn("fixture", out)

    def test_symlinked_task_store_is_refused(self):
        real = Path(self.tmp.name) / "elsewhere"; real.mkdir()
        link = Path(self.tmp.name) / "link"; link.symlink_to(real)
        val = validate_issue_event(event(), CONFIG)
        receipt = write_task(link, val["task_envelope"], state_dir=self.state, repository=val["repository"],
                             issue_number=90, delivery_id="d")
        self.assertEqual(receipt["reason_code"], "invalid_task_store")
        self.assertEqual(list(real.iterdir()), [])

    def test_concurrent_identical_deliveries_create_one_task_and_all_succeed(self):
        import threading
        val = validate_issue_event(event(), CONFIG)
        results, errors = [], []
        barrier = threading.Barrier(8)
        def go(i):
            try:
                barrier.wait()
                results.append(write_task(self.store.task_dir, val["task_envelope"], state_dir=self.state,
                                          repository=val["repository"], issue_number=90, delivery_id=f"d{i}"))
            except Exception as exc:  # pragma: no cover
                errors.append(exc)
        threads = [threading.Thread(target=go, args=(i,)) for i in range(8)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(errors, [])
        self.assertEqual(len(list(self.store.task_dir.glob("*.json"))), 1)
        self.assertEqual({r["outcome"] for r in results}, {"accepted"})
        self.assertEqual(sorted(r["reason_code"] for r in results).count("accepted"), 1)


if __name__ == "__main__":
    unittest.main()
