"""Tests for the Codex-style config template validator.

These run the real validator against the shipped templates (which must pass) and
against deliberately unsafe temporary templates (which must be rejected), so the
guard is proven to fail closed rather than only to pass.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import validate_codex_config as vcc  # noqa: E402


def write_template(text: str) -> Path:
    handle = tempfile.NamedTemporaryFile("w", suffix=".toml.example", delete=False)
    handle.write(text)
    handle.close()
    return Path(handle.name)


class ShippedTemplatesTest(unittest.TestCase):
    def test_all_shipped_templates_parse_and_are_safe(self) -> None:
        templates = sorted(vcc.CONFIG_DIR.glob("*.toml.example"))
        self.assertEqual(len(templates), 6)
        for path in templates:
            errors, _ = vcc.validate_template(path)
            self.assertEqual(errors, [], f"{path.name}: {errors}")

    def test_full_validation_passes(self) -> None:
        import subprocess
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_codex_config.py")],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class UnsafeTemplateTest(unittest.TestCase):
    def test_dangerous_sandbox_rejected(self) -> None:
        path = write_template('approval_policy = "on-request"\nsandbox_mode = "danger-full-access"\n')
        errors, _ = vcc.validate_template(path)
        self.assertTrue(any("UNSAFE_SANDBOX" in e for e in errors), errors)

    def test_non_on_request_approval_rejected(self) -> None:
        path = write_template('approval_policy = "never"\nsandbox_mode = "read-only"\n')
        errors, _ = vcc.validate_template(path)
        self.assertTrue(any("UNSAFE_APPROVAL" in e for e in errors), errors)

    def test_secret_value_rejected(self) -> None:
        path = write_template('approval_policy = "on-request"\nsandbox_mode = "read-only"\n'
                              'api_key = "sk-abcdefghijklmnopqrstuvwx"\n')
        errors, _ = vcc.validate_template(path)
        self.assertTrue(any("SECRET_VALUE" in e or "CREDENTIAL_PATTERN" in e for e in errors), errors)

    def test_invalid_toml_rejected(self) -> None:
        path = write_template('approval_policy = "on-request\nsandbox_mode = \n')
        errors, _ = vcc.validate_template(path)
        self.assertTrue(any("INVALID_TOML" in e for e in errors), errors)

    def test_sandbox_posture_mapping(self) -> None:
        self.assertEqual(vcc.expected_sandbox("read-only-by-default"), "read-only")
        self.assertEqual(vcc.expected_sandbox("scoped-workspace-write"), "workspace-write")


if __name__ == "__main__":
    unittest.main()
