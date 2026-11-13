from __future__ import annotations

import json
import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from subprocess import CompletedProcess
from pathlib import Path
from unittest.mock import patch

from scripts.blind_sniper_browser import BrowserAdapter, BrowserAdapterError, BrowserPolicyError, validate_url, main, redact_url_for_receipt


class BrowserPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {
            "BLIND_SNIPER_BROWSER_ALLOWED_DOMAINS": "127.0.0.1,example.test",
            "BLIND_SNIPER_BROWSER_BLOCKED_DOMAINS": "blocked.example.test",
            "BLIND_SNIPER_BROWSER_WRITE_APPROVED": "0",
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def adapter(self, **kwargs):
        return BrowserAdapter(
            task_id="BS-TEST-001", run_id="run-001", session_id="test_session",
            state_dir=Path(self.temp.name) / "state",
            binary="missing-agent-browser", **kwargs,
        )

    def test_allowlist_and_blocklist(self):
        self.assertEqual(validate_url("http://127.0.0.1:8080/"), "127.0.0.1")
        with self.assertRaises(BrowserPolicyError):
            validate_url("https://not-allowed.example/")
        with self.assertRaises(BrowserPolicyError):
            validate_url("https://blocked.example.test/")

    def test_non_http_scheme_is_rejected(self):
        with self.assertRaises(BrowserPolicyError):
            validate_url("file:///etc/passwd")

    def test_wildcard_domain_rule_covers_subdomains(self):
        with patch.dict(os.environ, {"BLIND_SNIPER_BROWSER_ALLOWED_DOMAINS": "*.example.test"}):
            self.assertEqual(validate_url("https://app.example.test/"), "app.example.test")
            self.assertEqual(validate_url("https://example.test/"), "example.test")

    def test_embedded_url_credentials_are_rejected(self):
        with self.assertRaises(BrowserPolicyError):
            validate_url("https://user:secret@example.test/")

    def test_mutating_action_requires_host_approval(self):
        adapter = self.adapter()
        adapter.state["current_url"] = "http://127.0.0.1/"
        with self.assertRaises(BrowserPolicyError):
            adapter.execute("click", "step-1", "#submit")

    def test_sensitive_selector_is_rejected(self):
        with patch.dict(os.environ, {"BLIND_SNIPER_BROWSER_WRITE_APPROVED": "1"}):
            adapter = self.adapter(approval_reference="CI-APPROVED")
            adapter.state["current_url"] = "http://127.0.0.1/"
            with self.assertRaises(BrowserPolicyError):
                adapter.execute("fill", "step-1", 'input[name="password"]', "secret")

    def test_session_cannot_be_reused_across_tasks(self):
        adapter = self.adapter()
        adapter.state["task_id"] = "OTHER-TASK"
        adapter._save_state()
        with self.assertRaises(BrowserPolicyError):
            BrowserAdapter(
                task_id="BS-TEST-001", run_id="run-001", session_id="test_session",
                state_dir=Path(self.temp.name) / "state", binary="missing-agent-browser",
            )

    def test_duplicate_step_receipt_is_rejected(self):
        adapter = self.adapter()
        adapter.receipt_file.parent.mkdir(parents=True, exist_ok=True)
        adapter.receipt_file.write_text(json.dumps({"step_id": "step-1"}) + "\n", encoding="utf-8")
        with self.assertRaises(BrowserPolicyError):
            adapter._append_receipt({"step_id": "step-1"})

    def test_persistent_profile_uses_private_profile_without_cli_domain_replay(self):
        adapter = self.adapter()
        with patch.dict(os.environ, {"BLIND_SNIPER_BROWSER_PERSISTENT_PROFILE": "1"}):
            with patch("scripts.blind_sniper_browser.subprocess.run", return_value=CompletedProcess([], 0, "{}", "")) as run:
                adapter._command("open", "http://127.0.0.1/")
        command = run.call_args.args[0]
        self.assertIn("--profile", command)
        self.assertNotIn("--allowed-domains", command)
        profile = Path(command[command.index("--profile") + 1])
        self.assertEqual(profile, adapter.profiles_dir / adapter.session_id)

    def test_ensure_page_restored_reopens_saved_url_after_blank_page(self):
        adapter = self.adapter()
        restore_url = "http://127.0.0.1/saved?query=private"
        adapter.state["restore_url"] = restore_url
        adapter.state["current_url"] = "http://127.0.0.1/[REDACTED]"
        with patch.object(adapter, "_current_url", side_effect=["about:blank", restore_url]):
            with patch.object(adapter, "_command", return_value=(0, "{}", "", [])) as command:
                adapter._ensure_page_restored()
        command.assert_called_once_with("open", restore_url)
        self.assertEqual(adapter.state["restore_url"], restore_url)
        self.assertEqual(adapter.state["current_url"], redact_url_for_receipt(restore_url))

    def test_action_policy_is_deny_by_default(self):
        adapter = self.adapter()
        policy = json.loads(adapter.policy_file.read_text(encoding="utf-8"))
        self.assertEqual(policy["default"], "deny")
        self.assertNotIn("eval", policy["allow"])
        self.assertIn("upload", policy["allow"])
        self.assertIn("download", policy["allow"])
        self.assertIn("close", policy["allow"])
        self.assertIn("url", policy["allow"])

    def test_engine_command_enforces_domain_and_content_boundaries(self):
        adapter = self.adapter()
        with patch.dict(os.environ, {"AGENT_BROWSER_EXECUTABLE_PATH": "/usr/bin/chromium"}):
            with patch("scripts.blind_sniper_browser.subprocess.run", return_value=CompletedProcess([], 0, "{}", "")) as run:
                adapter._command("open", "http://127.0.0.1/")
        command = run.call_args.args[0]
        self.assertEqual(command[1:3], ["--executable-path", "/usr/bin/chromium"])
        self.assertIn("--allowed-domains", command)
        self.assertIn("--restore", command)
        self.assertIn("--action-policy", command)
        self.assertIn("--content-boundaries", command)
        self.assertIn("127.0.0.1,example.test", command)
        self.assertFalse(run.call_args.kwargs["shell"])

    def test_browser_command_never_uses_shell(self):
        adapter = self.adapter()
        with self.assertRaises(BrowserAdapterError):
            adapter._command("open", "http://127.0.0.1/")


    def test_url_receipts_and_session_state_redact_path_query_and_fragment(self):
        adapter = self.adapter()
        url = "http://127.0.0.1/private/path?access_token=secret#fragment"
        payload = json.dumps({"url": url})
        completed = CompletedProcess([], 0, payload, "")
        with patch("scripts.blind_sniper_browser.subprocess.run", side_effect=[completed, completed]):
            result = adapter.execute("open", "open-redaction", url)
        serialized = json.dumps(result["receipt"])
        self.assertNotIn("secret", serialized)
        self.assertNotIn("/private/path", serialized)
        self.assertEqual(result["receipt"]["requested_url"], "http://127.0.0.1/[REDACTED]")
        self.assertNotIn("secret", adapter.session_file.read_text(encoding="utf-8"))
        self.assertEqual(
            redact_url_for_receipt("https://example.test/a?token=x#fragment"),
            "https://example.test/[REDACTED]",
        )

    def test_tab_and_frame_actions_map_to_supported_cli(self):
        adapter = self.adapter()
        with patch("scripts.blind_sniper_browser.subprocess.run", return_value=CompletedProcess([], 0, '{"tabs":[]}', "")) as run:
            adapter.execute("tabs", "tabs-1")
            adapter.execute("tab-new", "tab-new-1", "http://127.0.0.1/")
            adapter.execute("tab-switch", "tab-switch-1", "t1")
            adapter.execute("tab-close", "tab-close-1", "t1")
            adapter.execute("frame", "frame-1", "main")
        commands = [call.args[0] for call in run.call_args_list]
        self.assertIn(["tab"], [command[-1:] for command in commands])
        self.assertTrue(any(command[-3:] == ["tab", "new", "http://127.0.0.1/"] for command in commands))
        self.assertTrue(any(command[-2:] == ["tab", "t1"] for command in commands))
        self.assertTrue(any(command[-3:] == ["tab", "close", "t1"] for command in commands))
        self.assertTrue(any(command[-2:] == ["frame", "main"] for command in commands))

    def test_pdf_output_is_contained_and_uses_browser_pdf_command(self):
        adapter = self.adapter()
        adapter.state["current_url"] = "http://127.0.0.1/"
        with patch("scripts.blind_sniper_browser.subprocess.run", return_value=CompletedProcess([], 0, "{}", "")) as run:
            result = adapter.execute("pdf", "pdf-1", "page.pdf")
        self.assertEqual(run.call_args.args[0][-2], "pdf")
        self.assertTrue(run.call_args.args[0][-1].startswith(str(adapter.artifacts_dir)))
        self.assertEqual(result["receipt"]["artifact_paths"], [str(adapter.artifacts_dir / "page.pdf")])

    def test_upload_requires_approval_and_contained_workspace_file(self):
        adapter = self.adapter(approval_reference="OWNER-APPROVED")
        adapter.state["current_url"] = "http://127.0.0.1/"
        source = adapter.uploads_dir / "fixture.txt"
        source.write_text("fixture", encoding="utf-8")
        with patch.dict(os.environ, {"BLIND_SNIPER_BROWSER_WRITE_APPROVED": "1"}):
            with patch("scripts.blind_sniper_browser.subprocess.run", return_value=CompletedProcess([], 0, "{}", "")) as run:
                adapter.execute("upload", "upload-1", "input[type=file]", "fixture.txt")
        commands = [call.args[0] for call in run.call_args_list]
        self.assertTrue(any(command[-3:] == ["upload", "input[type=file]", str(source)] for command in commands))

    def test_upload_rejects_path_traversal_and_unsupported_types(self):
        adapter = self.adapter(approval_reference="OWNER-APPROVED")
        adapter.state["current_url"] = "http://127.0.0.1/"
        with patch.dict(os.environ, {"BLIND_SNIPER_BROWSER_WRITE_APPROVED": "1"}):
            with self.assertRaises(BrowserPolicyError):
                adapter.execute("upload", "upload-traversal", "input[type=file]", "../outside.txt")
            (adapter.uploads_dir / "payload.exe").write_text("x", encoding="utf-8")
            with self.assertRaises(BrowserPolicyError):
                adapter.execute("upload", "upload-exe", "input[type=file]", "payload.exe")

    def test_download_is_saved_only_inside_artifact_workspace(self):
        adapter = self.adapter()
        adapter.state["current_url"] = "http://127.0.0.1/"
        def fake_run(command, **kwargs):
            Path(command[-1]).write_bytes(b"downloaded")
            return CompletedProcess(command, 0, "{}", "")
        with patch("scripts.blind_sniper_browser.subprocess.run", side_effect=fake_run) as run:
            result = adapter.execute("download", "download-1", "a.download", "report.pdf")
        target = adapter.artifacts_dir / "report.pdf"
        self.assertTrue(target.is_file())
        self.assertEqual(target.read_bytes(), b"downloaded")
        self.assertEqual(run.call_args.args[0][-3], "download")
        self.assertEqual(result["receipt"]["artifact_paths"], [str(target)])

    def test_download_rejects_path_traversal(self):
        adapter = self.adapter()
        adapter.state["current_url"] = "http://127.0.0.1/"
        with self.assertRaises(BrowserPolicyError):
            adapter.execute("download", "download-traversal", "a.download", "../outside.pdf")

    def test_standalone_adapter_cli_is_blocked(self):
        output = io.StringIO()
        with redirect_stderr(output):
            result = main([])
        self.assertEqual(result, 2)
        self.assertIn("blind_sniper_browser_dispatch.py", output.getvalue())


    def test_clipboard_actions_map_to_cli_and_redact_written_text(self):
        adapter = self.adapter(approval_reference="OWNER-APPROVED")
        adapter.state["current_url"] = "http://127.0.0.1/"
        with patch.dict(os.environ, {"BLIND_SNIPER_BROWSER_WRITE_APPROVED": "1"}):
            with patch("scripts.blind_sniper_browser.subprocess.run", return_value=CompletedProcess([], 0, "clipboard-result", "")) as run:
                adapter.execute("clipboard-write", "clipboard-write-1", "private clipboard phrase")
                adapter.execute("clipboard-read", "clipboard-read-1")
                adapter.execute("clipboard-copy", "clipboard-copy-1")
                adapter.execute("clipboard-paste", "clipboard-paste-1")
        commands = [call.args[0] for call in run.call_args_list]
        self.assertTrue(any(command[-3:] == ["clipboard", "write", "private clipboard phrase"] for command in commands))
        self.assertTrue(any(command[-2:] == ["clipboard", "read"] for command in commands))
        self.assertTrue(any(command[-2:] == ["clipboard", "copy"] for command in commands))
        self.assertTrue(any(command[-2:] == ["clipboard", "paste"] for command in commands))
        receipt_text = adapter.receipt_file.read_text(encoding="utf-8")
        self.assertNotIn("private clipboard phrase", receipt_text)
        self.assertIn("[REDACTED]", receipt_text)

    def test_clipboard_mutations_require_host_approval(self):
        adapter = self.adapter()
        adapter.state["current_url"] = "http://127.0.0.1/"
        for action, args in (
            ("clipboard-write", ("text",)),
            ("clipboard-copy", ()),
            ("clipboard-paste", ()),
        ):
            with self.subTest(action=action):
                with self.assertRaises(BrowserPolicyError):
                    adapter.execute(action, f"blocked-{action}", *args)

    def test_clipboard_write_enforces_text_limit(self):
        adapter = self.adapter(approval_reference="OWNER-APPROVED")
        adapter.state["current_url"] = "http://127.0.0.1/"
        with patch.dict(os.environ, {"BLIND_SNIPER_BROWSER_WRITE_APPROVED": "1"}):
            with self.assertRaises(BrowserPolicyError):
                adapter.execute("clipboard-write", "clipboard-too-long", "x" * 10001)



if __name__ == "__main__":
    unittest.main()
