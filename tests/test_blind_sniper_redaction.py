"""Tests for the shared secret-redaction module."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import blind_sniper_redaction as redaction  # noqa: E402


class RedactionTests(unittest.TestCase):
    def test_known_patterns_are_masked(self):
        samples = [
            "Authorization: Bearer abcdefghijklmnop123456",
            "token ghp_" + "a" * 30,
            "github_pat_" + "b" * 30,
            "key sk-" + "c" * 24,
            "AIza" + "d" * 30,
            "AQ." + "e" * 45,
            "gAAAAA" + "f" * 24,
            '{"api_key": "supersecretvalue"}',
            "xoxb-1234567890-abcdefghij",
        ]
        for sample in samples:
            with self.subTest(sample=sample):
                redacted = redaction.redact_text(sample)
                self.assertNotEqual(redacted, sample)
                self.assertIn(redaction.PLACEHOLDER, redacted)

    def test_private_key_block_is_masked(self):
        text = "-----BEGIN RSA PRIVATE KEY-----\nMIIabc\n-----END RSA PRIVATE KEY-----"
        self.assertNotIn("MIIabc", redaction.redact_text(text))

    def test_headers_mask_sensitive_keys(self):
        headers = {"Authorization": "Bearer xyz", "X-Session-API-Key": "abc", "Accept": "application/json"}
        masked = redaction.redact_headers(headers)
        self.assertEqual(masked["Authorization"], redaction.PLACEHOLDER)
        self.assertEqual(masked["X-Session-API-Key"], redaction.PLACEHOLDER)
        self.assertEqual(masked["Accept"], "application/json")

    def test_nested_structures_are_redacted(self):
        value = {"outer": [{"token": "ghp_" + "z" * 30}], "safe": 1}
        redacted = redaction.redact_value(value)
        self.assertEqual(redacted["outer"][0]["token"], redaction.PLACEHOLDER)
        self.assertEqual(redacted["safe"], 1)

    def test_contains_secret_detects_and_passes_clean(self):
        self.assertTrue(redaction.contains_secret("leak sk-" + "q" * 20))
        self.assertFalse(redaction.contains_secret({"message": "nothing here"}))


if __name__ == "__main__":
    unittest.main()
