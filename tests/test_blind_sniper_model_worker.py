"""Tests for the bounded, independently-invoked model worker.

No network call is made: a fake transport is injected. The tests prove distinct
agent IDs, enforced tool allowlists, fresh context, bounded retries, receipts,
bounded concurrency and the disabled-without-key posture.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import blind_sniper_model_worker as mw  # noqa: E402


def _ok_body(content="done", usage=None):
    return {"choices": [{"message": {"content": content}}], "usage": usage or {"total_tokens": 7}}


class ModelWorkerTests(unittest.TestCase):
    def _invoker(self, transport, **kw):
        return mw.ModelInvoker(api_key="test-key", transport=transport, sleep=lambda _s: None, **kw)

    def test_invoke_returns_receipt_with_agent_id_and_usage(self):
        calls = []

        def transport(*, url, api_key, payload, timeout):
            calls.append(payload)
            return 200, _ok_body("answer", {"total_tokens": 11})

        agent = mw.ModelAgent(agent_id="agent-a", system_prompt="You are A", allowed_tools=["terminal"])
        invoker = self._invoker(transport)
        receipt = invoker.invoke(agent=agent, task_id="BS-MW-001", messages=[{"role": "user", "content": "hi"}])
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["agent_id"], "agent-a")
        self.assertEqual(receipt["task_id"], "BS-MW-001")
        self.assertEqual(receipt["usage"]["total_tokens"], 11)
        self.assertEqual(receipt["output"], "answer")
        # Fresh context: the system prompt is the agent's, plus only the supplied messages.
        self.assertEqual(calls[0]["messages"][0]["role"], "system")
        self.assertEqual(calls[0]["messages"][0]["content"], "You are A")

    def test_distinct_agents_produce_distinct_receipts(self):
        def transport(*, url, api_key, payload, timeout):
            return 200, _ok_body(payload["messages"][0]["content"])

        invoker = self._invoker(transport)
        a = mw.ModelAgent(agent_id="agent-a", system_prompt="A", allowed_tools=[])
        b = mw.ModelAgent(agent_id="agent-b", system_prompt="B", allowed_tools=[])
        ra = invoker.invoke(agent=a, task_id="T1", messages=[{"role": "user", "content": "x"}])
        rb = invoker.invoke(agent=b, task_id="T2", messages=[{"role": "user", "content": "y"}])
        self.assertNotEqual(ra["agent_id"], rb["agent_id"])
        self.assertEqual(ra["output"], "A")
        self.assertEqual(rb["output"], "B")

    def test_tool_allowlist_is_enforced(self):
        agent = mw.ModelAgent(agent_id="agent-a", system_prompt="A", allowed_tools=["terminal"])
        invoker = self._invoker(lambda **kw: (200, _ok_body()))
        with self.assertRaises(mw.ToolNotAllowedError):
            invoker.invoke(agent=agent, task_id="T1", messages=[{"role": "user", "content": "x"}],
                           requested_tools=["terminal", "browser_write"])
        # Allowed tools pass.
        receipt = invoker.invoke(agent=agent, task_id="T1", messages=[{"role": "user", "content": "x"}],
                                 requested_tools=["terminal"])
        self.assertEqual(receipt["status"], "PASS")

    def test_retries_until_success_within_bound(self):
        attempts = {"n": 0}

        def transport(*, url, api_key, payload, timeout):
            attempts["n"] += 1
            if attempts["n"] < 3:
                return 500, {"error": "temporary"}
            return 200, _ok_body()

        invoker = self._invoker(transport, max_attempts=3)
        agent = mw.ModelAgent(agent_id="a", system_prompt="A", allowed_tools=[])
        receipt = invoker.invoke(agent=agent, task_id="T1", messages=[{"role": "user", "content": "x"}])
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["attempt"], 3)

    def test_exhausted_retries_return_fail_receipt(self):
        invoker = self._invoker(lambda **kw: (500, {"error": "down"}), max_attempts=2)
        agent = mw.ModelAgent(agent_id="a", system_prompt="A", allowed_tools=[])
        receipt = invoker.invoke(agent=agent, task_id="T1", messages=[{"role": "user", "content": "x"}])
        self.assertEqual(receipt["status"], "FAIL")
        self.assertIn("HTTP 500", receipt["error"])

    def test_disabled_without_api_key_does_not_call_transport(self):
        called = {"n": 0}

        def transport(**kw):
            called["n"] += 1
            return 200, _ok_body()

        invoker = mw.ModelInvoker(api_key="", transport=transport)
        self.assertFalse(invoker.enabled)
        agent = mw.ModelAgent(agent_id="a", system_prompt="A", allowed_tools=[])
        receipt = invoker.invoke(agent=agent, task_id="T1", messages=[{"role": "user", "content": "x"}])
        self.assertEqual(receipt["status"], "DISABLED")
        self.assertEqual(called["n"], 0)

    def test_receipt_redacts_secret_in_output(self):
        def transport(*, url, api_key, payload, timeout):
            return 200, _ok_body("leaked sk-" + "a" * 24)

        invoker = self._invoker(transport)
        agent = mw.ModelAgent(agent_id="a", system_prompt="A", allowed_tools=[])
        receipt = invoker.invoke(agent=agent, task_id="T1", messages=[{"role": "user", "content": "x"}])
        self.assertNotIn("sk-", receipt["output"])
        self.assertIn("[REDACTED]", receipt["output"])

    def test_invoke_many_bounds_concurrency_and_returns_sorted(self):
        import threading
        active = {"now": 0, "peak": 0}
        lock = threading.Lock()

        def transport(*, url, api_key, payload, timeout):
            with lock:
                active["now"] += 1
                active["peak"] = max(active["peak"], active["now"])
            import time as _t
            _t.sleep(0.02)
            with lock:
                active["now"] -= 1
            return 200, _ok_body()

        invoker = self._invoker(transport)
        jobs = [
            {"agent": mw.ModelAgent(agent_id=f"a{i}", system_prompt="A", allowed_tools=[]),
             "task_id": f"T{i}", "messages": [{"role": "user", "content": "x"}]}
            for i in range(4)
        ]
        receipts = invoker.invoke_many(jobs=jobs, max_concurrency=2)
        self.assertEqual([r["task_id"] for r in receipts], ["T0", "T1", "T2", "T3"])
        self.assertLessEqual(active["peak"], 2)

    def test_invoke_many_rejects_out_of_range_concurrency(self):
        invoker = self._invoker(lambda **kw: (200, _ok_body()))
        with self.assertRaises(mw.ModelWorkerError):
            invoker.invoke_many(jobs=[], max_concurrency=99)


if __name__ == "__main__":
    unittest.main()
