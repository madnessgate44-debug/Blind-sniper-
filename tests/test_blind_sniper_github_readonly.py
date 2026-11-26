from __future__ import annotations

import hashlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import threading
import time
import unittest
from dataclasses import replace

REPO_ROOT = Path(__file__).resolve().parents[1]
import sys
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.blind_sniper_connectors import BUILTIN_SPECS, ConnectorRegistry, ConnectorStatus, _utc_now_iso  # noqa: E402
from scripts.blind_sniper_github_readonly import GitHubReadOnlyConnector  # noqa: E402


class ServerState:
    def __init__(self):
        self.routes = {}
        self.methods = []
        self.headers = []
        self.delay = 0


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        state = self.server.state
        state.methods.append(self.command)
        state.headers.append(dict(self.headers))
        if state.delay:
            time.sleep(state.delay)
        status, headers, body = state.routes.get(self.path, (404, {}, b'{"message":"missing"}'))
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        self.server.state.methods.append(self.command)
        self.send_response(500)
        self.end_headers()

    def log_message(self, *args):
        pass


class LocalGitHubServer:
    def __enter__(self):
        self.state = ServerState()
        try:
            self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        except PermissionError as exc:
            raise unittest.SkipTest(f"sandbox does not permit localhost sockets: {exc}") from exc
        self.server.state = self.state
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


def registry_for(connector):
    operations = [x["name"] for x in connector.tools()]
    spec = replace(BUILTIN_SPECS["github"], auth_kind="local_none", env_vars=[],
                   token_env_var=None, operations=operations)
    reg = ConnectorRegistry(specs={"github": spec}, env={}, connectors=[connector])
    reg._statuses["github"] = ConnectorStatus(connector_id="github", auth_status="verified",
        health="healthy", last_verified_at=_utc_now_iso(), operations_available=operations)
    return reg


class TestGitHubReadOnly(unittest.TestCase):
    def test_schemas_are_strict_and_registry_rejects_bad_inputs(self):
        connector = GitHubReadOnlyConnector("owner/repo", base_url="http://127.0.0.1:1")
        reg = registry_for(connector)
        for tool, args in (("pr_status", {"number": True}), ("pr_status", {"number": 2, "path": "/tmp"})):
            result = reg.call("engineer", "github", tool, args, [f"github.{tool}"])
            self.assertEqual(result["failure_kind"], "invalid_arguments", result)
        for tool, args in (("pr_status", {"number": 0}), ("check_runs", {"ref": "main"}),
                           ("issue_comments", {"number": 1, "limit": 31})):
            with self.assertRaises(ValueError):
                connector.call(tool, args, timeout_s=1)
        schemas = {tool["name"]: tool["input_schema"] for tool in connector.tools()}
        self.assertEqual(schemas["pr_status"]["properties"]["number"]["minimum"], 1)
        self.assertEqual(schemas["issue_comments"]["properties"]["limit"]["maximum"], 30)
        self.assertTrue(all(t["side_effects"] == "read_only" for t in connector.tools()))
        self.assertTrue(connector.cancellable)

    def test_comments_are_capped_and_marked_untrusted_without_auth_header(self):
        body = "x" * 450 + " instruction-like content"
        with LocalGitHubServer() as server:
            server.state.routes["/repos/owner/repo/issues/8/comments?per_page=30"] = (200, {}, json.dumps([
                {"id": 7, "body": body, "user": {"login": "person"}, "created_at": "now", "html_url": "https://github.com/x"}
            ]).encode())
            connector = GitHubReadOnlyConnector("owner/repo", base_url=server.base_url)
            result = connector.call("issue_comments", {"number": 8, "limit": 30}, timeout_s=3)
            item = result["comments"][0]
            self.assertEqual(len(item["body_excerpt"]), 400)
            self.assertEqual(item["body_sha256"], hashlib.sha256(body.encode()).hexdigest())
            self.assertIs(result["untrusted_content"], True)
            self.assertEqual(server.state.methods, ["GET"])
            self.assertTrue(all(not any(k.lower() == "authorization" for k in headers) for headers in server.state.headers))

    def test_pull_and_check_run_fields(self):
        sha = "a" * 40
        with LocalGitHubServer() as server:
            server.state.routes["/repos/o/r/pulls/4"] = (200, {}, json.dumps({"number": 4, "title": "T",
                "state": "open", "draft": False, "merged": False, "head": {"sha": sha, "ref": "topic"},
                "base": {"ref": "main"}, "mergeable": True}).encode())
            server.state.routes[f"/repos/o/r/commits/{sha}/check-runs"] = (200, {}, json.dumps({"check_runs": [
                {"id": 9, "name": "CI", "status": "completed", "conclusion": "success", "html_url": "https://github.com/check"}
            ]}).encode())
            server.state.routes[f"/repos/o/r/actions/runs?head_sha={sha}&per_page=100"] = (200, {}, json.dumps({
                "workflow_runs": [{"id": 15}]
            }).encode())
            c = GitHubReadOnlyConnector("o/r", base_url=server.base_url)
            pr = c.call("pr_status", {"number": 4}, timeout_s=3)
            checks = c.call("check_runs", {"ref": sha}, timeout_s=3)
            self.assertEqual((pr["head_sha"], pr["base_ref"], pr["head_ref"], pr["mergeable"]), (sha, "main", "topic", True))
            self.assertEqual(checks["workflow_run_ids"], [15])

    def test_http_failures_redirect_size_malformed_and_timeout(self):
        with LocalGitHubServer() as server:
            c = GitHubReadOnlyConnector("o/r", base_url=server.base_url, response_cap=40)
            def invoke(path, timeout=3):
                return c.call("pr_status", {"number": 1}, timeout_s=timeout)
            server.state.routes["/repos/o/r/pulls/1"] = (403, {}, b'{"message":"limit"}')
            with self.assertRaisesRegex(RuntimeError, "rate limit"):
                invoke("x")
            server.state.routes["/repos/o/r/pulls/1"] = (404, {}, b'{}')
            with self.assertRaisesRegex(LookupError, "404"):
                invoke("x")
            server.state.routes["/repos/o/r/pulls/1"] = (200, {}, b"not json")
            with self.assertRaisesRegex(ValueError, "malformed JSON"):
                invoke("x")
            server.state.routes["/repos/o/r/pulls/1"] = (200, {}, b'{"title":"' + b'x' * 90 + b'"}')
            with self.assertRaisesRegex(ValueError, "size cap"):
                invoke("x")
            server.state.routes["/repos/o/r/pulls/1"] = (302, {"Location": "http://example.com/steal"}, b"")
            with self.assertRaisesRegex(RuntimeError, "redirect refused"):
                invoke("x")
            server.state.routes["/repos/o/r/pulls/1"] = (200, {}, b'{"number":1}')
            server.state.delay = 2
            started = time.monotonic()
            with self.assertRaisesRegex(TimeoutError, "timed out"):
                invoke("x", timeout=0.3)
            self.assertLess(time.monotonic() - started, 1.5)

    def test_rate_limit_429_and_allowlist(self):
        with LocalGitHubServer() as server:
            server.state.routes["/repos/o/r/pulls/1"] = (429, {}, b"{}")
            c = GitHubReadOnlyConnector("o/r", base_url=server.base_url)
            with self.assertRaisesRegex(RuntimeError, "HTTP 429"):
                c.call("pr_status", {"number": 1}, timeout_s=3)
        for url in ("http://example.com", "https://example.com", "https://api.github.com.evil.test"):
            with self.assertRaises(ValueError):
                GitHubReadOnlyConnector("o/r", base_url=url)


@unittest.skipUnless(os.environ.get("BS_LIVE_GITHUB_READONLY") == "1", "live public GitHub test disabled")
class TestLiveGitHubReadOnly(unittest.TestCase):
    def test_pull_94_through_connector_registry(self):
        connector = GitHubReadOnlyConnector("madnessgate44-debug/Blind-sniper-")
        reg = registry_for(connector)
        result = reg.call("engineer", "github", "pr_status", {"number": 94}, ["github.pr_status"], timeout_s=12)
        self.assertEqual(result.get("number"), 94, result)
        self.assertTrue(result.get("title"), result)
        self.assertIn(result.get("state"), ("open", "closed"), result)
        self.assertRegex(result.get("head_sha", ""), r"^[0-9a-f]{40}$")


if __name__ == "__main__":
    unittest.main()
