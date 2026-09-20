"""Test for 429 cooldown mechanism honoring Retry-After and capping at 60 seconds."""

import os
import sys
from pathlib import Path

# Add the project root to sys.path for importing core modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import unittest
from unittest.mock import patch, MagicMock
import urllib.error

import _guard
_guard.ensure_isolation()  # MUST precede any project import

from core.llm_router import call_openrouter


class Test429Cooldown(unittest.TestCase):
    @patch('urllib.request.urlopen')
    @patch('time.sleep')
    def test_429_honor_retry_after_and_cap(self, mock_sleep, mock_urlopen):
        # Mock the config used in the llm_router module
        with patch('core.llm_router.config') as mock_config:
            mock_config.ai.openrouter_api_key = 'test-key'
            mock_config.ai.openrouter_model = 'test-model'
            mock_config.ai.openrouter_api_url = 'https://openrouter.ai/api/v1'
            mock_config.ai.request_timeout = 10

            # First response: 429 with Retry-After: 120 (should be capped to 60)
            # We simulate an HTTPError with status 429 and headers
            http_error_429 = urllib.error.HTTPError(
                url='https://openrouter.ai/api/v1/chat/completions',
                code=429,
                msg='Too Many Requests',
                hdrs={'Retry-After': '120'},
                fp=None
            )
            # Second response: 200 OK with a simple JSON
            mock_response_200 = MagicMock()
            mock_response_200.status = 200
            mock_response_200.headers = {}
            mock_response_200.read.return_value = b'{"choices": [{"message": {"content": "Hello"}}]}'
            mock_response_200.__enter__.return_value = mock_response_200
            mock_response_200.__exit__.return_value = False

            # Side effect: first call raises HTTPError, second returns the mock response
            mock_urlopen.side_effect = [http_error_429, mock_response_200]

            # Call the function
            result = call_openrouter("Hello", task_type="general")

            # Assert that we got the expected result
            self.assertEqual(result, "Hello")

            # Assert that urlopen was called twice
            self.assertEqual(mock_urlopen.call_count, 2)

            # Assert that sleep was called once with the capped value (60)
            mock_sleep.assert_called_once()
            args, kwargs = mock_sleep.call_args
            self.assertEqual(args[0], 60)  # wait_time should be capped at 60

    @patch('urllib.request.urlopen')
    @patch('time.sleep')
    def test_429_no_retry_after_uses_fallback(self, mock_sleep, mock_urlopen):
        with patch('core.llm_router.config') as mock_config:
            mock_config.ai.openrouter_api_key = 'test-key'
            mock_config.ai.openrouter_model = 'test-model'
            mock_config.ai.openrouter_api_url = 'https://openrouter.ai/api/v1'
            mock_config.ai.request_timeout = 10

            # First response: 429 with no Retry-After header
            http_error_429 = urllib.error.HTTPError(
                url='https://openrouter.ai/api/v1/chat/completions',
                code=429,
                msg='Too Many Requests',
                hdrs={},
                fp=None
            )
            # Second response: 200 OK
            mock_response_200 = MagicMock()
            mock_response_200.status = 200
            mock_response_200.headers = {}
            mock_response_200.read.return_value = b'{"choices": [{"message": {"content": "Hi"}}]}'
            mock_response_200.__enter__.return_value = mock_response_200
            mock_response_200.__exit__.return_value = False

            mock_urlopen.side_effect = [http_error_429, mock_response_200]

            result = call_openrouter("Hi", task_type="general")

            self.assertEqual(result, "Hi")
            self.assertEqual(mock_urlopen.call_count, 2)
            # Should sleep for fallback 5.0 seconds
            mock_sleep.assert_called_once()
            args, kwargs = mock_sleep.call_args
            self.assertEqual(args[0], 5.0)


if __name__ == '__main__':
    unittest.main()