"""
NEXUS VAULTS - Structural Preflight (ISOLATED, NETWORK-FREE)

Runs entirely inside the test sandbox. Verifies:
1. Config loads from sandbox paths (never production DB/OUTPUT)
2. Secret masking works
3. Database schema initializes in sandbox
4. US timezone clock + schedule window structure
5. FFmpeg binary present
6. Credential blanking (no test can reach YouTube/AI providers)
Live OAuth / AI connectivity checks belong in operations, never in the test suite.
"""
import unittest
import subprocess

import _guard
_guard.ensure_isolation()  # MUST precede any project import

from core.config import config  # noqa: E402
from core.database import init_db, get_next_file_number  # noqa: E402
from core.scheduler import get_production_clock, get_schedule_window  # noqa: E402


class StructuralPreflightTest(unittest.TestCase):
    def test_01_sandbox_paths(self):
        repo = _guard.PROD_REPO
        self.assertFalse(str(config.storage.database_path.resolve()).startswith(str(repo)),
                         "Tests must not resolve to the production database!")
        self.assertFalse(str(config.storage.output_dir.resolve()).startswith(str(repo)),
                         "Tests must not resolve to the production OUTPUT!")
        self.assertEqual(config.app.mode, "test")

    def test_02_credentials_blanked(self):
        keys = [config.youtube.client_id, config.youtube.client_secret,
                config.youtube.refresh_token, config.ai.gemini_api_key,
                config.ai.groq_api_key, config.ai.nvidia_api_key,
                config.ai.openrouter_api_key, config.media.pexels_api_key]
        leaked = [i for i, k in enumerate(keys) if k]  # boolean only — never print values
        self.assertEqual(leaked, [], "Sandbox must hold no credentials (leaked key indices hidden)")

    def test_03_secret_masking(self):
        from core.config import _mask_secret
        self.assertEqual(_mask_secret(""), "NOT SET")
        self.assertEqual(_mask_secret("123456"), "SET")
        masked = _mask_secret("sk-or-v1-abcdef123456")
        self.assertEqual(masked, "SET")
        self.assertNotIn("abcdef", masked)

    def test_04_db_schema_in_sandbox(self):
        init_db()
        self.assertGreaterEqual(get_next_file_number(), 1)

    def test_05_schedule_window_structure(self):
        clock = get_production_clock()
        self.assertIsNotNone(clock.tzinfo)
        sched = get_schedule_window()
        self.assertIn("target_upload_iso_utc", sched)
        self.assertIn("ready_by_deadline_us", sched)
        self.assertTrue(sched["target_upload_iso_utc"].endswith(".000Z"))

    def test_06_ffmpeg_binary(self):
        res = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("ffmpeg version", res.stdout)


if __name__ == "__main__":
    unittest.main()
