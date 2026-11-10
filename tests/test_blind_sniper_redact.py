"""Tests for the shared secret redaction helper."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from blind_sniper_redact import REDACTED, redact, redact_text


class RedactionTests(unittest.TestCase):
    def test_github_tokens_are_redacted(self):
        text = "push with ghp_" + "a" * 30 + " and gho_" + "b" * 30
        self.assertNotIn("ghp_", redact_text(text))
        self.assertIn(REDACTED, redact_text(text))

    def test_gemini_and_openai_keys_are_redacted(self):
        self.assertNotIn("AIza", redact_text("key AIza" + "c" * 35))
        self.assertNotIn("AQ.", redact_text("key AQ." + "d" * 50))
        self.assertNotIn("sk-", redact_text("key sk-" + "e" * 30))

    def test_private_key_block_is_redacted(self):
        pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIabc\n-----END RSA PRIVATE KEY-----"
        self.assertNotIn("MIIabc", redact_text(pem))

    def test_explicit_secret_value_is_removed_even_if_unpatterned(self):
        secret = "s3cr3t-valu3-that-matches-nothing"
        self.assertNotIn(secret, redact_text(f"token={secret}", secrets=[secret]))

    def test_redact_recurses_through_structures(self):
        result = redact({"a": ["ghp_" + "f" * 30], "b": {"c": "sk-" + "g" * 30}})
        self.assertEqual(result["a"], [REDACTED])
        self.assertEqual(result["b"]["c"], REDACTED)

    def test_short_secrets_are_not_used_as_needles(self):
        # A one-character "secret" must not shred unrelated text.
        self.assertEqual(redact_text("hello world", secrets=["e"]), "hello world")


if __name__ == "__main__":
    unittest.main()
