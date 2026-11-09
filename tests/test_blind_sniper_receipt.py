"""Tests for the durable executor receipt schema."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import blind_sniper_receipt as receipt_mod  # noqa: E402


class ReceiptSchemaTests(unittest.TestCase):
    def _valid(self, **overrides):
        base = {
            "task_id": "BS-DURABLE-001",
            "command": "validate-runtime",
            "exit_code": 0,
            "run_id": "1234567890",
            "run_url": "https://github.com/o/r/actions/runs/1234567890",
            "timestamp": "2026-11-09T12:00:00Z",
            "status": "PASS",
        }
        base.update(overrides)
        return base

    def test_build_receipt_has_exact_fields(self):
        receipt = receipt_mod.build_receipt(
            task_id="BS-DURABLE-001",
            command="run-tests",
            exit_code=0,
            run_id="42",
            run_url="https://github.com/o/r/actions/runs/42",
            timestamp="2026-11-09T12:00:00Z",
        )
        self.assertEqual(set(receipt), set(receipt_mod.RECEIPT_FIELDS))

    def test_status_reflects_exit_code(self):
        self.assertEqual(receipt_mod.status_for_exit_code(0), "PASS")
        self.assertEqual(receipt_mod.status_for_exit_code(1), "FAIL")
        self.assertEqual(receipt_mod.status_for_exit_code(137), "FAIL")

    def test_valid_receipt_passes(self):
        receipt_mod.validate_receipt(self._valid())

    def test_only_allowlisted_commands_accepted(self):
        self.assertEqual(set(receipt_mod.ALLOWED_COMMANDS), {"validate-runtime", "run-tests"})
        for bad in ("rm -rf /", "unit-tests", "", "run-tests; echo hi", "runtime-validator"):
            with self.assertRaises(receipt_mod.ReceiptError):
                receipt_mod.validate_receipt(self._valid(command=bad))

    def test_status_must_agree_with_exit_code(self):
        with self.assertRaises(receipt_mod.ReceiptError):
            receipt_mod.validate_receipt(self._valid(exit_code=1, status="PASS"))
        with self.assertRaises(receipt_mod.ReceiptError):
            receipt_mod.validate_receipt(self._valid(exit_code=0, status="FAIL"))

    def test_missing_field_rejected(self):
        bad = self._valid()
        del bad["run_url"]
        with self.assertRaises(receipt_mod.ReceiptError):
            receipt_mod.validate_receipt(bad)

    def test_extra_field_rejected(self):
        bad = self._valid()
        bad["token"] = "leaked"
        with self.assertRaises(receipt_mod.ReceiptError):
            receipt_mod.validate_receipt(bad)

    def test_bad_task_id_rejected(self):
        for bad in ("", "has space", "../escape", "a" * 65, "semi;colon"):
            with self.assertRaises(receipt_mod.ReceiptError):
                receipt_mod.validate_receipt(self._valid(task_id=bad))

    def test_bad_run_id_rejected(self):
        for bad in ("", "abc", "12a", 12):
            with self.assertRaises(receipt_mod.ReceiptError):
                receipt_mod.validate_receipt(self._valid(run_id=bad))

    def test_run_url_must_be_https(self):
        with self.assertRaises(receipt_mod.ReceiptError):
            receipt_mod.validate_receipt(self._valid(run_url="http://insecure"))

    def test_timestamp_must_be_utc_z(self):
        for bad in ("2026-11-09 12:00:00", "2026-11-09T12:00:00+00:00", "not-a-date"):
            with self.assertRaises(receipt_mod.ReceiptError):
                receipt_mod.validate_receipt(self._valid(timestamp=bad))

    def test_write_receipt_roundtrip(self):
        receipt = self._valid()
        with tempfile.TemporaryDirectory() as tmp:
            target = receipt_mod.write_receipt(receipt, tmp, receipt["task_id"])
            self.assertEqual(target, Path(tmp) / "ops" / "receipts" / "BS-DURABLE-001.json")
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), receipt)


if __name__ == "__main__":
    unittest.main()
