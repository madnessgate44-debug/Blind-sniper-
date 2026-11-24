"""Tests for the Forge patch verification adapter."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import blind_sniper_forge_verify as forge_verify  # noqa: E402

FIXTURES = "tests/fixtures/forge-verify"


def run_main(payload: dict | None) -> tuple[int, str]:
    if payload is None:
        forge_verify.INPUT_PATH = ROOT / ".blind-sniper" / "forge-verify" / "does-not-exist.json"
    else:
        handle = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8",
        )
        json.dump(payload, handle)
        handle.close()
        forge_verify.INPUT_PATH = Path(handle.name)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = forge_verify.main()
    return code, out.getvalue()


class ForgePatchVerifyTests(unittest.TestCase):
    def test_real_forge_emitted_patch_passes(self):
        code, out = run_main({
            "patch_path": f"{FIXTURES}/multiply.patch",
            "target_dir": f"{FIXTURES}/target",
            "checks": ["node-check", "node-test"],
        })
        self.assertEqual(code, 0)
        self.assertIn("RESULT: PASS", out)
        self.assertIn("CHECK node-test: PASS", out)

    def test_broken_patch_fails_checks(self):
        code, out = run_main({
            "patch_path": f"{FIXTURES}/broken.patch",
            "target_dir": f"{FIXTURES}/target",
            "checks": ["node-check", "node-test"],
        })
        self.assertEqual(code, 1)
        self.assertIn("RESULT: FAIL", out)

    def test_missing_input_is_refused(self):
        code, out = run_main(None)
        self.assertEqual(code, 2)
        self.assertIn("Input file missing", out)

    def test_path_escape_is_refused(self):
        code, out = run_main({
            "patch_path": "../outside.patch",
            "target_dir": f"{FIXTURES}/target",
            "checks": ["node-test"],
        })
        self.assertEqual(code, 2)
        self.assertIn("must remain inside the repository", out)

    def test_non_allowlisted_check_is_refused(self):
        code, out = run_main({
            "patch_path": f"{FIXTURES}/multiply.patch",
            "target_dir": f"{FIXTURES}/target",
            "checks": ["rm-rf"],
        })
        self.assertEqual(code, 2)
        self.assertIn("non-empty de-duplicated subset", out)

    def test_unexpected_input_keys_are_refused(self):
        code, out = run_main({
            "patch_path": f"{FIXTURES}/multiply.patch",
            "target_dir": f"{FIXTURES}/target",
            "checks": ["node-test"],
            "extra": True,
        })
        self.assertEqual(code, 2)
        self.assertIn("exactly patch_path, target_dir and checks", out)


if __name__ == "__main__":
    unittest.main()
