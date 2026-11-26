"""Offline tests for GitHub issue intake: trust boundary, transactional persistence, idempotency."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import blind_sniper_github_intake as intake
from blind_sniper_daemon import PrivateTaskStore
from blind_sniper_github_intake import (process_delivery, validate_issue_event, verify_signature,
                                        write_rejection, write_task)

REPO = "madnessgate44-debug/Blind-sniper-"
SECRET = "unit-test-webhook-secret-not-real"
CONFIG = {"repository": REPO, "allowed_authors": ["trusted"], "agents": ["researcher"],
          "webhook_secret_env": "BS_TEST_WEBHOOK_SECRET"}
ENV = {"BS_TEST_WEBHOOK_SECRET": SECRET}
TASK = {"task_id": "BS-GH-INTAKE-001", "agent_id": "researcher", "objective": "Review intake",
        "payload": {"case": "fixture"}, "require_tool_use": False}


def event(task=None, **changes):
    body = "```json\n" + json.dumps(task or TASK) + "\n```"
    result = {"action": "opened", "repository": {"full_name": REPO, "fork": False},
              "issue": {"number": 90, "state": "open", "user": {"login": "trusted"}, "body": body}}
    result.update(changes)
    return result


def sign(raw: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def deliver(state, ev, delivery="delivery-1", signature=None, config=CONFIG, env=ENV):
    raw = json.dumps(ev).encode()
    return process_delivery(raw, delivery_id=delivery, signature=sign(raw) if signature is None else signature,
                            config=config, state_dir=state, env=env)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        (root / "repo").mkdir()
        self.state = root / "private-state"
        self.store = PrivateTaskStore(self.state, workspace_root=root / "repo")

    def tasks(self):
        return sorted(self.store.task_dir.glob("*.json"))

    def receipts(self):
        return [json.loads(p.read_text()) for p in sorted((self.state / "intake" / "receipts").glob("*.json"))]


class TrustBoundaryTests(Base):
    def test_valid_signed_delivery_creates_one_exact_private_task_and_daemon_reads_it(self):
        with patch("blind_sniper_model_worker.ModelWorker.run", side_effect=AssertionError("model touched")), \
             patch("blind_sniper_tool_runtime.NativeToolRuntime.execute", side_effect=AssertionError("tool touched")):
            receipt = deliver(self.state, event())
        self.assertEqual((receipt["outcome"], receipt["reason_code"]), ("accepted", "accepted"))
        paths = self.tasks()
        self.assertEqual(len(paths), 1)
        self.assertEqual(json.loads(paths[0].read_text()), TASK)
        self.assertEqual(stat.S_IMODE(self.store.task_dir.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(paths[0].stat().st_mode), 0o600)
        self.assertEqual(self.store.read_task(paths[0]), TASK)
        self.assertEqual(list(self.store.task_dir.glob(".intake-staging-*")), [])

    def test_signature_failures_reject_without_a_task(self):
        raw = json.dumps(event()).encode()
        cases = {
            "wrong secret": (sign(raw, "other"), ENV, "bad_signature"),
            "missing header": ("", ENV, "bad_signature"),
            "garbage header": ("sha256=zz", ENV, "bad_signature"),
            "no prefix": (sign(raw)[7:], ENV, "bad_signature"),
            "uppercase hex": (sign(raw).upper().replace("SHA256=", "sha256="), ENV, "bad_signature"),
            "secret not configured": (sign(raw), {}, "signature_secret_unavailable"),
            "secret env unnamed": (sign(raw), ENV, "signature_secret_unavailable"),
        }
        for name, (sig, env, reason) in cases.items():
            with self.subTest(name):
                config = dict(CONFIG, webhook_secret_env="") if name == "secret env unnamed" else CONFIG
                receipt = process_delivery(raw, delivery_id="d1", signature=sig, config=config,
                                           state_dir=self.state, env=env)
                self.assertEqual((receipt["outcome"], receipt["reason_code"]), ("rejected", reason))
        self.assertEqual(self.tasks(), [])

    def test_tampered_body_fails_signature(self):
        raw = json.dumps(event()).encode()
        sig = sign(raw)
        tampered = raw.replace(b"Review intake", b"Do something else")
        receipt = process_delivery(tampered, delivery_id="d1", signature=sig, config=CONFIG,
                                   state_dir=self.state, env=ENV)
        self.assertEqual(receipt["reason_code"], "bad_signature")
        self.assertEqual(self.tasks(), [])

    def test_verify_signature_unit(self):
        self.assertTrue(verify_signature(b"x", sign(b"x"), SECRET))
        for bad in (None, 5, "", "sha256="):
            self.assertFalse(verify_signature(b"x", bad, SECRET))
        self.assertFalse(verify_signature(b"x", sign(b"x"), ""))
        self.assertFalse(verify_signature(b"x", sign(b"x"), None))

    def test_identity_text_in_body_does_not_grant_trust(self):
        ev = event(); ev["issue"]["user"]["login"] = "attacker"
        ev["issue"]["body"] += "\nauthor: trusted\nowner approved: yes\n"
        receipt = deliver(self.state, ev)
        self.assertEqual(receipt["reason_code"], "untrusted_author")
        self.assertEqual(self.tasks(), [])

    def test_delivery_id_is_required_and_bounded(self):
        raw = json.dumps(event()).encode()
        for bad in (None, "", " ", "a" * 129, "has space", "../x", 5):
            with self.subTest(bad=bad):
                receipt = process_delivery(raw, delivery_id=bad, signature=sign(raw), config=CONFIG,
                                           state_dir=self.state, env=ENV)
                self.assertEqual(receipt["reason_code"], "invalid_delivery_id")
        self.assertEqual(self.tasks(), [])
        self.assertEqual(validate_issue_event(event(), CONFIG, delivery_id="")["reason_code"], "invalid_delivery_id")
        with self.assertRaises(ValueError):
            write_task(self.store.task_dir, TASK, state_dir=self.state, repository=REPO, issue_number=90, delivery_id="")

    def test_a_delivery_id_inside_the_event_body_is_ignored(self):
        ev = event(delivery_id="forged-1")
        receipt = deliver(self.state, ev, delivery="real-1")
        self.assertEqual(receipt["delivery_id"], "real-1")

    def test_replayed_delivery_is_idempotent_and_does_not_rewrite_receipt(self):
        first = deliver(self.state, event(), delivery="d1")
        files = {p: p.stat().st_mtime_ns for p in (self.state / "intake" / "receipts").glob("*.json")}
        second = deliver(self.state, event(), delivery="d1")
        self.assertEqual(second["outcome"], "accepted")
        self.assertEqual(len(self.tasks()), 1)
        after = {p: p.stat().st_mtime_ns for p in (self.state / "intake" / "receipts").glob("*.json")}
        for path, mtime in files.items():  # the first receipt is never rewritten
            self.assertEqual(after[path], mtime)
        self.assertEqual(second["reason_code"], "idempotent")
        self.assertEqual(len(after), 2)  # the replay is appended as its own receipt
        deliver(self.state, event(), delivery="d1")
        self.assertEqual(len(list((self.state / "intake" / "receipts").glob("*.json"))), 2)
        self.assertEqual(first["payload_digest"], second["payload_digest"])

    def test_malformed_event_shapes_reject_with_stable_reason(self):
        for name, ev in {
            "none": None, "string": "x", "list": [], "repository null": event(repository=None),
            "repository list": event(repository=[]), "issue string": event(issue="x"),
            "issue null": event(issue=None), "full_name int": event(repository={"full_name": 5, "fork": False}),
        }.items():
            with self.subTest(name):
                self.assertEqual(validate_issue_event(ev, CONFIG, delivery_id="d1")["reason_code"], "malformed_event")
        for name, change in {"user null": None, "user string": "x", "user list": []}.items():
            with self.subTest(name):
                ev = event(); ev["issue"]["user"] = change
                self.assertEqual(validate_issue_event(ev, CONFIG, delivery_id="d1")["reason_code"], "untrusted_author")
        for bad in (None, "x", [], {"repository": REPO}):
            with self.subTest(config=bad):
                self.assertIn(validate_issue_event(event(), bad, delivery_id="d1")["outcome"], ("rejected",))
        raw = b"\xff\xfe not json"
        receipt = process_delivery(raw, delivery_id="d1", signature=sign(raw), config=CONFIG,
                                   state_dir=self.state, env=ENV)
        self.assertEqual(receipt["reason_code"], "malformed_event")

    def test_rejects_event_variants_and_bad_templates(self):
        cases = []
        e = event(); e["issue"]["pull_request"] = {}; cases.append((e, "pull_request"))
        e = event(); e["repository"]["fork"] = True; cases.append((e, "fork_repository"))
        e = event(); e["repository"].pop("fork"); cases.append((e, "fork_repository"))
        e = event(); e["issue"]["user"]["login"] = "other"; cases.append((e, "untrusted_author"))
        e = event(); e["issue"]["state"] = "closed"; cases.append((e, "closed_issue"))
        e = event(); e["issue"].pop("state"); cases.append((e, "closed_issue"))
        e = event(); e["action"] = "created"; cases.append((e, "unsupported_action"))
        e = event(); e["repository"]["full_name"] = "someone/else"; cases.append((e, "repository_mismatch"))
        e = event(); e["issue"]["body"] = "```json\n{}\n```"; cases.append((e, "missing_fields"))
        e = event(dict(TASK, tool_allowlist=[])); cases.append((e, "unknown_keys"))
        e = event(dict(TASK, allowed_paths=["/"])); cases.append((e, "unknown_keys"))
        e = event(dict(TASK, browser_approval_reference="no")); cases.append((e, "unknown_keys"))
        e = event(); e["issue"]["body"] = "x" * (16 * 1024 + 1); cases.append((e, "body_too_large"))
        e = event(); e["issue"]["body"] = "```json\n{bad}\n```"; cases.append((e, "invalid_json"))
        e = event(); e["issue"]["body"] = "no template here"; cases.append((e, "missing_template"))
        e = event(dict(TASK, agent_id="unknown")); cases.append((e, "unknown_agent"))
        e = event(dict(TASK, payload={"x": "a" * 9000})); cases.append((e, "invalid_payload"))
        e = event(dict(TASK, task_id="bad/id")); cases.append((e, "invalid_task_id"))
        e = event(dict(TASK, require_tool_use="yes")); cases.append((e, "invalid_require_tool_use"))
        for ev, reason in cases:
            with self.subTest(reason=reason):
                self.assertEqual(validate_issue_event(ev, CONFIG, delivery_id="d1")["reason_code"], reason)


class PersistenceTests(Base):
    def publish(self, task=None, issue=90, delivery="d1"):
        return write_task(self.store.task_dir, task or TASK, state_dir=self.state, repository=REPO,
                          issue_number=issue, delivery_id=delivery)

    def test_changed_payload_rejected_without_overwrite(self):
        self.publish()
        receipt = self.publish(dict(TASK, payload={"case": "changed"}), delivery="d2")
        self.assertEqual((receipt["outcome"], receipt["reason_code"]), ("rejected", "changed_payload"))
        self.assertEqual(json.loads(self.tasks()[0].read_text()), TASK)

    def test_task_id_collision_with_another_issue(self):
        self.publish()
        receipt = self.publish(issue=91, delivery="d2")
        self.assertEqual(receipt["reason_code"], "task_id_collision")
        self.assertEqual(len(self.tasks()), 1)
        index_files = list((self.state / "intake" / "index").glob("*.json"))
        self.assertEqual(len(index_files), 1)  # the colliding issue left no index behind

    def test_index_write_failure_leaves_no_visible_task(self):
        real = intake._exclusive_json
        def fail_on_index(path, value):
            if "index" in str(path):
                raise OSError("injected index failure")
            return real(path, value)
        with patch.object(intake, "_exclusive_json", side_effect=fail_on_index):
            receipt = self.publish()
        self.assertEqual(receipt["outcome"], "rejected")
        self.assertEqual(self.tasks(), [])
        self.assertEqual(list(self.store.task_dir.glob(".intake-staging-*")), [])
        self.assertEqual(list((self.state / "intake" / "index").glob("*.json")), [])
        retry = self.publish(delivery="d2")
        self.assertEqual(retry["outcome"], "accepted")
        self.assertEqual(len(self.tasks()), 1)

    def test_publish_link_failure_rolls_back_index_and_task(self):
        with patch.object(intake.os, "link", side_effect=OSError("injected link failure")):
            receipt = self.publish()
        self.assertEqual(receipt["outcome"], "rejected")
        self.assertEqual(self.tasks(), [])
        self.assertEqual(list((self.state / "intake" / "index").glob("*.json")), [])
        self.assertEqual(self.publish(delivery="d2")["outcome"], "accepted")

    def test_interruption_after_index_before_commit_leaves_nothing_the_daemon_reads(self):
        with patch.object(intake.os, "link", side_effect=KeyboardInterrupt()):
            with self.assertRaises(KeyboardInterrupt):
                self.publish()
        self.assertEqual(self.tasks(), [])
        self.assertEqual(list((self.state / "intake" / "index").glob("*.json")), [])
        self.assertEqual(self.publish(delivery="d2")["outcome"], "accepted")

    def test_stale_staging_file_is_never_a_task_and_is_swept(self):
        leftover = self.store.task_dir / ".intake-staging-999-BS-GH-INTAKE-001"
        leftover.write_text("{}")
        self.assertEqual(self.tasks(), [])
        self.publish()
        self.assertFalse(leftover.exists())
        self.assertEqual(len(self.tasks()), 1)

    def test_receipt_write_failure_after_commit_keeps_task_and_replay_heals(self):
        real = intake._write_receipt
        with patch.object(intake, "_write_receipt", side_effect=OSError("injected receipt failure")):
            with self.assertRaises(OSError):
                self.publish()
        self.assertEqual(len(self.tasks()), 1)   # committed: the index and task agree
        self.assertEqual(self.receipts(), [])
        healed = self.publish(delivery="d1")
        self.assertEqual((healed["outcome"], healed["reason_code"]), ("accepted", "idempotent"))
        self.assertEqual(len(self.receipts()), 1)
        self.assertEqual(len(self.tasks()), 1)

    def test_receipts_are_exclusive_and_never_replace_each_other(self):
        self.publish()
        self.publish(dict(TASK, payload={"case": "changed"}), delivery="d2")
        outcomes = sorted(r["outcome"] for r in self.receipts())
        self.assertEqual(outcomes, ["accepted", "rejected"])
        path = next((self.state / "intake" / "receipts").glob("*.json"))
        before = path.read_text()
        intake._write_receipt(path.parent, dict(json.loads(before), timestamp="changed"))
        self.assertEqual(path.read_text(), before)

    def test_receipt_has_no_body_or_payload_and_is_private(self):
        self.publish()
        path = next((self.state / "intake" / "receipts").glob("90-*.json"))
        raw = path.read_text()
        for needle in ("fixture", "Review intake"):
            self.assertNotIn(needle, raw)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(json.loads(raw)["payload_digest"],
                         hashlib.sha256(json.dumps(TASK, ensure_ascii=False, sort_keys=True,
                                                   separators=(",", ":")).encode()).hexdigest())

    def test_rejection_receipt_keeps_reason_and_writes_no_task(self):
        ev = event(); ev["issue"]["user"]["login"] = "other"
        receipt = write_rejection(self.state, validate_issue_event(ev, CONFIG, delivery_id="d1"))
        self.assertEqual((receipt["outcome"], receipt["reason_code"]), ("rejected", "untrusted_author"))
        self.assertEqual(self.tasks(), [])

    def test_hostile_issue_number_cannot_escape_receipt_dir(self):
        ev = event(); ev["issue"]["number"] = "../../escape"
        result = validate_issue_event(ev, CONFIG, delivery_id="d1")
        self.assertEqual(result["outcome"], "rejected")
        write_rejection(self.state, result)
        self.assertFalse((self.state.parent / "escape.json").exists())
        with self.assertRaises(ValueError):
            write_task(self.store.task_dir, TASK, state_dir=self.state, repository="r", issue_number="../x",
                       delivery_id="d1")

    def test_symlinked_task_store_is_refused(self):
        real = Path(self.tmp.name) / "elsewhere"; real.mkdir()
        link = Path(self.tmp.name) / "link"; link.symlink_to(real)
        receipt = write_task(link, TASK, state_dir=self.state, repository=REPO, issue_number=90, delivery_id="d1")
        self.assertEqual(receipt["reason_code"], "invalid_task_store")
        self.assertEqual(list(real.iterdir()), [])

    def test_thread_contention_on_one_host_yields_one_task(self):
        results, errors = [], []
        barrier = threading.Barrier(8)
        def go(i):
            try:
                barrier.wait()
                results.append(self.publish(delivery=f"d{i}"))
            except Exception as exc:  # pragma: no cover
                errors.append(exc)
        threads = [threading.Thread(target=go, args=(i,)) for i in range(8)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(errors, [])
        self.assertEqual(len(self.tasks()), 1)
        self.assertEqual(sorted(r["reason_code"] for r in results).count("accepted"), 1)
        self.assertEqual({r["outcome"] for r in results}, {"accepted"})


class CliAndProcessTests(Base):
    def run_cli(self, raw: bytes, delivery="d1", signature=None, env_secret=SECRET, name="ev.json"):
        root = Path(self.tmp.name)
        cfg = root / "cfg.json"; cfg.write_text(json.dumps(CONFIG))
        ev = root / name; ev.write_bytes(raw)
        env = {k: v for k, v in os.environ.items() if k != "BS_TEST_WEBHOOK_SECRET"}
        if env_secret is not None:
            env["BS_TEST_WEBHOOK_SECRET"] = env_secret
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "blind_sniper_github_intake.py"), "--event-path", str(ev),
             "--delivery-id", delivery, "--signature", sign(raw) if signature is None else signature,
             "--config-path", str(cfg), "--state-dir", str(self.state)],
            capture_output=True, text=True, env=env)

    def test_cli_accept_replay_reject_and_no_body_in_output(self):
        raw = json.dumps(event()).encode()
        first = self.run_cli(raw)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(self.run_cli(raw).returncode, 0)
        self.assertEqual(len(self.tasks()), 1)
        bad = self.run_cli(raw, signature="sha256=" + "0" * 64, delivery="d2")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("bad_signature", bad.stdout)
        nosecret = self.run_cli(raw, env_secret=None, delivery="d3")
        self.assertEqual(nosecret.returncode, 1)
        self.assertIn("signature_secret_unavailable", nosecret.stdout)
        for out in (first.stdout, bad.stdout, nosecret.stdout, first.stderr, bad.stderr, nosecret.stderr):
            for needle in ("Review intake", "fixture", SECRET):
                self.assertNotIn(needle, out)

    def test_separate_processes_contend_and_yield_one_task(self):
        raw = json.dumps(event()).encode()
        root = Path(self.tmp.name)
        cfg = root / "cfg.json"; cfg.write_text(json.dumps(CONFIG))
        ev = root / "ev.json"; ev.write_bytes(raw)
        env = dict(os.environ, BS_TEST_WEBHOOK_SECRET=SECRET)
        go = root / "go"
        script = ("import sys,time,os\n"
                  "while not os.path.exists(sys.argv[1]): time.sleep(0.002)\n"
                  "sys.argv=['x']+sys.argv[2:]\n"
                  f"sys.path.insert(0,{str(ROOT / 'scripts')!r})\n"
                  "import blind_sniper_github_intake as m\n"
                  "raise SystemExit(m.main())\n")
        procs = []
        for i in range(6):
            procs.append(subprocess.Popen(
                [sys.executable, "-c", script, str(go), "--event-path", str(ev), "--delivery-id", f"p{i}",
                 "--signature", sign(raw), "--config-path", str(cfg), "--state-dir", str(self.state)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env))
        go.write_text("go")
        outs = [(p.wait(timeout=60), p.stdout.read(), p.stderr.read()) for p in procs]
        self.assertTrue(all(code == 0 for code, _, _ in outs), outs)
        self.assertEqual(len(self.tasks()), 1)
        reasons = sorted(json.loads(o)["reason_code"] for _, o, _ in outs)
        self.assertEqual(reasons.count("accepted"), 1)
        self.assertEqual(reasons.count("idempotent"), 5)
        self.assertEqual(list(self.store.task_dir.glob(".intake-staging-*")), [])


if __name__ == "__main__":
    unittest.main()
