import sys
import unittest
from unittest.mock import patch, MagicMock
sys.path.insert(0, 'C:/YT-SHORTS')
from core.llm_router import extract_json, call_openrouter
import json

class TestConfig(unittest.TestCase):
    def test_secret_masking(self):
        from core.config import _mask_secret
        self.assertEqual(_mask_secret(\"\"), \"<NOT SET>\")
        self.assertEqual(_mask_secret(\"123456\"), \"***\")
        masked = _mask_secret(\"sk-or-v1-abcdef123456\")
        self.assertTrue(masked.startswith(\"sk-o\"))
        self.assertTrue(masked.endswith(\"3456\"))
        self.assertNotIn(\"abcdef\", masked)

    def test_config_loaded(self):
        from core.config import config
        summary = config.mask_summary()
        self.assertIn(\"NEXUS VAULTS 2.0\", summary)
        self.assertIn(\"AI_PROVIDER_CHAIN\", summary)
        # Ensure raw secrets do not appear in summary
        if config.ai.openrouter_api_key:
            self.assertNotIn(config.ai.openrouter_api_key, summary)
        if config.ai.groq_api_key:
            self.assertNotIn(config.ai.groq_api_key, summary)

    def test_exact_credential_binding(self):
        from core.config import config
        self.assertIsNotNone(config.youtube.client_id)
        self.assertIsNotNone(config.youtube.client_secret)
        self.assertIsNotNone(config.youtube.refresh_token)

    def test_extract_json_with_thinking(self):
        raw = \"Here's thinking process:\\n1. Think\\n`json\\n{\\\"test\\\": 42}\\n`\\nExtra text\"
        clean = extract_json(raw)
        data = json.loads(clean)
        self.assertEqual(data[\"test\"], 42)
        
        raw_no_markdown = \"Thinking:\\n- Analyze\\n{\\\"key\\\": \\\"value\\\"}\\nDone\"
        clean2 = extract_json(raw_no_markdown)
        data2 = json.loads(clean2)
        self.assertEqual(data2[\"key\"], \"value\")

class TestCircuitBreaker(unittest.TestCase):
    def test_openrouter_429_retry_once(self):
        success_resp = MagicMock()
        success_resp.read.return_value = b'{\"choices\": [{\"message\": {\"content\": \"success\"}}]}'
        success_resp.status = 200
        success_resp.headers = {}
        with patch('urllib.request.urlopen') as mock_urlopen:
            resp_429 = MagicMock()
            resp_429.read.return_value = b''
            resp_429.status = 429
            resp_429.headers = {'Retry-After': '2'}
            mock_urlopen.side_effect = [resp_429, success_resp]
            with patch('time.sleep') as mock_sleep:
                result = call_openrouter(\"test prompt\", \"test system\", task_type=\"general\")
                self.assertEqual(result, \"success\")
                mock_sleep.assert_called_once_with(2)
                self.assertEqual(mock_urlopen.call_count, 2)

    def test_openrouter_429_no_retry_after(self):
        success_resp = MagicMock()
        success_resp.read.return_value = b'{\"choices\": [{\"message\": {\"content\": \"success\"}}]}'
        success_resp.status = 200
        success_resp.headers = {}
        with patch('urllib.request.urlopen') as mock_urlopen:
            resp_429 = MagicMock()
            resp_429.read.return_value = b''
            resp_429.status = 429
            resp_429.headers = {}
            mock_urlopen.side_effect = [resp_429, success_resp]
            with patch('time.sleep') as mock_sleep:
                result = call_openrouter(\"test\", \"system\", task_type=\"general\")
                self.assertEqual(result, \"success\")
                mock_sleep.assert_called_once_with(5.0)
                self.assertEqual(mock_urlopen.call_count, 2)

    def test_openrouter_429_max_one_retry_then_fail(self):
        with patch('urllib.request.urlopen') as mock_urlopen:
            resp_429 = MagicMock()
            resp_429.read.return_value = b''
            resp_429.status = 429
            resp_429.headers = {'Retry-After': '1'}
            mock_urlopen.side_effect = [resp_429, resp_429]
            with patch('time.sleep') as mock_sleep:
                result = call_openrouter(\"test\", \"system\", task_type=\"general\")
                self.assertIsNone(result)
                mock_sleep.assert_called_once()
                self.assertEqual(mock_urlopen.call_count, 2)

if __name__ == '__main__':
    unittest.main()
