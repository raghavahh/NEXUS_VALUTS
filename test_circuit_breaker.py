import sys
import unittest
from unittest.mock import patch, MagicMock
sys.path.insert(0, 'C:/YT-SHORTS')
from core.llm_router import call_openrouter
import json

class TestCircuitBreaker(unittest.TestCase):
    def test_openrouter_429_retry_once(self):
        # Mock successful response
        success_resp = MagicMock()
        success_resp.read.return_value = b'{\"choices\": [{\"message\": {\"content\": \"success\"}}]}'
        success_resp.status = 200
        success_resp.headers = {}
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            # First response: 429 with Retry-After
            resp_429 = MagicMock()
            resp_429.read.return_value = b''
            resp_429.status = 429
            resp_429.headers = {'Retry-After': '2'}
            # Second response: success
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
            mock_urlopen.side_effect = [resp_429, resp_429]  # both 429
            
            with patch('time.sleep') as mock_sleep:
                result = call_openrouter(\"test\", \"system\", task_type=\"general\")
                self.assertIsNone(result)
                mock_sleep.assert_called_once()
                self.assertEqual(mock_urlopen.call_count, 2)

if __name__ == '__main__':
    unittest.main()
