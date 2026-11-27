"""Unit logic tests for scripts.blind_sniper_connectors.

These tests use fake injected HTTP callables and fake environment dictionaries
and do NOT prove any real network connection or live external API behavior.
"""

from __future__ import annotations

import threading

import json
import os
from dataclasses import replace
from pathlib import Path
import stat
import sys
import tempfile
import time
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.blind_sniper_connectors import (  # noqa: E402
    BUILTIN_SPECS,
    Connector,
    ConnectorRegistry,
    ConnectorStatus,
    _utc_now_iso,
    authorize,
    main as cli_main,
)


class FakeConnector(Connector):
    cancellable = True

    def __init__(self, fn=None):
        self.fn = fn

    @property
    def connector_id(self) -> str:
        return "files"

    def tools(self) -> list[dict]:
        return [{"name": "read_file", "side_effects": "read_only", "description": "Read a test item", "input_schema": {
            "type": "object", "properties": {"path": {"type": "string"}},
            "required": ["path"], "additionalProperties": False,
        }}]

    def health(self) -> dict:
        return {"health": "healthy"}

    def call(self, tool_name, arguments, *, timeout_s, cancel=None):
        if self.fn:
            return self.fn(tool_name, arguments, timeout_s=timeout_s, cancel=cancel)
        return {"value": "test result"}


class MutatingFakeConnector(FakeConnector):
    def tools(self) -> list[dict]:
        return [{"name": "write_file", "side_effects": "mutating", "description": "Write a test item",
                 "input_schema": {"type": "object", "properties": {"path": {"type": "string"}},
                                  "required": ["path"], "additionalProperties": False}}]


class FakeHttpResponse:
    def __init__(self, routes: dict[tuple[str, str], tuple[int, dict[str, str], bytes]]) -> None:
        self.routes = routes
        self.calls: list[tuple[str, str, dict[str, str], bytes | None]] = []

    def __call__(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        data: bytes | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        self.calls.append((method.upper(), url, dict(headers or {}), data))
        key = (method.upper(), url)
        if key in self.routes:
            return self.routes[key]
        for (r_method, r_prefix), resp in self.routes.items():
            if method.upper() == r_method and url.startswith(r_prefix):
                return resp
        return 404, {}, b"not found"


class TestBlindSniperConnectors(unittest.TestCase):
    def connector_registry(self, connector=None, path=None, verified=True):
        reg = ConnectorRegistry(env={}, http=FakeHttpResponse({}), connectors=[connector or FakeConnector()],
                                call_receipts_path=path)
        if verified:
            reg._statuses["files"] = ConnectorStatus(
                connector_id="files", auth_status="verified", health="healthy",
                last_verified_at=_utc_now_iso(),
                operations_available=list(BUILTIN_SPECS["files"].operations), checked_by="test")
        return reg

    def test_discovery_and_success_receipt_digest(self):
        reg = self.connector_registry()
        found = reg.discover()
        self.assertEqual(found["files"]["tools"][0]["name"], "read_file")
        args = {"path": "sample.txt"}
        result = reg.call("engineer", "files", "read_file", args, ["files.read_file"])
        self.assertEqual(result["value"], "test result")
        receipt = reg.call_receipts[-1]
        self.assertEqual(len(receipt["arguments_sha256"]), 64)
        encoded = json.dumps(receipt)
        self.assertNotIn("sample.txt", encoded)
        self.assertNotIn("test result", encoded)

    def test_mutating_exception_after_invocation_blocks_replay(self):
        effects = []
        def fail_after_effect(tool, args, *, timeout_s, cancel=None):
            effects.append(args["path"])
            raise RuntimeError("failure after external write")
        reg = self.connector_registry(connector=MutatingFakeConnector(fail_after_effect))
        first = reg.call("engineer", "files", "write_file", {"path": "changed.txt"},
                         ["files.write_file"], confirmed=True)
        self.assertEqual(first["failure_kind"], "execution_state_unknown", first)
        second = reg.call("engineer", "files", "write_file", {"path": "changed.txt"},
                          ["files.write_file"], confirmed=True)
        self.assertEqual(second["failure_kind"], "execution_state_unknown", second)
        self.assertEqual(effects, ["changed.txt"])

    def test_durable_receipt_failure_after_mutation_blocks_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt_target = Path(tmp) / "is-a-directory"
            receipt_target.mkdir()
            effects = []
            def write(tool, args, *, timeout_s, cancel=None):
                effects.append(args["path"])
                return {"written": True}
            reg = self.connector_registry(connector=MutatingFakeConnector(write), path=receipt_target)
            first = reg.call("engineer", "files", "write_file", {"path": "changed.txt"},
                             ["files.write_file"], confirmed=True)
            self.assertEqual(first["status"], "UNKNOWN", first)
            self.assertEqual(first["failure_kind"], "receipt_persistence_failed", first)
            second = reg.call("engineer", "files", "write_file", {"path": "changed.txt"},
                              ["files.write_file"], confirmed=True)
            self.assertEqual(second["failure_kind"], "execution_state_unknown", second)
            self.assertEqual(effects, ["changed.txt"])

    def test_call_denials_and_validation(self):
        reg = self.connector_registry()
        cases = [
            (("engineer", "missing", "read_file", {"path": "x"}, ["files.read_file"]), "unknown_connector"),
            (("engineer", "files", "other", {"path": "x"}, ["files.other"]), "unknown_tool"),
            (("engineer", "files", "read_file", {"path": "x"}, []), "not_in_task_allowlist"),
            (("unknown_role", "files", "read_file", {"path": "x"}, ["files.read_file"]), "not_authorized"),
            (("engineer", "files", "read_file", {"path": 7}, ["files.read_file"]), "invalid_arguments"),
            (("engineer", "files", "read_file", {"path": "x", "extra": True}, ["files.read_file"]), "invalid_arguments"),
        ]
        for args, failure in cases:
            with self.subTest(failure=failure):
                self.assertEqual(reg.call(*args)["failure_kind"], failure)
        unverified = self.connector_registry(verified=False)
        self.assertEqual(unverified.call("engineer", "files", "read_file", {"path": "x"}, ["files.read_file"])["failure_kind"], "unauthenticated")
        self.assertEqual(len(reg.call_receipts), len(cases))

    def test_bare_or_foreign_tool_name_does_not_satisfy_task_allowlist(self):
        reg = self.connector_registry()
        for allow in (["read_file"], ["other.read_file"], ["files.read_file.extra"], [], ["files.*"]):
            with self.subTest(allow=allow):
                self.assertEqual(reg.call("engineer", "files", "read_file", {"path": "x"}, allow)["failure_kind"],
                                 "not_in_task_allowlist")

    def test_success_result_is_redacted_of_env_secrets(self):
        secret = "ghp_SuperSecretTokenValue123456"
        def leaky(*_a, **_k):
            return {"note": "token=" + secret}
        reg = self.connector_registry(FakeConnector(leaky))
        reg.env["GITHUB_TOKEN"] = secret
        out = reg.call("engineer", "files", "read_file", {"path": "x"}, ["files.read_file"])
        self.assertNotIn(secret, json.dumps(out))

    def test_discovery_survives_a_broken_connector(self):
        class Broken(FakeConnector):
            def tools(self):
                raise RuntimeError("boom")
        reg = self.connector_registry(Broken())
        found = reg.discover()
        self.assertEqual(found["files"]["tools"], [])
        self.assertEqual(found["files"]["health"]["health"], "error")

    def test_timeout_argument_is_clamped(self):
        seen = []
        def record(tool, args, *, timeout_s, cancel=None):
            seen.append(timeout_s)
            return {}
        reg = self.connector_registry(FakeConnector(record))
        for requested in (500, -1, 0, 5):
            reg.call("engineer", "files", "read_file", {"path": "x"}, ["files.read_file"], timeout_s=requested)
        self.assertEqual(seen, [30.0, 30.0, 30.0, 5.0])

    def test_existing_wide_receipt_file_is_tightened_to_0600(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "calls.jsonl")
            open(path, "w").close()
            os.chmod(path, 0o644)
            reg = self.connector_registry()
            reg.call_receipts_path = Path(path)
            reg.call("engineer", "files", "read_file", {"path": "x"}, ["files.read_file"])
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)

    def call_files(self, reg, path="x", timeout=0.1):
        return reg.call("engineer", "files", "read_file", {"path": path}, ["files.read_file"], timeout_s=timeout)

    def test_uncancellable_connector_is_refused_and_never_invoked(self):
        calls = []
        class Plain(FakeConnector):
            cancellable = False
        reg = self.connector_registry(Plain(lambda *a, **k: calls.append(1) or {}))
        self.assertEqual(self.call_files(reg)["failure_kind"], "uncancellable_connector")
        self.assertEqual(calls, [])

    def test_cooperative_timeout_stops_work_and_no_side_effect_follows(self):
        effects, started = [], threading.Event()
        def work(tool, args, *, timeout_s, cancel):
            started.set()
            if cancel.wait(5):          # honours cancellation: stops before the side effect
                return {}
            effects.append("written")
            return {}
        reg = self.connector_registry(FakeConnector(work))
        result = self.call_files(reg)
        self.assertEqual(result["failure_kind"], "timeout")
        time.sleep(0.4)
        self.assertEqual(effects, [])             # execution actually stopped
        self.assertEqual(reg.unresolved_calls(), [])
        self.assertEqual(self.call_files(reg)["failure_kind"], "timeout")  # a stopped call may be retried

    def test_mutating_call_that_stops_after_mutating_is_not_auto_replayed(self):
        writes = []
        class Mutator(FakeConnector):
            def tools(self):
                return [{"name": "write_file", "description": "Write", "input_schema": {
                    "type": "object", "properties": {"path": {"type": "string"}},
                    "required": ["path"], "additionalProperties": False}}]
        def mutate_then_stop(tool, args, *, timeout_s, cancel):
            writes.append(args["path"])          # side effect happens first
            cancel.wait(5)                        # then honours cancel and stops
            return {}
        files_spec = BUILTIN_SPECS["files"]
        reg = ConnectorRegistry(env={}, http=FakeHttpResponse({}), connectors=[Mutator(mutate_then_stop)],
                                specs={"files": replace(files_spec, operations=files_spec.operations + ["write_file"])})
        reg._statuses["files"] = ConnectorStatus(connector_id="files", auth_status="verified", health="healthy",
                                                 last_verified_at=_utc_now_iso(),
                                                 operations_available=list(files_spec.operations) + ["write_file"])
        call = lambda: reg.call("engineer", "files", "write_file", {"path": "p"}, ["files.write_file"], timeout_s=0.1, confirmed=True)
        first = call()
        self.assertEqual(first.get("failure_kind"), "timeout_partial_unknown", first)
        self.assertFalse(reg.unresolved_calls()[0]["still_running"])
        self.assertEqual(call()["failure_kind"], "execution_state_unknown")
        self.assertEqual(writes, ["p"])           # exactly one mutation, never replayed
        self.assertTrue(reg.resolve_unknown(reg.unresolved_calls()[0]["call_sha256"], True))

    def test_stubborn_connector_leaves_unknown_state_and_blocks_replay(self):
        effects, release = [], threading.Event()
        def stubborn(tool, args, *, timeout_s, cancel):
            release.wait(10)                      # ignores cancel
            effects.append("late side effect")
            return {}
        reg = self.connector_registry(FakeConnector(stubborn))
        reg.cancel_grace_s = 0.05
        result = self.call_files(reg, "a")
        self.assertEqual(result["failure_kind"], "timeout_unknown_state")
        self.assertEqual(reg.unresolved_calls()[0]["still_running"], True)
        calls_before = len(effects)
        for path in ("a", "b"):                   # same call and a different call: both refused while it runs
            self.assertEqual(self.call_files(reg, path)["failure_kind"], "execution_state_unknown")
        release.set()
        time.sleep(0.3)
        self.assertEqual(effects, ["late side effect"])   # exactly one execution, never replayed
        self.assertEqual(calls_before, 0)                 # the effect really did land after the timeout
        self.assertEqual(self.call_files(reg, "a")["failure_kind"], "execution_state_unknown")  # same call still blocked
        digest = reg.unresolved_calls()[0]["call_sha256"]
        self.assertFalse(reg.resolve_unknown(digest, False))
        self.assertTrue(reg.resolve_unknown(digest, True))
        self.assertEqual(self.call_files(reg, "b", timeout=1).get("failure_kind"), None)  # connector usable again after resolve

    def test_resolve_refused_while_thread_still_running(self):
        release = threading.Event()
        reg = self.connector_registry(FakeConnector(lambda *a, cancel=None, **k: release.wait(10) and {}))
        reg.cancel_grace_s = 0.05
        self.call_files(reg)
        digest = reg.unresolved_calls()[0]["call_sha256"]
        self.assertFalse(reg.resolve_unknown(digest, True))
        release.set()

    def test_exception_redaction_and_receipt_file_permissions(self):
        secret = "AIzaSySuperSecretGeminiKey998877"
        prior_secret = os.environ.get("GEMINI_API_KEY")
        os.environ["GEMINI_API_KEY"] = secret
        try:
            def broken(*_args, **_kwargs):
                raise RuntimeError("failed with " + secret)
            with tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp) / "calls.jsonl"
                reg = self.connector_registry(FakeConnector(broken), path=target)
                result = reg.call("engineer", "files", "read_file", {"path": "x"}, ["files.read_file"])
                self.assertEqual(result["failure_kind"], "connector_error")
                self.assertNotIn(secret, json.dumps(result))
                self.assertNotIn(secret, json.dumps(reg.call_receipts))
                self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
                self.assertNotIn("x", target.read_text())
                self.assertNotIn("failed with", target.read_text())
        finally:
            if prior_secret is None:
                os.environ.pop("GEMINI_API_KEY", None)
            else:
                os.environ["GEMINI_API_KEY"] = prior_secret

    def test_destructive_call_requires_confirmation(self):
        class DestructiveFake(FakeConnector):
            def tools(self):
                return [{"name": "delete_file", "description": "Delete", "input_schema": {
                    "type": "object", "properties": {}, "required": [], "additionalProperties": False}}]
            def call(self, tool_name, arguments, *, timeout_s, cancel=None):
                return {"deleted": True}
        files_spec = BUILTIN_SPECS["files"]
        reg = ConnectorRegistry(env={}, http=FakeHttpResponse({}), specs={"files": replace(files_spec, operations=files_spec.operations + ["delete_file"])}, connectors=[DestructiveFake()])
        spec = ConnectorStatus(connector_id="files", auth_status="verified", health="healthy",
                               last_verified_at=_utc_now_iso(),
                               operations_available=list(BUILTIN_SPECS["files"].operations))
        reg._statuses["files"] = spec
        self.assertEqual(reg.call("engineer", "files", "delete_file", {}, ["files.delete_file"])["failure_kind"], "not_authorized")
        self.assertEqual(reg.call("engineer", "files", "delete_file", {}, ["files.delete_file"], confirmed=True), {"deleted": True})

    def test_unconfigured_when_env_is_empty(self) -> None:
        fake_http = FakeHttpResponse({})
        reg = ConnectorRegistry(env={}, http=fake_http)
        statuses = reg.all_statuses(now=1_700_000_000.0)

        for cid in ("github", "google_drive", "gmail", "google_calendar", "google_docs", "google_sheets", "whatsapp_business", "model_gemini"):
            self.assertEqual(statuses[cid].auth_status, "unconfigured")
            self.assertEqual(statuses[cid].operations_available, [])

        self.assertEqual(len(fake_http.calls), 0)

    def test_verified_github_path_with_fake_http(self) -> None:
        env = {
            "GITHUB_TOKEN": "ghp_test_token_12345",
            "GITHUB_REPOSITORY": "acme/widgets",
        }
        fake_http = FakeHttpResponse({
            ("GET", "https://api.github.com/rate_limit"): (
                200,
                {"X-OAuth-Scopes": "repo, read:org"},
                b'{"resources":{"core":{"limit":5000}}}',
            ),
            ("GET", "https://api.github.com/repos/acme/widgets"): (
                200,
                {"X-OAuth-Scopes": "repo, read:org"},
                b'{"full_name":"acme/widgets"}',
            ),
        })
        reg = ConnectorRegistry(env=env, http=fake_http)
        st = reg.verify("github", now=1_700_000_000.0)

        self.assertEqual(st.auth_status, "verified")
        self.assertEqual(st.granted_scopes, ["repo", "read:org"])
        self.assertEqual(st.operations_available, BUILTIN_SPECS["github"].operations)
        self.assertEqual(st.checked_by, "verifier")
        self.assertIsNone(st.last_error)
        self.assertEqual([c[:2] for c in fake_http.calls], [
            ("GET", "https://api.github.com/rate_limit"),
            ("GET", "https://api.github.com/repos/acme/widgets"),
        ])

    def test_secret_redaction_in_error_and_persisted_receipt(self) -> None:
        secret_key = "AIzaSySuperSecretGeminiKey998877"
        env = {"GEMINI_API_KEY": secret_key}
        fake_http = FakeHttpResponse({
            ("GET", "https://generativelanguage.googleapis.com/v1beta/models"): (
                401,
                {},
                f"Unauthorized key {secret_key} Bearer abc.def.ghi".encode("utf-8"),
            ),
        })
        reg = ConnectorRegistry(env=env, http=fake_http)
        st = reg.verify("model_gemini", now=1_700_000_000.0)

        self.assertEqual(st.auth_status, "error")
        self.assertIsNotNone(st.last_error)
        self.assertNotIn(secret_key, str(st))
        self.assertNotIn(secret_key, st.last_error or "")
        self.assertNotIn("abc.def.ghi", st.last_error or "")

        with tempfile.TemporaryDirectory() as tmpdir:
            receipt_file = Path(tmpdir) / "receipts.json"
            reg.persist(receipt_file, now=1_700_000_000.0)
            raw_receipt = receipt_file.read_text(encoding="utf-8")
            self.assertNotIn(secret_key, raw_receipt)
            self.assertNotIn("abc.def.ghi", raw_receipt)

    def test_expired_token_handling_and_refresh_state(self) -> None:
        env = {
            "GOOGLE_CLIENT_ID": "client-1",
            "GOOGLE_CLIENT_SECRET": "secret-1",
            "GOOGLE_REFRESH_TOKEN": "refresh-1",
        }
        now = 1_700_000_000.0
        fake_http = FakeHttpResponse({
            ("POST", "https://oauth2.googleapis.com/token"): (
                200,
                {},
                json.dumps({
                    "access_token": "ya29.fresh_token",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                }).encode("utf-8"),
            ),
            ("GET", "https://www.googleapis.com/oauth2/v3/tokeninfo?access_token=ya29.fresh_token"): (
                200,
                {},
                json.dumps({
                    "scope": "https://www.googleapis.com/auth/spreadsheets.readonly",
                    "expires_in": 3600,
                }).encode("utf-8"),
            ),
        })
        reg = ConnectorRegistry(env=env, http=fake_http)
        st1 = reg.verify("google_sheets", now=now)
        self.assertEqual(st1.auth_status, "verified")
        self.assertEqual(st1.refresh_state, "fresh")

        # Advance time past expiration so status becomes expired
        after_expiry = now + 4000.0
        st_expired = reg.status("google_sheets", now=after_expiry)
        self.assertEqual(st_expired.auth_status, "expired")

        # Re-verify after expiration triggers refresh_state="refreshed"
        st_refreshed = reg.verify("google_sheets", now=after_expiry)
        self.assertEqual(st_refreshed.auth_status, "verified")
        self.assertEqual(st_refreshed.refresh_state, "refreshed")

    def test_authorize_rules_scopes_and_confirmation(self) -> None:
        now = 1_700_000_000.0
        reg = ConnectorRegistry(env={}, http=FakeHttpResponse({}))

        # Default deny for unknown role or unpermitted operation
        ok, _ = authorize("unknown_role", "github", "read_repo", reg, now=now)
        self.assertFalse(ok)
        ok, _ = authorize("planner", "github", "open_pull_request", reg, now=now, confirmed=True)
        self.assertFalse(ok)

        # Deny when unverified
        env_gh = {"GITHUB_TOKEN": "tok_123", "GITHUB_REPOSITORY": "org/repo"}
        reg_gh = ConnectorRegistry(
            env=env_gh,
            http=FakeHttpResponse({
                ("GET", "https://api.github.com/rate_limit"): (200, {}, b"{}"),
                ("GET", "https://api.github.com/repos/org/repo"): (200, {}, b"{}"),
            }),
        )
        ok, _ = authorize("engineer", "github", "read_repo", reg_gh, now=now)
        self.assertFalse(ok)

        # Allow after verify; destructive operation requires confirmed=True
        reg_gh.verify("github", now=now)
        ok_unconfirmed, _ = authorize("engineer", "github", "comment_issue", reg_gh, now=now, confirmed=False)
        self.assertFalse(ok_unconfirmed)
        ok_confirmed, _ = authorize("engineer", "github", "comment_issue", reg_gh, now=now, confirmed=True)
        self.assertTrue(ok_confirmed)

        # Deny when a required scope is missing
        env_g = {
            "GOOGLE_CLIENT_ID": "cid",
            "GOOGLE_CLIENT_SECRET": "csec",
            "GOOGLE_REFRESH_TOKEN": "rtok",
        }
        reg_g = ConnectorRegistry(
            env=env_g,
            http=FakeHttpResponse({
                ("POST", "https://oauth2.googleapis.com/token"): (
                    200,
                    {},
                    b'{"access_token":"atok","expires_in":3600}',
                ),
                ("GET", "https://www.googleapis.com/oauth2/v3/tokeninfo?access_token=atok"): (
                    200,
                    {},
                    b'{"scope":"https://www.googleapis.com/auth/drive.readonly","expires_in":3600}',
                ),
            }),
        )
        reg_g.verify("google_drive", now=now)
        ok_read, _ = authorize("researcher", "google_drive", "list_files", reg_g, now=now)
        self.assertTrue(ok_read)
        ok_missing_scope, _ = authorize("worker_executor", "google_drive", "create_file", reg_g, now=now, confirmed=False)
        self.assertFalse(ok_missing_scope)

    def test_terminal_is_denied_to_all_runtime_roles_by_default(self) -> None:
        now = 1_700_000_000.0
        reg = ConnectorRegistry(env={}, http=FakeHttpResponse({}))
        reg._statuses["terminal"] = ConnectorStatus(
            connector_id="terminal", auth_status="verified", health="healthy",
            last_verified_at=_utc_now_iso(now),
            operations_available=list(reg.specs["terminal"].operations), checked_by="test")
        for role in ("engineer", "qa_verifier", "worker_executor"):
            allowed, _ = authorize(role, "terminal", "run_command", reg, now=now, confirmed=True)
            self.assertFalse(allowed, role)

    def test_receipt_mode_0600_atomic_roundtrip_and_stale_receipt(self) -> None:
        now = 1_700_000_000.0
        env = {"GITHUB_TOKEN": "tok_abc", "GITHUB_REPOSITORY": "org/repo"}
        reg = ConnectorRegistry(
            env=env,
            http=FakeHttpResponse({
                ("GET", "https://api.github.com/rate_limit"): (200, {"X-OAuth-Scopes": "repo"}, b"{}"),
                ("GET", "https://api.github.com/repos/org/repo"): (200, {"X-OAuth-Scopes": "repo"}, b"{}"),
            }),
            max_age_seconds=3600,
        )
        reg.verify("github", now=now)

        with tempfile.TemporaryDirectory() as tmpdir:
            rpath = Path(tmpdir) / "nested" / "receipts.json"
            reg.persist(rpath, now=now)

            mode = stat.S_IMODE(os.stat(rpath).st_mode)
            self.assertEqual(mode, 0o600)

            loaded_reg = ConnectorRegistry(env=env, http=FakeHttpResponse({}), max_age_seconds=3600)
            loaded_reg.load(rpath)

            # Fresh within max_age_seconds
            self.assertEqual(loaded_reg.status("github", now=now + 100.0).auth_status, "verified")

            # Stale after max_age_seconds
            self.assertEqual(loaded_reg.status("github", now=now + 3605.0).auth_status, "configured_unverified")

    def test_cli_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            rpath = Path(tmpdir) / "cli_receipts.json"
            code = cli_main(["status", "github", "--receipts", str(rpath)])
            self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
