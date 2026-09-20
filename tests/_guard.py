"""
NEXUS VAULTS - Test Isolation Guard (FAIL-CLOSED)

Every test module MUST import this guard BEFORE importing any project module:

    import _guard; _guard.ensure_isolation()
    from core.database import ...   # only after the guard

The guard redirects DATABASE_PATH / OUTPUT_DIR / TEMP_DIR / STORYBOARD_DIR to a
per-process sandbox, forces APP_MODE=test, and blanks credential keys so no
test can ever reach YouTube, AI providers, or the production database.

If project modules were already imported under production configuration, the
guard raises instead of silently proceeding (fail-closed).
"""
import os
import sys
import tempfile
from pathlib import Path

_SANDBOX: Path | None = None
PROD_REPO = Path(__file__).resolve().parent.parent
PROD_DB = PROD_REPO / "nexus.db"


def _prod_fingerprint() -> str | None:
    import hashlib
    if PROD_DB.exists():
        return hashlib.md5(PROD_DB.read_bytes()).hexdigest()
    return None


def ensure_isolation() -> Path:
    """Idempotent. Returns the sandbox root."""
    global _SANDBOX
    if _SANDBOX is not None:
        return _SANDBOX

    # FAIL-CLOSED: project modules already imported?
    loaded = [m for m in sys.modules if m.split(".")[0] in
              ("core", "content", "media", "research", "analytics", "publisher", "qc", "main")]
    if loaded:
        # Allowed only if they were configured against a sandbox (mode != production
        # and DB path outside the production repo).
        try:
            cfg = sys.modules["core.config"].config
            db_in_repo = str(cfg.storage.database_path.resolve()).startswith(str(PROD_REPO))
            if cfg.app.mode == "production" or db_in_repo:
                raise RuntimeError(
                    f"[TEST GUARD] Project modules already imported under PRODUCTION config "
                    f"(mode={cfg.app.mode}, db={cfg.storage.database_path}). Refusing to run tests."
                )
        except KeyError:
            raise RuntimeError(
                f"[TEST GUARD] Project modules already imported before isolation: {loaded[:5]}. "
                "Import _guard first in every test module."
            )

    _SANDBOX = Path(tempfile.mkdtemp(prefix="nexus_test_sandbox_"))
    env = {
        "APP_MODE": "test",
        "APP_ENV": "test",
        "TEST_MODE": "true",
        "TEST_SKIP_UPLOAD": "true",
        "DATABASE_PATH": str(_SANDBOX / "nexus.db"),
        "OUTPUT_DIR": str(_SANDBOX / "OUTPUT"),
        "TEMP_DIR": str(_SANDBOX / "OUTPUT" / "temp"),
        "STORYBOARD_DIR": str(_SANDBOX / "OUTPUT" / "storyboard"),
        # Blank credentials: no test can reach YouTube / AI providers / Pexels
        "GEMINI_API_KEY": "", "GROQ_API_KEY": "", "NVIDIA_API_KEY": "",
        "OPENROUTER_API_KEY": "", "PEXELS_API_KEY": "",
        "YT_CLIENT_ID": "", "YT_CLIENT_SECRET": "", "YT_REFRESH_TOKEN": "",
        # Detach state persistence from the production .nexus_state
        "NEXUS_TEST_SANDBOX": str(_SANDBOX),
    }
    os.environ.update(env)
    (_SANDBOX / "OUTPUT" / "temp").mkdir(parents=True, exist_ok=True)
    (_SANDBOX / "OUTPUT" / "storyboard").mkdir(parents=True, exist_ok=True)
    return _SANDBOX


def prod_db_fingerprint() -> str | None:
    return _prod_fingerprint()
