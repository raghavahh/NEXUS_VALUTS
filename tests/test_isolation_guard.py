"""
NEXUS VAULTS - Test/Production Firewall Tests
Proves the isolation guard fails CLOSED and production stays untouched.
"""
import unittest
import subprocess
import sys
from pathlib import Path

import _guard
_guard.ensure_isolation()

REPO = _guard.PROD_REPO


class IsolationGuardTest(unittest.TestCase):
    def test_01_guard_fails_closed_if_project_imported_first(self):
        """Importing core.config under production config, then the guard, MUST raise."""
        code = (
            "import sys, os; sys.path.insert(0, r'%s'); sys.path.insert(0, r'%s'); "
            "os.environ.pop('NEXUS_TEST_SANDBOX', None); "
            "import core.config; "
            "os.environ['NEXUS_TEST_SANDBOX'] = r'%s'; "
            "import _guard; _guard.ensure_isolation()"
        ) % (REPO, REPO / "tests", _guard._SANDBOX)
        import os
        clean_env = {k: v for k, v in os.environ.items() if k not in (
            "NEXUS_TEST_SANDBOX", "APP_MODE", "APP_ENV", "DATABASE_PATH",
            "OUTPUT_DIR", "TEMP_DIR", "STORYBOARD_DIR", "TEST_MODE")}
        res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60, env=clean_env)
        self.assertNotEqual(res.returncode, 0, "Guard must FAIL when project modules load first!")
        self.assertIn("TEST GUARD", res.stderr + res.stdout)

    def test_02_guard_sandbox_shape(self):
        import core.config as cfgmod
        c = cfgmod.config
        self.assertIn("nexus_test_sandbox", str(c.storage.database_path).lower())
        self.assertEqual(c.app.mode, "test")

    def test_03_no_real_credentials_in_sandbox_env(self):
        import os
        leaked = [k for k in ("GEMINI_API_KEY", "GROQ_API_KEY", "NVIDIA_API_KEY", "OPENROUTER_API_KEY",
                              "PEXELS_API_KEY", "YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")
                  if os.getenv(k, "")]
        self.assertEqual(leaked, [], "Sandbox env leaked credential keys (names only): " + ",".join(leaked))

if __name__ == "__main__":
    unittest.main()
