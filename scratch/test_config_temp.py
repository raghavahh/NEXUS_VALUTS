"""
Unit Tests for Centralized Configuration and Environment Loading
"""

import unittest
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# import _guard
# _guard.ensure_isolation()  # MUST precede any project import
from core.config import config, _mask_secret

class TestConfig(unittest.TestCase):
    def test_secret_masking(self):
        self.assertEqual(_mask_secret(""), "<NOT SET>")
        self.assertEqual(_mask_secret("123456"), "***")
        masked = _mask_secret("sk-or-v1-abcdef123456")
        self.assertTrue(masked.startswith("sk-o"))
        self.assertTrue(masked.endswith("3456"))
        self.assertNotIn("abcdef", masked)

    def test_config_loaded(self):
        summary = config.mask_summary()
        self.assertIn("NEXUS VAULTS 2.0", summary)
        self.assertIn("AI_PROVIDER_CHAIN", summary)
        # Ensure raw secrets do not appear in summary
        if config.ai.openrouter_api_key:
            self.assertNotIn(config.ai.openrouter_api_key, summary)
        if config.ai.groq_api_key:
            self.assertNotIn(config.ai.groq_api_key, summary)

    def test_exact_credential_binding(self):
        # Must bind exact names, not aliases
        self.assertIsNotNone(config.youtube.client_id)
        self.assertIsNotNone(config.youtube.client_secret)
        self.assertIsNotNone(config.youtube.refresh_token)

    def test_extract_json_with_thinking(self):
        from core.llm_router import extract_json
        import json
        raw = "Here's thinking process:\n1. Think\n```json\n{\"test\": 42}\n```\nExtra text"
        clean = extract_json(raw)
        data = json.loads(clean)
        self.assertEqual(data["test"], 42)

        raw_no_markdown = "Thinking:\n- Analyze\n{\"key\": \"value\"}\nDone"
        clean2 = extract_json(raw_no_markdown)
        data2 = json.loads(clean2)
        self.assertEqual(data2["key"], "value")

        raw_extra_data = "Here is JSON: {\"success\": true} and extra details {note: 123}."
        clean3 = extract_json(raw_extra_data)
        data3 = json.loads(clean3)
        self.assertTrue(data3["success"])


if __name__ == "__main__":
    unittest.main()

